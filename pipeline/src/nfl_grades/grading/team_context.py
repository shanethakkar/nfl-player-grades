"""Post-grade denormalization: team_abbr on season_grades + team_season_epa.

Both writes are idempotent (UPDATE ... WHERE NULL / DELETE+INSERT).
Run after grading a season so the web app can read pre-computed values
instead of doing expensive plays-table aggregates at request time.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# team_abbr backfill
# ---------------------------------------------------------------------------

_BACKFILL_TEAM_ABBR = text("""
    UPDATE season_grades sg
    SET team_abbr = (
        SELECT t.abbr
        FROM player_seasons ps
        JOIN teams t ON t.team_id = ps.team_id
        WHERE ps.player_id = sg.player_id
          AND ps.season    = sg.season
        ORDER BY ps.snaps_offense + ps.snaps_defense DESC
        LIMIT 1
    )
    WHERE sg.season = :season
""")


def backfill_team_abbr(conn: Connection, season: int) -> int:
    """Set season_grades.team_abbr from player_seasons for all rows in season.

    Uses the team where the player logged the most combined snaps — identical
    to the player_seasons join already used in the CB leaderboard query, and
    equivalent to the plays LATERAL join for non-traded players.

    Returns the number of rows updated.
    """
    result = conn.execute(_BACKFILL_TEAM_ABBR, {"season": season})
    n = result.rowcount
    logger.info("backfill_team_abbr season=%d: %d rows updated", season, n)
    return n


# ---------------------------------------------------------------------------
# team_season_epa compute
# ---------------------------------------------------------------------------

_DELETE_TEAM_EPA = text("DELETE FROM team_season_epa WHERE season = :season")

_COMPUTE_TEAM_EPA = text("""
    WITH team_epa AS (
        SELECT
            pl.posteam                AS team_abbr,
            AVG(pl.epa)::REAL         AS epa_per_play
        FROM plays pl
        WHERE pl.season      = :season
          AND pl.season_type = 'REG'
          AND pl.posteam     IS NOT NULL
          AND pl.down        BETWEEN 1 AND 4
          AND pl.play_type   IN ('pass', 'run')
          AND pl.epa         IS NOT NULL
        GROUP BY pl.posteam
    )
    INSERT INTO team_season_epa (season, team_abbr, epa_per_play, epa_rank, n_teams)
    SELECT
        :season                                                                AS season,
        team_abbr,
        epa_per_play,
        RANK() OVER (ORDER BY epa_per_play DESC)::int                         AS epa_rank,
        COUNT(*) OVER ()::int                                                  AS n_teams
    FROM team_epa
""")


def compute_team_epa(conn: Connection, season: int) -> int:
    """Compute team EPA per season from plays and store in team_season_epa.

    Idempotent: deletes existing rows for the season before inserting.
    Returns the number of teams written.
    """
    conn.execute(_DELETE_TEAM_EPA, {"season": season})
    conn.execute(_COMPUTE_TEAM_EPA, {"season": season})
    n = conn.execute(
        text("SELECT COUNT(*) FROM team_season_epa WHERE season = :season"),
        {"season": season},
    ).scalar() or 0
    logger.info("compute_team_epa season=%d: %d teams written", season, n)
    return int(n)


__all__ = ["backfill_team_abbr", "compute_team_epa"]
