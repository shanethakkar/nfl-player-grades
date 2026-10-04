"""Regular-season week helpers for the weekly refresh (ADR-0031).

nflverse sources mark the regular season differently: ``season_type`` (pbp,
player stats, NGS), ``game_type`` (snap counts, PFR, schedules) or nothing
at all (FTN, where weeks past the final regular-season week are playoffs).
NGS adds a ``week = 0`` season-summary row. These helpers hide that so the
weekly refresh can ask "which week is this source through?" and "drop
anything past week N" the same way for every source.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from nfl_grades.grading.progress import final_regular_season_week


class SourceLagError(RuntimeError):
    """A source isn't aligned with the last completed week on the schedule:
    it hasn't reached it, or its season summary already runs past it."""


def _regular_season(df: pd.DataFrame, season: int) -> pd.Series:
    """Boolean mask of regular-season rows."""
    if "season_type" in df.columns:
        return df["season_type"] == "REG"
    if "game_type" in df.columns:
        return df["game_type"] == "REG"
    if "week" in df.columns:
        return df["week"] <= final_regular_season_week(season)
    return pd.Series(False, index=df.index)


def max_regular_season_week(df: pd.DataFrame, season: int) -> int | None:
    """Last regular-season week with rows in a source (None if none)."""
    if "week" not in df.columns:
        return None
    weeks = df.loc[_regular_season(df, season) & (df["week"] > 0), "week"]
    return None if weeks.empty else int(weeks.max())


def cap_regular_season(df: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """Drop regular-season rows after ``week``. Playoff rows and sources
    without a week are left alone."""
    if "week" not in df.columns:
        return df
    after = _regular_season(df, season) & (df["week"] > week)
    return df.loc[~after]


def summary_ahead(df: pd.DataFrame, season: int, week: int) -> bool:
    """True if a source with a ``week = 0`` season-summary row (NGS) already
    has regular-season games after ``week``. Capping can drop those weekly
    rows but not their contribution to the summary, which graders read (RB
    RYOE)."""
    if "week" not in df.columns or not (df["week"] == 0).any():
        return False
    latest = max_regular_season_week(df, season)
    return latest is not None and latest > week


def last_completed_week(schedule: pd.DataFrame) -> int | None:
    """Latest regular-season week whose every game has a result, from a
    nflverse schedule. None before any week is complete.

    A week, not a run of weeks: a game that was never completed (BUF-CIN,
    2022 week 17) doesn't hold the rest of the season open.
    """
    reg = schedule[schedule["game_type"] == "REG"]
    complete = reg["result"].notna().groupby(reg["week"]).all()
    complete_weeks = complete[complete].index
    return None if complete_weeks.empty else int(complete_weeks.max())


def check_alignment(source_weeks: Mapping[str, int | None], expected_week: int) -> None:
    """Fail unless every source is through ``expected_week``.

    Raises:
        SourceLagError: naming each source and the week it is through.
    """
    lagging = {s: w for s, w in source_weeks.items() if w != expected_week}
    if lagging:
        detail = ", ".join(f"{s} at week {w}" for s, w in sorted(lagging.items(), key=str))
        raise SourceLagError(
            f"sources not through week {expected_week} (the last completed week): {detail}"
        )
