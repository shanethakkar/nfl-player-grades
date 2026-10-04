"""Top-level grading orchestrator.

Dispatches to per-position grading modules. QB (ADR-0013), RB
(ADR-0014), WR (ADR-0015), TE (ADR-0016), CB (ADR-0018), S
(ADR-0019), EDGE (ADR-0020), iDL (ADR-0021), LB (ADR-0022), K
(ADR-0023), P (ADR-0024), and OL (ADR-0025; team-level) are live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.engine import Connection

from nfl_grades.grading import cb, edge, idl, kicker, lb, ol, punter, qb, rb, safety, te, wr
from nfl_grades.grading.scoring import InsufficientCohortError

logger = logging.getLogger(__name__)

# Each value is the position-specific ``run(season, *, conn=None)`` function.
POSITION_RUNNERS = {
    "QB":   qb.run,
    "RB":   rb.run,
    "WR":   wr.run,
    "TE":   te.run,
    "CB":   cb.run,
    "S":    safety.run,
    "EDGE": edge.run,
    "iDL":  idl.run,
    "LB":   lb.run,
    "K":    kicker.run,
    "P":    punter.run,
    "OL":   ol.run,
}

# Union of per-position RunResult dataclasses — they each carry
# position-specific counters (n_qbs_*, n_rbs_*, n_wrs_*) but share the
# (season, stat_components_written, season_grades_written) shape.
PositionRunResult = (
    qb.RunResult | rb.RunResult | wr.RunResult | te.RunResult
    | cb.RunResult | safety.RunResult | edge.RunResult | idl.RunResult
    | lb.RunResult | kicker.RunResult | punter.RunResult | ol.RunResult
)


@dataclass(frozen=True)
class NotGraded:
    """A position-season the grader refused to grade (too few Qualified
    players). Its existing rows are left untouched."""

    season: int
    reason: str


@dataclass
class GradeRunSummary:
    season: int
    by_position: dict[str, PositionRunResult | NotGraded]


def run(
    season: int, position: str | None = None, *, conn: Connection | None = None
) -> GradeRunSummary:
    """Run grading for one season, optionally restricted to a single position.

    Args:
        season: NFL season year (e.g. 2024).
        position: single position to grade, or None for all.
        conn: write inside the caller's transaction instead of one per
            position (the weekly refresh commits every grade at once).
    """
    if position is None:
        positions = list(POSITION_RUNNERS)
    else:
        # Try exact match first, then case-insensitive fallback (handles iDL vs IDL).
        if position in POSITION_RUNNERS:
            pos = position
        else:
            upper = position.upper()
            pos = next((k for k in POSITION_RUNNERS if k.upper() == upper), None)
        if pos is None:
            raise ValueError(
                f"position {position!r} not supported; known: {sorted(POSITION_RUNNERS)}"
            )
        positions = [pos]

    results: dict[str, PositionRunResult | NotGraded] = {}
    for pos in positions:
        logger.info("grading %s for season %d", pos, season)
        try:
            results[pos] = POSITION_RUNNERS[pos](season, conn=conn)
        except InsufficientCohortError as exc:
            # The grader's pipeline_runs row is already marked 'error'.
            logger.warning("%s %d not graded: %s", pos, season, exc)
            results[pos] = NotGraded(season=season, reason=str(exc))
    return GradeRunSummary(season=season, by_position=results)
