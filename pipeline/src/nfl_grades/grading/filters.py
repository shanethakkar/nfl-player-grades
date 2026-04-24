"""SQL fragments for the standard grading filters.

Kept in one place so every position's feature extraction uses the same
definition of "a countable play" and "garbage time". See ADR-0013.

Usage:
    from nfl_grades.grading.filters import GARBAGE_TIME_SQL, QB_DROPBACK_FILTER_SQL

    query = f"SELECT ... FROM plays WHERE {QB_DROPBACK_FILTER_SQL}"
"""

from __future__ import annotations

# ADR-0013 garbage-time rule. Using the raw columns from the plays
# table (qtr, score_differential, game_seconds_remaining) rather than
# nflverse's win_probability because that model is aggressive about
# locking in late-game outcomes.
GARBAGE_TIME_SQL = """(
       (qtr >= 4 AND ABS(score_differential) > 21)
    OR (qtr  = 4 AND game_seconds_remaining < 300
                 AND ABS(score_differential) > 14)
)"""

# Plays to include in the QB v1 grade. One row per dropback in REG
# season, excluding aborted snaps, 2-pt conversions, and garbage time.
QB_DROPBACK_FILTER_SQL = f"""
    season_type = 'REG'
    AND qb_dropback = TRUE
    AND (aborted_play IS NULL OR aborted_play = FALSE)
    AND (two_point_attempt IS NULL OR two_point_attempt = FALSE)
    AND passer_player_id IS NOT NULL
    AND NOT {GARBAGE_TIME_SQL}
""".strip()

# ADR-0014 RB v1 filters.
#
# Rushing plays that count toward an RB's rushing components. Scrambles
# and kneels are excluded — scrambles belong to the QB, kneels to clock
# management rather than RB skill.
RB_RUSH_FILTER_SQL = f"""
    season_type = 'REG'
    AND rush_attempt = TRUE
    AND rusher_player_id IS NOT NULL
    AND (qb_kneel IS NULL OR qb_kneel = FALSE)
    AND (qb_scramble IS NULL OR qb_scramble = FALSE)
    AND (two_point_attempt IS NULL OR two_point_attempt = FALSE)
    AND NOT {GARBAGE_TIME_SQL}
""".strip()

# Receiving plays that count toward an RB's receiving components. We
# look at all targets (not just completions); incompletions + catches
# are needed to compute catch % and EPA/target.
RB_REC_FILTER_SQL = f"""
    season_type = 'REG'
    AND pass_attempt = TRUE
    AND receiver_player_id IS NOT NULL
    AND (two_point_attempt IS NULL OR two_point_attempt = FALSE)
    AND NOT {GARBAGE_TIME_SQL}
""".strip()
