"""Tests for PBP ingestion.

Pure transform tests (NaN handling, type coercion, renames, PK filtering)
+ integration tests for the DELETE+INSERT cycle.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.ingest.pbp import (
    _DB_COLUMNS,
    _SOURCE_COLUMNS,
    _coerce,
    _replace_season,
    _transform,
)


def _make_source_row(**overrides) -> dict:
    """Minimal PBP source row: one entry for every expected source col."""
    defaults: dict = {
        "game_id": "2024_01_ARI_BUF",
        "play_id": 1,
        "season": 2024,
        "season_type": "REG",
        "week": 1,
        "game_date": "2024-09-08",
        "posteam": "BUF", "defteam": "ARI",
        "home_team": "BUF", "away_team": "ARI",
        "qtr": 1, "down": 1, "ydstogo": 10, "yardline_100": 75,
        "score_differential": 0,
        "game_seconds_remaining": 3600, "half_seconds_remaining": 1800,
        "wp": 0.55,
        "play_type": "pass",
        "qb_dropback": 1.0, "pass_attempt": 1.0, "rush_attempt": 0.0,
        "sack": 0.0, "qb_scramble": 0.0, "qb_spike": 0.0, "qb_kneel": 0.0,
        "aborted_play": 0.0, "two_point_attempt": 0.0, "penalty": 0.0,
        "passer_player_id": "00-0034857",   # Josh Allen
        "rusher_player_id": None,
        "receiver_player_id": "00-0036322",
        "sack_player_id": None,
        "interception_player_id": None,
        "yards_gained": 7, "epa": 0.42, "wpa": 0.015,
        "cpoe": 3.2, "success": 1.0,
        "air_yards": 5, "yards_after_catch": 2,
        "complete_pass": 1.0, "incomplete_pass": 0.0, "interception": 0.0,
        "fumble": 0.0, "fumble_lost": 0.0, "pass_touchdown": 0.0,
        "rush_touchdown": 0.0, "touchdown": 0.0,
        "xyac_mean_yardage": 3.8,
        "desc": "(14:59) 17-J.Allen pass short right to 14-S.Diggs for 7 yards.",
    }
    defaults.update(overrides)
    # Any missing target column triggers the transform's RuntimeError guard.
    assert set(defaults.keys()) == set(_SOURCE_COLUMNS), (
        f"missing source cols: {set(_SOURCE_COLUMNS) - set(defaults.keys())}"
    )
    return defaults


class TestCoerce:
    def test_text_nan_string_becomes_none(self) -> None:
        assert _coerce("posteam", "nan") is None
        assert _coerce("posteam", "NaN") is None
        assert _coerce("posteam", "") is None

    def test_text_roundtrips(self) -> None:
        assert _coerce("posteam", "KC") == "KC"
        assert _coerce("play_desc", "a long description") == "a long description"

    def test_float_nan_becomes_none_for_ints(self) -> None:
        assert _coerce("yards_gained", float("nan")) is None
        assert _coerce("qtr", float("nan")) is None

    def test_float_ints_coerce(self) -> None:
        # PBP sometimes delivers int-valued columns as float64.
        assert _coerce("yards_gained", 7.0) == 7
        assert _coerce("yards_gained", np.int64(7)) == 7

    def test_bool_nan_becomes_none(self) -> None:
        assert _coerce("qb_dropback", float("nan")) is None

    def test_bool_from_float(self) -> None:
        assert _coerce("qb_dropback", 1.0) is True
        assert _coerce("qb_dropback", 0.0) is False

    def test_real_passes_through(self) -> None:
        assert _coerce("epa", 0.42) == pytest.approx(0.42)
        assert _coerce("epa", float("nan")) is None

    def test_date_from_string(self) -> None:
        assert _coerce("game_date", "2024-09-08") == date(2024, 9, 8)

    def test_date_from_pandas_timestamp(self) -> None:
        assert _coerce("game_date", pd.Timestamp("2024-09-08")) == date(2024, 9, 8)


class TestTransform:
    def test_minimal_roundtrip(self) -> None:
        df = pd.DataFrame([_make_source_row()])
        rows, skipped = _transform(df, 2024)
        assert skipped == 0
        assert len(rows) == 1
        r = rows[0]
        # Types
        assert isinstance(r["play_id"], int)
        assert isinstance(r["epa"], float)
        assert isinstance(r["qb_dropback"], bool) and r["qb_dropback"] is True
        assert isinstance(r["game_date"], date)
        # Renamed column
        assert "play_desc" in r and "desc" not in r
        assert "pass to" in r["play_desc"].lower() or "diggs" in r["play_desc"].lower()
        # Season enforced from arg, not source
        assert r["season"] == 2024

    def test_preserves_db_column_order(self) -> None:
        # Insert SQL relies on _DB_COLUMNS ordering; every row must carry
        # exactly those keys.
        df = pd.DataFrame([_make_source_row()])
        rows, _ = _transform(df, 2024)
        assert set(rows[0].keys()) == set(_DB_COLUMNS)

    def test_nan_rich_row(self) -> None:
        # A "no_play" row: play_type null, most outcome fields NaN.
        df = pd.DataFrame([_make_source_row(
            play_type=None, qb_dropback=float("nan"), pass_attempt=float("nan"),
            epa=float("nan"), cpoe=float("nan"), air_yards=float("nan"),
            yards_after_catch=float("nan"), passer_player_id=None,
            receiver_player_id=None,
        )])
        rows, _ = _transform(df, 2024)
        r = rows[0]
        assert r["play_type"] is None
        assert r["qb_dropback"] is None
        assert r["epa"] is None
        assert r["air_yards"] is None
        assert r["passer_player_id"] is None

    def test_skips_rows_missing_pk(self) -> None:
        df = pd.DataFrame([
            _make_source_row(),
            _make_source_row(game_id=None, play_id=2),
            _make_source_row(play_id=None),
        ])
        rows, skipped = _transform(df, 2024)
        assert len(rows) == 1
        assert skipped == 2

    def test_raises_on_missing_source_column(self) -> None:
        # Drop a required column -> transform must not silently coerce NaN.
        row = _make_source_row()
        row.pop("epa")
        df = pd.DataFrame([row])
        with pytest.raises(RuntimeError, match="missing expected columns"):
            _transform(df, 2024)


# ---------------------------------------------------------------------------
# DB integration
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    try:
        engine = get_engine()
        with engine.connect() as connection:
            tx = connection.begin()
            try:
                yield connection
            finally:
                tx.rollback()
    except OperationalError as e:
        pytest.skip(f"Postgres unavailable: {e}")


class TestReplaceSeason:
    def _row(self, **overrides) -> dict:
        """A minimal valid target-shape row (DB cols, not source cols)."""
        r: dict = {c: None for c in _DB_COLUMNS}
        r.update({
            "game_id": "TEST_GAME_1", "play_id": 1,
            "season": 1999, "season_type": "REG",
            "epa": 0.5, "qb_dropback": True,
            "play_desc": "test play",
        })
        r.update(overrides)
        return r

    def test_insert_then_replace_is_idempotent(self, conn) -> None:
        rows = [
            self._row(play_id=1, epa=0.5),
            self._row(play_id=2, epa=-0.1, qb_dropback=False),
        ]
        n1 = _replace_season(conn, rows, 1999)
        assert n1 == 2

        # Re-insert with different values; should cleanly replace.
        rows2 = [self._row(play_id=1, epa=1.5)]
        n2 = _replace_season(conn, rows2, 1999)
        assert n2 == 1

        final = conn.execute(
            text("SELECT play_id, epa FROM plays WHERE season=1999 ORDER BY play_id")
        ).all()
        assert final == [(1, pytest.approx(1.5))]

    def test_empty_clears_season(self, conn) -> None:
        assert _replace_season(conn, [self._row()], 1999) == 1
        assert _replace_season(conn, [], 1999) == 0
        count = conn.execute(
            text("SELECT COUNT(*) FROM plays WHERE season=1999")
        ).scalar()
        assert count == 0

    def test_nulls_round_trip(self, conn) -> None:
        # Most columns NULL — exercises every nullable column.
        rows = [self._row(play_id=42, epa=None, qb_dropback=None,
                           play_desc=None)]
        assert _replace_season(conn, rows, 1999) == 1
        row = conn.execute(text(
            "SELECT epa, qb_dropback, play_desc FROM plays "
            "WHERE season=1999 AND play_id=42"
        )).first()
        assert row == (None, None, None)

    def test_does_not_affect_other_seasons(self, conn) -> None:
        _replace_season(conn, [self._row(play_id=1, season=1998)], 1998)
        _replace_season(conn, [self._row(play_id=2, season=1999)], 1999)
        _replace_season(conn, [], 1999)
        # 1998 must survive.
        count_1998 = conn.execute(
            text("SELECT COUNT(*) FROM plays WHERE season=1998")
        ).scalar()
        assert count_1998 == 1
