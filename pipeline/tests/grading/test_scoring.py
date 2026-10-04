"""Tests for the shared scoring step (Component z-scores -> Composite,
Grade, percentile) used by every position grader, preview and regrade."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.scoring import (
    MIN_QUALIFIED_COHORT,
    InsufficientCohortError,
    pooled_sd,
    score,
)


def _all_qualified(z: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=z.index)


def _score_in_cohort(
    z: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series,
    *,
    composite_sd: float = 1.0,
) -> pd.DataFrame:
    """Score a handful of players inside a filler cohort of league-average
    (z = 0) qualified players, so the minimum cohort is met. The scale is
    pinned with ``composite_sd`` so assertions see the weighted sum itself.
    Returns only the rows of ``z``."""
    filler = pd.DataFrame(0.0, index=range(-MIN_QUALIFIED_COHORT, 0), columns=z.columns)
    padded = pd.concat([filler, z])
    if isinstance(weights, pd.Series):
        weights = pd.concat(
            [pd.Series([weights.iloc[0]] * len(filler), index=filler.index), weights]
        )
    out = score(padded, weights, _all_qualified(padded), composite_sd=composite_sd)
    return out.loc[z.index]


def _synthetic_position(
    n_players: int, correlation: float, rng: np.random.Generator
) -> pd.DataFrame:
    """Three Component z-scores with the given pairwise correlation."""
    cov = np.full((3, 3), correlation) + np.eye(3) * (1 - correlation)
    return pd.DataFrame(
        rng.multivariate_normal(np.zeros(3), cov, size=n_players), columns=["a", "b", "c"]
    )


class TestStandardization:
    def test_composite_has_unit_sd_over_the_qualified_cohort(self) -> None:
        # Two correlated Components: the raw weighted sum has SD well above
        # 1 over the qualified players. Unqualified backups sit far out and
        # must not affect the scale.
        rng = np.random.default_rng(0)
        base = rng.normal(size=40)
        z = pd.DataFrame({"a": base, "b": base + rng.normal(scale=0.3, size=40)})
        z.loc[35:, :] = 6.0
        qualified = pd.Series([True] * 35 + [False] * 5)
        out = score(z, {"a": 0.6, "b": 0.4}, qualified)
        assert out.loc[qualified, "composite_z"].std(ddof=1) == pytest.approx(1.0)

    def test_same_grade_means_same_percentile_whatever_the_component_correlation(self) -> None:
        # ADR-0028: an LB-like Formula (uncorrelated Components, raw composite
        # SD ~0.58) and an iDL-like one (highly correlated, SD ~0.95) must put
        # the same share of players at 90+. Grade 90 is composite z = 1.91,
        # i.e. the ~97th percentile of a normal cohort.
        rng = np.random.default_rng(1)
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        share_90_plus = {}
        for correlation in (0.0, 0.9):
            z = _synthetic_position(20_000, correlation, rng)
            out = score(z, weights, _all_qualified(z))
            share_90_plus[correlation] = (out["grade"] >= 90).mean()
        assert share_90_plus[0.0] == pytest.approx(0.028, abs=0.004)
        assert share_90_plus[0.9] == pytest.approx(0.028, abs=0.004)

    def test_rankings_match_the_unstandardized_composite(self) -> None:
        rng = np.random.default_rng(2)
        z = _synthetic_position(50, 0.3, rng)
        weights = {"a": 0.5, "b": 0.3, "c": -0.2}
        raw = 0.5 * z["a"] + 0.3 * z["b"] - 0.2 * z["c"]
        out = score(z, weights, _all_qualified(z))
        assert out["grade"].rank().tolist() == raw.rank().tolist()

    def test_externally_supplied_sd_is_used_instead_of_the_cohort_sd(self) -> None:
        # Provisional grades: a small in-season cohort borrows the pooled SD
        # from completed seasons. Raw composite 0.5*a + 0.5*b, divided by 0.5.
        z = pd.DataFrame({"a": [1.0, 0.0, -1.0], "b": [0.0, 2.0, -2.0]})
        out = _score_in_cohort(z, {"a": 1.0, "b": 1.0}, composite_sd=0.5)
        assert out["composite_z"].tolist() == pytest.approx([1.0, 2.0, -3.0])


class TestComposite:
    def test_composite_is_weighted_sum_normalized_by_weight_magnitude(self) -> None:
        z = pd.DataFrame({"a": [1.0, 0.0, -1.0], "b": [0.0, 2.0, -2.0]})
        out = _score_in_cohort(z, {"a": 1.0, "b": 1.0})
        assert out["composite_z"].tolist() == pytest.approx([0.5, 1.0, -1.5])

    def test_negative_weight_counts_toward_magnitude(self) -> None:
        # |0.75| + |-0.25| = 1.0, so composite = 0.75*a - 0.25*b.
        z = pd.DataFrame({"a": [2.0], "b": [2.0]})
        out = _score_in_cohort(z, {"a": 0.75, "b": -0.25})
        assert out["composite_z"].iloc[0] == pytest.approx(1.0)

    def test_grade_is_sigmoid_of_composite(self) -> None:
        # ADR-0008: z=0 -> 50, z=+2 -> ~90.9, z=-2 -> ~9.1.
        z = pd.DataFrame({"a": [0.0, 2.0, -2.0]})
        out = _score_in_cohort(z, {"a": 1.0})
        assert out["grade"].tolist() == pytest.approx([50.0, 90.887, 9.113], abs=1e-3)

    def test_output_is_indexed_like_input(self) -> None:
        z = pd.DataFrame(
            {"a": np.linspace(-1, 1, MIN_QUALIFIED_COHORT)},
            index=range(100, 100 + MIN_QUALIFIED_COHORT),
        )
        out = score(z, {"a": 1.0}, _all_qualified(z))
        assert list(out.index) == list(z.index)


class TestPercentile:
    def test_percentile_ranks_against_qualified_cohort_only(self) -> None:
        # Ten qualified players and one unqualified backup who sits between
        # the 5th and 6th qualified players.
        z = pd.DataFrame({"a": [*range(1, 11), 5.5]}, dtype=float)
        qualified = pd.Series([True] * 10 + [False])
        out = score(z, {"a": 1.0}, qualified)
        assert out["percentile"].tolist() == pytest.approx([*range(10, 101, 10), 50.0])


class TestMinimumCohort:
    def test_too_few_qualified_players_raises_instead_of_grading(self) -> None:
        z = pd.DataFrame({"a": np.linspace(-2, 2, 30)})
        n_qualified = MIN_QUALIFIED_COHORT - 1
        qualified = pd.Series([True] * n_qualified + [False] * (30 - n_qualified))
        with pytest.raises(InsufficientCohortError):
            score(z, {"a": 1.0}, qualified)

    def test_minimum_cohort_is_enough(self) -> None:
        z = pd.DataFrame({"a": np.linspace(-2, 2, MIN_QUALIFIED_COHORT)})
        out = score(z, {"a": 1.0}, _all_qualified(z))
        assert out["grade"].notna().all()

    def test_ungraded_qualified_players_do_not_count_toward_the_cohort(self) -> None:
        z = pd.DataFrame({"a": np.linspace(-2, 2, MIN_QUALIFIED_COHORT)})
        z.loc[0, "a"] = float("nan")
        with pytest.raises(InsufficientCohortError):
            score(z, {"a": 1.0}, _all_qualified(z))

    def test_minimum_applies_with_an_external_sd(self) -> None:
        z = pd.DataFrame({"a": [1.0, -1.0]})
        with pytest.raises(InsufficientCohortError):
            score(z, {"a": 1.0}, _all_qualified(z), composite_sd=1.0)


class TestMissingComponents:
    def test_weights_renormalize_over_the_components_a_player_has(self) -> None:
        # Player 0 has no "b": their Composite is "a" alone, not 0.5*a + 0.5*0.
        z = pd.DataFrame({"a": [2.0, 2.0], "b": [float("nan"), 0.0]})
        out = _score_in_cohort(z, {"a": 0.5, "b": 0.5})
        assert out["composite_z"].tolist() == pytest.approx([2.0, 1.0])

    def test_renormalization_uses_weight_magnitude(self) -> None:
        # Missing "a": remaining weights are b=+0.2, c=-0.2, so the
        # Composite is 0.5*b - 0.5*c.
        z = pd.DataFrame({"a": [float("nan")], "b": [2.0], "c": [-2.0]})
        out = _score_in_cohort(z, {"a": 0.6, "b": 0.2, "c": -0.2})
        assert out["composite_z"].iloc[0] == pytest.approx(2.0)

    def test_component_absent_from_the_frame_counts_as_missing(self) -> None:
        z = pd.DataFrame({"a": [2.0]})
        out = _score_in_cohort(z, {"a": 0.5, "b": 0.5})
        assert out["composite_z"].iloc[0] == pytest.approx(2.0)

    def test_player_with_no_components_is_ungraded(self) -> None:
        z = pd.DataFrame({"a": [float("nan"), 1.0], "b": [float("nan"), 0.0]})
        out = _score_in_cohort(z, {"a": 0.5, "b": 0.5})
        assert out.loc[0, ["composite_z", "grade", "percentile"]].isna().all()
        assert out.loc[1, ["composite_z", "grade", "percentile"]].notna().all()


class TestPerPlayerFormula:
    def test_each_player_is_scored_with_their_own_formula(self) -> None:
        # TE blocking role: its Formula omits "earn", so a big earn z-score
        # doesn't move a blocking TE's Composite.
        full = {"epa": 0.5, "earn": 0.5}
        blocking = {"epa": 1.0}
        z = pd.DataFrame({"epa": [1.0, 1.0], "earn": [3.0, 3.0]}, index=[7, 8])
        formulas = pd.Series([full, blocking], index=[7, 8])
        out = _score_in_cohort(z, formulas)
        assert out.loc[7, "composite_z"] == pytest.approx(2.0)
        assert out.loc[8, "composite_z"] == pytest.approx(1.0)

    def test_percentile_pools_players_across_formulas(self) -> None:
        # Ten full-Formula players at 0..0.9, one blocking TE at 0.55: the
        # blocking TE is ranked against the full-Formula players, so beats 6.
        full = {"epa": 1.0, "earn": 1.0}
        blocking = {"epa": 1.0}
        epa = [i / 10 for i in range(10)]
        z = pd.DataFrame({"epa": [*epa, 0.55], "earn": [*epa, 0.0]})
        formulas = pd.Series([full] * 10 + [blocking])
        out = score(z, formulas, _all_qualified(z))
        assert out["percentile"].iloc[-1] == pytest.approx(100 * 7 / 11)


class TestPooledSd:
    def test_pools_spread_within_each_season_not_between_seasons(self) -> None:
        # Two seasons with SD 1 each but very different means: the pooled
        # SD is 1, not the SD of all six values.
        raw = pd.Series([1.0, 2.0, 3.0, 11.0, 12.0, 13.0])
        season = pd.Series([2024, 2024, 2024, 2025, 2025, 2025])
        assert pooled_sd(raw, _all_qualified(raw.to_frame()), season) == pytest.approx(1.0)

    def test_weights_each_season_by_its_degrees_of_freedom(self) -> None:
        # Season A: SD 1 over 3 players (2 df). Season B: SD 2 over 5 (4 df).
        a = pd.Series([1.0, 2.0, 3.0])
        b = pd.Series([0.0, 2.0, 4.0, 2.0 - np.sqrt(2), 2.0 + np.sqrt(2)])
        raw = pd.concat([a, b], ignore_index=True)
        season = pd.Series([1] * 3 + [2] * 5)
        expected = np.sqrt((2 * a.var() + 4 * b.var()) / 6)
        assert pooled_sd(raw, _all_qualified(raw.to_frame()), season) == pytest.approx(expected)

    def test_ignores_unqualified_and_ungraded_players(self) -> None:
        raw = pd.Series([1.0, 2.0, 3.0, 50.0, float("nan")])
        cohort = pd.Series([True, True, True, False, True])
        season = pd.Series([1] * 5)
        assert pooled_sd(raw, cohort, season) == pytest.approx(1.0)

    def test_no_cohort_raises(self) -> None:
        raw = pd.Series([1.0])
        with pytest.raises(InsufficientCohortError):
            pooled_sd(raw, _all_qualified(raw.to_frame()), pd.Series([1]))
