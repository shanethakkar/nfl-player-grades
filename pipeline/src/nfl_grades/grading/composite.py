"""Combine per-component z-scores into a single composite z-score.

The composite is a weighted sum with weights normalized by magnitude over
the components each player actually has:

    composite_z[i] = sum_{c present} w[c] * z[i, c] / sum_{c present} |w[c]|

A missing component (NaN) drops out and the remaining weights are
renormalized (ADR-0028), instead of zero-filling it (which pulls the
player toward 50) or leaving the player ungraded. A player with no
components at all gets NaN.
"""

from __future__ import annotations

import pandas as pd


def combine(component_z: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Return the magnitude-normalized weighted-sum composite z-score per player.

    Args:
        component_z: wide DataFrame indexed by player with one column
            per component name. NaN means the player lacks that component.
        weights: ``{component_name: signed weight}``.

    Raises:
        KeyError: if any weight references a column not in ``component_z``.
        ValueError: if the sum of weights is zero.
    """
    missing = set(weights) - set(component_z.columns)
    if missing:
        raise KeyError(f"weights reference missing columns: {sorted(missing)}")
    # Normalize by total magnitude so signed weights (e.g. a negative
    # weight on an "is-bad" component like fumble rate) contribute the
    # designed share of the composite.
    if sum(abs(w) for w in weights.values()) <= 0:
        raise ValueError(f"weights must have positive total magnitude; got {weights}")

    weighted_sum = pd.Series(0.0, index=component_z.index)
    present_magnitude = pd.Series(0.0, index=component_z.index)
    for col, w in weights.items():
        present = component_z[col].notna()
        weighted_sum += w * component_z[col].fillna(0.0)
        present_magnitude += abs(w) * present
    return weighted_sum / present_magnitude.where(present_magnitude > 0)
