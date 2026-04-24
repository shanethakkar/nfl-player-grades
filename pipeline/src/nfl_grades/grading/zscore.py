"""Within-population z-score helpers.

Z-score uses the mean and SD of a **qualified** subset (e.g. QBs with
>= 200 dropbacks for QB grading). All players are z-scored against
those statistics — a backup's z-score is "this is where they'd stack
up if they played a starter's schedule."

Using sample SD with ``ddof=1`` (nflverse / public-analytics
convention). On 30+ qualified QBs the difference between ddof 0 and 1
is under 2%, but it matters for small cohorts like RB1s or top-4
receivers per team.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def zscore(
    values: pd.Series,
    qualified_mask: pd.Series | None = None,
) -> pd.Series:
    """Return z-scores for ``values`` using qualified-subset stats.

    Args:
        values: per-player component values (may contain NaN).
        qualified_mask: boolean Series, same index as ``values``. If
            None, all non-NaN values are used for the mean/SD.

    Rows where ``values`` is NaN return NaN. Rows outside the qualified
    mask are still z-scored — they just don't participate in defining
    the distribution.
    """
    subset = values.dropna() if qualified_mask is None else values[qualified_mask].dropna()

    if len(subset) < 2:
        # Not enough qualified rows to compute a meaningful SD. Fall
        # back to zeros so the grade stays on-scale rather than NaN.
        return pd.Series(0.0, index=values.index).where(values.notna(), float("nan"))

    mu = float(subset.mean())
    sd = float(subset.std(ddof=1))
    if sd == 0 or np.isnan(sd):
        return pd.Series(0.0, index=values.index).where(values.notna(), float("nan"))

    return (values - mu) / sd
