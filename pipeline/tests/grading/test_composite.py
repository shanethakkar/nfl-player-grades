"""Tests for the weighted-composite combiner."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.composite import combine


class TestCombine:
    def test_normalized_weighted_sum(self) -> None:
        df = pd.DataFrame(
            {
                "a": [1.0, 0.0, -1.0],
                "b": [0.0, 2.0, -2.0],
            }
        )
        # weights [1, 1] -> average.
        out = combine(df, {"a": 1.0, "b": 1.0})
        assert out.iloc[0] == pytest.approx(0.5)
        assert out.iloc[1] == pytest.approx(1.0)
        assert out.iloc[2] == pytest.approx(-1.5)

    def test_weights_are_renormalized(self) -> None:
        df = pd.DataFrame({"a": [1.0], "b": [3.0]})
        # 0.25/0.75 -> same ratios as 1/3.
        out_a = combine(df, {"a": 0.25, "b": 0.75})
        out_b = combine(df, {"a": 1.0, "b": 3.0})
        assert out_a.iloc[0] == pytest.approx(out_b.iloc[0])

    def test_nan_in_component_propagates(self) -> None:
        df = pd.DataFrame(
            {
                "a": [1.0, 2.0],
                "b": [float("nan"), 4.0],
            }
        )
        out = combine(df, {"a": 0.5, "b": 0.5})
        assert np.isnan(out.iloc[0])
        assert out.iloc[1] == pytest.approx(3.0)

    def test_missing_column_raises(self) -> None:
        df = pd.DataFrame({"a": [1.0]})
        with pytest.raises(KeyError):
            combine(df, {"a": 0.5, "b": 0.5})

    def test_zero_weight_total_raises(self) -> None:
        df = pd.DataFrame({"a": [1.0]})
        with pytest.raises(ValueError):
            combine(df, {"a": 0.0})

    def test_qb_v1_weights_example(self) -> None:
        """ADR-0013 weights: 0.50 / 0.25 / 0.25. A QB at z=+1 on all three
        components should have composite_z = 1.0."""
        df = pd.DataFrame(
            {
                "qb_epa_per_dropback": [1.0],
                "qb_cpoe": [1.0],
                "qb_success_rate": [1.0],
            }
        )
        out = combine(df, {"qb_epa_per_dropback": 0.50, "qb_cpoe": 0.25, "qb_success_rate": 0.25})
        assert out.iloc[0] == pytest.approx(1.0)

    def test_signed_weights_normalize_by_magnitude(self) -> None:
        """ADR-0014: RB v1 has a negative weight on fumble rate. A player
        at z=+1 on every component (including fumble rate) should have
        composite_z = (sum of signed weights) / (sum of magnitudes), NOT
        1.0 (that would be what happens if the combiner normalized by
        signed total)."""
        df = pd.DataFrame({"good": [1.0], "bad": [1.0]})
        # Signed weights: +0.8 good, -0.2 bad. Magnitudes sum to 1.0.
        # Expected composite = 0.8*1 + (-0.2)*1 = 0.6.
        out = combine(df, {"good": 0.8, "bad": -0.2})
        assert out.iloc[0] == pytest.approx(0.6)

    def test_signed_weights_negative_component_penalizes(self) -> None:
        """A 'bad' component (negative weight) with a positive z-score
        should pull the composite down relative to a player with the
        same 'good' z-score but a lower 'bad' z-score."""
        df = pd.DataFrame(
            {
                "good": [1.0, 1.0],
                "bad": [2.0, 0.0],  # first player has more "bad"
            }
        )
        out = combine(df, {"good": 0.8, "bad": -0.2})
        # Player with higher bad z should grade lower.
        assert out.iloc[0] < out.iloc[1]

    def test_wr_v1_weights_example(self) -> None:
        """ADR-0015: WR v1 weights are 0.35/0.27/0.10/0.10/0.08/-0.05.
        Sum of magnitudes = 0.95. A WR at z=+1 on every component
        (including fumble rate) should have:

            composite_z = (0.35+0.27+0.10+0.10+0.08-0.05) / 0.95
                        = 0.85 / 0.95
                        ≈ 0.8947

        This locks in both the weight values and the magnitude-
        normalization invariant for the WR position — if a future
        refactor accidentally switches to signed-sum normalization
        (0.85 / 0.85 = 1.0), this test fires.
        """
        from nfl_grades.grading.weights import WR_V1_WEIGHTS

        components = list(WR_V1_WEIGHTS.keys())
        df = pd.DataFrame({c: [1.0] for c in components})
        out = combine(df, WR_V1_WEIGHTS)

        expected = sum(WR_V1_WEIGHTS.values()) / sum(abs(w) for w in WR_V1_WEIGHTS.values())
        assert out.iloc[0] == pytest.approx(expected)
        assert out.iloc[0] == pytest.approx(0.8947, abs=1e-4)

    def test_te_v1_weights_example(self) -> None:
        """ADR-0016: TE tier-1 = WR-aligned with 7% separation. |w| = 0.92."""
        from nfl_grades.grading.weights import TE_V1_WEIGHTS

        components = list(TE_V1_WEIGHTS.keys())
        df = pd.DataFrame({c: [1.0] for c in components})
        out = combine(df, TE_V1_WEIGHTS)
        expected = sum(TE_V1_WEIGHTS.values()) / sum(abs(w) for w in TE_V1_WEIGHTS.values())
        assert out.iloc[0] == pytest.approx(expected)
        # 0.35+0.27+0.07+0.10+0.08-0.05 = 0.82; |w| = 0.92
        assert out.iloc[0] == pytest.approx(0.82 / 0.92, abs=1e-6)

    def test_te_v1_blocking_weights_example(self) -> None:
        """Blocking TE: earn omitted, redistributed to EPA/YAC. Magnitude-
        preserving, so |w| = 0.92 and signed sum = 0.82 are unchanged from
        tier-1 (ADR-0016 §Tier 2)."""
        from nfl_grades.grading.weights import TE_V1_BLOCKING_WEIGHTS

        comp = list(TE_V1_BLOCKING_WEIGHTS.keys())
        df = pd.DataFrame({c: [1.0] for c in comp})
        out = combine(df, TE_V1_BLOCKING_WEIGHTS)
        expected = sum(TE_V1_BLOCKING_WEIGHTS.values()) / sum(
            abs(w) for w in TE_V1_BLOCKING_WEIGHTS.values()
        )
        assert out.iloc[0] == pytest.approx(expected)
        # 0.406+0.314+0.07+0.08-0.05 = 0.82; |w| = 0.92
        assert out.iloc[0] == pytest.approx(0.82 / 0.92, abs=1e-6)
