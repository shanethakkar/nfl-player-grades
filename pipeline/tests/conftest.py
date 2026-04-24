"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def rng():
    """Deterministic numpy RNG for reproducible tests."""
    import numpy as np

    return np.random.default_rng(42)
