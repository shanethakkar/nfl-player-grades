"""Ingest kicker stats into kicker_stats (per-season totals).

Source: ``nflvs_player_stats`` (per-game rows; aggregated to season totals,
regular season only). Used by K v1 grading (ADR-0023).

v1 scope: placekicking only (FG + XP). Kickoffs intentionally excluded
because the 2024 dynamic-kickoff rule change broke continuity of
touchback/return rates; a v2 component if added.

Coverage: nflvs has K data from at least 2016. Earlier seasons exist
but we cap at 2016 to match other position grading availability.
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

KICKER_STATS_MIN_SEASON: int = 2016

# Per-game count columns we sum to season totals.
_SUM_COLS: list[str] = [
    "fg_att", "fg_made", "fg_blocked",
    "fg_made_0_19", "fg_missed_0_19",
    "fg_made_20_29", "fg_missed_20_29",
    "fg_made_30_39", "fg_missed_30_39",
    "fg_made_40_49", "fg_missed_40_49",
    "fg_made_50_59", "fg_missed_50_59",
    "fg_made_60_", "fg_missed_60_",
    "pat_att", "pat_made", "pat_blocked",
    "gwfg_att", "gwfg_made",
]


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int
    rows_written: int
    rows_skipped_no_match: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Fetch and store kicker season stats. Idempotent DELETE + INSERT."""
    if season < KICKER_STATS_MIN_SEASON:
        raise ValueError(
            f"kicker_stats begins in {KICKER_STATS_MIN_SEASON}; got season={season}"
        )

    df_raw = cache_or_fetch("nflvs_player_stats", season=season, refresh=refresh)
    agg = _aggregate(df_raw, season)

    engine = get_engine()
    with pipeline_run("ingest:kicker_stats", season=season) as handle:
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
            f"k_rows={result.rows_ingested} "
            f"written={result.rows_written} "
            f"skipped_no_match={result.rows_skipped_no_match}"
        )
    return result


def _aggregate(df_raw: pd.DataFrame, season: int) -> pd.DataFrame:
    """Filter to REG-season K rows and aggregate per player to season totals."""
    if hasattr(df_raw, "to_pandas"):
        df_raw = df_raw.to_pandas()
    if "season_type" in df_raw.columns:
        df = df_raw[df_raw["season_type"] == "REG"].copy()
    else:
        df = df_raw.copy()
    if "position" in df.columns:
        df = df[df["position"] == "K"].copy()
    if df.empty:
        return df

    missing = set(_SUM_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"nflvs_player_stats season={season} missing K columns: {missing}. "
            "Update _SUM_COLS in ingest/kicker.py."
        )

    games_per_player = (
        df.groupby("player_id")["week"].nunique().rename("games")
        if "week" in df.columns
        else pd.Series(dtype=int, name="games")
    )

    agg_dict = {c: (c, "sum") for c in _SUM_COLS}
    # fg_long is a per-game max, not a sum — season long = max of per-game longs.
    if "fg_long" in df.columns:
        agg_dict["fg_long"] = ("fg_long", "max")

    agg = df.groupby("player_id").agg(**agg_dict).reset_index()
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

    def _bucket_att(row: pd.Series, made_col: str, missed_col: str) -> int | None:
        m = row.get(made_col)
        x = row.get(missed_col)
        if (m is None or (isinstance(m, float) and pd.isna(m))) and (
            x is None or (isinstance(x, float) and pd.isna(x))
        ):
            return None
        return int((m or 0) + (x or 0))

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
            "fg_att":           _int_or_none(row.get("fg_att")),
            "fg_made":          _int_or_none(row.get("fg_made")),
            "fg_blocked":       _int_or_none(row.get("fg_blocked")),
            "fg_long":          _int_or_none(row.get("fg_long")),
            "fg_att_0_19":      _bucket_att(row, "fg_made_0_19", "fg_missed_0_19"),
            "fg_made_0_19":     _int_or_none(row.get("fg_made_0_19")),
            "fg_att_20_29":     _bucket_att(row, "fg_made_20_29", "fg_missed_20_29"),
            "fg_made_20_29":    _int_or_none(row.get("fg_made_20_29")),
            "fg_att_30_39":     _bucket_att(row, "fg_made_30_39", "fg_missed_30_39"),
            "fg_made_30_39":    _int_or_none(row.get("fg_made_30_39")),
            "fg_att_40_49":     _bucket_att(row, "fg_made_40_49", "fg_missed_40_49"),
            "fg_made_40_49":    _int_or_none(row.get("fg_made_40_49")),
            "fg_att_50_59":     _bucket_att(row, "fg_made_50_59", "fg_missed_50_59"),
            "fg_made_50_59":    _int_or_none(row.get("fg_made_50_59")),
            "fg_att_60_plus":   _bucket_att(row, "fg_made_60_", "fg_missed_60_"),
            "fg_made_60_plus":  _int_or_none(row.get("fg_made_60_")),
            "pat_att":          _int_or_none(row.get("pat_att")),
            "pat_made":         _int_or_none(row.get("pat_made")),
            "pat_blocked":      _int_or_none(row.get("pat_blocked")),
            "gwfg_att":         _int_or_none(row.get("gwfg_att")),
            "gwfg_made":        _int_or_none(row.get("gwfg_made")),
        })

    if skipped:
        logger.warning(
            "kicker_stats season=%d: %d gsis_ids with no player record "
            "(run rosters ingest first)",
            season, skipped,
        )
    return rows, skipped


_DELETE_SQL = text("DELETE FROM kicker_stats WHERE season = :season")
_INSERT_SQL = text("""
    INSERT INTO kicker_stats (
        player_id, season, games,
        fg_att, fg_made, fg_blocked, fg_long,
        fg_att_0_19, fg_made_0_19,
        fg_att_20_29, fg_made_20_29,
        fg_att_30_39, fg_made_30_39,
        fg_att_40_49, fg_made_40_49,
        fg_att_50_59, fg_made_50_59,
        fg_att_60_plus, fg_made_60_plus,
        pat_att, pat_made, pat_blocked,
        gwfg_att, gwfg_made
    ) VALUES (
        :player_id, :season, :games,
        :fg_att, :fg_made, :fg_blocked, :fg_long,
        :fg_att_0_19, :fg_made_0_19,
        :fg_att_20_29, :fg_made_20_29,
        :fg_att_30_39, :fg_made_30_39,
        :fg_att_40_49, :fg_made_40_49,
        :fg_att_50_59, :fg_made_50_59,
        :fg_att_60_plus, :fg_made_60_plus,
        :pat_att, :pat_made, :pat_blocked,
        :gwfg_att, :gwfg_made
    )
""")


def _upsert(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    conn.execute(_DELETE_SQL, {"season": season})
    if rows:
        conn.execute(_INSERT_SQL, rows)
    return len(rows)


__all__ = ["KICKER_STATS_MIN_SEASON", "RunResult", "run"]
