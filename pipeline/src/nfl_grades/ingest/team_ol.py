"""Ingest team-level offensive-line stats into team_ol_stats (per-season totals).

Sources:
  - pbp: passing/rushing plays + penalties, aggregated by posteam
  - pfr_advstats_rush: yards_before_contact summed across all team RBs

Used by OL v1 grading (ADR-0025). Coverage: 2018+ (PFR rush stats begin 2018;
pbp goes back further but the rush-blocking signal needs PFR).
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

TEAM_OL_STATS_MIN_SEASON: int = 2018  # bound by pfr_advstats_rush availability


@dataclass(frozen=True)
class RunResult:
    season: int
    teams_written: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    if season < TEAM_OL_STATS_MIN_SEASON:
        raise ValueError(
            f"team_ol_stats begins in {TEAM_OL_STATS_MIN_SEASON}; got season={season}"
        )

    pbp = cache_or_fetch("pbp", season=season, refresh=refresh)
    pfr_rush = cache_or_fetch("pfr_advstats_rush", season=season, refresh=refresh)

    pbp_agg = _aggregate_pbp(pbp, season)
    rush_agg = _aggregate_pfr_rush(pfr_rush, season)
    merged = pbp_agg.merge(rush_agg, on="posteam", how="left")

    engine = get_engine()
    with pipeline_run("ingest:team_ol_stats", season=season) as handle:
        with engine.begin() as conn:
            abbr_to_team = _abbr_to_team_lookup(conn)
            rows = _build_rows(merged, season, abbr_to_team)
            written = _upsert(conn, rows, season)
        result = RunResult(season=season, teams_written=written)
        handle.rows_written = written
        handle.note(f"teams_written={written}")
    return result


def _aggregate_pbp(pbp: pd.DataFrame, season: int) -> pd.DataFrame:
    """Aggregate REG-season pbp rows by posteam (offensive team)."""
    if hasattr(pbp, "to_pandas"):
        pbp = pbp.to_pandas()
    if "season_type" in pbp.columns:
        pbp = pbp[pbp["season_type"] == "REG"].copy()
    pbp = pbp[pbp["posteam"].notna()].copy()
    if pbp.empty:
        return pbp

    # Pass blocking
    pass_plays = pbp[pbp["qb_dropback"] == 1].copy()
    sacks = pass_plays[pass_plays["sack"] == 1]
    qb_hits = pass_plays[pass_plays["qb_hit"] == 1]

    # Run blocking
    rushes = pbp[pbp["rush_attempt"] == 1].copy()
    rushes_yards = rushes["rushing_yards"].fillna(0).astype(float)

    # OL-attributed penalties
    pen = pbp[pbp["penalty"] == 1].copy()
    false_starts = pen[pen["penalty_type"] == "False Start"]
    holdings = pen[pen["penalty_type"] == "Offensive Holding"]

    by_team = pass_plays.groupby("posteam").size().rename("dropbacks").to_frame()
    by_team["sacks_allowed"] = sacks.groupby("posteam").size()
    by_team["qb_hits_allowed"] = qb_hits.groupby("posteam").size()

    rush_grp = rushes.groupby("posteam")
    by_team["rushes"] = rush_grp.size()
    by_team["rush_yards"] = rush_grp["rushing_yards"].sum()
    by_team["rush_epa_total"] = rush_grp["epa"].sum()
    by_team["rushes_success"] = rushes[rushes["epa"] > 0].groupby("posteam").size()
    by_team["rushes_stuffed"] = rushes[rushes_yards.values <= 0].groupby("posteam").size()
    by_team["rushes_explosive"] = rushes[rushes_yards.values >= 10].groupby("posteam").size()

    # Penalties by penalty_team (the team that committed the penalty);
    # for OL penalties we want the offensive team.
    by_team["false_starts"] = false_starts.groupby("penalty_team").size()
    by_team["holdings"] = holdings.groupby("penalty_team").size()

    by_team = by_team.fillna(0).astype(int, errors="ignore")
    by_team = by_team.reset_index()
    return by_team


def _aggregate_pfr_rush(pfr_rush: pd.DataFrame, season: int) -> pd.DataFrame:
    """Sum rushing_yards_before_contact across all rushers per team.

    Source: pfr_advstats_rush (per-game rows).
    Mapping: pfr `team` col -> our team.abbr.
    """
    if hasattr(pfr_rush, "to_pandas"):
        pfr_rush = pfr_rush.to_pandas()
    if "game_type" in pfr_rush.columns:
        pfr_rush = pfr_rush[pfr_rush["game_type"] == "REG"].copy()
    if pfr_rush.empty or "rushing_yards_before_contact" not in pfr_rush.columns:
        return pd.DataFrame(columns=["posteam", "yards_before_contact"])

    # PFR uses 'team' column (3-letter abbr matching nflverse).
    team_col = "team" if "team" in pfr_rush.columns else "tm"
    if team_col not in pfr_rush.columns:
        logger.warning("pfr_advstats_rush season=%d: no team column; skipping ybc", season)
        return pd.DataFrame(columns=["posteam", "yards_before_contact"])

    agg = (
        pfr_rush.groupby(team_col)["rushing_yards_before_contact"]
        .sum()
        .rename("yards_before_contact")
        .reset_index()
        .rename(columns={team_col: "posteam"})
    )
    return agg


def _abbr_to_team_lookup(conn: Connection) -> dict[str, int]:
    rows = conn.execute(text("SELECT abbr, team_id FROM teams")).all()
    return {abbr: tid for abbr, tid in rows}


def _build_rows(
    merged: pd.DataFrame,
    season: int,
    abbr_to_team: dict[str, int],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def _i(val: object) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)

    def _f(val: object) -> float | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)

    for _, r in merged.iterrows():
        abbr = str(r["posteam"])
        tid = abbr_to_team.get(abbr)
        if tid is None:
            logger.warning("team_ol_stats season=%d: no team_id for abbr=%s", season, abbr)
            continue
        rows.append({
            "team_id":              tid,
            "season":               season,
            "dropbacks":            _i(r.get("dropbacks")),
            "sacks_allowed":        _i(r.get("sacks_allowed")),
            "qb_hits_allowed":      _i(r.get("qb_hits_allowed")),
            "pressures_allowed":    None,  # filled in by a later step (PFR per-defender)
            "rushes":               _i(r.get("rushes")),
            "rush_yards":           _i(r.get("rush_yards")),
            "yards_before_contact": _i(r.get("yards_before_contact")),
            "rush_epa_total":       _f(r.get("rush_epa_total")),
            "rushes_success":       _i(r.get("rushes_success")),
            "rushes_stuffed":       _i(r.get("rushes_stuffed")),
            "rushes_explosive":     _i(r.get("rushes_explosive")),
            "false_starts":         _i(r.get("false_starts")),
            "holdings":             _i(r.get("holdings")),
        })
    return rows


_DELETE_SQL = text("DELETE FROM team_ol_stats WHERE season = :season")
_INSERT_SQL = text("""
    INSERT INTO team_ol_stats (
        team_id, season,
        dropbacks, sacks_allowed, qb_hits_allowed, pressures_allowed,
        rushes, rush_yards, yards_before_contact, rush_epa_total,
        rushes_success, rushes_stuffed, rushes_explosive,
        false_starts, holdings
    ) VALUES (
        :team_id, :season,
        :dropbacks, :sacks_allowed, :qb_hits_allowed, :pressures_allowed,
        :rushes, :rush_yards, :yards_before_contact, :rush_epa_total,
        :rushes_success, :rushes_stuffed, :rushes_explosive,
        :false_starts, :holdings
    )
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(_DELETE_SQL, {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["TEAM_OL_STATS_MIN_SEASON", "RunResult", "run"]
