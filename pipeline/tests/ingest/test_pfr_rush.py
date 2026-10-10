"""Tests for the PFR rush ingest's weekly aggregation."""

from __future__ import annotations

import pandas as pd

from nfl_grades.ingest.pfr_rush import _aggregate_pfr, _build_rows


def _raw(rows: list[dict]) -> pd.DataFrame:
    base = {
        "game_type": "REG",
        "carries": 10.0,
        "rushing_yards_after_contact": 20.0,
        "rushing_yards_before_contact": 15.0,
        "rushing_broken_tackles": 1.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


class TestAggregatePfr:
    def test_one_row_per_player_and_week(self) -> None:
        raw = _raw(
            [
                {"pfr_player_id": "A", "week": 1, "carries": 12.0},
                {"pfr_player_id": "A", "week": 2, "carries": 8.0},
                {"pfr_player_id": "B", "week": 1, "carries": 5.0},
            ]
        )
        agg = _aggregate_pfr(raw, 2024).set_index(["pfr_player_id", "week"])
        assert len(agg) == 3
        assert agg.loc[("A", 1), "carries"] == 12
        assert agg.loc[("A", 2), "carries"] == 8

    def test_drops_postseason_rows(self) -> None:
        raw = _raw(
            [
                {"pfr_player_id": "A", "week": 18},
                {"pfr_player_id": "A", "week": 19, "game_type": "WC"},
            ]
        )
        assert _aggregate_pfr(raw, 2024)["week"].tolist() == [18]

    def test_weeks_sum_to_the_season_totals(self) -> None:
        raw = _raw(
            [
                {"pfr_player_id": "A", "week": w, "rushing_yards_after_contact": float(w)}
                for w in range(1, 6)
            ]
        )
        agg = _aggregate_pfr(raw, 2024)
        assert agg["yards_after_contact"].sum() == 15
        assert agg["carries"].sum() == 50


class TestBuildRows:
    def test_rows_carry_the_week_and_skip_non_rbs(self) -> None:
        agg = _aggregate_pfr(
            _raw(
                [
                    {"pfr_player_id": "A", "week": 3},
                    {"pfr_player_id": "Q", "week": 3},
                ]
            ),
            2024,
        )
        rows, no_match, not_rb = _build_rows(agg, 2024, {"A": (1, "RB"), "Q": (2, "QB")})
        assert [(r["player_id"], r["week"]) for r in rows] == [(1, 3)]
        assert (no_match, not_rb) == (0, 1)
