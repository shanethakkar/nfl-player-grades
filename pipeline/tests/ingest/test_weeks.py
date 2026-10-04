"""Tests for regular-season week helpers used by the weekly refresh."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.ingest._weeks import (
    SourceLagError,
    cap_regular_season,
    check_alignment,
    last_completed_week,
    max_regular_season_week,
)


def _schedule(results_by_week: dict[int, tuple[int, int]]) -> pd.DataFrame:
    """REG schedule: {week: (games_played, games_scheduled)}, plus one
    unplayed playoff game."""
    rows = []
    for week, (played, scheduled) in results_by_week.items():
        for i in range(scheduled):
            rows.append({"game_type": "REG", "week": week, "result": 3.0 if i < played else np.nan})
    rows.append({"game_type": "WC", "week": 19, "result": np.nan})
    return pd.DataFrame(rows)


class TestLastCompletedWeek:
    def test_week_in_progress_is_not_complete(self) -> None:
        schedule = _schedule({1: (16, 16), 2: (16, 16), 3: (16, 16), 4: (10, 16), 5: (0, 15)})
        assert last_completed_week(schedule) == 3

    def test_no_week_complete_before_the_season(self) -> None:
        assert last_completed_week(_schedule({1: (0, 16), 2: (0, 16)})) is None

    def test_completed_season(self) -> None:
        assert last_completed_week(_schedule({w: (16, 16) for w in range(1, 19)})) == 18

    def test_cancelled_game_does_not_hold_the_week_open(self) -> None:
        # BUF-CIN 2022 week 17 was never completed; the schedule records
        # no result. Later weeks being complete settles it.
        schedule = _schedule({16: (16, 16), 17: (15, 16), 18: (16, 16)})
        assert last_completed_week(schedule) == 18


class TestMaxRegularSeasonWeek:
    def test_uses_season_type_and_ignores_the_ngs_season_summary(self) -> None:
        df = pd.DataFrame(
            {"season_type": ["REG", "REG", "REG", "POST"], "week": [0, 2, 3, 19]}
        )
        assert max_regular_season_week(df, 2026) == 3

    def test_uses_game_type(self) -> None:
        df = pd.DataFrame({"game_type": ["REG", "WC"], "week": [4, 19]})
        assert max_regular_season_week(df, 2026) == 4

    def test_without_a_type_column_weeks_past_the_final_week_are_postseason(self) -> None:
        df = pd.DataFrame({"week": [17, 18, 19]})
        assert max_regular_season_week(df, 2025) == 18
        assert max_regular_season_week(df, 2019) == 17

    def test_empty_source_has_no_week(self) -> None:
        assert max_regular_season_week(pd.DataFrame({"week": []}), 2026) is None


class TestCapRegularSeason:
    def test_drops_regular_season_weeks_after_the_cap_only(self) -> None:
        df = pd.DataFrame(
            {"season_type": ["REG", "REG", "REG", "POST"], "week": [3, 4, 5, 19]}
        )
        capped = cap_regular_season(df, 2026, 4)
        assert capped["week"].tolist() == [3, 4, 19]

    def test_source_without_a_week_column_is_unchanged(self) -> None:
        df = pd.DataFrame({"team": ["BUF"]})
        assert cap_regular_season(df, 2026, 4).equals(df)


class TestCheckAlignment:
    def test_aligned_sources_pass(self) -> None:
        check_alignment({"pbp": 3, "ngs_passing": 3}, expected_week=3)

    def test_lagging_source_fails_and_is_named(self) -> None:
        with pytest.raises(SourceLagError, match="ngs_passing.*2"):
            check_alignment({"pbp": 3, "ngs_passing": 2}, expected_week=3)

    def test_source_with_no_rows_fails(self) -> None:
        with pytest.raises(SourceLagError, match="ftn"):
            check_alignment({"pbp": 3, "ftn": None}, expected_week=3)
