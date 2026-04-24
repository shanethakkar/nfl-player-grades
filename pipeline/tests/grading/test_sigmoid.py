"""Smoke tests for the sigmoid grade mapping."""

from __future__ import annotations

import numpy as np

from nfl_grades.grading.sigmoid import to_grade


def test_zero_maps_to_fifty():
    assert to_grade(0.0) == 50.0


def test_bounds():
    grades = to_grade(np.array([-10.0, 10.0]))
    assert 0.0 <= grades[0] < 1.0
    assert 99.0 < grades[1] <= 100.0


def test_plus_two_is_roughly_ninety():
    g = float(to_grade(2.0))
    assert 88.0 <= g <= 93.0


def test_monotonic(rng):
    zs = np.sort(rng.normal(size=50))
    grades = to_grade(zs)
    assert np.all(np.diff(grades) >= 0)
