"""Tests for the shared scoring step (Component z-scores -> Composite,
Grade, percentile) used by every position grader, preview and regrade."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.scoring import score


def _all_qualified(z: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=z.index)


class TestComposite:
    def test_composite_is_weighted_sum_normalized_by_weight_magnitude(self) -> None:
        z = pd.DataFrame({"a": [1.0, 0.0, -1.0], "b": [0.0, 2.0, -2.0]})
        out = score(z, {"a": 1.0, "b": 1.0}, _all_qualified(z))
        assert out["composite_z"].tolist() == pytest.approx([0.5, 1.0, -1.5])

    def test_negative_weight_counts_toward_magnitude(self) -> None:
        # |0.75| + |-0.25| = 1.0, so composite = 0.75*a - 0.25*b.
        z = pd.DataFrame({"a": [2.0], "b": [2.0]})
        out = score(z, {"a": 0.75, "b": -0.25}, _all_qualified(z))
        assert out["composite_z"].iloc[0] == pytest.approx(1.0)

    def test_grade_is_sigmoid_of_composite(self) -> None:
        # ADR-0008: z=0 -> 50, z=+2 -> ~90.9, z=-2 -> ~9.1.
        z = pd.DataFrame({"a": [0.0, 2.0, -2.0]})
        out = score(z, {"a": 1.0}, _all_qualified(z))
        assert out["grade"].tolist() == pytest.approx([50.0, 90.887, 9.113], abs=1e-3)

    def test_output_is_indexed_like_input(self) -> None:
        z = pd.DataFrame({"a": [1.0, -1.0]}, index=[101, 202])
        out = score(z, {"a": 1.0}, _all_qualified(z))
        assert list(out.index) == [101, 202]


class TestPercentile:
    def test_percentile_ranks_against_qualified_cohort_only(self) -> None:
        # Four qualified players and one unqualified backup who sits between
        # the 2nd and 3rd qualified players.
        z = pd.DataFrame({"a": [-2.0, -1.0, 1.0, 2.0, 0.0]})
        qualified = pd.Series([True, True, True, True, False])
        out = score(z, {"a": 1.0}, qualified)
        assert out["percentile"].tolist() == pytest.approx([25.0, 50.0, 75.0, 100.0, 50.0])

    def test_fewer_than_two_qualified_gives_percentile_50(self) -> None:
        z = pd.DataFrame({"a": [-1.0, 1.0, 3.0]})
        qualified = pd.Series([False, True, False])
        out = score(z, {"a": 1.0}, qualified)
        assert out["percentile"].tolist() == [50.0, 50.0, 50.0]


class TestMissingComponents:
    def test_neutral_treats_a_missing_component_as_league_average(self) -> None:
        z = pd.DataFrame({"a": [2.0, 2.0], "b": [float("nan"), 0.0]})
        out = score(z, {"a": 0.5, "b": 0.5}, _all_qualified(z), missing="neutral")
        assert out["composite_z"].tolist() == pytest.approx([1.0, 1.0])

    def test_neutral_is_the_default(self) -> None:
        z = pd.DataFrame({"a": [2.0], "b": [float("nan")]})
        out = score(z, {"a": 0.5, "b": 0.5}, _all_qualified(z))
        assert out["composite_z"].iloc[0] == pytest.approx(1.0)

    def test_ungraded_leaves_a_player_with_a_missing_component_ungraded(self) -> None:
        z = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [float("nan"), 0.0, 0.0]})
        out = score(z, {"a": 0.5, "b": 0.5}, _all_qualified(z), missing="ungraded")
        assert np.isnan(out.loc[0, "composite_z"])
        assert np.isnan(out.loc[0, "grade"])
        assert np.isnan(out.loc[0, "percentile"])
        # The ungraded player doesn't occupy a slot in the percentile cohort.
        assert out.loc[1:, "percentile"].tolist() == pytest.approx([50.0, 100.0])

    def test_component_absent_from_the_frame_counts_as_missing(self) -> None:
        z = pd.DataFrame({"a": [2.0]})
        out = score(z, {"a": 0.5, "b": 0.5}, _all_qualified(z))
        assert out["composite_z"].iloc[0] == pytest.approx(1.0)


class TestPerPlayerFormula:
    def test_each_player_is_scored_with_their_own_formula(self) -> None:
        # TE blocking role: its Formula omits "earn", so a big earn z-score
        # doesn't move a blocking TE's Composite.
        full = {"epa": 0.5, "earn": 0.5}
        blocking = {"epa": 1.0}
        z = pd.DataFrame({"epa": [1.0, 1.0], "earn": [3.0, 3.0]}, index=[7, 8])
        formulas = pd.Series([full, blocking], index=[7, 8])
        out = score(z, formulas, _all_qualified(z))
        assert out.loc[7, "composite_z"] == pytest.approx(2.0)
        assert out.loc[8, "composite_z"] == pytest.approx(1.0)

    def test_percentile_pools_players_across_formulas(self) -> None:
        z = pd.DataFrame({"epa": [1.0, 2.0], "earn": [0.0, 0.0]})
        formulas = pd.Series([{"epa": 1.0, "earn": 1.0}, {"epa": 1.0}])
        out = score(z, formulas, _all_qualified(z))
        assert out["percentile"].tolist() == pytest.approx([50.0, 100.0])
