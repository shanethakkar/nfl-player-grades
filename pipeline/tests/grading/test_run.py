"""Tests for the grading orchestrator (grading/run.py).

DB-backed, inside a transaction that rolls back; skipped unless
DATABASE_URL points at a local database.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.config import settings
from nfl_grades.db import get_engine
from nfl_grades.grading import progress
from nfl_grades.grading import run as grading_run
from nfl_grades.grading.progress import COMPLETE, SeasonProgress
from nfl_grades.grading.scoring import InsufficientCohortError

SEASON = 2099


@pytest.fixture
def conn() -> Iterator[Connection]:
    if not any(h in settings.database_url for h in ("localhost", "127.0.0.1")):
        pytest.skip("grading orchestrator tests only run against a local DATABASE_URL")
    with get_engine().connect() as connection:
        tx = connection.begin()
        try:
            yield connection
        finally:
            tx.rollback()


@pytest.fixture
def stale_k_grade(conn: Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """Last week's K grade for SEASON, and a K grader that now finds too few
    qualified kickers."""
    player_id = conn.execute(text("SELECT MIN(player_id) FROM players")).scalar_one()
    conn.execute(
        text(
            "INSERT INTO season_grades (player_id, season, position, composite_grade, "
            "composite_z, percentile, data_tier, qualified, through_week) "
            "VALUES (:p, :s, 'K', 60, 0.4, 60, 1, TRUE, 3)"
        ),
        {"p": player_id, "s": SEASON},
    )
    conn.execute(
        text(
            "INSERT INTO stat_components (player_id, season, component_name, z_score) "
            "VALUES (:p, :s, 'k_fg_over_expected_per_att', 0.4)"
        ),
        {"p": player_id, "s": SEASON},
    )

    def too_few(season: int, *, conn: Connection | None = None) -> None:
        raise InsufficientCohortError("8 qualified players with a Composite; need 10")

    monkeypatch.setitem(grading_run.POSITION_RUNNERS, "K", too_few)


def _k_rows(conn: Connection) -> tuple[int, int]:
    grades = conn.execute(
        text("SELECT COUNT(*) FROM season_grades WHERE season = :s AND position = 'K'"),
        {"s": SEASON},
    ).scalar_one()
    components = conn.execute(
        text("SELECT COUNT(*) FROM stat_components WHERE season = :s AND component_name LIKE 'k\\_%'"),
        {"s": SEASON},
    ).scalar_one()
    return grades, components


class TestNotGraded:
    def test_provisional_position_below_the_cohort_drops_last_weeks_grades(
        self, conn: Connection, stale_k_grade: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(progress, "load", lambda _c, _s: SeasonProgress(4, 4.0))
        summary = grading_run.run(SEASON, "K", conn=conn)
        assert isinstance(summary.by_position["K"], grading_run.NotGraded)
        assert _k_rows(conn) == (0, 0)

    def test_completed_season_keeps_its_grades(
        self, conn: Connection, stale_k_grade: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(progress, "load", lambda _c, _s: COMPLETE)
        grading_run.run(SEASON, "K", conn=conn)
        assert _k_rows(conn) == (1, 1)
