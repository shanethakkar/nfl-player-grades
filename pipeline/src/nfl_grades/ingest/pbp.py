"""Ingest play-by-play into the thin ``plays`` table.

Source:  nflreadpy.load_pbp(seasons=[s])  via ingest/_cache.py
Target:  plays (schema in db/migrations/0003_create_plays.sql)

Strategy:
    - Pull the full 372-column PBP DataFrame (via the Parquet cache).
    - Project down to our 42 target columns (see ``PLAYS_COLUMNS``).
    - Rename ``desc`` -> ``play_desc`` (SQL reserved-word).
    - Convert nullable numeric / boolean columns from pandas NaN/NaT to
      Python None so psycopg binds them correctly (same pattern as
      rosters.py — Pandas' automatic type promotion bites us otherwise).
    - Replace the season's rows via DELETE + bulk INSERT, in a single
      transaction. Idempotent.

Grain:
    One row per (game_id, play_id). PBP is already at play grain — this
    module doesn't aggregate, it just re-shapes.

See also:
    - ADR-0011 — column selection rationale
    - ingest/_cache.py — the nflreadpy entry point
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)


# Columns we project out of the raw PBP DataFrame, in the order they
# appear in the DB table. The rename map handles the one name change
# (nflverse 'desc' -> 'play_desc' because 'desc' is a SQL reserved word).
_SOURCE_COLUMNS: tuple[str, ...] = (
    "game_id",
    "play_id",
    "season",
    "season_type",
    "week",
    "game_date",
    "posteam",
    "defteam",
    "home_team",
    "away_team",
    "qtr",
    "down",
    "ydstogo",
    "yardline_100",
    "score_differential",
    "game_seconds_remaining",
    "half_seconds_remaining",
    "wp",
    "play_type",
    "qb_dropback",
    "pass_attempt",
    "rush_attempt",
    "sack",
    "qb_scramble",
    "qb_spike",
    "qb_kneel",
    "aborted_play",
    "two_point_attempt",
    "penalty",
    "passer_player_id",
    "rusher_player_id",
    "receiver_player_id",
    "sack_player_id",
    "interception_player_id",
    "yards_gained",
    "epa",
    "wpa",
    "cpoe",
    "success",
    "air_yards",
    "yards_after_catch",
    "complete_pass",
    "incomplete_pass",
    "interception",
    "fumble",
    "fumble_lost",
    "pass_touchdown",
    "rush_touchdown",
    "touchdown",
    "xyac_mean_yardage",
    "desc",  # -> play_desc
)

_COLUMN_RENAME: dict[str, str] = {"desc": "play_desc"}

# Classification of each column for type coercion. Pandas NaN/NaT
# handling differs per dtype; we convert explicitly.
_INT_COLS: frozenset[str] = frozenset(
    {
        "play_id",
        "season",
        "week",
        "game_seconds_remaining",
        "half_seconds_remaining",
        "yards_gained",
        "air_yards",
        "yards_after_catch",
    }
)
_SMALLINT_COLS: frozenset[str] = frozenset(
    {
        "qtr",
        "down",
        "ydstogo",
        "yardline_100",
        "score_differential",
    }
)
_REAL_COLS: frozenset[str] = frozenset({"wp", "epa", "wpa", "cpoe", "xyac_mean_yardage"})
_BOOL_COLS: frozenset[str] = frozenset(
    {
        "qb_dropback",
        "pass_attempt",
        "rush_attempt",
        "sack",
        "qb_scramble",
        "qb_spike",
        "qb_kneel",
        "aborted_play",
        "two_point_attempt",
        "penalty",
        "success",
        "complete_pass",
        "incomplete_pass",
        "interception",
        "fumble",
        "fumble_lost",
        "pass_touchdown",
        "rush_touchdown",
        "touchdown",
    }
)
_DATE_COLS: frozenset[str] = frozenset({"game_date"})
_TEXT_COLS: frozenset[str] = frozenset(
    {
        "game_id",
        "season_type",
        "posteam",
        "defteam",
        "home_team",
        "away_team",
        "play_type",
        "passer_player_id",
        "rusher_player_id",
        "receiver_player_id",
        "sack_player_id",
        "interception_player_id",
        "play_desc",
    }
)


# DB-side target column list (after rename).
_DB_COLUMNS: tuple[str, ...] = tuple(_COLUMN_RENAME.get(c, c) for c in _SOURCE_COLUMNS)


@dataclass(frozen=True)
class RunResult:
    season: int
    rows_ingested: int  # rows pulled from the source DataFrame
    rows_written: int  # rows inserted into Postgres (= rows_ingested unless we drop some)
    rows_skipped_no_pk: int  # rows missing game_id or play_id (shouldn't happen, but defensive)


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Ingest PBP for ``season`` into the ``plays`` table.

    Idempotent: re-running deletes and re-inserts the season.
    """
    if season < 1999:
        raise ValueError(f"PBP coverage begins in 1999; got {season}")

    df_raw = cache_or_fetch("pbp", season=season, refresh=refresh)
    logger.info("pbp raw shape for season %d: %s", season, df_raw.shape)

    rows, skipped = _transform(df_raw, season)

    engine = get_engine()
    with pipeline_run("ingest:pbp", season=season) as handle:
        with engine.begin() as conn:
            written = _replace_season(conn, rows, season)
        result = RunResult(
            season=season,
            rows_ingested=len(df_raw),
            rows_written=written,
            rows_skipped_no_pk=skipped,
        )
        handle.rows_written = written
        handle.note(
            f"rows_ingested={result.rows_ingested} "
            f"rows_written={result.rows_written} "
            f"skipped_no_pk={result.rows_skipped_no_pk}"
        )
    return result


# ---------------------------------------------------------------------------
# Transform: pandas DataFrame -> list[dict] with proper None handling
# ---------------------------------------------------------------------------


def _transform(df: pd.DataFrame, season: int) -> tuple[list[dict[str, object]], int]:
    """Project + rename + coerce types. Returns (rows, skipped_no_pk)."""
    missing = [c for c in _SOURCE_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"PBP source is missing expected columns: {missing}. "
            f"Check nflreadpy version / ADR-0011."
        )

    sub = df[list(_SOURCE_COLUMNS)].rename(columns=_COLUMN_RENAME)

    rows: list[dict[str, object]] = []
    skipped = 0
    # itertuples is ~5x faster than iterrows for 50k rows and safe here
    # because all target columns are valid Python identifiers after rename.
    for rec in sub.itertuples(index=False, name=None):
        row: dict[str, object] = {}
        for col, val in zip(_DB_COLUMNS, rec, strict=True):
            row[col] = _coerce(col, val)

        if row["game_id"] is None or row["play_id"] is None:
            skipped += 1
            continue
        # Enforce the season invariant even if the source says otherwise
        # (shouldn't happen in practice, but defends against bad data).
        row["season"] = season
        rows.append(row)
    return rows, skipped


def _coerce(col: str, val: object) -> object:
    """Convert pandas NaN/NaT/numpy-typed values into proper Python types
    that psycopg can bind.

    Branch on the column's expected SQL type because the right coercion
    depends on the target — integer columns can't take NaN, text columns
    can't take numpy.float64, etc.
    """
    # Fast-path for explicit None.
    if val is None:
        return None

    # pandas/numpy NaN + NaT detection (single float NaN covers both).
    if isinstance(val, float) and math.isnan(val):
        return None

    if col in _TEXT_COLS:
        s = str(val)
        # Pandas represents missing strings as literal 'nan' sometimes,
        # and numpy-typed strings need a normal str cast either way.
        if s in ("nan", "NaN", "NaT", ""):
            return None
        return s

    if col in _INT_COLS or col in _SMALLINT_COLS:
        try:
            iv = int(val)  # numpy ints and floats without fractional part OK
        except (TypeError, ValueError):
            return None
        return iv

    if col in _REAL_COLS:
        try:
            fv = float(val)
        except (TypeError, ValueError):
            return None
        if math.isnan(fv):
            return None
        return fv

    if col in _BOOL_COLS:
        # PBP booleans arrive as float 0.0/1.0 with NaN for "n/a" plays.
        try:
            fv = float(val)
        except (TypeError, ValueError):
            return None
        if math.isnan(fv):
            return None
        return bool(fv)

    if col in _DATE_COLS:
        # pd.Timestamp and datetime.datetime both inherit from datetime.date,
        # so we have to check the more-specific types first and reduce them
        # to a plain date via .date().
        if isinstance(val, (pd.Timestamp, datetime)):
            return val.date()
        if isinstance(val, date):
            return val
        try:
            return pd.to_datetime(val).date()
        except Exception:
            return None

    # Fallback — shouldn't reach here if the column classification is complete.
    return val


# ---------------------------------------------------------------------------
# DB write: DELETE-then-bulk-INSERT in one transaction
# ---------------------------------------------------------------------------


_INSERT_SQL = text(
    "INSERT INTO plays ("
    + ", ".join(_DB_COLUMNS)
    + ") VALUES ("
    + ", ".join(f":{c}" for c in _DB_COLUMNS)
    + ")"
)


def _replace_season(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    """Wipe ``plays`` for this season, insert the new rows. Idempotent."""
    conn.execute(
        text("DELETE FROM plays WHERE season = :s"),
        {"s": season},
    )
    if not rows:
        return 0

    # Chunk the insert. SQLAlchemy's executemany via psycopg handles
    # ~50k rows fine, but chunking gives progress logging and caps peak
    # memory in the driver buffer.
    chunk_size = 5000
    written = 0
    for i in range(0, len(rows), chunk_size):
        batch = rows[i : i + chunk_size]
        conn.execute(_INSERT_SQL, batch)
        written += len(batch)
        logger.debug("inserted %d/%d rows", written, len(rows))
    return written
