"""Era leg of ``season_grades.data_tier`` (ADR-0003).

The **final** ``data_tier`` on a row can also depend on **position/role** (e.g. TE
blocking-only caveat — see ADR-0016). This module encodes only the **era** slice so
``data_tier`` is not conflated with the era helper name.

    _era_tier_for_season(season) -> (tier, reason | None)
"""

from __future__ import annotations

# String stored in season_grades.data_tier_reason when the era path (not role)
# implies thin modern tracking data.
REASON_ERA_PRE_NGS: str = "era_pre_ngs"


def _era_tier_for_season(season: int) -> tuple[int, str | None]:
    """Era-based tier for any graded season.

    Returns:
        (tier, reason): ``reason`` is ``REASON_ERA_PRE_NGS`` when ``tier`` is
        2 (2006-2015 PBP but no NGS) or 3 (pre-2006), else ``None`` for tier 1.

    ADR-0003: 1 = full PBP+NGS era (2016+), 2 = PBP 2006-2015, 3 = pre-EPA.
    """
    if season >= 2016:
        return 1, None
    if season >= 2006:
        return 2, REASON_ERA_PRE_NGS
    return 3, REASON_ERA_PRE_NGS
