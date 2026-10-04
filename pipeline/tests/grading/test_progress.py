"""Tests for season progress: how far into a season a grade covers, and how
absolute volume thresholds pro-rate for Provisional grades."""

from __future__ import annotations

import pytest

from nfl_grades.grading.progress import (
    COMPLETE,
    FULL_SEASON_GAMES,
    MIN_PRORATE_GAMES,
    SeasonProgress,
    from_plays,
)


class TestSeasonProgress:
    def test_complete_season_leaves_thresholds_unchanged(self) -> None:
        assert not COMPLETE.is_provisional
        assert COMPLETE.through_week is None
        assert COMPLETE.scale(200) == 200

    def test_provisional_thresholds_scale_by_games_over_17(self) -> None:
        progress = SeasonProgress(through_week=6, games=5.5)
        assert progress.is_provisional
        assert progress.scale(200) == pytest.approx(200 * 5.5 / FULL_SEASON_GAMES)

    def test_scaling_has_a_floor(self) -> None:
        week_one = SeasonProgress(through_week=1, games=1.0)
        assert week_one.scale(170) == pytest.approx(170 * MIN_PRORATE_GAMES / FULL_SEASON_GAMES)

    def test_scaling_never_exceeds_the_full_season_threshold(self) -> None:
        assert SeasonProgress(through_week=17, games=17.0).scale(200) == pytest.approx(200)


class TestFromPlays:
    def test_season_through_its_final_week_is_complete(self) -> None:
        assert from_plays(season=2024, through_week=18, games=17.0) == COMPLETE
        # 2016-2020 had 17 regular-season weeks.
        assert from_plays(season=2019, through_week=17, games=16.0) == COMPLETE

    def test_season_in_progress_is_provisional_through_its_last_week(self) -> None:
        assert from_plays(season=2026, through_week=3, games=3.0) == SeasonProgress(
            through_week=3, games=3.0
        )

    def test_season_with_no_plays_is_treated_as_complete(self) -> None:
        # Graders find no features and write nothing either way.
        assert from_plays(season=2027, through_week=None, games=None) == COMPLETE
