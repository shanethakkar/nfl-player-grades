"""Tests for the FTN receiving ingest's weekly aggregation."""

from __future__ import annotations

import pandas as pd

from nfl_grades.ingest.ftn_receiving import _aggregate


def _pbp(rows: list[dict]) -> pd.DataFrame:
    base = {"season_type": "REG", "game_id": "2024_01_A_B"}
    return pd.DataFrame([{**base, **r} for r in rows])


def _ftn(rows: list[dict]) -> pd.DataFrame:
    base = {
        "nflverse_game_id": "2024_01_A_B",
        "is_catchable_ball": True,
        "is_drop": False,
        "is_contested_ball": False,
        "is_created_reception": False,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


class TestAggregate:
    def test_one_row_per_receiver_and_week(self) -> None:
        pbp = _pbp(
            [
                {"play_id": 1, "week": 1, "receiver_player_id": "R1"},
                {"play_id": 2, "week": 1, "receiver_player_id": "R1"},
                {"play_id": 3, "week": 2, "receiver_player_id": "R1", "game_id": "g2"},
            ]
        )
        ftn = _ftn(
            [
                {"nflverse_play_id": 1, "is_drop": True},
                {"nflverse_play_id": 2},
                {"nflverse_play_id": 3, "nflverse_game_id": "g2", "is_catchable_ball": False},
            ]
        )
        agg = _aggregate(pbp, ftn).set_index(["gsis_id", "week"])
        assert agg.loc[("R1", 1), ["catchable_balls", "drops"]].tolist() == [2, 1]
        assert agg.loc[("R1", 2), ["catchable_balls", "drops"]].tolist() == [0, 0]

    def test_plays_join_on_game_and_play_id(self) -> None:
        # play_id repeats across games; only (game_id, play_id) is unique.
        pbp = _pbp(
            [
                {"play_id": 1, "week": 1, "receiver_player_id": "R1"},
                {"play_id": 1, "week": 1, "receiver_player_id": "R2", "game_id": "g2"},
            ]
        )
        ftn = _ftn([{"nflverse_play_id": 1, "is_drop": True}])
        agg = _aggregate(pbp, ftn)
        assert agg["gsis_id"].tolist() == ["R1"]

    def test_skips_postseason_and_plays_without_a_receiver(self) -> None:
        pbp = _pbp(
            [
                {"play_id": 1, "week": 19, "receiver_player_id": "R1", "season_type": "POST"},
                {"play_id": 2, "week": 1, "receiver_player_id": None},
            ]
        )
        ftn = _ftn([{"nflverse_play_id": 1}, {"nflverse_play_id": 2}])
        assert _aggregate(pbp, ftn).empty
