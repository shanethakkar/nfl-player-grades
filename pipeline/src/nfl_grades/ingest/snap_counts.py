"""Ingest per-game snap counts and aggregate into season totals.

Fills the playing-time columns on ``player_seasons`` that ``rosters.py``
leaves at zero:

    games, games_started, snaps_offense, snaps_defense, snaps_special

Grain:
    - Source (nflreadpy.load_snap_counts) is per (game, player) and keyed on
      pfr_player_id, NOT gsis_id. We join back via players.pfr_id (populated
      by rosters ingest).
    - We aggregate to (player, season) = sum across all games the player
      played. Since player_seasons is end-of-season grain (one row per player
      per season), the whole-season total naturally flows to the row for
      the player's end-of-season team.

Scope in v1:
    - Regular season only (``game_type == 'REG'``). Playoff snap volume has
      different team-count dynamics and would distort per-game rates.
      Playoffs can be added as a separate column later if useful.

``games_started`` heuristic:
    - snap_counts does NOT expose a "started" flag. We approximate:
      a game counts as "started" if the player played >=50% of their
      primary-phase snaps in that game. Primary phase is inferred as the
      phase (offense/defense/st) with the highest snap_pct across the
      player's season.
    - This is documented as approximate; a more authoritative source (PFR
      game logs) can replace it later.

See also:
    - ingest/_cache.py          (the nflreadpy entry point)
    - ingest/rosters.py         (upstream: populates players + pfr_id)
    - docs/exploration/2026-04-23-snaps-depth.md
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


# Threshold for counting a game as "started" — fraction of the player's
# primary-phase snaps they were on the field for.
_STARTED_SNAP_PCT_THRESHOLD = 0.50


@dataclass(frozen=True)
class RunResult:
    season: int
    player_seasons_updated: int
    rows_skipped_no_pfr_match: int
    rows_ingested: int               # rows in the raw snap_counts dataframe (REG-only)


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch snap counts for ``season``, aggregate to (player, season),
    and UPDATE the matching ``player_seasons`` rows.

    Requires: rosters.run(season) has already populated the
    (player_id, season, team_id) rows we're updating, and players.pfr_id
    has been backfilled.

    Idempotent: re-running overwrites the snap columns with freshly
    computed totals.
    """
    if season < 2012:
        raise ValueError(f"snap_counts coverage begins in 2012; got {season}")

    df = cache_or_fetch("snap_counts", season=season, refresh=refresh)

    # V1: regular season only.
    df_reg = df[df["game_type"] == "REG"].copy()
    total_rows = len(df_reg)

    engine = get_engine()
    with pipeline_run("ingest:snap_counts", season=season) as handle:
        with engine.begin() as conn:
            pfr_to_player_id = _pfr_to_player_id(conn)
            agg_rows, skipped_no_match = _aggregate(
                df_reg, season, pfr_to_player_id
            )
            updated = _update_player_seasons(conn, agg_rows, season)

        result = RunResult(
            season=season,
            player_seasons_updated=updated,
            rows_skipped_no_pfr_match=skipped_no_match,
            rows_ingested=total_rows,
        )
        handle.rows_written = updated
        handle.note(
            f"rows_ingested={result.rows_ingested} "
            f"player_seasons_updated={result.player_seasons_updated} "
            f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match}"
        )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pfr_to_player_id(conn: Connection) -> dict[str, int]:
    """Build (pfr_id -> player_id) lookup from the players master."""
    rows = conn.execute(
        text("SELECT pfr_id, player_id FROM players WHERE pfr_id IS NOT NULL")
    ).all()
    return {pfr_id: player_id for pfr_id, player_id in rows}


def _aggregate(
    df_reg: pd.DataFrame,
    season: int,
    pfr_to_player_id: dict[str, int],
) -> tuple[list[dict[str, object]], int]:
    """Aggregate per-game snap rows to per-player-season totals.

    Returns:
        (list of rows ready for UPDATE, count of distinct pfr_ids with no player match)
    """
    if df_reg.empty:
        return [], 0

    # Group by pfr_player_id; sum snaps, count games, and compute started.
    # We intentionally do NOT group by team — a traded player's snaps for
    # both teams roll up to their end-of-season player_seasons row.
    rows: list[dict[str, object]] = []
    unmatched_pfr_ids: set[str] = set()

    grouped = df_reg.groupby("pfr_player_id", sort=False)
    for pfr_id, sub in grouped:
        player_id = pfr_to_player_id.get(str(pfr_id))
        if player_id is None:
            unmatched_pfr_ids.add(str(pfr_id))
            continue

        off = int(sub["offense_snaps"].sum())
        deff = int(sub["defense_snaps"].sum())
        st = int(sub["st_snaps"].sum())
        games = int(len(sub))

        # Pick the player's primary phase for the "started" heuristic.
        mean_off = float(sub["offense_pct"].mean())
        mean_def = float(sub["defense_pct"].mean())
        mean_st = float(sub["st_pct"].mean())
        if mean_off >= mean_def and mean_off >= mean_st:
            started = int((sub["offense_pct"] >= _STARTED_SNAP_PCT_THRESHOLD).sum())
        elif mean_def >= mean_st:
            started = int((sub["defense_pct"] >= _STARTED_SNAP_PCT_THRESHOLD).sum())
        else:
            started = int((sub["st_pct"] >= _STARTED_SNAP_PCT_THRESHOLD).sum())

        rows.append({
            "player_id": player_id,
            "season": season,
            "games": games,
            "games_started": started,
            "snaps_offense": off,
            "snaps_defense": deff,
            "snaps_special": st,
        })

    return rows, len(unmatched_pfr_ids)


def _update_player_seasons(
    conn: Connection, rows: list[dict[str, object]], season: int
) -> int:
    """Apply aggregated snap totals back to existing player_seasons rows.

    Uses a temporary table + UPDATE ... FROM so we don't hit row-at-a-time
    UPDATE performance for ~2k players. Only rows in ``player_seasons`` are
    updated — aggregated rows for players who don't have a player_seasons
    row (e.g. played but weren't on any end-of-season roster) are silently
    ignored. Count those via the returned int if needed.
    """
    if not rows:
        return 0

    conn.execute(text(
        """
        CREATE TEMPORARY TABLE _snap_agg (
            player_id     INTEGER PRIMARY KEY,
            season        INTEGER NOT NULL,
            games         INTEGER NOT NULL,
            games_started INTEGER NOT NULL,
            snaps_offense INTEGER NOT NULL,
            snaps_defense INTEGER NOT NULL,
            snaps_special INTEGER NOT NULL
        ) ON COMMIT DROP
        """
    ))

    conn.execute(
        text(
            """
            INSERT INTO _snap_agg (
                player_id, season, games, games_started,
                snaps_offense, snaps_defense, snaps_special
            )
            VALUES (
                :player_id, :season, :games, :games_started,
                :snaps_offense, :snaps_defense, :snaps_special
            )
            """
        ),
        rows,
    )

    result = conn.execute(text(
        """
        UPDATE player_seasons ps
           SET games         = a.games,
               games_started = a.games_started,
               snaps_offense = a.snaps_offense,
               snaps_defense = a.snaps_defense,
               snaps_special = a.snaps_special
          FROM _snap_agg a
         WHERE ps.player_id = a.player_id
           AND ps.season    = a.season
        """
    ))
    # rowcount on UPDATE gives the number of rows actually modified.
    return result.rowcount or 0
