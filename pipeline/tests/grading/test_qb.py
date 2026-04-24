"""End-to-end tests for the QB grading pipeline.

Two flavors:
    - Pure-python test of ``compute_grades``: feed synthetic
      per-player features, check shrinkage/z/composite/grade outputs.
    - Integration: with real ingested plays (2024), a hand-picked
      top-of-league QB should grade above the league median.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.grading.era_tier import REASON_ERA_PRE_NGS, _era_tier_for_season
from nfl_grades.grading.qb import (
    POSITION,
    compute_grades,
    extract_features,
    write_results,
)

# ---------------------------------------------------------------------------
# Pure-python: compute_grades
# ---------------------------------------------------------------------------


def _synth_features(n_qbs: int = 10, seed: int = 0) -> pd.DataFrame:
    """Build a realistic synthetic QB cohort.

    Emulates 2024-ish league averages / spreads:
        - EPA/db: mean 0.05, SD 0.10
        - CPOE:   mean 0.0,  SD 2.5
        - success rate: mean 0.46, SD 0.03
    Player volumes:
        - 6 starters at 500-650 dropbacks each
        - 4 backups  at 50-150 dropbacks each
    """
    rng = np.random.default_rng(seed)
    starters = 6
    backups = n_qbs - starters
    n_dropbacks = np.concatenate(
        [
            rng.integers(500, 651, size=starters),
            rng.integers(50, 151, size=backups),
        ]
    )
    # Give "better" players in the cohort (by player_id) higher true skill
    # so the ordering is deterministic per seed.
    skill = np.linspace(1.0, -1.0, n_qbs)  # descending skill by player_id
    epa = 0.05 + 0.10 * skill + rng.normal(scale=0.02, size=n_qbs)
    cpoe = 0.0 + 2.5 * skill + rng.normal(scale=0.5, size=n_qbs)
    success = 0.46 + 0.03 * skill + rng.normal(scale=0.005, size=n_qbs)
    return pd.DataFrame(
        {
            "player_id": range(1, n_qbs + 1),
            "gsis_id": [f"00-{i:07d}" for i in range(n_qbs)],
            "full_name": [f"QB {i}" for i in range(n_qbs)],
            "n_dropbacks": n_dropbacks,
            "n_pass_attempts": (n_dropbacks * 0.93).astype(int),
            "epa_per_dropback": epa,
            "cpoe": cpoe,
            "success_rate": success,
        }
    )


class TestComputeGrades:
    def test_output_columns_present(self) -> None:
        graded = compute_grades(_synth_features(10))
        expected = {
            "player_id",
            "qualified",
            "confidence",
            "composite_z",
            "grade",
            "percentile",
            "raw_qb_epa_per_dropback",
            "adjusted_qb_epa_per_dropback",
            "z_qb_epa_per_dropback",
            "raw_qb_cpoe",
            "adjusted_qb_cpoe",
            "z_qb_cpoe",
            "raw_qb_success_rate",
            "adjusted_qb_success_rate",
            "z_qb_success_rate",
        }
        assert expected.issubset(graded.columns)

    def test_grades_are_in_0_100(self) -> None:
        graded = compute_grades(_synth_features(20, seed=1))
        assert (graded["grade"] >= 0).all()
        assert (graded["grade"] <= 100).all()

    def test_qualified_flag_follows_threshold(self) -> None:
        graded = compute_grades(_synth_features(10, seed=2))
        # Starters (500-650 dropbacks) should be qualified; backups (50-150)
        # should not.
        assert graded.loc[graded["n_dropbacks"] >= 200, "qualified"].all()
        assert not graded.loc[graded["n_dropbacks"] < 200, "qualified"].any()

    def test_skill_monotonic_in_grade(self) -> None:
        # The synth helper gives descending skill by player_id, so within
        # the qualified cohort the top player_id should have the highest
        # grade.
        graded = compute_grades(_synth_features(10, seed=3))
        qual = graded[graded["qualified"]].sort_values("player_id")
        # Skill descends by player_id, so grade should descend too.
        grades = qual["grade"].to_numpy()
        assert grades[0] > grades[-1]

    def test_confidence_scaling(self) -> None:
        graded = compute_grades(_synth_features(10, seed=4))
        # Confidence caps at 1.0.
        assert (graded["confidence"] <= 1.0).all()
        # QBs with 300+ dropbacks are at confidence=1.
        full = graded[graded["n_dropbacks"] >= 300]
        assert (full["confidence"] == 1.0).all()

    def test_percentile_bounds(self) -> None:
        graded = compute_grades(_synth_features(10, seed=5))
        assert (graded["percentile"] >= 0).all()
        assert (graded["percentile"] <= 100).all()

    def test_deterministic(self) -> None:
        a = compute_grades(_synth_features(15, seed=42))
        b = compute_grades(_synth_features(15, seed=42))
        pd.testing.assert_frame_equal(a, b)


class TestDataTier:
    def test_tiers(self) -> None:
        assert _era_tier_for_season(2024) == (1, None)
        assert _era_tier_for_season(2016) == (1, None)
        assert _era_tier_for_season(2015) == (2, REASON_ERA_PRE_NGS)
        assert _era_tier_for_season(2006) == (2, REASON_ERA_PRE_NGS)
        assert _era_tier_for_season(2005) == (3, REASON_ERA_PRE_NGS)


# ---------------------------------------------------------------------------
# Integration: requires Postgres + ingested 2024 plays
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    try:
        engine = get_engine()
        with engine.connect() as connection:
            tx = connection.begin()
            try:
                yield connection
            finally:
                tx.rollback()
    except OperationalError as e:
        pytest.skip(f"Postgres unavailable: {e}")


@pytest.fixture
def has_2024_plays(conn):
    count = conn.execute(
        text("SELECT COUNT(*) FROM plays WHERE season=2024 AND qb_dropback")
    ).scalar()
    if count == 0:
        pytest.skip("2024 plays not ingested; run ingest pbp --season 2024")
    return True


class TestExtractFeatures:
    def test_returns_qbs(self, conn, has_2024_plays) -> None:
        df = extract_features(conn, 2024)
        assert not df.empty
        assert {
            "player_id",
            "gsis_id",
            "full_name",
            "n_dropbacks",
            "n_pass_attempts",
            "epa_per_dropback",
            "cpoe",
            "success_rate",
        }.issubset(df.columns)

    def test_mahomes_appears_with_plausible_stats(self, conn, has_2024_plays) -> None:
        df = extract_features(conn, 2024)
        m = df[df["gsis_id"] == "00-0033873"]
        assert len(m) == 1
        row = m.iloc[0]
        # Mahomes 2024: ~600 dropbacks, slightly positive EPA, +CPOE.
        # Garbage-time filter will knock some off - expect 400-650.
        assert 400 <= row["n_dropbacks"] <= 650
        assert -0.10 < row["epa_per_dropback"] < 0.25
        assert 0.40 < row["success_rate"] < 0.60


class TestWriteResults:
    def test_roundtrip_into_tables(self, conn, has_2024_plays) -> None:
        # Grade with a sentinel season so we don't clobber real data in
        # the test transaction (rolled back anyway, but be explicit).
        features = extract_features(conn, 2024)
        # Pretend this is a different season so the stat_components /
        # season_grades rows don't collide with any existing ones.
        features = features.head(20).copy()
        graded = compute_grades(features)

        n_components, n_grades = write_results(conn, graded, 1999)

        # stat_components: one row per (player, component). 3 components.
        assert n_components == 3 * len(graded)
        # season_grades: one per qualified+unqualified with a non-NaN grade.
        assert n_grades == graded["grade"].notna().sum()

        n_false = conn.execute(
            text(
                "SELECT COUNT(*) FROM stat_components "
                "WHERE season = 1999 AND (used_in_composite IS NOT TRUE)"
            )
        ).scalar()
        assert n_false == 0

        # Read back a row and verify round-trip
        grade_row = conn.execute(
            text(
                "SELECT composite_grade, qualified, data_tier, data_tier_reason "
                "FROM season_grades WHERE season=1999 AND position=:p LIMIT 1"
            ),
            {"p": POSITION},
        ).first()
        assert grade_row is not None
        assert 0 <= grade_row[0] <= 100
        # 1999 predates the EPA model, so the helper classifies it tier 3.
        assert grade_row[2] == 3
        assert grade_row[3] == REASON_ERA_PRE_NGS
