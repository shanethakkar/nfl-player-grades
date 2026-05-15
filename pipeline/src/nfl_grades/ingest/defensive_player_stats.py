"""Ingest CB/S/EDGE/iDL/LB box-score volume stats into defensive_player_season_stats.

Source: ``nflvs_player_stats`` (per-week rows; aggregated to season totals,
REG only). Populates context columns shown on the defensive leaderboards —
these are NOT inputs to the grades.

Filter: position in the defensive set below so offensive players, K, and P
don't pollute the table.
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

DEFENSIVE_STATS_MIN_SEASON: int = 2016

_INCLUDED_POSITIONS: frozenset[str] = frozenset({
    # Secondary — nflverse uses SAF as the dominant safety label from
    # ~2020 onward; S/FS/SS still appear in older seasons (and for some
    # players in current ones). DB is a generic fallback.
    "CB", "DB", "FS", "SS", "S", "SAF",
    # Linebackers
    "LB", "ILB", "MLB", "OLB",
    # Front (interior + edge). EDGE included for future-proofing.
    "DE", "DT", "NT", "DL", "EDGE",
})

_SUM_COLS_INT: list[str] = [
    "def_tackles_solo",
    "def_tackle_assists",
    "def_qb_hits",
    "def_pass_defended",
    "def_interceptions",
    "def_interception_yards",
    "def_fumbles_forced",
    "def_tds",
]
_SUM_COLS_REAL: list[str] = [
    "def_sacks",
    "def_tackles_for_loss",
]


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_match: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch + aggregate defensive stats for one season. Idempotent."""
    if season < DEFENSIVE_STATS_MIN_SEASON:
        raise ValueError(
            f"defensive_player_season_stats begins in {DEFENSIVE_STATS_MIN_SEASON}; "
            f"got season={season}"
        )

    df_raw = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)
    agg = _aggregate(df_raw, season)

    engine = get_engine()
    with pipeline_run("ingest:defensive_player_stats", season=season) as handle:
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
            f"def_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_match={result.rows_skipped_no_match}"
        )
    return result


def _aggregate(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter to REG-season defensive rows and aggregate per player to season totals."""
    if hasattr(df_raw, "to_pandas"):
        df_raw = df_raw.to_pandas()
    if "season_type" in df_raw.columns:
        df = df_raw[df_raw["season_type"] == "REG"].copy()
    else:
        df = df_raw.copy()
    if "position" in df.columns:
        df = df[df["position"].isin(_INCLUDED_POSITIONS)].copy()
    if df.empty:
        return df

    sum_cols = _SUM_COLS_INT + _SUM_COLS_REAL
    missing = set(sum_cols) - set(df.columns)
    if missing:
        raise ValueError(
            f"nflvs_player_stats season={season} missing defensive columns: {missing}. "
            "Update _SUM_COLS_INT / _SUM_COLS_REAL in ingest/defensive_player_stats.py."
        )

    games_per_player = (
        df.groupby("player_id")["week"].nunique().rename("games")
        if "week" in df.columns
        else pd.Series(dtype=int, name="games")
    )

    agg = df.groupby("player_id")[sum_cols].sum().reset_index()
    if not games_per_player.empty:
        agg = agg.join(games_per_player, on="player_id")
    else:
        agg["games"] = 0
    return agg


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

    def _float_or_none(val: object) -> float | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)

    for _, row in agg.iterrows():
        gsis = str(row["player_id"])
        pid = gsis_to_player.get(gsis)
        if pid is None:
            skipped += 1
            continue
        rows.append({
            "player_id":        pid,
            "season":           season,
            "games":            _int_or_none(row.get("games")) or 0,
            "tackles_solo":     _int_or_none(row.get("def_tackles_solo")),
            "tackle_assists":   _int_or_none(row.get("def_tackle_assists")),
            "tackles_for_loss": _float_or_none(row.get("def_tackles_for_loss")),
            "sacks":            _float_or_none(row.get("def_sacks")),
            "qb_hits":          _int_or_none(row.get("def_qb_hits")),
            "pass_defended":    _int_or_none(row.get("def_pass_defended")),
            "interceptions":    _int_or_none(row.get("def_interceptions")),
            "int_yards":        _int_or_none(row.get("def_interception_yards")),
            "forced_fumbles":   _int_or_none(row.get("def_fumbles_forced")),
            "def_tds":          _int_or_none(row.get("def_tds")),
        })

    if skipped:
        logger.warning(
            "defensive_player_season_stats season=%d: %d gsis_ids with no player "
            "record (run rosters ingest first)",
            season, skipped,
        )
    return rows, skipped


_DELETE_SQL = text("DELETE FROM defensive_player_season_stats WHERE season = :season")
_INSERT_SQL = text("""
    INSERT INTO defensive_player_season_stats (
        player_id, season, games,
        tackles_solo, tackle_assists, tackles_for_loss,
        sacks, qb_hits,
        pass_defended, interceptions, int_yards,
        forced_fumbles, def_tds
    ) VALUES (
        :player_id, :season, :games,
        :tackles_solo, :tackle_assists, :tackles_for_loss,
        :sacks, :qb_hits,
        :pass_defended, :interceptions, :int_yards,
        :forced_fumbles, :def_tds
    )
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(_DELETE_SQL, {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["DEFENSIVE_STATS_MIN_SEASON", "RunResult", "run"]
