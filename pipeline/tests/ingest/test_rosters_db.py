"""Integration tests for the SQL upsert helpers in rosters.py.

These run against the dev Postgres and ALWAYS roll back. They isolate the
SQL — they do NOT exercise pipeline_run() (which opens its own short-lived
transactions and would commit through our rollback).

Skipped automatically if the DB is unavailable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.ingest.rosters import (
    _read_gsis_to_player_id,
    _team_abbr_to_id,
    _upsert_player_seasons,
    _upsert_players,
)

# Sentinel gsis_ids — guaranteed not to collide with real nflverse data.
FAKE_GSIS = {
    "alpha": "TEST-AAAA",
    "beta": "TEST-BBBB",
}


@pytest.fixture
def conn():
    """Yield a transactional connection that ALWAYS rolls back."""
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
        pytest.skip("team_aliases not seeded; run `nflgrades migrate --seeds`")
    return row[0]


class TestTeamLookup:
    def test_loads_aliases(self, conn) -> None:
        lookup = _team_abbr_to_id(conn)
        # 32 active teams × multiple aliases = many rows; should at least
        # contain a few well-known ones.
        assert "KC" in lookup
        assert "BAL" in lookup
        assert "PHI" in lookup
        # Historical aliases too.
        assert "OAK" in lookup  # Raiders pre-2020
        assert "STL" in lookup  # Rams pre-2016


class TestUpsertPlayers:
    def test_insert_then_update(self, conn, kc_team_id: int) -> None:
        rows = [
            {
                "gsis_id": FAKE_GSIS["alpha"],
                "pfr_id": "TestAl00",
                "full_name": "Alpha Player",
                "position": "QB",
                "birth_date": "1995-01-01",
                "height_inches": 75,
                "weight_lbs": 220,
                "draft_year": 2017,
                "draft_round": 1,
                "draft_pick": 10,
                "current_team_id": kc_team_id,
            }
        ]
        n = _upsert_players(conn, rows)
        assert n == 1

        row = conn.execute(
            text("SELECT full_name, position, weight_lbs FROM players WHERE gsis_id = :g"),
            {"g": FAKE_GSIS["alpha"]},
        ).first()
        assert row is not None
        assert row[0] == "Alpha Player"
        assert row[1] == "QB"
        assert row[2] == 220

        rows[0]["weight_lbs"] = 225
        rows[0]["full_name"] = "Alpha Updated"
        _upsert_players(conn, rows)

        row2 = conn.execute(
            text("SELECT full_name, weight_lbs FROM players WHERE gsis_id = :g"),
            {"g": FAKE_GSIS["alpha"]},
        ).first()
        assert row2[0] == "Alpha Updated"
        assert row2[1] == 225

    def test_empty_input_is_noop(self, conn) -> None:
        assert _upsert_players(conn, []) == 0

    def test_null_ints_are_accepted(self, conn, kc_team_id: int) -> None:
        # The bug we're guarding against: pandas turns nullable int columns
        # into float64 with NaN, which Postgres rejects. Make sure passing
        # real None works for every nullable int column.
        rows = [
            {
                "gsis_id": FAKE_GSIS["beta"],
                "pfr_id": None,
                "full_name": "Beta Player",
                "position": "WR",
                "birth_date": None,
                "height_inches": None,
                "weight_lbs": None,
                "draft_year": None,
                "draft_round": None,
                "draft_pick": None,
                "current_team_id": kc_team_id,
            }
        ]
        n = _upsert_players(conn, rows)
        assert n == 1


class TestUpsertPlayerSeasons:
    def test_delete_then_insert(self, conn, kc_team_id: int) -> None:
        _upsert_players(
            conn,
            [
                {
                    "gsis_id": FAKE_GSIS["alpha"],
                    "pfr_id": None,
                    "full_name": "Alpha",
                    "position": "QB",
                    "birth_date": None,
                    "height_inches": None,
                    "weight_lbs": None,
                    "draft_year": None,
                    "draft_round": None,
                    "draft_pick": None,
                    "current_team_id": kc_team_id,
                }
            ],
        )
        gsis_to_id = _read_gsis_to_player_id(conn)
        player_id = gsis_to_id[FAKE_GSIS["alpha"]]

        ps = [
            {
                "player_id": player_id,
                "season": 1999,
                "team_id": kc_team_id,
                "position_played": "QB",
                "games": 0,
                "games_started": 0,
                "snaps_offense": 0,
                "snaps_defense": 0,
                "snaps_special": 0,
            }
        ]
        n = _upsert_player_seasons(conn, ps, season=1999)
        assert n == 1

        rows = conn.execute(
            text("SELECT player_id, position_played FROM player_seasons WHERE season = 1999"),
        ).all()
        assert len(rows) == 1
        assert rows[0][1] == "QB"

        ps[0]["position_played"] = "WR"
        n2 = _upsert_player_seasons(conn, ps, season=1999)
        assert n2 == 1
        rows2 = conn.execute(
            text("SELECT position_played FROM player_seasons WHERE season = 1999"),
        ).all()
        assert len(rows2) == 1
        assert rows2[0][0] == "WR"

    def test_empty_still_deletes(self, conn) -> None:
        assert _upsert_player_seasons(conn, [], season=1999) == 0
        assert _upsert_player_seasons(conn, [], season=1999) == 0
