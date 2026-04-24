"""Ingest Next Gen Stats into the three ``ngs_*`` tables.

Sources (via ingest/_cache.py):
    - nflreadpy.load_nextgen_stats(stat_type='passing')  -> ngs_passing
    - nflreadpy.load_nextgen_stats(stat_type='rushing')  -> ngs_rushing
    - nflreadpy.load_nextgen_stats(stat_type='receiving')-> ngs_receiving

Coverage: 2016+. Earlier seasons: raises ValueError.

Grain: one row per (player_id, season, season_type, week, team_id).
The ``week=0`` row is the nflverse-convention season summary — the
grading pipeline reads those for per-season metrics.

Strategy (same for all three):
    - fetch raw DataFrame
    - resolve player_gsis_id -> player_id via ``players``
    - resolve team_abbr -> team_id via ``team_aliases``
    - coerce floats / ints / NaN
    - DELETE WHERE season=:s, then bulk INSERT

Skipped rows (unknown player / unknown team) are counted and logged —
they should be zero for modern seasons; non-zero usually signals a
missing roster ingest or a historical team abbr we haven't aliased.

See ADR-0012 for the three-tables decision.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)

StatType = Literal["passing", "rushing", "receiving"]


# ---------------------------------------------------------------------------
# Per-stat-type column specs
# ---------------------------------------------------------------------------
# Each spec is (table_name, source_name, db_columns_in_order, int_cols).
# ``db_columns_in_order`` excludes PK cols (player_id/season/season_type/
# week/team_id) and excludes anything we derive or drop.
# ``int_cols`` is the subset of those columns that must be coerced to int
# (the rest are REAL / float).


_PASSING_METRIC_COLS: tuple[str, ...] = (
    "avg_time_to_throw", "avg_completed_air_yards", "avg_intended_air_yards",
    "avg_air_yards_differential", "aggressiveness",
    "max_completed_air_distance", "avg_air_yards_to_sticks",
    "attempts", "pass_yards", "pass_touchdowns", "interceptions",
    "completions", "passer_rating", "completion_percentage",
    "expected_completion_percentage", "completion_percentage_above_expectation",
    "avg_air_distance", "max_air_distance",
)
_PASSING_INT_COLS: frozenset[str] = frozenset({
    "attempts", "pass_yards", "pass_touchdowns", "interceptions", "completions",
})

_RUSHING_METRIC_COLS: tuple[str, ...] = (
    "efficiency", "percent_attempts_gte_eight_defenders", "avg_time_to_los",
    "rush_attempts", "rush_yards", "avg_rush_yards", "rush_touchdowns",
    "expected_rush_yards", "rush_yards_over_expected",
    "rush_yards_over_expected_per_att", "rush_pct_over_expected",
)
_RUSHING_INT_COLS: frozenset[str] = frozenset({
    "rush_attempts", "rush_yards", "rush_touchdowns",
})

_RECEIVING_METRIC_COLS: tuple[str, ...] = (
    "avg_cushion", "avg_separation", "avg_intended_air_yards",
    "percent_share_of_intended_air_yards",
    "receptions", "targets", "catch_percentage", "yards", "rec_touchdowns",
    "avg_yac", "avg_expected_yac", "avg_yac_above_expectation",
)
_RECEIVING_INT_COLS: frozenset[str] = frozenset({
    "receptions", "targets", "yards", "rec_touchdowns",
})


@dataclass(frozen=True)
class _Spec:
    stat_type: StatType
    table: str
    source: str                       # key in the cache registry
    metric_cols: tuple[str, ...]
    int_cols: frozenset[str]


_SPECS: dict[StatType, _Spec] = {
    "passing": _Spec("passing", "ngs_passing", "ngs_passing",
                     _PASSING_METRIC_COLS, _PASSING_INT_COLS),
    "rushing": _Spec("rushing", "ngs_rushing", "ngs_rushing",
                     _RUSHING_METRIC_COLS, _RUSHING_INT_COLS),
    "receiving": _Spec("receiving", "ngs_receiving", "ngs_receiving",
                       _RECEIVING_METRIC_COLS, _RECEIVING_INT_COLS),
}


_PK_COLS: tuple[str, ...] = (
    "player_id", "season", "season_type", "week", "team_id"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    stat_type: str
    season: int
    rows_ingested: int
    rows_written: int
    skipped_unknown_player: int
    skipped_unknown_team: int


def run(stat_type: StatType, season: int, *, refresh: bool = False) -> RunResult:
    """Ingest one NGS stat type for one season.

    Raises:
        ValueError: for ``season < 2016`` (no NGS coverage) or unknown stat_type.
    """
    if season < 2016:
        raise ValueError(f"NGS coverage begins in 2016; got {season}")
    if stat_type not in _SPECS:
        raise ValueError(f"unknown stat_type {stat_type!r}; use passing/rushing/receiving")
    spec = _SPECS[stat_type]

    df = cache_or_fetch(spec.source, season=season, refresh=refresh)  # type: ignore[arg-type]
    logger.info("ngs %s raw shape for %d: %s", stat_type, season, df.shape)

    engine = get_engine()
    with pipeline_run(f"ingest:ngs_{stat_type}", season=season) as handle:
        with engine.begin() as conn:
            team_lookup = _team_abbr_to_id(conn)
            player_lookup = _gsis_to_player_id(conn)
            rows, skipped_player, skipped_team = _transform(
                df, spec, team_lookup, player_lookup, season
            )
            written = _replace_season(conn, spec.table, spec.metric_cols, rows, season)
        result = RunResult(
            stat_type=stat_type,
            season=season,
            rows_ingested=len(df),
            rows_written=written,
            skipped_unknown_player=skipped_player,
            skipped_unknown_team=skipped_team,
        )
        handle.rows_written = written
        handle.note(
            f"rows_ingested={result.rows_ingested} "
            f"rows_written={result.rows_written} "
            f"skipped_unknown_player={result.skipped_unknown_player} "
            f"skipped_unknown_team={result.skipped_unknown_team}"
        )
    return result


def run_all(season: int, *, refresh: bool = False) -> list[RunResult]:
    """Convenience: ingest all three NGS stat types for one season."""
    return [run(st, season, refresh=refresh) for st in ("passing", "rushing", "receiving")]


# ---------------------------------------------------------------------------
# Lookup helpers (shared with depth_charts.py; duplicated here to keep
# ingest modules self-contained — the teams/players lookups are tiny).
# ---------------------------------------------------------------------------


def _team_abbr_to_id(conn: Connection) -> dict[str, int]:
    rows = conn.execute(text("SELECT alias, team_id FROM team_aliases")).all()
    if not rows:
        raise RuntimeError("team_aliases is empty; run `nflgrades migrate` first.")
    return {alias: team_id for alias, team_id in rows}


def _gsis_to_player_id(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT gsis_id, player_id FROM players WHERE gsis_id IS NOT NULL")
    ).all()
    return {gsis: pid for gsis, pid in rows}


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def _transform(
    df: pd.DataFrame,
    spec: _Spec,
    team_lookup: dict[str, int],
    player_lookup: dict[str, int],
    season: int,
) -> tuple[list[dict[str, object]], int, int]:
    """Project + resolve IDs + coerce types. Returns (rows, skipped_player, skipped_team)."""
    # All PK source cols + metric cols must be present.
    required = {"player_gsis_id", "season", "season_type", "week", "team_abbr"} | set(spec.metric_cols)
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"NGS {spec.stat_type} source missing columns: {sorted(missing)}. "
            "Check nflreadpy version / ADR-0012."
        )

    rows: list[dict[str, object]] = []
    skipped_player = 0
    skipped_team = 0

    for rec in df.itertuples(index=False):
        gsis = rec.player_gsis_id
        abbr = rec.team_abbr
        if gsis is None or (isinstance(gsis, float) and math.isnan(gsis)):
            skipped_player += 1
            continue
        player_id = player_lookup.get(str(gsis))
        if player_id is None:
            skipped_player += 1
            continue
        team_id = team_lookup.get(str(abbr)) if abbr is not None else None
        if team_id is None:
            skipped_team += 1
            continue

        row: dict[str, object] = {
            "player_id": player_id,
            "season": season,       # enforce invariant
            "season_type": str(rec.season_type),
            "week": int(rec.week),
            "team_id": team_id,
        }

        for col in spec.metric_cols:
            val = getattr(rec, col)    # col name varies per stat type
            row[col] = _coerce_metric(val, is_int=col in spec.int_cols)
        rows.append(row)

    return rows, skipped_player, skipped_team


def _coerce_metric(val: object, *, is_int: bool) -> object:
    """NaN/None -> None. Numeric values cast to int or float."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if is_int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    try:
        fv = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(fv):
        return None
    return fv


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


def _replace_season(
    conn: Connection,
    table: str,
    metric_cols: tuple[str, ...],
    rows: list[dict[str, object]],
    season: int,
) -> int:
    """Wipe season then bulk INSERT. Idempotent."""
    # Table name comes from our spec dict, not user input — safe to interpolate.
    conn.execute(text(f"DELETE FROM {table} WHERE season = :s"), {"s": season})
    if not rows:
        return 0

    all_cols = _PK_COLS + metric_cols
    insert_sql = text(
        f"INSERT INTO {table} ("
        + ", ".join(all_cols)
        + ") VALUES ("
        + ", ".join(f":{c}" for c in all_cols)
        + ")"
    )

    # NGS is small (<2k rows/season/table); no chunking needed.
    conn.execute(insert_sql, rows)
    return len(rows)
