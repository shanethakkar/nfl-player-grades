"""Tests for snap_counts ingestion.

Pure aggregation tests (no DB) + an integration test for the UPDATE SQL.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.ingest.snap_counts import _aggregate, _update_player_seasons


def _make_game_row(
    *,
    pfr_id: str,
    week: int,
    off_snaps: int = 0,
    off_pct: float = 0.0,
    def_snaps: int = 0,
    def_pct: float = 0.0,
    st_snaps: int = 0,
    st_pct: float = 0.0,
    game_type: str = "REG",
) -> dict:
    return {
        "season": 2024,
        "week": week,
        "game_type": game_type,
        "pfr_player_id": pfr_id,
        "offense_snaps": float(off_snaps),
        "offense_pct": off_pct,
        "defense_snaps": float(def_snaps),
        "defense_pct": def_pct,
        "st_snaps": float(st_snaps),
        "st_pct": st_pct,
    }


class TestAggregate:
    def test_sums_snaps_across_games(self) -> None:
        df = pd.DataFrame(
            [
                _make_game_row(pfr_id="MahoPa00", week=1, off_snaps=70, off_pct=1.0),
                _make_game_row(pfr_id="MahoPa00", week=2, off_snaps=65, off_pct=1.0),
                _make_game_row(pfr_id="MahoPa00", week=3, off_snaps=72, off_pct=1.0),
            ]
        )
        rows, skipped = _aggregate(df, 2024, {"MahoPa00": 100})
        assert skipped == 0
        assert len(rows) == 1
        r = rows[0]
        assert r["player_id"] == 100
        assert r["games"] == 3
        assert r["games_started"] == 3  # all 100% snap rate -> started all
        assert r["snaps_offense"] == 207
        assert r["snaps_defense"] == 0
        assert r["snaps_special"] == 0

    def test_started_heuristic_respects_primary_phase(self) -> None:
        # Defensive player with 3 games started (def_pct >= 0.5), 1 cameo.
        df = pd.DataFrame(
            [
                _make_game_row(pfr_id="DefGuy00", week=1, def_snaps=60, def_pct=1.00),
                _make_game_row(pfr_id="DefGuy00", week=2, def_snaps=55, def_pct=0.92),
                _make_game_row(pfr_id="DefGuy00", week=3, def_snaps=50, def_pct=0.83),
                _make_game_row(
                    pfr_id="DefGuy00", week=4, def_snaps=10, def_pct=0.15, st_snaps=5, st_pct=0.25
                ),
            ]
        )
        rows, _ = _aggregate(df, 2024, {"DefGuy00": 200})
        r = rows[0]
        assert r["games"] == 4
        assert r["games_started"] == 3

    def test_specialist_uses_st_phase_for_started(self) -> None:
        df = pd.DataFrame(
            [_make_game_row(pfr_id="Kicker00", week=w, st_snaps=5, st_pct=0.9) for w in range(1, 4)]
        )
        rows, _ = _aggregate(df, 2024, {"Kicker00": 300})
        assert rows[0]["games_started"] == 3
        assert rows[0]["snaps_special"] == 15

    def test_unmatched_pfr_is_skipped_and_counted(self) -> None:
        df = pd.DataFrame(
            [
                _make_game_row(pfr_id="KnownGuy", week=1, off_snaps=50, off_pct=1.0),
                _make_game_row(pfr_id="UnknownA", week=1, off_snaps=10, off_pct=0.2),
                _make_game_row(pfr_id="UnknownA", week=2, off_snaps=12, off_pct=0.2),
                _make_game_row(pfr_id="UnknownB", week=1, st_snaps=5, st_pct=0.2),
            ]
        )
        rows, skipped = _aggregate(df, 2024, {"KnownGuy": 400})
        assert len(rows) == 1
        # Two distinct unmatched pfr_ids.
        assert skipped == 2

    def test_traded_player_sums_across_teams(self) -> None:
        # Same pfr_id played for two different teams across the season;
        # totals should be combined (we attribute to end-of-season team).
        df = pd.DataFrame(
            [
                _make_game_row(pfr_id="Traded00", week=1, off_snaps=50, off_pct=0.8),
                _make_game_row(pfr_id="Traded00", week=2, off_snaps=55, off_pct=0.85),
                _make_game_row(pfr_id="Traded00", week=10, off_snaps=60, off_pct=0.90),
            ]
        )
        rows, _ = _aggregate(df, 2024, {"Traded00": 500})
        r = rows[0]
        assert r["games"] == 3
        assert r["snaps_offense"] == 165

    def test_empty_input(self) -> None:
        rows, skipped = _aggregate(pd.DataFrame(), 2024, {})
        assert rows == []
        assert skipped == 0


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
    row = conn.execute(text("SELECT team_id FROM team_aliases WHERE alias = 'KC'")).first()
    if row is None:
        pytest.skip("team_aliases not seeded")
    return row[0]


class TestUpdatePlayerSeasons:
    def test_updates_only_matching_rows(self, conn, kc_team_id: int) -> None:
        # Insert a fake player + player_seasons row.
        player_id = conn.execute(
            text("""
                INSERT INTO players (gsis_id, full_name, position, current_team_id)
                VALUES ('TEST-SNAPS-1', 'Snap Tester', 'QB', :t)
                RETURNING player_id
            """),
            {"t": kc_team_id},
        ).scalar_one()
        conn.execute(
            text("""
                INSERT INTO player_seasons (
                    player_id, season, team_id, position_played,
                    games, games_started, snaps_offense, snaps_defense, snaps_special
                ) VALUES (:p, 1999, :t, 'QB', 0, 0, 0, 0, 0)
            """),
            {"p": player_id, "t": kc_team_id},
        )

        agg = [
            {
                "player_id": player_id,
                "season": 1999,
                "games": 17,
                "games_started": 16,
                "snaps_offense": 1100,
                "snaps_defense": 0,
                "snaps_special": 0,
            }
        ]
        updated = _update_player_seasons(conn, agg, 1999)
        assert updated == 1

        row = conn.execute(
            text("""
                SELECT games, games_started, snaps_offense
                FROM player_seasons WHERE player_id=:p AND season=1999
            """),
            {"p": player_id},
        ).first()
        assert row == (17, 16, 1100)

    def test_empty_is_noop(self, conn) -> None:
        assert _update_player_seasons(conn, [], 1999) == 0

    def test_no_matching_player_season_row_is_silent(self, conn, kc_team_id: int) -> None:
        # Insert a player but NO player_seasons row for 1999.
        player_id = conn.execute(
            text("""
                INSERT INTO players (gsis_id, full_name, position, current_team_id)
                VALUES ('TEST-SNAPS-2', 'Orphan', 'WR', :t)
                RETURNING player_id
            """),
            {"t": kc_team_id},
        ).scalar_one()
        agg = [
            {
                "player_id": player_id,
                "season": 1999,
                "games": 5,
                "games_started": 3,
                "snaps_offense": 200,
                "snaps_defense": 0,
                "snaps_special": 10,
            }
        ]
        updated = _update_player_seasons(conn, agg, 1999)
        assert updated == 0
