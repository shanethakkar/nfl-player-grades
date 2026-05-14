"""Ingest FTN per-play receiver charting flags aggregated to season totals.

Source: ``ftn`` (per-play boolean flags for catchable / drop / contested /
created) joined to ``pbp.receiver_player_id`` via ``(game_id, play_id)``.
nflverse exposes FTN charting starting in 2022.

Output table: ``ftn_receiving_charting`` (player_id, season, catchable_balls,
drops, contested_balls, created_receptions). Used by WR v1.1 grading
(ADR-0015 revised) for the drop_rate component.

Earlier seasons (2016-2021) have no FTN data; the grader handles missing
drop_rate via NaN-neutralization (component contribution = 0).
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

FTN_RECEIVING_MIN_SEASON: int = 2022


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_written: int
    rows_skipped_no_gsis_match: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Pull FTN charting + PBP, aggregate per-receiver, write to DB.

    Idempotent: DELETE + INSERT per season.
    """
    if season < FTN_RECEIVING_MIN_SEASON:
        raise ValueError(
            f"FTN charting begins in {FTN_RECEIVING_MIN_SEASON}; got season={season}"
        )

    pbp = cache_or_fetch("pbp", season=season, refresh=refresh)
    ftn = cache_or_fetch("ftn", season=season, refresh=refresh)

    # Filter PBP to regular season + plays with a receiver.
    pbp_reg = pbp[
        (pbp["season_type"] == "REG") & pbp["receiver_player_id"].notna()
    ].copy()
    pbp_reg["play_id"] = pbp_reg["play_id"].astype(int)

    # Join: (game_id, play_id) is the unique key. nflverse_play_id alone is
    # not unique across games.
    joined = pbp_reg.merge(
        ftn[[
            "nflverse_game_id", "nflverse_play_id",
            "is_catchable_ball", "is_drop", "is_contested_ball",
            "is_created_reception",
        ]],
        left_on=["game_id", "play_id"],
        right_on=["nflverse_game_id", "nflverse_play_id"],
        how="inner",
    )

    if joined.empty:
        logger.warning("FTN receiving season=%d: no rows after join", season)
        return _write_empty(season)

    # Aggregate by gsis_id (which is what receiver_player_id holds in PBP).
    agg = joined.groupby("receiver_player_id").agg(
        catchable_balls=("is_catchable_ball", "sum"),
        drops=("is_drop", "sum"),
        contested_balls=("is_contested_ball", "sum"),
        created_receptions=("is_created_reception", "sum"),
    ).reset_index().rename(columns={"receiver_player_id": "gsis_id"})

    engine = get_engine()
    with pipeline_run("ingest:ftn_receiving_charting", season=season) as handle:
        with engine.begin() as conn:
            gsis_to_player = _gsis_to_player_lookup(conn)
            rows, skipped = _build_rows(agg, season, gsis_to_player)
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_written=written,
            rows_skipped_no_gsis_match=skipped,
        )
        handle.rows_written = written
        handle.note(
            f"ftn_rows={len(joined)} written={written} "
            f"skipped_no_gsis={skipped}"
        )
    return result


def _gsis_to_player_lookup(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT gsis_id, player_id FROM players WHERE gsis_id IS NOT NULL")
    ).all()
    return {gsis_id: player_id for gsis_id, player_id in rows}


def _build_rows(
    agg: pd.DataFrame,
    season: int,
    gsis_to_player: dict[str, int],
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    skipped = 0

    for _, r in agg.iterrows():
        gsis = r["gsis_id"]
        if pd.isna(gsis):
            skipped += 1
            continue
        player_id = gsis_to_player.get(str(gsis))
        if player_id is None:
            skipped += 1
            continue
        rows.append({
            "player_id":          player_id,
            "season":             season,
            "catchable_balls":    int(r["catchable_balls"]),
            "drops":              int(r["drops"]),
            "contested_balls":    int(r["contested_balls"]),
            "created_receptions": int(r["created_receptions"]),
        })

    if skipped:
        logger.warning(
            "ftn_receiving_charting season=%d: %d gsis_ids with no player record",
            season, skipped,
        )
    return rows, skipped


_INSERT_SQL = text("""
    INSERT INTO ftn_receiving_charting
        (player_id, season, catchable_balls, drops, contested_balls, created_receptions)
    VALUES
        (:player_id, :season, :catchable_balls, :drops, :contested_balls, :created_receptions)
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(
        text("DELETE FROM ftn_receiving_charting WHERE season = :season"),
        {"season": season},
    )
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


def _write_empty(season: int) -> RunResult:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM ftn_receiving_charting WHERE season = :season"),
            {"season": season},
        )
    return RunResult(season=season, rows_written=0, rows_skipped_no_gsis_match=0)


__all__ = ["FTN_RECEIVING_MIN_SEASON", "RunResult", "run"]
