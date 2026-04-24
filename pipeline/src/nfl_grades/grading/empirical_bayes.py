"""Empirical Bayes shrinkage toward a (league-volume-weighted) mean.

For a per-player component with sample size ``n``:

    shrunk = (n * raw + k * mu) / (n + k)

Interpretation:
    - ``mu`` is a prior mean (league average).
    - ``k`` is a pseudo-sample size representing confidence in the prior.
    - A player with ``n >> k`` barely moves (their data dominates).
    - A player with ``n << k`` is pulled hard toward the prior.

ADR-0013 specifies ``mu`` as the **volume-weighted** league mean (a
single pass attempt from a backup counts 1 toward the mean, just like a
pass attempt from a starter), rather than the simple per-player mean.
This is the standard recipe because we're shrinking per-play rates.

See ``shrink_series`` for the typical ``pandas`` flow.
"""

from __future__ import annotations

import pandas as pd


def volume_weighted_mean(raw: pd.Series, n: pd.Series) -> float:
    """Volume-weighted league mean of ``raw`` with weights ``n``.

    mu = sum(raw_i * n_i) / sum(n_i), skipping NaN-valued rows.
    """
    mask = raw.notna() & n.notna() & (n > 0)
    if not mask.any():
        return 0.0
    num = (raw[mask] * n[mask]).sum()
    den = n[mask].sum()
    return float(num / den) if den > 0 else 0.0


def shrink_series(raw: pd.Series, n: pd.Series, k: float, mu: float | None = None) -> pd.Series:
    """Return a Series of shrunk values, same index as ``raw``.

    Args:
        raw: per-player raw component value.
        n:   per-player sample size (dropbacks, attempts, etc.).
        k:   shrinkage strength (pseudo-sample size for the prior).
        mu:  prior mean. If None, computed as ``volume_weighted_mean(raw, n)``.

    NaN values in ``raw`` are preserved as NaN (shrinking a missing
    metric is meaningless). Rows with ``n = 0`` degenerate to the prior
    mean (0 * raw + k * mu) / (0 + k) = mu.
    """
    if mu is None:
        mu = volume_weighted_mean(raw, n)
    # Preserve NaN inputs (no data -> no shrunk value).
    nan_mask = raw.isna()
    n_safe = n.fillna(0)
    shrunk = (n_safe * raw.fillna(0) + k * mu) / (n_safe + k)
    shrunk[nan_mask] = float("nan")
    return shrunk
