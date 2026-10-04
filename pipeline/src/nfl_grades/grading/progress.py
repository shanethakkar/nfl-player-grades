"""Season progress: how much of a season a grade covers.

A season still in progress gets Provisional grades "through week N". Every
absolute volume threshold (min to grade, Qualified, the confidence
denominator, role gates) pro-rates by games played / 17, so the same
Formula works at week 3 and week 18. Completed seasons don't pro-rate, so
their grades are unchanged.

Progress is read from ``plays``: the last regular-season week ingested and
the average games played per team.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Thresholds in weights.py are set for a full 17-game season.
FULL_SEASON_GAMES = 17

# Thresholds never pro-rate below three games' worth: before that almost
# every player sits at the shrinkage prior and a tiny bar would qualify
# one-game cameos.
MIN_PRORATE_GAMES = 3


@dataclass(frozen=True)
class SeasonProgress:
    """How far into its regular season a grade covers.

    ``through_week`` is None for a completed season. ``games`` is the
    average number of games each team has played.
    """

    through_week: int | None = None
    games: float = FULL_SEASON_GAMES

    @property
    def is_provisional(self) -> bool:
        return self.through_week is not None

    @property
    def fraction(self) -> float:
        """Share of a full season's volume a full-time player has had so far."""
        if not self.is_provisional:
            return 1.0
        return min(max(self.games, MIN_PRORATE_GAMES) / FULL_SEASON_GAMES, 1.0)

    def scale(self, threshold: float) -> float:
        """Pro-rate a full-season volume threshold to games played so far."""
        return threshold * self.fraction


COMPLETE = SeasonProgress()


def final_regular_season_week(season: int) -> int:
    """Last regular-season week: 17 through 2020, 18 from 2021 (17 games)."""
    return 17 if season <= 2020 else 18


def from_plays(season: int, through_week: int | None, games: float | None) -> SeasonProgress:
    """Season progress from the last REG week in ``plays`` and the average
    games per team. A season through its final week is complete."""
    if through_week is None or games is None:
        return COMPLETE
    if through_week >= final_regular_season_week(season):
        return COMPLETE
    return SeasonProgress(through_week=int(through_week), games=float(games))


_PROGRESS_SQL = text("""
    WITH team_games AS (
        SELECT DISTINCT game_id, week, posteam
        FROM plays
        WHERE season = :season
          AND season_type = 'REG'
          AND posteam IS NOT NULL
    )
    SELECT MAX(week) AS through_week,
           COUNT(*)::float / NULLIF(COUNT(DISTINCT posteam), 0) AS games
    FROM team_games
""")


def load(conn: Connection, season: int) -> SeasonProgress:
    """Read a season's progress from ingested ``plays``."""
    row = conn.execute(_PROGRESS_SQL, {"season": season}).one()
    return from_plays(season, row.through_week, row.games)
