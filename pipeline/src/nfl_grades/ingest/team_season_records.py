"""Ingest regular-season team records (W-L, points for/against, point diff).

Source: ``nflreadpy.load_schedules`` — same source used in the team-weight
audit. Filters to ``game_type == 'REG'`` and aggregates per team-season.

Used by the team leaderboard on /teams as context columns. Not part of
the grading pipeline — these are denormalized so the web layer can
display them without per-request schedule scraping.

Idempotent: delete-then-insert for (season).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    season: int
    teams_written: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Build per-team regular-season record rows for ``season``.

    `refresh` is accepted for API symmetry with other ingest modules but
    is a no-op here — we always pull fresh schedule data because the
    schedules feed updates continuously through the offseason.
    """
    del refresh  # unused; we always re-pull

    import nflreadpy as nfl  # local import — heavy dep

    sched = nfl.load_schedules([season]).to_pandas()
    sched = sched[sched["game_type"] == "REG"].copy()
    # Drop unplayed games (in-progress seasons or scheduling oddities).
    sched = sched.dropna(subset=["home_score", "away_score"])

    if sched.empty:
        logger.warning("no REG schedule rows for season %d — skipping", season)
        return RunResult(season=season, teams_written=0)

    # Long-form: one row per (team_perspective, game).
    home = pd.DataFrame(
        {
            "team_abbr": sched["home_team"],
            "points_for": sched["home_score"].astype(int),
            "points_against": sched["away_score"].astype(int),
        }
    )
    away = pd.DataFrame(
        {
            "team_abbr": sched["away_team"],
            "points_for": sched["away_score"].astype(int),
            "points_against": sched["home_score"].astype(int),
        }
    )
    long = pd.concat([home, away], ignore_index=True)
    long["win"] = (long["points_for"] > long["points_against"]).astype(int)
    long["loss"] = (long["points_for"] < long["points_against"]).astype(int)
    long["tie"] = (long["points_for"] == long["points_against"]).astype(int)

    agg = (
        long.groupby("team_abbr")
        .agg(
            wins=("win", "sum"),
            losses=("loss", "sum"),
            ties=("tie", "sum"),
            points_for=("points_for", "sum"),
            points_against=("points_against", "sum"),
            n_games=("win", "size"),
        )
        .reset_index()
    )
    agg["point_diff"] = agg["points_for"] - agg["points_against"]

    engine = get_engine()
    with pipeline_run("ingest:team_season_records", season=season) as handle:
        with engine.begin() as conn:
            team_lookup = _team_abbr_to_id(conn)
            written = _replace_rows(conn, agg, team_lookup, season)
        handle.rows_written = written
        handle.note(f"teams_written={written}")
    return RunResult(season=season, teams_written=written)


def _team_abbr_to_id(conn: Connection) -> dict[str, int]:
    rows = conn.execute(text("SELECT alias, team_id FROM team_aliases")).all()
    if not rows:
        raise RuntimeError("team_aliases is empty; run migrate --seeds first.")
    return {alias: team_id for alias, team_id in rows}


def _replace_rows(
    conn: Connection, agg: pd.DataFrame, team_lookup: dict[str, int], season: int
) -> int:
    conn.execute(text("DELETE FROM team_season_records WHERE season = :s"), {"s": season})
    rows = []
    for _, r in agg.iterrows():
        team_id = team_lookup.get(str(r["team_abbr"]))
        if team_id is None:
            logger.warning("unknown team abbr in schedule data: %s", r["team_abbr"])
            continue
        rows.append(
            {
                "team_id": team_id,
                "season": season,
                "wins": int(r["wins"]),
                "losses": int(r["losses"]),
                "ties": int(r["ties"]),
                "points_for": int(r["points_for"]),
                "points_against": int(r["points_against"]),
                "point_diff": int(r["point_diff"]),
                "n_games": int(r["n_games"]),
            }
        )
    if not rows:
        return 0
    conn.execute(
        text(
            """
            INSERT INTO team_season_records
                (team_id, season, wins, losses, ties,
                 points_for, points_against, point_diff, n_games)
            VALUES
                (:team_id, :season, :wins, :losses, :ties,
                 :points_for, :points_against, :point_diff, :n_games)
            """
        ),
        rows,
    )
    return len(rows)


__all__ = ["RunResult", "run"]
