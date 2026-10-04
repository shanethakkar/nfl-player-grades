"""Tests for team grading (ADR-0026): per-position aggregation into
Offense / Defense / ST and Overall."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.team import compute_grades
from nfl_grades.grading.weights import TEAM_V1_PHASE_WEIGHTS

OFFENSE = ["QB", "RB", "WR", "TE"]
DEFENSE = ["EDGE", "iDL", "LB", "CB", "S"]
SPECIAL = ["K", "P"]


def _players(positions: list[str], seed: int = 0) -> pd.DataFrame:
    """One graded player per (team, position) for 32 teams."""
    rng = np.random.default_rng(seed)
    rows = [
        {
            "team_id": team_id,
            "position": pos,
            "player_id": team_id * 100 + i,
            "composite_z": float(rng.normal()),
            "composite_grade": 50.0,
            "snaps": 500,
        }
        for team_id in range(1, 33)
        for i, pos in enumerate(positions)
    ]
    return pd.DataFrame(rows)


def _ol(seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"team_id": range(1, 33), "ol_z": rng.normal(size=32), "ol_grade": 50.0}
    )


def _standardize(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=1)


class TestMissingPhase:
    def test_team_grades_exist_before_kickers_and_punters_are_graded(self) -> None:
        grades, _ = compute_grades(_players(OFFENSE + DEFENSE), _ol())
        assert grades["st_grade"].isna().all()
        assert grades[["overall_grade", "offense_grade", "defense_grade"]].notna().all().all()

    def test_overall_renormalizes_over_the_phases_present(self) -> None:
        grades, _ = compute_grades(_players(OFFENSE + DEFENSE), _ol())
        w_off, w_def = TEAM_V1_PHASE_WEIGHTS["offense"], TEAM_V1_PHASE_WEIGHTS["defense"]
        expected = _standardize(
            (w_off * grades["offense_z"] + w_def * grades["defense_z"]) / (w_off + w_def)
        )
        assert grades["overall_z"].to_numpy() == pytest.approx(expected.to_numpy())

    def test_full_season_overall_uses_every_phase(self) -> None:
        grades, _ = compute_grades(_players(OFFENSE + DEFENSE + SPECIAL), _ol())
        assert grades["st_grade"].notna().all()
        expected = _standardize(
            sum(grades[f"{phase}_z"] * w for phase, w in TEAM_V1_PHASE_WEIGHTS.items())
        )
        assert grades["overall_z"].to_numpy() == pytest.approx(expected.to_numpy())
