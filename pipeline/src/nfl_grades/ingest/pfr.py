"""Ingest PFR advanced defensive coverage stats into ``pfr_def_coverage``.

Source: ``nflreadpy.load_pfr_advstats(stat_type="def", seasons=[s])``.
Coverage begins 2018 — the first year PFR published per-CB target/comp data.

The nflreadpy source returns **per-game** rows (one row per player per game),
not season totals. This module:
  1. Filters to REG-season games.
  2. Aggregates to per-player season totals (sum).
  3. Filters to CBs only, using the players.pfr_id → position lookup.
  4. Upserts into pfr_def_coverage.

Column names (confirmed 2018–2025):
    pfr_player_id, game_id, season, game_type,
    def_targets, def_completions_allowed, def_yards_allowed,
    def_yards_after_catch, def_receiving_td_allowed, def_ints.
    (No position column; no pass_breakups/PBU column.)

Player linkage: PFR data carries pfr_player_id (PFR's own ID), not gsis_id.
We join to players.pfr_id which is backfilled by the rosters ingest.

See ADR-0018 for CB v1 methodology.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)

PFR_DEF_COVERAGE_MIN_SEASON: int = 2018

# Confirmed column names from nflreadpy 2018–2025.
# Only the columns we actually use are listed here; the rest are ignored.
_SUM_COLS = {
    "def_targets":              "targets",
    "def_completions_allowed":  "completions",
    "def_yards_allowed":        "yards",
    "def_yards_after_catch":    "yac",
    "def_receiving_td_allowed": "tds",
    "def_ints":                 "ints",
}


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int           # CB rows after aggregation
    rows_written: int            # rows successfully written
    rows_skipped_no_pfr_match: int  # pfr_ids with no player record
    rows_skipped_not_cb: int        # pfr_ids whose player is not CB


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store PFR defensive coverage stats for all CBs in ``season``.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    Raises ValueError for seasons before PFR_DEF_COVERAGE_MIN_SEASON.

    Pass breakups are sourced from nflverse player stats (def_pass_defended),
    joined by GSIS ID. CBs not found in that source get NULL pass_breakups.
    """
    if season < PFR_DEF_COVERAGE_MIN_SEASON:
        raise ValueError(
            f"PFR defensive coverage data begins in {PFR_DEF_COVERAGE_MIN_SEASON}; "
            f"got season={season}"
        )

    df_raw = cache_or_fetch("pfr_advstats_def", season=season, refresh=refresh)
    df_agg = _aggregate(df_raw, season)
    ps_df = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)

    engine = get_engine()
    with pipeline_run("ingest:pfr_def_coverage", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player = _pfr_to_player_lookup(conn, season)
            player_id_to_pbu = _build_player_id_to_pbu(conn, ps_df, season)
            rows, skipped_no_match, skipped_not_cb = _build_rows(
                df_agg, season, pfr_to_player, player_id_to_pbu
            )
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(df_agg),
            rows_written=written,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_skipped_not_cb=skipped_not_cb,
        )
        handle.rows_written = written
        handle.note(
            f"cb_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_pfr={result.rows_skipped_no_pfr_match} "
            f"skipped_not_cb={result.rows_skipped_not_cb}"
        )
    return result


def _aggregate(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter to REG-season games and aggregate to per-player season totals."""
    # Filter to regular season.
    if "game_type" in df_raw.columns:
        df = df_raw[df_raw["game_type"] == "REG"].copy()
    else:
        logger.warning("pfr_advstats_def season=%d: no game_type column; using all rows", season)
        df = df_raw.copy()

    if df.empty:
        return df

    # Verify expected columns exist.
    missing = set(_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"pfr_advstats_def season={season} missing expected columns: {missing}. "
            "Column names may have changed. Update _SUM_COLS in ingest/pfr.py."
        )

    # Count distinct games per player (proxy for games played).
    if "game_id" in df.columns:
        games_per_player = df.groupby("pfr_player_id")["game_id"].nunique().rename("games")
    else:
        games_per_player = pd.Series(dtype=int, name="games")

    # Sum coverage stats across games.
    agg_dict = {out_col: (src_col, "sum") for src_col, out_col in _SUM_COLS.items()}
    agg = df.groupby("pfr_player_id").agg(**agg_dict).reset_index()

    if not games_per_player.empty:
        agg = agg.join(games_per_player, on="pfr_player_id")
    else:
        agg["games"] = 0

    return agg


def _pfr_to_player_lookup(conn: Connection, season: int) -> dict[str, tuple[int, str]]:
    """Build pfr_id -> (player_id, position_played) for the given season.

    Uses player_seasons.position_played rather than players.position so that
    players who switched positions mid-career are classified correctly for
    each historical season (e.g. a CB who became a Safety in year N is still
    graded as CB for years < N).

    Players with no player_seasons row for the season are excluded — they
    were not on a roster that year and cannot be graded.

    When a player appeared on multiple teams in a season (traded), the team
    with the most defensive snaps determines position_played.
    """
    rows = conn.execute(
        text("""
            SELECT p.pfr_id, p.player_id, ps.position_played
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
    return {pfr_id: (player_id, position_played) for pfr_id, player_id, position_played in rows}


def _build_player_id_to_pbu(
    conn: Connection, ps_df: pd.DataFrame, season: int
) -> dict[int, int]:
    """Return internal player_id -> season PBU count from nflverse player stats.

    Filters nflverse to REG season, aggregates def_pass_defended, then maps
    GSIS IDs to internal player_ids using player_seasons for the given season
    (position-agnostic — the CB filter is already applied upstream via
    _pfr_to_player_lookup, so we just need the GSIS bridge here).
    """
    mask = (ps_df["season_type"] == "REG") & ps_df["player_id"].notna()
    reg = ps_df[mask]
    if reg.empty:
        return {}

    gsis_to_pbu: dict[str, int] = (
        reg.groupby("player_id")["def_pass_defended"]
        .sum()
        .fillna(0)
        .astype(int)
        .to_dict()
    )

    db_rows = conn.execute(
        text("""
            SELECT p.player_id, p.gsis_id
            FROM players p
            JOIN (
                SELECT DISTINCT ON (player_id) player_id
                FROM player_seasons
                WHERE season = :season AND position_played = 'CB'
                ORDER BY player_id, snaps_defense DESC
            ) ps ON ps.player_id = p.player_id
            WHERE p.gsis_id IS NOT NULL
        """),
        {"season": season},
    ).all()
    gsis_to_internal = {gsis_id: player_id for player_id, gsis_id in db_rows}

    return {
        gsis_to_internal[gsis]: pbu
        for gsis, pbu in gsis_to_pbu.items()
        if gsis in gsis_to_internal
    }


def _build_rows(
    df_agg: pd.DataFrame,
    season: int,
    pfr_to_player: dict[str, tuple[int, str]],
    player_id_to_pbu: dict[int, int],
) -> tuple[list[dict[str, object]], int, int]:
    """Convert aggregated DataFrame rows to dicts for DB insertion.

    Returns (rows, skipped_no_pfr_match, skipped_not_cb).
    """
    rows: list[dict[str, object]] = []
    skipped_no_match = 0
    skipped_not_cb = 0

    def _int_or_none(val: object) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)

    def _float_or_none(val: object) -> float | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)

    for _, row in df_agg.iterrows():
        pfr_id = str(row["pfr_player_id"])
        lookup = pfr_to_player.get(pfr_id)
        if lookup is None:
            skipped_no_match += 1
            continue
        player_id, position = lookup
        if position != "CB":
            skipped_not_cb += 1
            continue

        rows.append(
            {
                "player_id": player_id,
                "season": season,
                "games": _int_or_none(row.get("games")) or 0,
                "targets": _int_or_none(row["targets"]),
                "completions": _int_or_none(row.get("completions")),
                "yards": _int_or_none(row.get("yards")),
                "yac": _float_or_none(row.get("yac")),
                "tds": _int_or_none(row.get("tds")),
                "ints": _int_or_none(row.get("ints")),
                "pass_breakups": player_id_to_pbu.get(player_id),  # from nflverse player_stats
                "slot_pct": None,   # not available in nflreadpy pfr_advstats_def
            }
        )

    if skipped_no_match:
        logger.warning(
            "pfr_def_coverage season=%d: %d pfr_ids with no player record "
            "(run rosters ingest + pfr_id backfill first)",
            season, skipped_no_match,
        )
    return rows, skipped_no_match, skipped_not_cb


_DELETE_SQL = text("DELETE FROM pfr_def_coverage WHERE season = :season")

_INSERT_SQL = text("""
    INSERT INTO pfr_def_coverage
        (player_id, season, games, targets, completions, yards, yac, tds,
         ints, pass_breakups, slot_pct)
    VALUES
        (:player_id, :season, :games, :targets, :completions, :yards, :yac, :tds,
         :ints, :pass_breakups, :slot_pct)
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(_DELETE_SQL, {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = [
    "PFR_DEF_COVERAGE_MIN_SEASON",
    "RunResult",
    "run",
]
