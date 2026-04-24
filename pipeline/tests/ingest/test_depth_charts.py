"""Tests for depth_charts ingestion (pure transform + DB UPSERT integration)."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.ingest.depth_charts import (
    SNAPSHOT_WEEK,
    _replace_snapshot,
    _resolve_depth,
    _select_snapshot,
    _transform,
)


@pytest.fixture
def team_lookup() -> dict[str, int]:
    return {"KC": 1, "BAL": 2, "PHI": 3}


@pytest.fixture
def gsis_lookup() -> dict[str, int]:
    return {
        "00-MAHOMES": 100,
        "00-JACKSON": 101,
        "00-HURTS":   102,
        "00-KELCE":   103,
    }


def _row(**overrides) -> dict:
    """Shape one row in the NORMALIZED intermediate form (what _transform
    expects): club_code, gsis_id, position, depth_order_raw."""
    base = {
        "club_code": "KC",
        "position": "QB",
        "depth_order_raw": "1",
        "gsis_id": "00-MAHOMES",
    }
    base.update(overrides)
    return base


class TestResolveDepth:
    def test_parses_int_string(self) -> None:
        assert _resolve_depth("1") == 1

    def test_parses_int_directly(self) -> None:
        assert _resolve_depth(2) == 2

    def test_parses_with_whitespace(self) -> None:
        assert _resolve_depth(" 3 ") == 3

    def test_non_integer_returns_none(self) -> None:
        assert _resolve_depth("E") is None

    def test_missing_returns_none(self) -> None:
        assert _resolve_depth(None) is None


class TestSelectSnapshot:
    def test_old_format_picks_latest_reg_week(self) -> None:
        df = pd.DataFrame([
            {"season": 2024, "club_code": "KC", "week": 10.0, "game_type": "REG",
             "depth_team": "1", "gsis_id": "00-MAHOMES",
             "position": "QB", "depth_position": "QB"},
            {"season": 2024, "club_code": "KC", "week": 18.0, "game_type": "REG",
             "depth_team": "1", "gsis_id": "00-MAHOMES",
             "position": "QB", "depth_position": "QB"},
            {"season": 2024, "club_code": "KC", "week": 19.0, "game_type": "WC",
             "depth_team": "1", "gsis_id": "00-MAHOMES",
             "position": "QB", "depth_position": "QB"},
        ])
        snap, fmt, label = _select_snapshot(df, 2024)
        assert fmt == "week-keyed"
        assert label == "week=18"
        assert len(snap) == 1
        assert list(snap.columns) == ["club_code", "gsis_id", "position", "depth_order_raw"]
        assert snap.iloc[0]["position"] == "QB"

    def test_old_format_prefers_depth_position(self) -> None:
        df = pd.DataFrame([{
            "season": 2024, "club_code": "KC", "week": 1.0, "game_type": "REG",
            "depth_team": "1", "gsis_id": "00-MAHOMES",
            "position": "G", "depth_position": "RG",
        }])
        snap, _, _ = _select_snapshot(df, 2024)
        assert snap.iloc[0]["position"] == "RG"

    def test_new_format_picks_latest_timestamp(self) -> None:
        df = pd.DataFrame([
            {"dt": "2025-09-01T10:00:00Z", "team": "KC",
             "gsis_id": "00-MAHOMES", "pos_abb": "QB", "pos_rank": 1},
            {"dt": "2026-03-14T07:00:00Z", "team": "KC",
             "gsis_id": "00-MAHOMES", "pos_abb": "QB", "pos_rank": 1},
        ])
        snap, fmt, label = _select_snapshot(df, 2025)
        assert fmt == "timestamp-keyed"
        assert label == "dt=2026-03-14T07:00:00Z"
        assert len(snap) == 1

    def test_unrecognized_schema_raises(self) -> None:
        df = pd.DataFrame([{"foo": "bar"}])
        with pytest.raises(RuntimeError, match="unrecognized"):
            _select_snapshot(df, 2024)


class TestTransform:
    def test_maps_teams_and_players(
        self, team_lookup: dict[str, int], gsis_lookup: dict[str, int],
    ) -> None:
        df = pd.DataFrame([
            _row(),   # Mahomes KC QB1
            _row(gsis_id="00-KELCE", position="TE", depth_order_raw="1"),
            _row(club_code="BAL", gsis_id="00-JACKSON"),  # Lamar BAL QB1
            _row(club_code="PHI", gsis_id="00-HURTS"),    # Hurts PHI QB1
        ])
        rows, skipped = _transform(df, team_lookup, gsis_lookup, 2024)
        assert skipped == {"team": 0, "player": 0, "depth": 0, "duplicate": 0}
        assert len(rows) == 4
        assert all(r["week"] == SNAPSHOT_WEEK for r in rows)
        by = {(r["team_id"], r["position"]): r for r in rows}
        assert by[(1, "QB")]["player_id"] == 100
        assert by[(2, "QB")]["player_id"] == 101
        assert by[(3, "QB")]["player_id"] == 102

    def test_unknown_team_skipped(
        self, gsis_lookup: dict[str, int],
    ) -> None:
        df = pd.DataFrame([_row(club_code="XYZ")])
        rows, skipped = _transform(df, {"KC": 1}, gsis_lookup, 2024)
        assert rows == []
        assert skipped["team"] == 1

    def test_unknown_player_skipped(
        self, team_lookup: dict[str, int],
    ) -> None:
        df = pd.DataFrame([_row(gsis_id="00-UNKNOWN")])
        rows, skipped = _transform(df, team_lookup, {}, 2024)
        assert rows == []
        assert skipped["player"] == 1

    def test_missing_position_skipped(
        self, team_lookup: dict[str, int], gsis_lookup: dict[str, int],
    ) -> None:
        df = pd.DataFrame([_row(position="")])
        rows, skipped = _transform(df, team_lookup, gsis_lookup, 2024)
        assert rows == []
        assert skipped["player"] == 1

    def test_non_integer_depth_skipped(
        self, team_lookup: dict[str, int], gsis_lookup: dict[str, int],
    ) -> None:
        df = pd.DataFrame([_row(depth_order_raw="E")])
        rows, skipped = _transform(df, team_lookup, gsis_lookup, 2024)
        assert rows == []
        assert skipped["depth"] == 1

    def test_duplicates_deduped(
        self, team_lookup: dict[str, int], gsis_lookup: dict[str, int],
    ) -> None:
        # Same (team, position, depth_order) appearing twice — schema PK
        # would reject the second; we keep the first.
        df = pd.DataFrame([_row(), _row()])
        rows, skipped = _transform(df, team_lookup, gsis_lookup, 2024)
        assert len(rows) == 1
        assert skipped["duplicate"] == 1


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


@pytest.fixture
def kc_team_id(conn) -> int:
    row = conn.execute(
        text("SELECT team_id FROM team_aliases WHERE alias='KC'")
    ).first()
    if row is None:
        pytest.skip("team_aliases not seeded")
    return row[0]


class TestReplaceSnapshot:
    def test_insert_then_replace_is_idempotent(
        self, conn, kc_team_id: int
    ) -> None:
        player_id = conn.execute(
            text("""
                INSERT INTO players (gsis_id, full_name, position, current_team_id)
                VALUES ('TEST-DC-1', 'Depth Tester', 'QB', :t)
                RETURNING player_id
            """),
            {"t": kc_team_id},
        ).scalar_one()

        rows = [{
            "team_id": kc_team_id, "season": 1999, "week": SNAPSHOT_WEEK,
            "position": "QB", "depth_order": 1, "player_id": player_id,
        }]
        n1 = _replace_snapshot(conn, rows, 1999)
        assert n1 == 1

        # Second call should DELETE old + re-INSERT — not crash on PK.
        n2 = _replace_snapshot(conn, rows, 1999)
        assert n2 == 1

        final_count = conn.execute(
            text("SELECT COUNT(*) FROM depth_charts WHERE season=1999 AND week=:w"),
            {"w": SNAPSHOT_WEEK},
        ).scalar()
        assert final_count == 1

    def test_empty_rows_still_clears(self, conn) -> None:
        # Idempotent with empty input — clears season, no crash.
        assert _replace_snapshot(conn, [], 1999) == 0
        assert _replace_snapshot(conn, [], 1999) == 0
