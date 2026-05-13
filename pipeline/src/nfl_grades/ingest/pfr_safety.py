"""Ingest PFR advanced defensive stats for safeties into pfr_def_coverage_s.

Sources:
  1. ``pfr_advstats_def`` (same as CB): coverage stats (targets, completions,
     yards, ints) and, if present, missed tackle counts.
  2. ``nflvs_player_stats``: pass breakups (def_pass_defended), combined
     tackles (def_tackles_solo + def_tackle_assists), TFL (def_tackles_loss),
     sacks (def_sacks).
  3. ``player_seasons.snaps_defense``: used downstream by the grading module.

Column-name notes
-----------------
pfr_advstats_def coverage columns confirmed 2018-2025 (see CB ingest):
    pfr_player_id, game_id, season, game_type,
    def_targets, def_completions_allowed, def_yards_allowed, def_ints.
Tackle columns (def_missed_tackles etc.) are attempted with multiple name
variants; if none found, stored as NULL and NaN-neutralized in grading.

Safeties in our DB have position = 'S' (mapped from FS/SS/S/SAF by rosters).

See ADR-0019 for Safety v1 methodology.
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

PFR_DEF_COVERAGE_S_MIN_SEASON: int = 2018

# Coverage columns confirmed present in pfr_advstats_def 2018-2025.
_COVERAGE_SUM_COLS = {
    "def_targets":             "targets",
    "def_completions_allowed": "completions",
    "def_yards_allowed":       "yards",
    "def_ints":                "ints",
}

# Tackle columns attempted from pfr_advstats_def. Each tuple lists column
# name variants in preference order; first match wins. None found → NULL.
_TACKLE_ATTEMPT_COLS: dict[str, tuple[str, ...]] = {
    "missed_tackles": (
        "def_missed_tackles",
        "missed_tackles",
        "m_tkl",
        "def_m_tkl",
    ),
}


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_pfr_match: int
    rows_skipped_not_safety: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store PFR defensive stats for all safeties in ``season``.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    Raises ValueError for seasons before PFR_DEF_COVERAGE_S_MIN_SEASON.
    """
    if season < PFR_DEF_COVERAGE_S_MIN_SEASON:
        raise ValueError(
            f"PFR defensive coverage data begins in {PFR_DEF_COVERAGE_S_MIN_SEASON}; "
            f"got season={season}"
        )

    pfr_df = cache_or_fetch("pfr_advstats_def", season=season, refresh=refresh)
    ps_df = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)

    pfr_agg = _aggregate_pfr(pfr_df, season)
    nflvs_agg = _aggregate_nflverse(ps_df)

    engine = get_engine()
    with pipeline_run("ingest:pfr_def_coverage_s", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player = _pfr_to_player_lookup(conn)
            gsis_to_nflvs = _gsis_to_nflvs_lookup(conn, nflvs_agg)
            rows, skipped_no_match, skipped_not_safety = _build_rows(
                pfr_agg, season, pfr_to_player, gsis_to_nflvs
            )
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(pfr_agg),
            rows_written=written,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_skipped_not_safety=skipped_not_safety,
        )
        handle.rows_written = written
        handle.note(
            f"pfr_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_pfr={result.rows_skipped_no_pfr_match} "
            f"skipped_not_safety={result.rows_skipped_not_safety}"
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

    missing = set(_COVERAGE_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"pfr_advstats_def season={season} missing coverage columns: {missing}. "
            "Update _COVERAGE_SUM_COLS in ingest/pfr_safety.py."
        )

    if "game_id" in df.columns:
        games_per_player = df.groupby("pfr_player_id")["game_id"].nunique().rename("games")
    else:
        games_per_player = pd.Series(dtype=int, name="games")

    agg_dict = {out: (src, "sum") for src, out in _COVERAGE_SUM_COLS.items()}

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
    """Aggregate nflverse player_stats to per-gsis_id season totals.

    Returns a DataFrame with columns:
        gsis_id, pass_breakups, comb_tackles, tfl, sacks.
    """
    mask = (ps_df["season_type"] == "REG") & ps_df["player_id"].notna()
    reg = ps_df[mask].copy()
    if reg.empty:
        return pd.DataFrame(columns=["gsis_id", "pass_breakups", "comb_tackles", "tfl", "sacks"])

    def _col_or_zero(name: str) -> pd.Series:
        return reg[name].fillna(0) if name in reg.columns else pd.Series(0.0, index=reg.index)

    reg["_pbu"] = _col_or_zero("def_pass_defended")
    reg["_solo"] = _col_or_zero("def_tackles_solo")
    reg["_ast"] = _col_or_zero("def_tackle_assists")
    reg["_tfl"] = _col_or_zero("def_tackles_loss")
    reg["_sacks"] = _col_or_zero("def_sacks")

    agg = (
        reg.groupby("player_id")
        .agg(
            pass_breakups=("_pbu", "sum"),
            solo_tackles=("_solo", "sum"),
            ast_tackles=("_ast", "sum"),
            tfl=("_tfl", "sum"),
            sacks=("_sacks", "sum"),
        )
        .reset_index()
        .rename(columns={"player_id": "gsis_id"})
    )
    agg["comb_tackles"] = agg["solo_tackles"] + agg["ast_tackles"]
    return agg[["gsis_id", "pass_breakups", "comb_tackles", "tfl", "sacks"]]


# ---------------------------------------------------------------------------
# DB lookup helpers
# ---------------------------------------------------------------------------

def _pfr_to_player_lookup(conn: Connection) -> dict[str, tuple[int, str, str | None]]:
    """pfr_id -> (player_id, position, gsis_id) for all players with a pfr_id."""
    rows = conn.execute(
        text("""
            SELECT pfr_id, player_id, position, gsis_id
            FROM players
            WHERE pfr_id IS NOT NULL
        """)
    ).all()
    return {pfr_id: (player_id, position, gsis_id) for pfr_id, player_id, position, gsis_id in rows}


def _gsis_to_nflvs_lookup(
    conn: Connection,
    nflvs_agg: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    """Map gsis_id -> nflverse aggregated stats dict."""
    if nflvs_agg.empty:
        return {}
    return {
        str(row["gsis_id"]): row.to_dict()
        for _, row in nflvs_agg.iterrows()
        if pd.notna(row["gsis_id"])
    }


# ---------------------------------------------------------------------------
# Row construction
# ---------------------------------------------------------------------------

def _build_rows(
    pfr_agg: pd.DataFrame,
    season: int,
    pfr_to_player: dict[str, tuple[int, str, str | None]],
    gsis_to_nflvs: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], int, int]:
    """Merge PFR and nflverse aggregates into DB-ready rows for safeties."""
    rows: list[dict[str, object]] = []
    skipped_no_match = 0
    skipped_not_safety = 0

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
        if position != "S":
            skipped_not_safety += 1
            continue

        # Enrich with nflverse data.
        nv = gsis_to_nflvs.get(gsis_id or "", {})

        rows.append(
            {
                "player_id": player_id,
                "season": season,
                "games": _int_or_none(row.get("games")) or 0,
                "targets": _int_or_none(row.get("targets")),
                "completions": _int_or_none(row.get("completions")),
                "yards": _int_or_none(row.get("yards")),
                "ints": _int_or_none(row.get("ints")),
                "missed_tackles": _int_or_none(row.get("missed_tackles")),
                # From nflverse player_stats.
                "pass_breakups": _int_or_none(nv.get("pass_breakups")),
                "comb_tackles": _int_or_none(nv.get("comb_tackles")),
                "tfl": _int_or_none(nv.get("tfl")),
                "sacks": _float_or_none(nv.get("sacks")),
            }
        )

    if skipped_no_match:
        logger.warning(
            "pfr_def_coverage_s season=%d: %d pfr_ids with no player record "
            "(run rosters ingest + pfr_id backfill first)",
            season, skipped_no_match,
        )
    return rows, skipped_no_match, skipped_not_safety


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

_INSERT_SQL = text("""
    INSERT INTO pfr_def_coverage_s
        (player_id, season, games, targets, completions, yards, ints,
         pass_breakups, comb_tackles, tfl, sacks, missed_tackles)
    VALUES
        (:player_id, :season, :games, :targets, :completions, :yards, :ints,
         :pass_breakups, :comb_tackles, :tfl, :sacks, :missed_tackles)
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(text("DELETE FROM pfr_def_coverage_s WHERE season = :season"), {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = [
    "PFR_DEF_COVERAGE_S_MIN_SEASON",
    "RunResult",
    "run",
]
