"""`nflgrades weekly`: refresh one season end-to-end (ADR-0031).

One command, in dependency order, with fresh data:

    1. Download every source once (``_cache.one_fetch_per_source``).
    2. Find the last completed regular-season week on the schedule and cap
       every week-keyed source there (``_cache.capped_at_week``), so a run
       on a Friday doesn't pick up Thursday night's game.
    3. Refuse to write anything unless every source is through that week,
       and no season summary (NGS week 0) already includes the next one.
    4. Ingest stages, each its own commit. Rosters and snap counts share
       one, since rosters recreate ``player_seasons`` with zero snaps.
    5. Grade every position, OL, team grades and team context in a single
       transaction, so the site never sees a half-graded season.

A failure in step 3 leaves the database untouched; a failure in step 5
leaves the previous week's grades in place.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest import _cache
from nfl_grades.ingest._cache import SourceName, cache_or_fetch
from nfl_grades.ingest._weeks import (
    SourceLagError,
    check_alignment,
    last_completed_week,
    max_regular_season_week,
    summary_ahead,
)

logger = logging.getLogger(__name__)

# First seasons each source family covers (see the ingest modules).
NGS_MIN_SEASON = 2016
PFR_MIN_SEASON = 2018
FTN_MIN_SEASON = 2022


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[int], object]


@dataclass(frozen=True)
class WeeklyResult:
    season: int
    # None: no regular-season week has been completed yet; nothing ran.
    through_week: int | None
    stages: list[str]


def aligned_sources(season: int) -> list[SourceName]:
    """Week-keyed sources that must all be through the last completed week."""
    sources: list[SourceName] = ["pbp", "snap_counts", "nflvs_player_stats"]
    if season >= NGS_MIN_SEASON:
        sources += ["ngs_passing", "ngs_rushing", "ngs_receiving"]
    if season >= PFR_MIN_SEASON:
        sources += ["pfr_advstats_def", "pfr_advstats_rush"]
    if season >= FTN_MIN_SEASON:
        sources += ["ftn"]
    return sources


def _rosters_and_snap_counts(season: int) -> None:
    from nfl_grades.ingest import rosters, snap_counts

    with get_engine().begin() as conn:
        rosters.run(season, refresh=True, conn=conn)
        snap_counts.run(season, refresh=True, conn=conn)


def ingest_stages(season: int) -> list[Stage]:
    """Every ingest stage for ``season``, in dependency order."""
    from nfl_grades.ingest import (
        defensive_player_stats,
        depth_charts,
        ftn_receiving,
        kicker,
        ngs,
        pbp,
        pfr,
        pfr_dl,
        pfr_lb,
        pfr_rush,
        pfr_safety,
        punter,
        qb_stats,
        skill_player_stats,
        team_ol,
        team_season_records,
    )

    def fresh(fn: Callable[..., object]) -> Callable[[int], object]:
        return lambda s: fn(s, refresh=True)

    stages = [
        Stage("rosters+snap-counts", _rosters_and_snap_counts),
        Stage("depth-charts", fresh(depth_charts.run)),
        Stage("pbp", fresh(pbp.run)),
    ]
    if season >= NGS_MIN_SEASON:
        stages += [
            Stage("ngs", fresh(ngs.run_all)),
            Stage("kicker-stats", fresh(kicker.run)),
            Stage("punter-stats", fresh(punter.run)),
            Stage("qb-stats", fresh(qb_stats.run)),
            Stage("skill-stats", fresh(skill_player_stats.run)),
            Stage("defensive-stats", fresh(defensive_player_stats.run)),
        ]
    if season >= PFR_MIN_SEASON:
        stages += [
            Stage("pfr-def-coverage", fresh(pfr.run)),
            Stage("pfr-def-coverage-s", fresh(pfr_safety.run)),
            Stage("pfr-def-passrush", fresh(pfr_dl.run)),
            Stage("pfr-def-lb", fresh(pfr_lb.run)),
            Stage("pfr-rb-rush", fresh(pfr_rush.run)),
            Stage("team-ol", fresh(team_ol.run)),
        ]
    if season >= FTN_MIN_SEASON:
        stages.append(Stage("ftn-receiving", fresh(ftn_receiving.run)))
    stages.append(Stage("team-records", fresh(team_season_records.run)))
    return stages


def grade_season(season: int) -> None:
    """Every position, OL, team grades and team context in one transaction."""
    from nfl_grades.grading import run as grading_run
    from nfl_grades.grading import team, team_context

    with get_engine().begin() as conn:
        summary = grading_run.run(season, conn=conn)
        for position, result in summary.by_position.items():
            if isinstance(result, grading_run.NotGraded):
                logger.warning("%s %d not graded: %s", position, season, result.reason)
        team.run(season, conn=conn)
        team_context.run(season, conn=conn)


def run(
    season: int,
    *,
    ingest: Sequence[Stage] | None = None,
    grade: Callable[[int], object] = grade_season,
) -> WeeklyResult:
    """Refresh ``season`` through its last completed regular-season week.

    ``ingest`` and ``grade`` default to the real stages; tests swap them.

    Raises:
        SourceLagError: a source isn't through the last completed week.
            Nothing has been written.
    """
    with pipeline_run("weekly", season=season) as handle, _cache.one_fetch_per_source():
        schedule = cache_or_fetch("schedules", season, refresh=True)
        through_week = last_completed_week(schedule)
        if through_week is None:
            handle.note("no regular-season week completed yet; nothing to do")
            return WeeklyResult(season, None, [])
        handle.note(f"through_week={through_week}")

        ahead = [
            source
            for source in aligned_sources(season)
            if summary_ahead(cache_or_fetch(source, season, refresh=True), season, through_week)
        ]
        if ahead:
            raise SourceLagError(
                f"{', '.join(ahead)} season summaries already include games after week "
                f"{through_week}; re-run once week {through_week + 1} is complete"
            )

        with _cache.capped_at_week(season, through_week):
            source_weeks: dict[str, int | None] = {
                source: max_regular_season_week(
                    cache_or_fetch(source, season, refresh=True), season
                )
                for source in aligned_sources(season)
            }
            check_alignment(source_weeks, through_week)

            stages = list(ingest if ingest is not None else ingest_stages(season))
            for stage in stages:
                logger.info("weekly %d: %s", season, stage.name)
                stage.run(season)
            logger.info("weekly %d: grade", season)
            grade(season)

        handle.rows_written = len(stages) + 1
    return WeeklyResult(season, through_week, [s.name for s in stages] + ["grade"])
