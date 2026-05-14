"""Top-level grading orchestrator.

Dispatches to per-position grading modules. QB (ADR-0013), RB
(ADR-0014), WR (ADR-0015), TE (ADR-0016), CB (ADR-0018), S
(ADR-0019), EDGE (ADR-0020), iDL (ADR-0021), and LB (ADR-0022) are live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nfl_grades.grading import cb, edge, idl, lb, qb, rb, safety, te, wr

logger = logging.getLogger(__name__)

# Each value is the position-specific ``run(season)`` function.
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
}

# Union of per-position RunResult dataclasses — they each carry
# position-specific counters (n_qbs_*, n_rbs_*, n_wrs_*) but share the
# (season, stat_components_written, season_grades_written) shape.
PositionRunResult = (
    qb.RunResult | rb.RunResult | wr.RunResult | te.RunResult
    | cb.RunResult | safety.RunResult | edge.RunResult | idl.RunResult
    | lb.RunResult
)


@dataclass
class GradeRunSummary:
    season: int
    by_position: dict[str, PositionRunResult]


def run(season: int, position: str | None = None) -> GradeRunSummary:
    """Run grading for one season, optionally restricted to a single position.

    Args:
        season: NFL season year (e.g. 2024).
        position: single position to grade, or None for all available
            (currently QB and RB).
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

    results: dict[str, PositionRunResult] = {}
    for pos in positions:
        logger.info("grading %s for season %d", pos, season)
        results[pos] = POSITION_RUNNERS[pos](season)
    return GradeRunSummary(season=season, by_position=results)
