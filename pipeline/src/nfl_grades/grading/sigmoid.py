"""Composite z-score -> 0..100 grade via a tuned logistic."""

from __future__ import annotations

import numpy as np

DEFAULT_K = 1.15      # slope; chosen so z=+2 maps to ~90
DEFAULT_Z0 = 0.0      # center; z=0 -> 50


def to_grade(
    z: np.ndarray | float,
    k: float = DEFAULT_K,
    z0: float = DEFAULT_Z0,
) -> np.ndarray | float:
    """Map composite z-score(s) to a 0..100 grade.

    grade = 100 / (1 + exp(-k * (z - z0)))

    Tuned so that:
        z =  0  -> 50
        z = +2  -> ~90
        z = -2  -> ~10
    """
    return 100.0 / (1.0 + np.exp(-k * (np.asarray(z) - z0)))
