"""Ingest punter stats into punter_stats (per-season totals).

Source: pbp (play-by-play) — aggregated by `punter_player_id` for rows
where `punt_attempt=1`. nflverse `player_stats` doesn't carry detailed
punting columns, so pbp is the only viable source.

Used by P v1 grading (ADR-0024). Coverage: 2016+.
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

PUNTER_STATS_MIN_SEASON: int = 2016


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_match: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch pbp punt plays and aggregate to season totals.

    Idempotent: DELETE + INSERT replaces the previous season's rows.
    """
    if season < PUNTER_STATS_MIN_SEASON:
        raise ValueError(
            f"punter_stats begins in {PUNTER_STATS_MIN_SEASON}; got season={season}"
        )

    pbp = cache_or_fetch("pbp", season=season, refresh=refresh)
    agg = _aggregate(pbp, season)

    engine = get_engine()
    with pipeline_run("ingest:punter_stats", season=season) as handle:
        with engine.begin() as conn:
            gsis_to_player = _gsis_to_player_lookup(conn)
            rows, skipped = _build_rows(agg, season, gsis_to_player)
            written = _upsert(conn, rows, season)

        result = RunResult(
            season=season,
            rows_ingested=len(agg),
            rows_written=written,
            rows_skipped_no_match=skipped,
        )
        handle.rows_written = written
        handle.note(
            f"p_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_match={result.rows_skipped_no_match}"
        )
    return result


def _aggregate(pbp: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter to REG punts and aggregate per punter to season totals."""
    if hasattr(pbp, "to_pandas"):
        pbp = pbp.to_pandas()
    punts = pbp[pbp["punt_attempt"] == 1].copy()
    if "season_type" in punts.columns:
        punts = punts[punts["season_type"] == "REG"]
    # Drop rows missing the punter id (rare edge cases like fake punts).
    punts = punts[punts["punter_player_id"].notna()]
    if punts.empty:
        return punts

    # Normalize integer flags (some are float in pbp).
    flag_cols = (
        "punt_inside_twenty", "punt_in_endzone", "punt_blocked",
        "punt_fair_catch", "punt_out_of_bounds", "punt_downed",
    )
    for c in flag_cols:
        if c in punts.columns:
            punts[c] = punts[c].fillna(0).astype(int)
        else:
            punts[c] = 0

    punts["kick_distance"] = punts["kick_distance"].fillna(0).astype(int)
    punts["return_yards"] = punts["return_yards"].fillna(0).astype(int)
    punts["epa"] = punts["epa"].fillna(0.0).astype(float)

    grouped = punts.groupby("punter_player_id").agg(
        punts=("punt_attempt", "sum"),
        gross_yards=("kick_distance", "sum"),
        return_yards=("return_yards", "sum"),
        inside_20=("punt_inside_twenty", "sum"),
        touchbacks=("punt_in_endzone", "sum"),
        blocked=("punt_blocked", "sum"),
        fair_catches=("punt_fair_catch", "sum"),
        out_of_bounds=("punt_out_of_bounds", "sum"),
        downed=("punt_downed", "sum"),
        epa_total=("epa", "sum"),
        long_punt=("kick_distance", "max"),
    ).reset_index()
    grouped["net_yards"] = grouped["gross_yards"] - grouped["return_yards"]
    return grouped


def _gsis_to_player_lookup(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT gsis_id, player_id FROM players WHERE gsis_id IS NOT NULL")
    ).all()
    return {gsis: pid for gsis, pid in rows}


def _build_rows(
    agg: pd.DataFrame,
    season: int,
    gsis_to_player: dict[str, int],
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    skipped = 0

    def _int_or_none(val: object) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(val)

    for _, row in agg.iterrows():
        gsis = str(row["punter_player_id"])
        pid = gsis_to_player.get(gsis)
        if pid is None:
            skipped += 1
            continue
        rows.append({
            "player_id":      pid,
            "season":         season,
            "punts":          _int_or_none(row.get("punts")),
            "gross_yards":    _int_or_none(row.get("gross_yards")),
            "return_yards":   _int_or_none(row.get("return_yards")),
            "net_yards":      _int_or_none(row.get("net_yards")),
            "inside_20":      _int_or_none(row.get("inside_20")),
            "touchbacks":     _int_or_none(row.get("touchbacks")),
            "blocked":        _int_or_none(row.get("blocked")),
            "fair_catches":   _int_or_none(row.get("fair_catches")),
            "out_of_bounds":  _int_or_none(row.get("out_of_bounds")),
            "downed":         _int_or_none(row.get("downed")),
            "epa_total":      float(row.get("epa_total") or 0.0),
            "long_punt":      _int_or_none(row.get("long_punt")),
        })

    if skipped:
        logger.warning(
            "punter_stats season=%d: %d gsis_ids with no player record",
            season, skipped,
        )
    return rows, skipped


_DELETE_SQL = text("DELETE FROM punter_stats WHERE season = :season")
_INSERT_SQL = text("""
    INSERT INTO punter_stats (
        player_id, season,
        punts, gross_yards, return_yards, net_yards,
        inside_20, touchbacks, blocked, fair_catches, out_of_bounds, downed,
        epa_total, long_punt
    ) VALUES (
        :player_id, :season,
        :punts, :gross_yards, :return_yards, :net_yards,
        :inside_20, :touchbacks, :blocked, :fair_catches, :out_of_bounds, :downed,
        :epa_total, :long_punt
    )
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(_DELETE_SQL, {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["PUNTER_STATS_MIN_SEASON", "RunResult", "run"]
