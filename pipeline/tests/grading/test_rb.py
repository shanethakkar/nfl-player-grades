"""End-to-end tests for the RB grading pipeline (ADR-0014).

Mirrors test_qb.py structure:
    - Pure-python tests of ``compute_grades`` with synthetic features.
    - Integration tests against a real Postgres with 2024 plays + NGS.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.grading.era_tier import REASON_ERA_PRE_NGS, _era_tier_for_season
from nfl_grades.grading.rb import (
    POSITION,
    compute_grades,
    extract_features,
    write_results,
)

# ---------------------------------------------------------------------------
# Synthetic RB cohort
# ---------------------------------------------------------------------------


def _synth_features(
    *,
    n_feature_backs: int = 6,
    n_committee_backs: int = 6,
    n_specialists: int = 3,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a realistic synthetic RB cohort.

    Three archetypes:
        - Feature backs: 220-290 carries, 30-70 targets. Drive the
          z-score population.
        - Committee backs: 100-150 carries, 15-40 targets. Qualified
          only if touches >= 120.
        - Pass-game specialists: 30-60 carries, 60-90 targets. Usually
          qualified via receiving volume.

    Within each archetype, "skill" varies linearly by position in the
    list so tests can make ordering assertions.
    """
    rng = np.random.default_rng(seed)

    def skill_line(n: int, hi: float, lo: float) -> np.ndarray:
        return np.linspace(hi, lo, n)

    n_total = n_feature_backs + n_committee_backs + n_specialists

    n_carries = np.concatenate(
        [
            rng.integers(220, 291, size=n_feature_backs),
            rng.integers(100, 151, size=n_committee_backs),
            rng.integers(30, 61, size=n_specialists),
        ]
    )
    n_targets = np.concatenate(
        [
            rng.integers(30, 71, size=n_feature_backs),
            rng.integers(15, 41, size=n_committee_backs),
            rng.integers(60, 91, size=n_specialists),
        ]
    )
    n_receptions = (n_targets * 0.78).astype(int)
    # xYAC coverage is >99% on real RB receptions; treat it as 1:1 in
    # synthetic data so tests don't have to special-case a tiny gap.
    n_rec_with_xyac = n_receptions.copy()
    n_touches = n_carries + n_receptions
    n_fumbles = rng.integers(0, 3, size=n_total)
    fumble_rate = n_fumbles.astype(float) / np.maximum(n_touches, 1)

    skill = np.concatenate(
        [
            skill_line(n_feature_backs, 1.2, -0.2),  # strong feature > below-average feature
            skill_line(n_committee_backs, 0.6, -0.6),  # a couple good + a couple bad committee guys
            skill_line(n_specialists, 0.4, -0.4),
        ]
    )

    # 2024-ish RB league means / spreads.
    rush_epa = 0.00 + 0.08 * skill + rng.normal(scale=0.02, size=n_total)
    rush_success = 0.42 + 0.04 * skill + rng.normal(scale=0.01, size=n_total)
    rec_epa = 0.10 + 0.15 * skill + rng.normal(scale=0.03, size=n_total)
    ryoe = 0.0 + 0.8 * skill + rng.normal(scale=0.2, size=n_total)
    yac_over_exp = 0.0 + 0.3 * skill + rng.normal(scale=0.1, size=n_total)
    catch_pct = 0.77 + 0.04 * skill + rng.normal(scale=0.02, size=n_total)

    return pd.DataFrame(
        {
            "player_id": range(1, n_total + 1),
            "gsis_id": [f"00-{i:07d}" for i in range(n_total)],
            "full_name": [f"RB {i}" for i in range(n_total)],
            "n_carries": n_carries.astype(int),
            "n_targets": n_targets.astype(int),
            "n_receptions": n_receptions.astype(int),
            "n_rec_with_xyac": n_rec_with_xyac.astype(int),
            "n_touches": n_touches.astype(int),
            "n_fumbles": n_fumbles.astype(int),
            "rush_epa_per_attempt": rush_epa,
            "rush_success_rate": rush_success,
            "rec_epa_per_target": rec_epa,
            "ryoe_per_attempt": ryoe,
            "yac_over_expected_per_rec": yac_over_exp,
            "catch_pct": catch_pct,
            "fumble_rate": fumble_rate,
        }
    )


# ---------------------------------------------------------------------------
# Pure-python: compute_grades
# ---------------------------------------------------------------------------


class TestComputeGrades:
    def test_output_columns_present(self) -> None:
        graded = compute_grades(_synth_features(seed=0))
        expected = {
            "player_id",
            "qualified",
            "rushing_sub_qualified",
            "receiving_sub_qualified",
            "confidence",
            "composite_z",
            "grade",
            "percentile",
            "raw_rb_ryoe_per_attempt",
            "adjusted_rb_ryoe_per_attempt",
            "z_rb_ryoe_per_attempt",
            "raw_rb_rush_epa_per_attempt",
            "adjusted_rb_rush_epa_per_attempt",
            "z_rb_rush_epa_per_attempt",
            "raw_rb_rush_success_rate",
            "adjusted_rb_rush_success_rate",
            "z_rb_rush_success_rate",
            "raw_rb_rec_epa_per_target",
            "adjusted_rb_rec_epa_per_target",
            "z_rb_rec_epa_per_target",
            "raw_rb_yac_over_expected_per_rec",
            "adjusted_rb_yac_over_expected_per_rec",
            "z_rb_yac_over_expected_per_rec",
            "raw_rb_catch_pct",
            "adjusted_rb_catch_pct",
            "z_rb_catch_pct",
            "raw_rb_fumble_rate",
            "adjusted_rb_fumble_rate",
            "z_rb_fumble_rate",
        }
        missing = expected - set(graded.columns)
        assert not missing, f"missing columns: {missing}"

    def test_grades_in_0_100(self) -> None:
        graded = compute_grades(_synth_features(seed=1))
        assert (graded["grade"] >= 0).all()
        assert (graded["grade"] <= 100).all()

    def test_qualified_flag_follows_threshold(self) -> None:
        graded = compute_grades(_synth_features(seed=2))
        # Touches < 120 -> unqualified; >= 120 -> qualified.
        assert (graded.loc[graded["n_touches"] >= 120, "qualified"]).all()
        assert not (graded.loc[graded["n_touches"] < 120, "qualified"]).any()

    def test_sub_grade_thresholds(self) -> None:
        graded = compute_grades(_synth_features(seed=3))
        # 80 carries / 40 targets sub-grade thresholds.
        assert (graded.loc[graded["n_carries"] >= 80, "rushing_sub_qualified"]).all()
        assert not (graded.loc[graded["n_carries"] < 80, "rushing_sub_qualified"]).any()
        assert (graded.loc[graded["n_targets"] >= 40, "receiving_sub_qualified"]).all()
        assert not (graded.loc[graded["n_targets"] < 40, "receiving_sub_qualified"]).any()

    def test_pure_thumper_gets_valid_grade(self) -> None:
        """RB with 0 targets still receives a finite grade (not NaN).

        Exercises the "n=0 -> z=0 neutralize" policy from ADR-0014.
        """
        df = _synth_features(seed=4).iloc[:1].copy()
        df["n_targets"] = 0
        df["n_receptions"] = 0
        df["n_rec_with_xyac"] = 0
        df["n_touches"] = df["n_carries"]  # touches = carries only
        df["rec_epa_per_target"] = np.nan  # undefined (no targets)
        df["yac_over_expected_per_rec"] = np.nan
        df["catch_pct"] = np.nan
        # Fumbles only on rushes
        df["fumble_rate"] = df["n_fumbles"].astype(float) / np.maximum(df["n_touches"], 1)

        graded = compute_grades(df)
        assert not pd.isna(graded.iloc[0]["grade"])
        assert 0 <= graded.iloc[0]["grade"] <= 100
        # All three receiving component z-scores should be NaN raw (no data)
        # but will not have propagated NaN into composite — that's the whole
        # point of the neutralization.
        assert not pd.isna(graded.iloc[0]["composite_z"])

    def test_pass_game_specialist_qualifies_via_touches(self) -> None:
        """Ekeler-type (50 carries + 80 targets -> ~112 touches) sits
        just below the 120-touch composite threshold. Bump targets to
        90 and verify they qualify."""
        df = _synth_features(seed=5).iloc[:1].copy()
        df["n_carries"] = 50
        df["n_targets"] = 90
        df["n_receptions"] = 70
        df["n_rec_with_xyac"] = 70
        df["n_touches"] = df["n_carries"] + df["n_receptions"]
        graded = compute_grades(df)
        assert bool(graded.iloc[0]["qualified"]) is True

    def test_fumble_penalty_hurts_composite(self) -> None:
        """Two identical RBs except one fumbles more — the fumbler should
        have a worse composite (negative weight on fumble rate)."""
        base = _synth_features(seed=6).iloc[:2].copy().reset_index(drop=True)
        # Make both statistically identical on the other metrics.
        for col in (
            "rush_epa_per_attempt",
            "rush_success_rate",
            "rec_epa_per_target",
            "ryoe_per_attempt",
            "yac_over_expected_per_rec",
            "catch_pct",
            "n_carries",
            "n_targets",
            "n_receptions",
            "n_rec_with_xyac",
            "n_touches",
        ):
            base.loc[1, col] = base.loc[0, col]
        # Player 0: clean; player 1: high fumble rate.
        base.loc[0, "fumble_rate"] = 0.002
        base.loc[1, "fumble_rate"] = 0.040
        base.loc[0, "n_fumbles"] = int(base.loc[0, "n_touches"] * 0.002)
        base.loc[1, "n_fumbles"] = int(base.loc[1, "n_touches"] * 0.040)
        # Synth cohort of just these two + a few others so qualified SD
        # is defined.
        extras = _synth_features(seed=7).iloc[:6]
        full = pd.concat([base, extras], ignore_index=True)
        full["player_id"] = range(1, len(full) + 1)

        graded = compute_grades(full)
        clean = graded.iloc[0]
        fumbler = graded.iloc[1]
        assert clean["grade"] > fumbler["grade"]

    def test_skill_monotonic_within_feature_backs(self) -> None:
        graded = compute_grades(_synth_features(seed=8))
        # First 6 rows are feature backs in descending skill order.
        feature = graded.iloc[:6]
        assert feature.iloc[0]["grade"] > feature.iloc[-1]["grade"]

    def test_confidence_caps_at_one(self) -> None:
        graded = compute_grades(_synth_features(seed=9))
        assert (graded["confidence"] <= 1.0).all()
        assert (graded.loc[graded["n_touches"] >= 250, "confidence"] == 1.0).all()

    def test_percentile_bounds(self) -> None:
        graded = compute_grades(_synth_features(seed=10))
        assert (graded["percentile"] >= 0).all()
        assert (graded["percentile"] <= 100).all()

    def test_deterministic(self) -> None:
        a = compute_grades(_synth_features(seed=42))
        b = compute_grades(_synth_features(seed=42))
        pd.testing.assert_frame_equal(a, b)


class TestDataTier:
    def test_tiers(self) -> None:
        assert _era_tier_for_season(2024) == (1, None)
        assert _era_tier_for_season(2016) == (1, None)
        assert _era_tier_for_season(2015) == (2, REASON_ERA_PRE_NGS)
        assert _era_tier_for_season(2005) == (3, REASON_ERA_PRE_NGS)


# ---------------------------------------------------------------------------
# Integration: requires Postgres + ingested 2024 plays + 2024 NGS
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
def has_2024_rb_data(conn):
    n_plays = conn.execute(
        text("SELECT COUNT(*) FROM plays WHERE season=2024 AND rush_attempt")
    ).scalar()
    n_ngs = conn.execute(
        text("SELECT COUNT(*) FROM ngs_rushing WHERE season=2024 AND week=0")
    ).scalar()
    if not n_plays or not n_ngs:
        pytest.skip(
            "2024 plays or ngs_rushing not ingested; "
            "run `nflgrades ingest pbp --season 2024` and "
            "`nflgrades ingest ngs --stat-type rushing --season 2024`"
        )
    return True


class TestExtractFeatures:
    def test_returns_rbs(self, conn, has_2024_rb_data) -> None:
        df = extract_features(conn, 2024)
        assert not df.empty
        expected = {
            "player_id",
            "gsis_id",
            "full_name",
            "n_carries",
            "n_targets",
            "n_receptions",
            "n_rec_with_xyac",
            "n_touches",
            "n_fumbles",
            "rush_epa_per_attempt",
            "rush_success_rate",
            "rec_epa_per_target",
            "ryoe_per_attempt",
            "yac_over_expected_per_rec",
            "catch_pct",
            "fumble_rate",
        }
        assert expected.issubset(df.columns)

    def test_feature_ranges_plausible(self, conn, has_2024_rb_data) -> None:
        df = extract_features(conn, 2024)
        # Touches bounded by the minimum-to-grade threshold.
        assert (df["n_touches"] >= 30).all()
        # Rushing EPA/att for RBs in 2024 should fall within a sane band.
        rushing = df.dropna(subset=["rush_epa_per_attempt"])
        assert rushing["rush_epa_per_attempt"].between(-1.0, 1.0).all()

    def test_xyac_coverage_on_receiving_rbs(self, conn, has_2024_rb_data) -> None:
        """nflfastR's xYAC model should score >=95% of receptions for
        RBs who have enough of a receiving role to be useful. Guards
        against a regression where ``xyac_mean_yardage`` silently stops
        being ingested (dropping coverage to 0 and re-creating the
        original caveat)."""
        df = extract_features(conn, 2024)
        route_runners = df[df["n_receptions"] >= 20]
        assert len(route_runners) >= 10, "expected at least 10 RBs with 20+ receptions in 2024"
        coverage = route_runners["n_rec_with_xyac"] / route_runners["n_receptions"].clip(lower=1)
        assert (coverage >= 0.95).mean() >= 0.95, (
            f"xYAC coverage regressed: {(coverage >= 0.95).mean():.2%} of "
            "20-rec RBs have >=95% of their completions scored"
        )

    def test_fumble_totals_are_sane(self, conn, has_2024_rb_data) -> None:
        """RB fumble totals should land in a plausible band. A full
        season of NFL RBs historically sees roughly 40-150 fumbles
        depending on how the filter draws the line. Guards against
        `fumble` silently collapsing to all-NULL (which would surface
        as 0) or picking up non-ball-carrier plays."""
        df = extract_features(conn, 2024)
        total = int(df["n_fumbles"].sum())
        assert 20 <= total <= 250, f"RB fumble total out of band: {total}"


class TestWriteResults:
    def test_roundtrip_into_tables(self, conn, has_2024_rb_data) -> None:
        # Use a sentinel season so we don't collide with real data (the
        # outer transaction rolls back anyway, but be explicit).
        features = extract_features(conn, 2024).head(20).copy()
        graded = compute_grades(features)

        n_components, n_grades = write_results(conn, graded, 1998)

        # stat_components: 7 RB v1 components per player.
        assert n_components == 7 * len(graded)
        assert n_grades == graded["grade"].notna().sum()

        grade_row = conn.execute(
            text(
                "SELECT composite_grade, qualified, data_tier, data_tier_reason "
                "FROM season_grades WHERE season=1998 AND position=:p LIMIT 1"
            ),
            {"p": POSITION},
        ).first()
        assert grade_row is not None
        assert 0 <= grade_row[0] <= 100
        # 1998 predates the EPA model -> tier 3 by _era_tier_for_season.
        assert grade_row[2] == 3
        assert grade_row[3] == REASON_ERA_PRE_NGS
