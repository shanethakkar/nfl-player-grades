"""Shared scoring step: Component z-scores -> Composite -> Grade -> percentile.

Every position grader, ``nflgrades preview`` and ``nflgrades regrade`` go
through :func:`score`, so what you preview is what ships.

The Composite is standardized over the Qualified cohort before the sigmoid
(ADR-0028), so a given Grade maps to the same percentile at every position
and season regardless of how correlated a position's Components are.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from nfl_grades.grading import composite, sigmoid

# Fewest Qualified players with a Composite needed to estimate the Composite
# SD and a percentile distribution. Below this a position-season is not graded.
MIN_QUALIFIED_COHORT = 10


class InsufficientCohortError(ValueError):
    """A position-season has too few Qualified players (or no spread among
    them) to be graded. Raised instead of silently grading everyone 50."""


def score(
    component_z: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series,
    qualified: pd.Series,
    *,
    composite_sd: float | None = None,
) -> pd.DataFrame:
    """Score a position-season cohort.

    Args:
        component_z: one row per player, one column per Component z-score.
            NaN means the player lacks that Component: the Formula's weights
            are renormalized over the Components the player has. A Formula
            Component with no column is missing for every player. A player
            with no Components gets no Composite, Grade or percentile.
        weights: the Formula, ``{component: signed weight}``; or a Series
            (same index as ``component_z``) holding each player's Formula,
            for positions whose Formula depends on role (TE blocking).
        qualified: boolean mask (same index) defining the cohort that sets
            the Composite scale and the percentile distribution.
        composite_sd: divide the raw Composite by this instead of its SD
            over the Qualified cohort. Provisional grades pass the pooled SD
            from completed seasons, since a week-3 cohort is too small to
            estimate it.

    Returns a DataFrame indexed like ``component_z`` with columns
    ``composite_z`` (the raw Composite divided by the cohort SD, or by
    ``composite_sd``), ``grade`` and ``percentile``.

    Raises:
        InsufficientCohortError: fewer than ``MIN_QUALIFIED_COHORT``
            Qualified players have a Composite, or their Composites are all
            equal.
    """
    if isinstance(weights, pd.Series):
        formulas = weights.reindex(component_z.index)
    else:
        formulas = pd.Series([weights] * len(component_z), index=component_z.index, dtype=object)

    raw = pd.Series(np.nan, index=component_z.index, dtype=float)
    formula_key = formulas.map(lambda w: tuple(w.items()))
    for key, rows in formula_key.groupby(formula_key, sort=False).groups.items():
        formula = dict(key)
        z = component_z.loc[rows].reindex(columns=list(formula))
        raw.loc[rows] = composite.combine(z, formula)

    in_cohort = qualified.reindex(component_z.index).fillna(False).astype(bool) & raw.notna()
    n_cohort = int(in_cohort.sum())
    if n_cohort < MIN_QUALIFIED_COHORT:
        raise InsufficientCohortError(
            f"{n_cohort} qualified players with a Composite; need {MIN_QUALIFIED_COHORT}"
        )
    if composite_sd is None:
        composite_sd = float(raw[in_cohort].std(ddof=1))
        if composite_sd == 0:
            raise InsufficientCohortError(
                f"all {n_cohort} qualified players have the same Composite"
            )
    composite_z = raw / composite_sd

    grade = pd.Series(sigmoid.to_grade(composite_z.to_numpy()), index=component_z.index)
    return pd.DataFrame(
        {
            "composite_z": composite_z,
            "grade": grade,
            "percentile": _percentile(grade, in_cohort),
        },
        index=component_z.index,
    )


def _percentile(grade: pd.Series, cohort_mask: pd.Series) -> pd.Series:
    """Percentile of every player's grade within the qualified cohort.

    Unqualified players are placed against the qualified distribution too
    ("if you played starter reps, here's where you'd stack").
    """
    cohort = np.sort(grade[cohort_mask].to_numpy())
    ranks = np.searchsorted(cohort, grade.to_numpy(), side="right")
    return pd.Series(100.0 * ranks / len(cohort), index=grade.index).where(grade.notna())
