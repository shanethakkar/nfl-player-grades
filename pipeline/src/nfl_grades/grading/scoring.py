"""Shared scoring step: Component z-scores -> Composite -> Grade -> percentile.

Every position grader, ``nflgrades preview`` and ``nflgrades regrade`` go
through :func:`score`, so what you preview is what ships.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import numpy as np
import pandas as pd

from nfl_grades.grading import composite, sigmoid

MissingPolicy = Literal["neutral", "ungraded"]


def score(
    component_z: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series,
    qualified: pd.Series,
    *,
    missing: MissingPolicy = "neutral",
) -> pd.DataFrame:
    """Score a position-season cohort.

    Args:
        component_z: one row per player, one column per Component z-score.
            A Formula Component with no column is treated as missing for
            every player.
        weights: the Formula, ``{component: signed weight}``; or a Series
            (same index as ``component_z``) holding each player's Formula,
            for positions whose Formula depends on role (TE blocking).
        qualified: boolean mask (same index) defining the percentile cohort.
        missing: what a NaN Component z-score means.
            ``"neutral"``: no evidence of the skill, assume league average
            (z = 0). ``"ungraded"``: the player gets no Composite, Grade or
            percentile (QB, ADR-0013).

    Returns a DataFrame indexed like ``component_z`` with columns
    ``composite_z``, ``grade`` and ``percentile``.
    """
    if isinstance(weights, pd.Series):
        formulas = weights.reindex(component_z.index)
    else:
        formulas = pd.Series([weights] * len(component_z), index=component_z.index, dtype=object)

    composite_z = pd.Series(np.nan, index=component_z.index, dtype=float)
    formula_key = formulas.map(lambda w: tuple(w.items()))
    for key, rows in formula_key.groupby(formula_key, sort=False).groups.items():
        formula = dict(key)
        z = component_z.loc[rows].reindex(columns=list(formula))
        if missing == "neutral":
            z = z.fillna(0.0)
        composite_z.loc[rows] = composite.combine(z, formula)

    grade = pd.Series(sigmoid.to_grade(composite_z.to_numpy()), index=component_z.index)
    return pd.DataFrame(
        {
            "composite_z": composite_z,
            "grade": grade,
            "percentile": _percentile(grade, qualified.reindex(grade.index).fillna(False)),
        },
        index=component_z.index,
    )


def _percentile(grade: pd.Series, qualified: pd.Series) -> pd.Series:
    """Percentile of every player's grade within the qualified cohort.

    Unqualified players are placed against the qualified distribution too
    ("if you played starter reps, here's where you'd stack"). With fewer
    than two qualified grades there is no distribution: everyone gets 50.
    """
    cohort = np.sort(grade[qualified.astype(bool)].dropna().to_numpy())
    if len(cohort) < 2:
        pct = pd.Series(50.0, index=grade.index)
    else:
        ranks = np.searchsorted(cohort, grade.to_numpy(), side="right")
        pct = pd.Series(100.0 * ranks / len(cohort), index=grade.index)
    return pct.where(grade.notna())
