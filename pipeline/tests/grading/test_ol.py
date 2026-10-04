"""Tests for OL (team-level) grading, ADR-0025."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_grades.grading.ol import compute_grades
from nfl_grades.grading.progress import SeasonProgress


def _synth_teams(n_games: float, seed: int = 0) -> pd.DataFrame:
    """32 teams, each with ~62 plays a game (about 1,050 a season)."""
    rng = np.random.default_rng(seed)
    rushes = rng.integers(24, 30, size=32) * n_games
    dropbacks = rng.integers(33, 38, size=32) * n_games
    return pd.DataFrame(
        {
            "team_id": range(1, 33),
            "rushes": rushes.astype(int),
            "dropbacks": dropbacks.astype(int),
            "ybc_per_carry": rng.normal(1.6, 0.25, size=32),
            "pressure_proxy_per_dropback": rng.normal(0.14, 0.025, size=32),
        }
    )


class TestConfidence:
    def test_completed_season_has_full_confidence(self) -> None:
        graded = compute_grades(_synth_teams(17), 2024)
        assert (graded["confidence"] == 1.0).all()

    def test_provisional_confidence_reflects_volume_to_date(self) -> None:
        # Week 4 with a team on bye: it has three games of volume against a
        # four-game expectation.
        teams = _synth_teams(4)
        teams.loc[0, ["rushes", "dropbacks"]] = teams.loc[0, ["rushes", "dropbacks"]] * 3 // 4
        graded = compute_grades(teams, 2026, progress=SeasonProgress(through_week=4, games=4.0))
        assert graded.loc[0, "confidence"] < 0.9
        assert (graded.loc[1:, "confidence"] > 0.9).all()
        assert (graded["confidence"] <= 1.0).all()
