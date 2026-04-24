"""Combine per-component z-scores into a single composite z-score.

The composite is a weighted sum with weights normalized to sum to 1:

    composite_z[i] = sum_c (weights[c] / sum(weights)) * component_z[i, c]

Rows where any required component is NaN get NaN for the composite
(ADR-0013: we don't impute missing components). In the typical QB flow
every qualified QB has a value for every component, so this shouldn't
trigger; unqualified QBs with 0 pass attempts do lack CPOE and will
correctly end up with NaN composites (they're filtered out before
writing to season_grades).
"""

from __future__ import annotations

import pandas as pd


def combine(component_z: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Return the normalized weighted-sum composite z-score per player.

    Args:
        component_z: wide DataFrame indexed by player with one column
            per component name.
        weights: ``{component_name: weight}``. Weights are normalized to
            sum to 1.

    Raises:
        KeyError: if any weight references a column not in ``component_z``.
        ValueError: if the sum of weights is zero.
    """
    missing = set(weights) - set(component_z.columns)
    if missing:
        raise KeyError(f"weights reference missing columns: {sorted(missing)}")
    # Normalize by total magnitude so signed weights (e.g. a negative
    # weight on an "is-bad" component like fumble rate) contribute the
    # designed share of the composite. For all-positive weight sets
    # (like QB v1), sum(abs(w)) == sum(w), so this is a no-op.
    total_magnitude = sum(abs(w) for w in weights.values())
    if total_magnitude <= 0:
        raise ValueError(f"weights must have positive total magnitude; got {total_magnitude}")
    normalized = {c: w / total_magnitude for c, w in weights.items()}

    # Weighted sum; sum() propagates NaN when any input is NaN (min_count=len(weights)
    # would do it explicitly but pandas' default works: NaN * anything = NaN,
    # and sum() skips NaN — which is wrong. So we explicitly use "sum with skipna=False".
    result = pd.Series(0.0, index=component_z.index)
    any_nan = pd.Series(False, index=component_z.index)
    for col, w in normalized.items():
        col_vals = component_z[col]
        any_nan = any_nan | col_vals.isna()
        result = result + w * col_vals.fillna(0.0)
    result[any_nan] = float("nan")
    return result
