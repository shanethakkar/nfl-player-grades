"""Tests for empirical-bayes shrinkage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.empirical_bayes import shrink_series, volume_weighted_mean


class TestVolumeWeightedMean:
    def test_basic(self) -> None:
        raw = pd.Series([0.1, 0.2, 0.3])
        n = pd.Series([100, 200, 300])
        # mu = (0.1*100 + 0.2*200 + 0.3*300) / 600 = 140/600 = 0.2333
        assert volume_weighted_mean(raw, n) == pytest.approx(140 / 600)

    def test_skips_nans(self) -> None:
        raw = pd.Series([0.1, float("nan"), 0.3])
        n = pd.Series([100, 200, 300])
        # Only rows 0 and 2 count.
        assert volume_weighted_mean(raw, n) == pytest.approx((0.1 * 100 + 0.3 * 300) / (100 + 300))

    def test_all_nan_returns_zero(self) -> None:
        assert volume_weighted_mean(pd.Series([float("nan")] * 3), pd.Series([1, 1, 1])) == 0.0

    def test_zero_weights_returns_zero(self) -> None:
        assert volume_weighted_mean(pd.Series([0.1, 0.2]), pd.Series([0, 0])) == 0.0


class TestShrinkSeries:
    def test_high_n_barely_moves(self) -> None:
        raw = pd.Series([1.0])
        n = pd.Series([10000])
        # mu is raw's volume-weighted mean = 1.0, so shrinkage is a no-op anyway.
        # Use explicit mu to test behavior.
        out = shrink_series(raw, n, k=100, mu=0.0)
        # shrunk = (10000 * 1 + 100 * 0) / 10100 = 0.990...
        assert out.iloc[0] == pytest.approx(10000 / 10100)

    def test_low_n_pulled_hard(self) -> None:
        raw = pd.Series([1.0])
        n = pd.Series([10])
        out = shrink_series(raw, n, k=100, mu=0.0)
        # shrunk = (10 * 1 + 100 * 0) / 110 ≈ 0.0909
        assert out.iloc[0] == pytest.approx(10 / 110)

    def test_n_equals_k_halfway(self) -> None:
        raw = pd.Series([1.0])
        n = pd.Series([100])
        out = shrink_series(raw, n, k=100, mu=0.0)
        # (100 * 1 + 100 * 0) / 200 = 0.5
        assert out.iloc[0] == pytest.approx(0.5)

    def test_zero_n_degenerates_to_prior(self) -> None:
        raw = pd.Series([1.0])
        n = pd.Series([0])
        out = shrink_series(raw, n, k=100, mu=0.5)
        assert out.iloc[0] == pytest.approx(0.5)

    def test_nan_raw_stays_nan(self) -> None:
        raw = pd.Series([float("nan"), 1.0])
        n = pd.Series([50, 50])
        out = shrink_series(raw, n, k=100, mu=0.0)
        assert np.isnan(out.iloc[0])
        assert not np.isnan(out.iloc[1])

    def test_default_mu_uses_volume_weighted(self) -> None:
        # Two rows; their volume-weighted mean is 0.4. Shrinkage with
        # n=k should produce 0.5 * raw + 0.5 * mu for each row.
        raw = pd.Series([0.1, 0.5])
        n = pd.Series([100, 100])
        out = shrink_series(raw, n, k=100)  # mu defaults to vwm = 0.3
        expected_mu = (0.1 * 100 + 0.5 * 100) / 200  # 0.3
        assert out.iloc[0] == pytest.approx(0.5 * 0.1 + 0.5 * expected_mu)
        assert out.iloc[1] == pytest.approx(0.5 * 0.5 + 0.5 * expected_mu)
