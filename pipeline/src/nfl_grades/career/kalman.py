"""1D Kalman filter for career grade smoothing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KalmanResult:
    mean: float         # posterior mean (career grade)
    variance: float     # posterior variance
    n_seasons: int
    last_season: int


def smooth(
    season_grades: list[float],
    season_variances: list[float],
    seasons: list[int],
    tau_sq: float = 9.0,    # ~3 grade-point drift per off-season
) -> KalmanResult:
    """Run a 1D Kalman filter over sequential season grades.

    Parameters
    ----------
    season_grades : grades in chronological order.
    season_variances : per-season observation variance r_sq.
    seasons : season years aligned with `season_grades`; used to apply
        process noise proportional to the gap (handles missed seasons).
    tau_sq : process noise per year.
    """
    raise NotImplementedError("career.kalman.smooth: implement in build step 8")
