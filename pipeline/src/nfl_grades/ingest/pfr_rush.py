"""Ingest PFR advanced rushing stats for RBs into pfr_rb_rush.

Source: ``pfr_advstats_rush`` (per-game rows; aggregated to season totals).
Columns of interest:
  - rushing_yards_after_contact: total post-contact yards across the season
  - rushing_yards_before_contact: total pre-contact yards (mostly OL signal)
  - rushing_broken_tackles: total broken tackles on rushes
  - carries: rush attempts (denominator for per-carry rates)

Used by RB v1.4+ grading (ADR-0014 revision) — `rb_yards_after_contact_per_carry`
component, identified by the exhaustive audit as the highest-validity RB
candidate (+0.192 vs next-year Pro Bowl).

Coverage begins 2018 (PFR per-player data limitation).
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

PFR_RB_RUSH_MIN_SEASON: int = 2018

# Confirmed present in pfr_advstats_rush 2018-2025.
_RUSH_SUM_COLS: dict[str, str] = {
    "carries":                       "carries",
    "rushing_yards_after_contact":   "yards_after_contact",
    "rushing_yards_before_contact":  "yards_before_contact",
    "rushing_broken_tackles":        "broken_tackles",
}

# Canonical RB positions to keep (filter out non-RB players who occasionally
# show up in PFR rush data — wildcat QBs, gadget WRs).
_RB_POSITIONS = frozenset({"RB"})


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_pfr_match: int
    rows_skipped_not_rb: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store PFR rush stats for all RBs.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    Raises ValueError for seasons before PFR_RB_RUSH_MIN_SEASON.
    """
    if season < PFR_RB_RUSH_MIN_SEASON:
        raise ValueError(
            f"PFR rush stats begin in {PFR_RB_RUSH_MIN_SEASON}; got season={season}"
        )

    pfr_df = cache_or_fetch("pfr_advstats_rush", season=season, refresh=refresh)
    pfr_agg = _aggregate_pfr(pfr_df, season)

    engine = get_engine()
    with pipeline_run("ingest:pfr_rb_rush", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player = _pfr_to_player_lookup(conn, season)
            rows, skipped_no_match, skipped_not_rb = _build_rows(
                pfr_agg, season, pfr_to_player
            )
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(pfr_agg),
            rows_written=written,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_skipped_not_rb=skipped_not_rb,
        )
        handle.rows_written = written
        handle.note(
            f"pfr_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_pfr={result.rows_skipped_no_pfr_match} "
            f"skipped_not_rb={result.rows_skipped_not_rb}"
        )
    return result


def _aggregate_pfr(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter to REG and aggregate per-player season totals."""
    if hasattr(df_raw, "to_pandas"):
        df_raw = df_raw.to_pandas()
    if "game_type" in df_raw.columns:
        df = df_raw[df_raw["game_type"] == "REG"].copy()
    else:
        logger.warning(
            "pfr_advstats_rush season=%d: no game_type column; using all rows",
            season,
        )
        df = df_raw.copy()

    if df.empty:
        return df

    missing = set(_RUSH_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"pfr_advstats_rush season={season} missing columns: {missing}. "
            "Update _RUSH_SUM_COLS in ingest/pfr_rush.py."
        )

    if "game_id" in df.columns:
        games_per_player = (
            df.groupby("pfr_player_id")["game_id"].nunique().rename("games")
        )
    else:
        games_per_player = pd.Series(dtype=int, name="games")

    agg_dict: dict[str, tuple[str, str]] = {
        out: (src, "sum") for src, out in _RUSH_SUM_COLS.items()
    }
    agg = df.groupby("pfr_player_id").agg(**agg_dict).reset_index()
    if not games_per_player.empty:
        agg = agg.join(games_per_player, on="pfr_player_id")
    else:
        agg["games"] = 0
    return agg


def _pfr_to_player_lookup(
    conn: Connection, season: int
) -> dict[str, tuple[int, str]]:
    """pfr_id -> (player_id, position_played) for the given season.

    Uses the player_seasons row with the most offensive snaps for position
    tag (handles players who flipped positions mid-season).
    """
    rows = conn.execute(
        text(
            """
            SELECT p.pfr_id, p.player_id, ps.position_played
            FROM players p
            JOIN (
                SELECT DISTINCT ON (player_id) player_id, position_played
                FROM player_seasons
                WHERE season = :season
                ORDER BY player_id, snaps_offense DESC NULLS LAST
            ) ps ON ps.player_id = p.player_id
            WHERE p.pfr_id IS NOT NULL
            """
        ),
        {"season": season},
    ).all()
    return {
        pfr_id: (player_id, position_played)
        for pfr_id, player_id, position_played in rows
    }


def _build_rows(
    pfr_agg: pd.DataFrame,
    season: int,
    pfr_to_player: dict[str, tuple[int, str]],
) -> tuple[list[dict[str, object]], int, int]:
    rows: list[dict[str, object]] = []
    skipped_no_match = 0
    skipped_not_rb = 0

    def _int_or_none(val: object) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)

    for _, row in pfr_agg.iterrows():
        pfr_id = str(row["pfr_player_id"])
        lookup = pfr_to_player.get(pfr_id)
        if lookup is None:
            skipped_no_match += 1
            continue
        player_id, position = lookup
        if position not in _RB_POSITIONS:
            skipped_not_rb += 1
            continue
        rows.append(
            {
                "player_id":            player_id,
                "season":               season,
                "games":                _int_or_none(row.get("games")) or 0,
                "carries":              _int_or_none(row.get("carries")),
                "yards_after_contact":  _int_or_none(row.get("yards_after_contact")),
                "yards_before_contact": _int_or_none(row.get("yards_before_contact")),
                "broken_tackles":       _int_or_none(row.get("broken_tackles")),
            }
        )

    if skipped_no_match:
        logger.warning(
            "pfr_rb_rush season=%d: %d pfr_ids with no player record "
            "(run rosters ingest first)",
            season, skipped_no_match,
        )
    return rows, skipped_no_match, skipped_not_rb


_INSERT_SQL = text(
    """
    INSERT INTO pfr_rb_rush
        (player_id, season, games, carries,
         yards_after_contact, yards_before_contact, broken_tackles)
    VALUES
        (:player_id, :season, :games, :carries,
         :yards_after_contact, :yards_before_contact, :broken_tackles)
    """
)


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(
        text("DELETE FROM pfr_rb_rush WHERE season = :season"),
        {"season": season},
    )
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["PFR_RB_RUSH_MIN_SEASON", "RunResult", "run"]
