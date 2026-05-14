"""Ingest PFR advanced defensive stats for EDGE and iDL into pfr_def_pass_rush.

Sources:
  1. ``pfr_advstats_def``: pressures, sacks, QB hits, hurries, combined
     tackles, missed tackles. Per-game rows; aggregated to season totals.
  2. ``nflvs_player_stats``: def_tackles_for_loss (run TFLs, reported
     separately from sacks in nflverse — confirmed no overlap).

One shared table serves both EDGE and iDL graders. Each grader filters
by position_played when reading from pfr_def_pass_rush.

Coverage begins 2018 (PFR per-player data limitation).

See ADR-0020 (EDGE v1) and ADR-0021 (iDL v1).
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

PFR_DEF_PASS_RUSH_MIN_SEASON: int = 2018

# Pass-rush columns confirmed present in pfr_advstats_def 2018-2025.
_PASS_RUSH_SUM_COLS: dict[str, str] = {
    "def_pressures":        "pressures",
    "def_sacks":            "sacks",
    "def_times_hitqb":      "qb_hits",
    "def_times_hurried":    "hurries",
    "def_tackles_combined": "comb_tackles",
}

# Tackle columns tried with fallbacks; first match wins; None → NULL.
_TACKLE_ATTEMPT_COLS: dict[str, tuple[str, ...]] = {
    "missed_tackles": (
        "def_missed_tackles",
        "missed_tackles",
        "m_tkl",
        "def_m_tkl",
    ),
}

# Canonical position_played values for DL players.
_DL_POSITIONS = frozenset({"EDGE", "iDL"})


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_pfr_match: int
    rows_skipped_not_dl: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store PFR pass-rush stats for all EDGE and iDL players.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    Raises ValueError for seasons before PFR_DEF_PASS_RUSH_MIN_SEASON.
    """
    if season < PFR_DEF_PASS_RUSH_MIN_SEASON:
        raise ValueError(
            f"PFR defensive stats begin in {PFR_DEF_PASS_RUSH_MIN_SEASON}; "
            f"got season={season}"
        )

    pfr_df = cache_or_fetch("pfr_advstats_def", season=season, refresh=refresh)
    ps_df = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)

    pfr_agg = _aggregate_pfr(pfr_df, season)
    nflvs_agg = _aggregate_nflverse(ps_df)

    engine = get_engine()
    with pipeline_run("ingest:pfr_def_pass_rush", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player = _pfr_to_player_lookup(conn, season)
            gsis_to_nflvs = _gsis_to_nflvs_lookup(nflvs_agg)
            rows, skipped_no_match, skipped_not_dl = _build_rows(
                pfr_agg, season, pfr_to_player, gsis_to_nflvs
            )
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(pfr_agg),
            rows_written=written,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_skipped_not_dl=skipped_not_dl,
        )
        handle.rows_written = written
        handle.note(
            f"pfr_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_pfr={result.rows_skipped_no_pfr_match} "
            f"skipped_not_dl={result.rows_skipped_not_dl}"
        )
    return result


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate_pfr(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter pfr_advstats_def to REG season and aggregate per player."""
    if "game_type" in df_raw.columns:
        df = df_raw[df_raw["game_type"] == "REG"].copy()
    else:
        logger.warning("pfr_advstats_def season=%d: no game_type column; using all rows", season)
        df = df_raw.copy()

    if df.empty:
        return df

    missing = set(_PASS_RUSH_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"pfr_advstats_def season={season} missing columns: {missing}. "
            "Update _PASS_RUSH_SUM_COLS in ingest/pfr_dl.py."
        )

    if "game_id" in df.columns:
        games_per_player = df.groupby("pfr_player_id")["game_id"].nunique().rename("games")
    else:
        games_per_player = pd.Series(dtype=int, name="games")

    agg_dict: dict[str, tuple[str, str]] = {
        out: (src, "sum") for src, out in _PASS_RUSH_SUM_COLS.items()
    }

    for dest, variants in _TACKLE_ATTEMPT_COLS.items():
        found = next((v for v in variants if v in df.columns), None)
        if found:
            agg_dict[dest] = (found, "sum")
            logger.debug("pfr_advstats_def season=%d: using %r for %r", season, found, dest)
        else:
            logger.warning(
                "pfr_advstats_def season=%d: no column for %r (tried: %s); storing NULL",
                season, dest, ", ".join(variants),
            )

    agg = df.groupby("pfr_player_id").agg(**agg_dict).reset_index()

    if not games_per_player.empty:
        agg = agg.join(games_per_player, on="pfr_player_id")
    else:
        agg["games"] = 0

    for dest in _TACKLE_ATTEMPT_COLS:
        if dest not in agg.columns:
            agg[dest] = np.nan

    return agg


def _aggregate_nflverse(ps_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate nflverse player_stats to per-gsis_id season TFL totals."""
    mask = (ps_df["season_type"] == "REG") & ps_df["player_id"].notna()
    reg = ps_df[mask].copy()
    if reg.empty:
        return pd.DataFrame(columns=["gsis_id", "tfl"])

    tfl_col = "def_tackles_for_loss" if "def_tackles_for_loss" in reg.columns else None
    if tfl_col is None:
        logger.warning("nflvs_player_stats: no TFL column found; TFL will be NULL")
        return pd.DataFrame(columns=["gsis_id", "tfl"])

    agg = (
        reg.groupby("player_id")
        .agg(tfl=(tfl_col, "sum"))
        .reset_index()
        .rename(columns={"player_id": "gsis_id"})
    )
    return agg


# ---------------------------------------------------------------------------
# DB lookup helpers
# ---------------------------------------------------------------------------

def _pfr_to_player_lookup(
    conn: Connection, season: int
) -> dict[str, tuple[int, str, str | None]]:
    """pfr_id -> (player_id, position_played, gsis_id) for the given season."""
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


def _gsis_to_nflvs_lookup(nflvs_agg: pd.DataFrame) -> dict[str, float]:
    """gsis_id -> season TFL count."""
    if nflvs_agg.empty:
        return {}
    return {
        str(row["gsis_id"]): float(row["tfl"])
        for _, row in nflvs_agg.iterrows()
        if pd.notna(row["gsis_id"]) and pd.notna(row["tfl"])
    }


# ---------------------------------------------------------------------------
# Row construction
# ---------------------------------------------------------------------------

def _build_rows(
    pfr_agg: pd.DataFrame,
    season: int,
    pfr_to_player: dict[str, tuple[int, str, str | None]],
    gsis_to_nflvs: dict[str, float],
) -> tuple[list[dict[str, object]], int, int]:
    rows: list[dict[str, object]] = []
    skipped_no_match = 0
    skipped_not_dl = 0

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
        if position not in _DL_POSITIONS:
            skipped_not_dl += 1
            continue

        tfl = gsis_to_nflvs.get(gsis_id or "")

        rows.append({
            "player_id":      player_id,
            "season":         season,
            "games":          _int_or_none(row.get("games")) or 0,
            "pressures":      _float_or_none(row.get("pressures")),
            "sacks":          _float_or_none(row.get("sacks")),
            "qb_hits":        _int_or_none(row.get("qb_hits")),
            "hurries":        _int_or_none(row.get("hurries")),
            "comb_tackles":   _int_or_none(row.get("comb_tackles")),
            "missed_tackles": _int_or_none(row.get("missed_tackles")),
            "tfl":            tfl,
        })

    if skipped_no_match:
        logger.warning(
            "pfr_def_pass_rush season=%d: %d pfr_ids with no player record "
            "(run rosters ingest first)",
            season, skipped_no_match,
        )
    return rows, skipped_no_match, skipped_not_dl


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

_INSERT_SQL = text("""
    INSERT INTO pfr_def_pass_rush
        (player_id, season, games, pressures, sacks, qb_hits, hurries,
         comb_tackles, missed_tackles, tfl)
    VALUES
        (:player_id, :season, :games, :pressures, :sacks, :qb_hits, :hurries,
         :comb_tackles, :missed_tackles, :tfl)
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(
        text("DELETE FROM pfr_def_pass_rush WHERE season = :season"),
        {"season": season},
    )
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = [
    "PFR_DEF_PASS_RUSH_MIN_SEASON",
    "RunResult",
    "run",
]
