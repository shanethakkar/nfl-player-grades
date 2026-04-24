"""Tests for the zscore helper."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading.zscore import zscore


class TestZScore:
    def test_basic_mean_sd(self) -> None:
        s = pd.Series([0.0, 1.0, 2.0, 3.0, 4.0])
        z = zscore(s)
        # Sample SD (ddof=1) of 0..4 is sqrt(2.5); mean is 2.
        expected_sd = np.sqrt(2.5)
        assert z.iloc[0] == pytest.approx((0 - 2) / expected_sd)
        assert z.iloc[2] == pytest.approx(0.0)    # mean
        # Mean should be ~0, SD should be 1.
        assert z.mean() == pytest.approx(0.0, abs=1e-12)
        assert z.std(ddof=1) == pytest.approx(1.0)

    def test_nan_stays_nan(self) -> None:
        s = pd.Series([1.0, 2.0, float("nan"), 4.0])
        z = zscore(s)
        assert np.isnan(z.iloc[2])
        assert not np.isnan(z.iloc[0])

    def test_qualified_mask_shapes_distribution(self) -> None:
        # Qualified cohort: [0, 1, 2]. Mean=1, SD=1.
        # Unqualified outlier: 100 -> should z-score to (100-1)/1 = 99.
        s = pd.Series([0.0, 1.0, 2.0, 100.0])
        mask = pd.Series([True, True, True, False])
        z = zscore(s, qualified_mask=mask)
        assert z.iloc[3] == pytest.approx(99.0)
        # Qualified row at index 1 should z-score to 0 (it is the mean).
        assert z.iloc[1] == pytest.approx(0.0)

    def test_constant_column_returns_zeros(self) -> None:
        # SD = 0 -> fallback to zeros so downstream math doesn't explode.
        s = pd.Series([5.0, 5.0, 5.0])
        z = zscore(s)
        assert (z == 0.0).all()

    def test_too_few_qualified_returns_zeros(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        mask = pd.Series([True, False, False])
        z = zscore(s, qualified_mask=mask)
        # Only 1 qualified -> can't compute SD -> zeros.
        assert (z == 0.0).all()
