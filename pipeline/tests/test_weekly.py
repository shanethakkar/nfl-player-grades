"""Tests for `nflgrades weekly` (ADR-0031): stage order, the source-week
alignment gate, and logging.

The run tests need Postgres for ``pipeline_runs`` and only run against a
local database: they are skipped unless DATABASE_URL points at localhost.
Every source is faked, so nothing is downloaded.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sqlalchemy import text

from nfl_grades import weekly
from nfl_grades.config import settings
from nfl_grades.db import get_engine
from nfl_grades.ingest import _cache
from nfl_grades.ingest._cache import SourceSpec
from nfl_grades.ingest._weeks import SourceLagError

SEASON = 2026


class TestStageOrder:
    def test_ingest_runs_in_dependency_order(self) -> None:
        assert [stage.name for stage in weekly.ingest_stages(SEASON)] == [
            "rosters+snap-counts",
            "depth-charts",
            "pbp",
            "ngs",
            "kicker-stats",
            "punter-stats",
            "qb-stats",
            "skill-stats",
            "defensive-stats",
            "pfr-def-coverage",
            "pfr-def-coverage-s",
            "pfr-def-passrush",
            "pfr-def-lb",
            "pfr-rb-rush",
            "team-ol",
            "ftn-receiving",
            "team-records",
        ]

    def test_sources_outside_their_era_are_skipped(self) -> None:
        names = [stage.name for stage in weekly.ingest_stages(2017)]
        assert "pfr-def-coverage" not in names
        assert "ftn-receiving" not in names
        assert weekly.aligned_sources(2017) == [
            "pbp",
            "snap_counts",
            "nflvs_player_stats",
            "ngs_passing",
            "ngs_rushing",
            "ngs_receiving",
        ]


# ---------------------------------------------------------------------------
# Runs against local Postgres with faked sources
# ---------------------------------------------------------------------------


@pytest.fixture
def local_db() -> None:
    if not any(h in settings.database_url for h in ("localhost", "127.0.0.1")):
        pytest.skip("weekly run tests only run against a local DATABASE_URL")


def _schedule(completed_weeks: int) -> pl.DataFrame:
    weeks = np.repeat(np.arange(1, 6), 16)
    result = np.where(weeks <= completed_weeks, 3.0, np.nan)
    result[np.flatnonzero(weeks == completed_weeks + 1)[:5]] = 7.0  # next week under way
    return pl.DataFrame({"game_type": ["REG"] * len(weeks), "week": weeks, "result": result})


def _weekly_rows(through_week: int) -> pl.DataFrame:
    weeks = list(range(1, through_week + 1))
    return pl.DataFrame({"season_type": ["REG"] * len(weeks), "week": weeks})


@pytest.fixture
def fake_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, int]:
    """Every week-keyed source through week 3, schedule complete through
    week 3. Tests lower one source's week to make it lag."""
    monkeypatch.setattr(_cache, "_raw_root", lambda: tmp_path / "raw")
    through = {source: 3 for source in weekly.aligned_sources(SEASON)}

    def registry() -> dict[str, SourceSpec]:
        specs = {
            source: SourceSpec(season_keyed=True, fetch=lambda _s, w=week: _weekly_rows(w))
            for source, week in through.items()
        }
        specs["schedules"] = SourceSpec(season_keyed=True, fetch=lambda _s: _schedule(3))
        return specs

    monkeypatch.setattr(_cache, "_get_sources", registry)
    return through


def _record(calls: list[str], name: str) -> weekly.Stage:
    return weekly.Stage(name, lambda _season: calls.append(name))


def _last_weekly_run() -> tuple[str, str | None]:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, notes FROM pipeline_runs "
                "WHERE stage = 'weekly' ORDER BY run_id DESC LIMIT 1"
            )
        ).one()
    return row.status, row.notes


class TestRun:
    def test_aligned_sources_run_every_stage_in_order_then_grade(
        self, local_db: None, fake_sources: dict[str, int]
    ) -> None:
        calls: list[str] = []
        result = weekly.run(
            SEASON,
            ingest=[_record(calls, "a"), _record(calls, "b")],
            grade=lambda _season: calls.append("grade"),
        )
        assert calls == ["a", "b", "grade"]
        assert result.through_week == 3
        assert _last_weekly_run()[0] == "ok"

    def test_lagging_source_fails_before_anything_is_written(
        self, local_db: None, fake_sources: dict[str, int]
    ) -> None:
        fake_sources["ngs_passing"] = 2
        calls: list[str] = []
        with pytest.raises(SourceLagError, match="ngs_passing at week 2"):
            weekly.run(
                SEASON,
                ingest=[_record(calls, "a")],
                grade=lambda _season: calls.append("grade"),
            )
        assert calls == []
        status, notes = _last_weekly_run()
        assert status == "error"
        assert "ngs_passing" in (notes or "")

    def test_source_ahead_of_the_schedule_is_capped_not_failed(
        self, local_db: None, fake_sources: dict[str, int]
    ) -> None:
        # Thursday night's game of week 4 is already in pbp.
        fake_sources["pbp"] = 4
        seen: list[int] = []

        def read_pbp(season: int) -> None:
            seen.append(int(_cache.cache_or_fetch("pbp", season, refresh=True)["week"].max()))

        weekly.run(SEASON, ingest=[weekly.Stage("pbp", read_pbp)], grade=lambda _s: None)
        assert seen == [3]

    def test_season_summary_that_includes_the_next_week_fails(
        self, local_db: None, fake_sources: dict[str, int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # NGS keeps a week=0 season-summary row. Capping can't remove a
        # partial week 4 from it, so the run refuses rather than mixing weeks.
        registry = _cache._get_sources()
        summary_through_4 = pl.DataFrame(
            {"season_type": ["REG"] * 5, "week": [0, 1, 2, 3, 4]}
        )
        registry["ngs_rushing"] = SourceSpec(season_keyed=True, fetch=lambda _s: summary_through_4)
        monkeypatch.setattr(_cache, "_get_sources", lambda: registry)
        calls: list[str] = []
        with pytest.raises(SourceLagError, match="ngs_rushing"):
            weekly.run(SEASON, ingest=[_record(calls, "a")], grade=lambda _s: None)
        assert calls == []

    def test_before_any_week_is_complete_nothing_runs(
        self, local_db: None, fake_sources: dict[str, int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = _cache._get_sources()
        registry["schedules"] = SourceSpec(season_keyed=True, fetch=lambda _s: _schedule(0))
        monkeypatch.setattr(_cache, "_get_sources", lambda: registry)
        calls: list[str] = []
        result = weekly.run(
            SEASON, ingest=[_record(calls, "a")], grade=lambda _s: calls.append("grade")
        )
        assert calls == []
        assert result.through_week is None
