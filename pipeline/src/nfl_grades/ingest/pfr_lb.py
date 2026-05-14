"""Ingest PFR + nflverse defensive stats for off-ball LBs into pfr_def_lb.

Sources:
  1. ``pfr_advstats_def``: tackles, missed tackles, pressures, sacks, QB
     hits, hurries, blitzes, plus per-target coverage stats (targets,
     completions, yards, INTs).
  2. ``nflvs_player_stats``: def_tackles_for_loss, def_pass_defended (PBU),
     def_fumbles_forced.

LBs are a multi-skill position (run defense + coverage + situational pass
rush), so we pull the full row of PFR stats rather than the pass-rush-only
subset used for DL. Filtering for off-ball vs edge-rush OLBs happens at
grading time (via def_targets >= 20).

Coverage begins 2018 (PFR per-player data limitation).

See ADR-0022 (LB v1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)

PFR_DEF_LB_MIN_SEASON: int = 2018

# Columns confirmed present in pfr_advstats_def 2018-2025.
_PFR_SUM_COLS: dict[str, str] = {
    "def_tackles_combined":      "comb_tackles",
    "def_missed_tackles":        "missed_tackles",
    "def_pressures":             "pressures",
    "def_sacks":                 "sacks",
    "def_times_hitqb":           "qb_hits",
    "def_times_hurried":         "hurries",
    "def_targets":               "targets",
    "def_completions_allowed":   "completions_allowed",
    "def_yards_allowed":         "yards_allowed",
    "def_receiving_td_allowed":  "tds_allowed",
    "def_ints":                  "ints",
}

# nflverse columns: PBU + TFL + forced fumbles. These exist in nflvs_player_stats.
_NFLVS_SUM_COLS: dict[str, str] = {
    "def_pass_defended":    "pbu",
    "def_tackles_for_loss": "tfl",
    "def_fumbles_forced":   "fumbles_forced",
}

# We grade only off-ball LB. EDGE and iDL stay in pfr_def_pass_rush.
_LB_POSITIONS = frozenset({"LB"})


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_pfr_match: int
    rows_skipped_not_lb: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store PFR + nflvs stats for all LB players.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    """
    if season < PFR_DEF_LB_MIN_SEASON:
        raise ValueError(
            f"PFR defensive stats begin in {PFR_DEF_LB_MIN_SEASON}; "
            f"got season={season}"
        )

    pfr_df = cache_or_fetch("pfr_advstats_def", season=season, refresh=refresh)
    nflvs_df = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)

    pfr_agg = _aggregate_pfr(pfr_df, season)
    nflvs_agg = _aggregate_nflverse(nflvs_df)

    engine = get_engine()
    with pipeline_run("ingest:pfr_def_lb", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player = _pfr_to_player_lookup(conn, season)
            gsis_to_nflvs = _gsis_to_nflvs_lookup(nflvs_agg)
            rows, skipped_no_match, skipped_not_lb = _build_rows(
                pfr_agg, season, pfr_to_player, gsis_to_nflvs
            )
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(pfr_agg),
            rows_written=written,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_skipped_not_lb=skipped_not_lb,
        )
        handle.rows_written = written
        handle.note(
            f"pfr_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_pfr={result.rows_skipped_no_pfr_match} "
            f"skipped_not_lb={result.rows_skipped_not_lb}"
        )
    return result


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate_pfr(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    if "game_type" in df_raw.columns:
        df = df_raw[df_raw["game_type"] == "REG"].copy()
    else:
        logger.warning("pfr_advstats_def season=%d: no game_type column", season)
        df = df_raw.copy()

    if df.empty:
        return df

    missing = set(_PFR_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"pfr_advstats_def season={season} missing columns: {missing}"
        )

    if "game_id" in df.columns:
        games_per_player = df.groupby("pfr_player_id")["game_id"].nunique().rename("games")
    else:
        games_per_player = pd.Series(dtype=int, name="games")

    agg_dict: dict[str, tuple[str, str]] = {
        out: (src, "sum") for src, out in _PFR_SUM_COLS.items()
    }
    agg = df.groupby("pfr_player_id").agg(**agg_dict).reset_index()
    if not games_per_player.empty:
        agg = agg.join(games_per_player, on="pfr_player_id")
    else:
        agg["games"] = 0
    return agg


def _aggregate_nflverse(ps_df: pd.DataFrame) -> pd.DataFrame:
    mask = (ps_df["season_type"] == "REG") & ps_df["player_id"].notna()
    reg = ps_df[mask].copy()
    if reg.empty:
        return pd.DataFrame(columns=["gsis_id"] + list(_NFLVS_SUM_COLS.values()))

    present = {src: out for src, out in _NFLVS_SUM_COLS.items() if src in reg.columns}
    if not present:
        logger.warning("nflvs_player_stats: no LB-coverage columns found")
        return pd.DataFrame(columns=["gsis_id"] + list(_NFLVS_SUM_COLS.values()))

    agg_dict: dict[str, tuple[str, str]] = {
        out: (src, "sum") for src, out in present.items()
    }
    agg = (
        reg.groupby("player_id")
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={"player_id": "gsis_id"})
    )
    for out in _NFLVS_SUM_COLS.values():
        if out not in agg.columns:
            agg[out] = np.nan
    return agg


# ---------------------------------------------------------------------------
# DB lookups
# ---------------------------------------------------------------------------

def _pfr_to_player_lookup(
    conn: Connection, season: int
) -> dict[str, tuple[int, str, str | None]]:
    rows = conn.execute(
        text("""
            SELECT p.pfr_id, p.player_id, ps.position_played, p.gsis_id
            FROM players p
            JOIN (
                SELECT DISTINCT ON (player_id) player_id, position_played
                FROM player_seasons
                WHERE season = :season
                ORDER BY player_id, snaps_defense DESC
            ) ps ON ps.player_id = p.player_id
            WHERE p.pfr_id IS NOT NULL
        """),
        {"season": season},
    ).all()
    return {
        pfr_id: (player_id, position_played, gsis_id)
        for pfr_id, player_id, position_played, gsis_id in rows
    }


def _gsis_to_nflvs_lookup(nflvs_agg: pd.DataFrame) -> dict[str, dict[str, float]]:
    if nflvs_agg.empty:
        return {}
    out: dict[str, dict[str, float]] = {}
    for _, row in nflvs_agg.iterrows():
        gsis = row["gsis_id"]
        if pd.isna(gsis):
            continue
        out[str(gsis)] = {
            col: float(row[col]) if pd.notna(row[col]) else 0.0
            for col in _NFLVS_SUM_COLS.values()
        }
    return out


# ---------------------------------------------------------------------------
# Row build
# ---------------------------------------------------------------------------

def _build_rows(
    pfr_agg: pd.DataFrame,
    season: int,
    pfr_to_player: dict[str, tuple[int, str, str | None]],
    gsis_to_nflvs: dict[str, dict[str, float]],
) -> tuple[list[dict[str, object]], int, int]:
    rows: list[dict[str, object]] = []
    skipped_no_match = 0
    skipped_not_lb = 0

    def _int_or_none(val: object) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)

    def _float_or_none(val: object) -> float | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)

    for _, row in pfr_agg.iterrows():
        pfr_id = str(row["pfr_player_id"])
        lookup = pfr_to_player.get(pfr_id)
        if lookup is None:
            skipped_no_match += 1
            continue
        player_id, position, gsis_id = lookup
        if position not in _LB_POSITIONS:
            skipped_not_lb += 1
            continue

        nflvs = gsis_to_nflvs.get(gsis_id or "") or {}

        rows.append({
            "player_id":           player_id,
            "season":              season,
            "games":               _int_or_none(row.get("games")) or 0,
            "comb_tackles":        _int_or_none(row.get("comb_tackles")),
            "missed_tackles":      _int_or_none(row.get("missed_tackles")),
            "tfl":                 nflvs.get("tfl"),
            "pressures":           _float_or_none(row.get("pressures")),
            "sacks":               _float_or_none(row.get("sacks")),
            "qb_hits":             _int_or_none(row.get("qb_hits")),
            "hurries":             _int_or_none(row.get("hurries")),
            "targets":             _int_or_none(row.get("targets")),
            "completions_allowed": _int_or_none(row.get("completions_allowed")),
            "yards_allowed":       _float_or_none(row.get("yards_allowed")),
            "tds_allowed":         _int_or_none(row.get("tds_allowed")),
            "ints":                _int_or_none(row.get("ints")),
            "pbu":                 _int_or_none(nflvs.get("pbu")),
            "fumbles_forced":      _int_or_none(nflvs.get("fumbles_forced")),
        })

    if skipped_no_match:
        logger.warning(
            "pfr_def_lb season=%d: %d pfr_ids with no player record "
            "(run rosters ingest first)",
            season, skipped_no_match,
        )
    return rows, skipped_no_match, skipped_not_lb


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

_INSERT_SQL = text("""
    INSERT INTO pfr_def_lb
        (player_id, season, games, comb_tackles, missed_tackles, tfl,
         pressures, sacks, qb_hits, hurries, targets, completions_allowed,
         yards_allowed, tds_allowed, ints, pbu, fumbles_forced)
    VALUES
        (:player_id, :season, :games, :comb_tackles, :missed_tackles, :tfl,
         :pressures, :sacks, :qb_hits, :hurries, :targets, :completions_allowed,
         :yards_allowed, :tds_allowed, :ints, :pbu, :fumbles_forced)
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(
        text("DELETE FROM pfr_def_lb WHERE season = :season"),
        {"season": season},
    )
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["PFR_DEF_LB_MIN_SEASON", "RunResult", "run"]
