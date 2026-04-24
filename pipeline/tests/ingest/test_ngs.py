"""Tests for NGS ingest (passing/rushing/receiving)."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.ingest.ngs import (
    _PASSING_METRIC_COLS,
    _RECEIVING_METRIC_COLS,
    _RUSHING_METRIC_COLS,
    _SPECS,
    _coerce_metric,
    _replace_season,
    _transform,
    run,
)

# ---------------------------------------------------------------------------
# Unit: coerce
# ---------------------------------------------------------------------------


class TestCoerceMetric:
    def test_none_passes_through(self) -> None:
        assert _coerce_metric(None, is_int=False) is None
        assert _coerce_metric(None, is_int=True) is None

    def test_nan_becomes_none(self) -> None:
        assert _coerce_metric(float("nan"), is_int=False) is None
        assert _coerce_metric(float("nan"), is_int=True) is None

    def test_int_coerces(self) -> None:
        assert _coerce_metric(504, is_int=True) == 504
        assert _coerce_metric(504.0, is_int=True) == 504

    def test_float_preserves(self) -> None:
        result = _coerce_metric(2.91, is_int=False)
        assert isinstance(result, float)
        assert result == pytest.approx(2.91)


# ---------------------------------------------------------------------------
# Unit: transform
# ---------------------------------------------------------------------------


def _passing_row(**overrides) -> dict:
    """Source-shape row (NOT target-shape): mirrors what nflreadpy returns."""
    defaults: dict = {
        "season": 2024, "season_type": "REG", "week": 0,
        "player_gsis_id": "00-0033873",   # Mahomes
        "team_abbr": "KC",
    }
    for c in _PASSING_METRIC_COLS:
        defaults[c] = 1.0 if c not in {"attempts", "pass_yards", "pass_touchdowns", "interceptions", "completions"} else 100
    defaults.update(overrides)
    return defaults


class TestTransform:
    def test_passing_roundtrip(self) -> None:
        df = pd.DataFrame([_passing_row()])
        rows, sp, st = _transform(
            df, _SPECS["passing"],
            team_lookup={"KC": 17},
            player_lookup={"00-0033873": 42},
            season=2024,
        )
        assert sp == 0 and st == 0
        assert len(rows) == 1
        r = rows[0]
        assert r["player_id"] == 42
        assert r["team_id"] == 17
        assert r["season"] == 2024
        assert r["season_type"] == "REG"
        assert r["week"] == 0
        # A metric column should carry through
        assert r["avg_time_to_throw"] == pytest.approx(1.0)
        # Int-classified metrics should be int
        assert isinstance(r["attempts"], int)

    def test_skips_unknown_player(self) -> None:
        df = pd.DataFrame([
            _passing_row(),
            _passing_row(player_gsis_id="00-9999999"),   # not in lookup
        ])
        rows, sp, st = _transform(
            df, _SPECS["passing"],
            team_lookup={"KC": 17},
            player_lookup={"00-0033873": 42},
            season=2024,
        )
        assert len(rows) == 1
        assert sp == 1 and st == 0

    def test_skips_unknown_team(self) -> None:
        df = pd.DataFrame([_passing_row(team_abbr="XYZ")])
        rows, sp, st = _transform(
            df, _SPECS["passing"],
            team_lookup={"KC": 17},
            player_lookup={"00-0033873": 42},
            season=2024,
        )
        assert len(rows) == 0
        assert sp == 0 and st == 1

    def test_null_player_gsis(self) -> None:
        # Some historical rows have missing gsis (shouldn't for NGS 2016+,
        # but be defensive).
        df = pd.DataFrame([_passing_row(player_gsis_id=None)])
        rows, sp, st = _transform(
            df, _SPECS["passing"],
            team_lookup={"KC": 17},
            player_lookup={"00-0033873": 42},
            season=2024,
        )
        assert len(rows) == 0
        assert sp == 1

    def test_raises_on_missing_source_column(self) -> None:
        row = _passing_row()
        row.pop("avg_time_to_throw")
        df = pd.DataFrame([row])
        with pytest.raises(RuntimeError, match="missing columns"):
            _transform(df, _SPECS["passing"], {}, {}, 2024)

    def test_rushing_and_receiving_also_work(self) -> None:
        # Rushing
        rushing_row = {
            "season": 2024, "season_type": "REG", "week": 0,
            "player_gsis_id": "00-0035700", "team_abbr": "GB",
            **{c: (1 if c in {"rush_attempts", "rush_yards", "rush_touchdowns"} else 1.0)
               for c in _RUSHING_METRIC_COLS},
        }
        rows, _, _ = _transform(
            pd.DataFrame([rushing_row]),
            _SPECS["rushing"],
            {"GB": 12},
            {"00-0035700": 99},
            2024,
        )
        assert len(rows) == 1 and rows[0]["player_id"] == 99

        # Receiving
        rec_row = {
            "season": 2024, "season_type": "REG", "week": 0,
            "player_gsis_id": "00-0034407", "team_abbr": "ATL",
            **{c: (1 if c in {"receptions", "targets", "yards", "rec_touchdowns"} else 1.0)
               for c in _RECEIVING_METRIC_COLS},
        }
        rows, _, _ = _transform(
            pd.DataFrame([rec_row]),
            _SPECS["receiving"],
            {"ATL": 2},
            {"00-0034407": 55},
            2024,
        )
        assert len(rows) == 1 and rows[0]["team_id"] == 2


class TestRunValidation:
    def test_rejects_pre_2016(self) -> None:
        with pytest.raises(ValueError, match="2016"):
            run("passing", 2015)

    def test_rejects_unknown_stat_type(self) -> None:
        with pytest.raises(ValueError, match="unknown stat_type"):
            run("kicking", 2024)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration: _replace_season
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


@pytest.fixture
def team_id(conn):
    # Grab any existing team for use as FK target
    row = conn.execute(text("SELECT team_id FROM teams LIMIT 1")).first()
    assert row, "no teams seeded — run migrate --seeds"
    return row[0]


@pytest.fixture
def player_id(conn):
    row = conn.execute(
        text("SELECT player_id FROM players WHERE gsis_id IS NOT NULL LIMIT 1")
    ).first()
    if not row:
        pytest.skip("no players with gsis_id; run ingest rosters first")
    return row[0]


class TestReplaceSeason:
    def _row(self, player_id, team_id, **overrides) -> dict:
        # Target-shape row for ngs_passing
        r: dict = {
            "player_id": player_id,
            "season": 1999,   # use a sentinel season so production data isn't touched
            "season_type": "REG",
            "week": 0,
            "team_id": team_id,
        }
        for c in _PASSING_METRIC_COLS:
            r[c] = None
        r["attempts"] = 500
        r["avg_time_to_throw"] = 2.8
        r.update(overrides)
        return r

    def test_insert_then_replace(self, conn, player_id, team_id) -> None:
        rows = [self._row(player_id, team_id)]
        n = _replace_season(conn, "ngs_passing", _PASSING_METRIC_COLS, rows, 1999)
        assert n == 1

        # Replace with different data
        rows2 = [self._row(player_id, team_id, attempts=600)]
        _replace_season(conn, "ngs_passing", _PASSING_METRIC_COLS, rows2, 1999)
        count = conn.execute(
            text("SELECT COUNT(*) FROM ngs_passing WHERE season=1999")
        ).scalar()
        assert count == 1

        attempts = conn.execute(
            text("SELECT attempts FROM ngs_passing WHERE season=1999")
        ).scalar()
        assert attempts == 600

    def test_empty_rows_wipes_season(self, conn, player_id, team_id) -> None:
        _replace_season(conn, "ngs_passing", _PASSING_METRIC_COLS,
                        [self._row(player_id, team_id)], 1999)
        _replace_season(conn, "ngs_passing", _PASSING_METRIC_COLS, [], 1999)
        count = conn.execute(
            text("SELECT COUNT(*) FROM ngs_passing WHERE season=1999")
        ).scalar()
        assert count == 0
