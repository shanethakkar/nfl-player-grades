"""Pure tests for the DataFrame transforms in rosters.py.

No DB. We hand-build tiny DataFrames mimicking the shape of
``nflreadpy.load_players()`` and ``load_rosters()``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from nfl_grades.ingest.rosters import (
    _transform_player_seasons,
    _transform_players,
)


@pytest.fixture
def team_lookup() -> dict[str, int]:
    """Minimal alias->team_id lookup."""
    return {"KC": 1, "BAL": 2, "PHI": 3, "OAK": 4, "LV": 4}  # OAK->LV alias


@pytest.fixture
def players_master() -> pd.DataFrame:
    """Fake load_players() with two players + one extra not in this season."""
    return pd.DataFrame(
        [
            {
                "gsis_id": "00-0033873",
                "pfr_id": "MahoPa00",
                "display_name": "Patrick Mahomes",
                "position_group": "QB",
                "position": "QB",
                "birth_date": "1995-09-17",
                "height": 75,
                "weight": 225,
                "draft_year": 2017,
                "draft_round": 1,
                "draft_pick": 10,
                "latest_team": "KC",
            },
            {
                "gsis_id": "00-0036355",
                "pfr_id": "JackLa00",
                "display_name": "Lamar Jackson",
                "position_group": "QB",
                "position": "QB",
                "birth_date": "1997-01-07",
                "height": 74,
                "weight": 215,
                "draft_year": 2018,
                "draft_round": 1,
                "draft_pick": 32,
                "latest_team": "BAL",
            },
            {
                "gsis_id": "00-0099999",
                "pfr_id": None,
                "display_name": "Retired Player",
                "position_group": "QB",
                "position": "QB",
                "birth_date": "1980-01-01",
                "height": 72,
                "weight": 210,
                "draft_year": 2002,
                "draft_round": 7,
                "draft_pick": 250,
                "latest_team": "KC",
            },
        ]
    )


@pytest.fixture
def rosters_2024() -> pd.DataFrame:
    """Fake load_rosters([2024]). Includes a player NOT in master."""
    return pd.DataFrame(
        [
            {
                "season": 2024,
                "gsis_id": "00-0033873",
                "team": "KC",
                "position": "QB",
                "depth_chart_position": "QB",
                "full_name": "Patrick Mahomes",
            },
            {
                "season": 2024,
                "gsis_id": "00-0036355",
                "team": "BAL",
                "position": "QB",
                "depth_chart_position": "QB",
                "full_name": "Lamar Jackson",
            },
            {
                "season": 2024,
                "gsis_id": "00-0040000",  # not in master -> fallback path
                "team": "PHI",
                "position": "WR",
                "depth_chart_position": "WR",
                "full_name": "Rookie Receiver",
                "birth_date": pd.Timestamp("2002-05-01"),
                "height": 73,
                "weight": 195,
                "entry_year": 2024,
                "draft_number": 145,
            },
        ]
    )


def _by_gsis(rows: list[dict]) -> dict[str, dict]:
    return {r["gsis_id"]: r for r in rows}


class TestTransformPlayers:
    def test_filters_to_season_gsis(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        rows, skipped = _transform_players(players_master, rosters_2024, team_lookup)
        gsis_ids = {r["gsis_id"] for r in rows}
        # Mahomes + Jackson from master, plus the rookie via fallback.
        assert gsis_ids == {"00-0033873", "00-0036355", "00-0040000"}
        assert "00-0099999" not in gsis_ids
        assert skipped == 0

    def test_resolves_team_via_lookup(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        rows, _ = _transform_players(players_master, rosters_2024, team_lookup)
        mahomes = _by_gsis(rows)["00-0033873"]
        assert mahomes["current_team_id"] == 1
        assert mahomes["position"] == "QB"
        assert mahomes["full_name"] == "Patrick Mahomes"
        assert mahomes["pfr_id"] == "MahoPa00"

    def test_fallback_path_uses_rosters_fields(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        rows, _ = _transform_players(players_master, rosters_2024, team_lookup)
        rookie = _by_gsis(rows)["00-0040000"]
        assert rookie["full_name"] == "Rookie Receiver"
        assert rookie["position"] == "WR"
        assert rookie["current_team_id"] == 3
        assert rookie["draft_year"] == 2024
        assert rookie["draft_pick"] == 145
        assert rookie["birth_date"] == "2002-05-01"
        assert rookie["height_inches"] == 73
        assert rookie["weight_lbs"] == 195

    def test_returns_python_int_not_numpy(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        # Postgres adapter wants real None, not NaN, for nullable int columns.
        rows, _ = _transform_players(players_master, rosters_2024, team_lookup)
        for r in rows:
            for col in ("draft_year", "draft_round", "draft_pick", "height_inches", "weight_lbs"):
                v = r[col]
                assert v is None or isinstance(v, int), f"{col}={v!r} ({type(v)})"

    def test_unknown_position_is_skipped_and_counted(
        self,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        bad_master = pd.DataFrame(
            [
                {
                    "gsis_id": "00-0033873",
                    "display_name": "Patrick Mahomes",
                    "position_group": "WTF",
                    "position": "WTF",
                    "birth_date": None,
                    "height": None,
                    "weight": None,
                    "draft_year": None,
                    "draft_round": None,
                    "draft_pick": None,
                    "latest_team": "KC",
                }
            ]
        )
        small_rosters = rosters_2024[rosters_2024["gsis_id"] == "00-0033873"].copy()
        rows, skipped = _transform_players(bad_master, small_rosters, team_lookup)
        assert rows == []
        assert skipped == 1


class TestTransformPlayerSeasons:
    def test_basic_mapping(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        gsis_to_id = {
            "00-0033873": 100,
            "00-0036355": 101,
            "00-0040000": 102,
        }
        rows, sk_pos, sk_team = _transform_player_seasons(
            rosters_2024,
            2024,
            team_lookup,
            gsis_to_id,
            df_players_master=players_master,
        )
        assert sk_pos == 0 and sk_team == 0
        assert len(rows) == 3
        mahomes = next(r for r in rows if r["player_id"] == 100)
        assert mahomes["season"] == 2024
        assert mahomes["team_id"] == 1
        assert mahomes["position_played"] == "QB"
        # Snap counts left at 0; filled by snap_counts ingest later.
        assert mahomes["snaps_offense"] == 0

    def test_unknown_team_skipped(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
    ) -> None:
        gsis_to_id = {gid: i for i, gid in enumerate(rosters_2024["gsis_id"])}
        partial_lookup = {"KC": 1, "BAL": 2}  # missing PHI -> rookie dropped
        rows, _, sk_team = _transform_player_seasons(
            rosters_2024,
            2024,
            partial_lookup,
            gsis_to_id,
            df_players_master=players_master,
        )
        assert sk_team == 1
        assert len(rows) == 2

    def test_unknown_player_skipped_silently(
        self,
        players_master: pd.DataFrame,
        rosters_2024: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        gsis_to_id = {"00-0033873": 100}
        rows, sk_pos, sk_team = _transform_player_seasons(
            rosters_2024,
            2024,
            team_lookup,
            gsis_to_id,
            df_players_master=players_master,
        )
        assert len(rows) == 1
        assert sk_pos == 0 and sk_team == 0

    def test_duplicates_dropped(
        self,
        players_master: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        dupes = pd.DataFrame(
            [
                {
                    "season": 2024,
                    "gsis_id": "X",
                    "team": "KC",
                    "position": "QB",
                    "depth_chart_position": "QB",
                },
                {
                    "season": 2024,
                    "gsis_id": "X",
                    "team": "KC",
                    "position": "QB",
                    "depth_chart_position": "QB",
                },
            ]
        )
        rows, _, _ = _transform_player_seasons(
            dupes, 2024, team_lookup, {"X": 99}, df_players_master=players_master
        )
        assert len(rows) == 1


class TestPlayerSeasonsDLSplit:
    """A roster DE whose career positions both say interior lands in iDL (#4)."""

    @pytest.fixture
    def dl_rosters(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"season": 2025, "gsis_id": "BROWN", "team": "KC",
                 "position": "DL", "depth_chart_position": "DE"},
                {"season": 2025, "gsis_id": "MUHAMMAD", "team": "KC",
                 "position": "DL", "depth_chart_position": "DE"},
                {"season": 2025, "gsis_id": "GARRETT", "team": "KC",
                 "position": "DL", "depth_chart_position": "DE"},
            ]
        )

    @pytest.fixture
    def dl_master(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"gsis_id": "BROWN", "position": "DT", "pff_position": "DI"},
                {"gsis_id": "MUHAMMAD", "position": "DT", "pff_position": "ED"},
                {"gsis_id": "GARRETT", "position": "DE", "pff_position": "ED"},
            ]
        )

    def test_interior_career_de_is_idl_and_edge_rushers_stay_edge(
        self,
        dl_rosters: pd.DataFrame,
        dl_master: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        gsis_to_id = {"BROWN": 1, "MUHAMMAD": 2, "GARRETT": 3}
        rows, _, _ = _transform_player_seasons(
            dl_rosters, 2025, team_lookup, gsis_to_id, df_players_master=dl_master
        )
        by_id = {r["player_id"]: r["position_played"] for r in rows}
        assert by_id == {1: "iDL", 2: "EDGE", 3: "EDGE"}

    def test_master_without_pff_column_keeps_roster_label(
        self,
        dl_rosters: pd.DataFrame,
        dl_master: pd.DataFrame,
        team_lookup: dict[str, int],
    ) -> None:
        gsis_to_id = {"BROWN": 1, "MUHAMMAD": 2, "GARRETT": 3}
        rows, _, _ = _transform_player_seasons(
            dl_rosters, 2025, team_lookup, gsis_to_id,
            df_players_master=dl_master.drop(columns="pff_position"),
        )
        assert {r["position_played"] for r in rows} == {"EDGE"}
