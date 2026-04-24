"""End-to-end tests for the WR grading pipeline (ADR-0015).

Mirrors test_rb.py structure:
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
from nfl_grades.grading.wr import (
    POSITION,
    compute_grades,
    extract_features,
    write_results,
)

# ---------------------------------------------------------------------------
# Synthetic WR cohort
# ---------------------------------------------------------------------------


def _synth_features(
    *,
    n_wr1: int = 8,
    n_wr2: int = 6,
    n_wr3: int = 4,
    seed: int = 0,
) -> pd.DataFrame:
    """Build a realistic synthetic WR cohort.

    Three archetypes:
        - WR1s: 120-160 targets. Full z-score population, qualified.
        - WR2s: 70-100 targets. Qualified.
        - WR3s: 30-55 targets. Some qualified, some not.

    Within each archetype skill varies linearly by index so tests can
    make ordering assertions.
    """
    rng = np.random.default_rng(seed)

    def skill_line(n: int, hi: float, lo: float) -> np.ndarray:
        return np.linspace(hi, lo, n)

    n_total = n_wr1 + n_wr2 + n_wr3

    n_targets = np.concatenate(
        [
            rng.integers(120, 161, size=n_wr1),
            rng.integers(70, 101, size=n_wr2),
            rng.integers(30, 56, size=n_wr3),
        ]
    )
    # Roughly 65% catch rate for WRs (slightly below RBs because of
    # deeper average target depth).
    n_receptions = (n_targets * 0.64).astype(int)
    # xYAC coverage >95% in the modern era; treat 1:1 in synthetic.
    n_rec_with_xyac = n_receptions.copy()

    # Team pass volume: roughly 550 REG-season pass attempts per team
    # over ~17 games = ~32/game. An "active" WR appearing in most games
    # gets denominators in the 400-550 range.
    n_team_pass_att_active = np.concatenate(
        [
            rng.integers(480, 561, size=n_wr1),
            rng.integers(380, 500, size=n_wr2),
            rng.integers(220, 400, size=n_wr3),
        ]
    )

    n_fumbles = rng.integers(0, 2, size=n_total)
    fumble_rate = n_fumbles.astype(float) / np.maximum(n_receptions, 1)

    skill = np.concatenate(
        [
            skill_line(n_wr1, 1.3, -0.3),
            skill_line(n_wr2, 0.6, -0.6),
            skill_line(n_wr3, 0.3, -0.3),
        ]
    )

    # 2024-ish WR league means / spreads.
    rec_epa = 0.10 + 0.10 * skill + rng.normal(scale=0.03, size=n_total)
    success_rate = 0.47 + 0.04 * skill + rng.normal(scale=0.015, size=n_total)
    yac_over_exp = 0.0 + 0.35 * skill + rng.normal(scale=0.15, size=n_total)
    separation = 2.9 + 0.30 * skill + rng.normal(scale=0.10, size=n_total)

    # Target earn rate hovers near 0.18-0.25 for WR1s, 0.13-0.18 for
    # WR2s. Derive from targets / team_pass_att_active so the math is
    # consistent with what extract_features would produce.
    target_earn_rate = n_targets.astype(float) / np.maximum(n_team_pass_att_active, 1)

    return pd.DataFrame(
        {
            "player_id": range(1, n_total + 1),
            "gsis_id": [f"00-{i:07d}" for i in range(n_total)],
            "full_name": [f"WR {i}" for i in range(n_total)],
            "n_targets": n_targets.astype(int),
            "n_receptions": n_receptions.astype(int),
            "n_rec_with_xyac": n_rec_with_xyac.astype(int),
            "n_team_pass_att_active": n_team_pass_att_active.astype(int),
            "n_fumbles": n_fumbles.astype(int),
            "rec_epa_per_target": rec_epa,
            "success_rate_per_target": success_rate,
            "yac_over_expected_per_rec": yac_over_exp,
            "separation": separation,
            "target_earn_rate": target_earn_rate,
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
            "confidence",
            "composite_z",
            "grade",
            "percentile",
            "raw_wr_rec_epa_per_target",
            "adjusted_wr_rec_epa_per_target",
            "z_wr_rec_epa_per_target",
            "raw_wr_yac_over_expected_per_rec",
            "adjusted_wr_yac_over_expected_per_rec",
            "z_wr_yac_over_expected_per_rec",
            "raw_wr_separation",
            "adjusted_wr_separation",
            "z_wr_separation",
            "raw_wr_target_earn_rate",
            "adjusted_wr_target_earn_rate",
            "z_wr_target_earn_rate",
            "raw_wr_success_rate_per_target",
            "adjusted_wr_success_rate_per_target",
            "z_wr_success_rate_per_target",
            "raw_wr_fumble_rate",
            "adjusted_wr_fumble_rate",
            "z_wr_fumble_rate",
        }
        missing = expected - set(graded.columns)
        assert not missing, f"missing columns: {missing}"

    def test_grades_in_0_100(self) -> None:
        graded = compute_grades(_synth_features(seed=1))
        assert (graded["grade"] >= 0).all()
        assert (graded["grade"] <= 100).all()

    def test_qualified_flag_follows_threshold(self) -> None:
        graded = compute_grades(_synth_features(seed=2))
        # Targets < 50 -> unqualified; >= 50 -> qualified.
        assert (graded.loc[graded["n_targets"] >= 50, "qualified"]).all()
        assert not (graded.loc[graded["n_targets"] < 50, "qualified"]).any()

    def test_missing_separation_neutralizes_to_zero(self) -> None:
        """A WR below NGS's volume threshold has separation = NaN.
        The grader should still produce a finite composite by
        neutralizing that component's z to 0, not propagating NaN."""
        df = _synth_features(seed=3).iloc[:1].copy()
        df["separation"] = np.nan  # simulate no NGS row
        # Need a cohort so z-scores are defined.
        others = _synth_features(seed=4)
        df = pd.concat([df, others], ignore_index=True)
        df["player_id"] = range(1, len(df) + 1)

        graded = compute_grades(df)
        subject = graded.iloc[0]
        assert pd.isna(subject["z_wr_separation"]), (
            "stat_components z should preserve NaN for UI honesty"
        )
        assert not pd.isna(subject["composite_z"]), (
            "composite must be defined even when a component is NaN"
        )
        assert 0 <= subject["grade"] <= 100

    def test_fumble_penalty_hurts_composite(self) -> None:
        """Two otherwise-identical WRs — the fumbler should grade
        below the clean one because fumble rate enters with a negative
        weight."""
        base = _synth_features(seed=5).iloc[:2].copy().reset_index(drop=True)
        for col in (
            "n_targets",
            "n_receptions",
            "n_rec_with_xyac",
            "n_team_pass_att_active",
            "rec_epa_per_target",
            "success_rate_per_target",
            "yac_over_expected_per_rec",
            "separation",
            "target_earn_rate",
        ):
            base.loc[1, col] = base.loc[0, col]
        base.loc[0, "fumble_rate"] = 0.002
        base.loc[1, "fumble_rate"] = 0.050
        base.loc[0, "n_fumbles"] = 0
        base.loc[1, "n_fumbles"] = 3

        extras = _synth_features(seed=6).iloc[:8]
        full = pd.concat([base, extras], ignore_index=True)
        full["player_id"] = range(1, len(full) + 1)

        graded = compute_grades(full)
        clean = graded.iloc[0]
        fumbler = graded.iloc[1]
        assert clean["grade"] > fumbler["grade"]

    def test_skill_monotonic_within_wr1s(self) -> None:
        """First n_wr1 rows are WR1s in descending skill order — best
        should outgrade worst."""
        graded = compute_grades(_synth_features(seed=7))
        wr1s = graded.iloc[:8]
        assert wr1s.iloc[0]["grade"] > wr1s.iloc[-1]["grade"]

    def test_confidence_caps_at_one(self) -> None:
        graded = compute_grades(_synth_features(seed=8))
        assert (graded["confidence"] <= 1.0).all()
        # ADR-0015: confidence saturates at 100 targets.
        assert (graded.loc[graded["n_targets"] >= 100, "confidence"] == 1.0).all()

    def test_percentile_bounds(self) -> None:
        graded = compute_grades(_synth_features(seed=9))
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
# Integration: requires Postgres + ingested 2024 plays + 2024 NGS receiving
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
def has_2024_wr_data(conn):
    n_plays = conn.execute(
        text("SELECT COUNT(*) FROM plays WHERE season=2024 AND pass_attempt")
    ).scalar()
    n_ngs = conn.execute(
        text("SELECT COUNT(*) FROM ngs_receiving WHERE season=2024 AND week=0")
    ).scalar()
    if not n_plays or not n_ngs:
        pytest.skip(
            "2024 plays or ngs_receiving not ingested; "
            "run `nflgrades ingest pbp --season 2024` and "
            "`nflgrades ingest ngs --stat-type receiving --season 2024`"
        )
    return True


class TestExtractFeatures:
    def test_returns_wrs(self, conn, has_2024_wr_data) -> None:
        df = extract_features(conn, 2024)
        assert not df.empty
        expected = {
            "player_id",
            "gsis_id",
            "full_name",
            "n_targets",
            "n_receptions",
            "n_rec_with_xyac",
            "n_team_pass_att_active",
            "n_fumbles",
            "rec_epa_per_target",
            "success_rate_per_target",
            "yac_over_expected_per_rec",
            "separation",
            "target_earn_rate",
            "fumble_rate",
        }
        assert expected.issubset(df.columns)

    def test_feature_ranges_plausible(self, conn, has_2024_wr_data) -> None:
        df = extract_features(conn, 2024)
        # Targets bounded by the min-to-grade threshold.
        assert (df["n_targets"] >= 20).all()
        # Rec EPA/target for WRs in 2024 should fall within a sane band.
        receiving = df.dropna(subset=["rec_epa_per_target"])
        assert receiving["rec_epa_per_target"].between(-1.0, 1.0).all()
        # Target earn rate is a rate in [0, 1]. Qualified WRs usually
        # land between 0.10 and 0.30.
        earn = df.dropna(subset=["target_earn_rate"])
        assert (earn["target_earn_rate"] >= 0).all()
        assert (earn["target_earn_rate"] <= 1.0).all()

    def test_justin_jefferson_plausible_stats(self, conn, has_2024_wr_data) -> None:
        """Jefferson 2024: heavy usage, positive EPA/target. Guards
        against any silent regression that swaps the WR feature query
        onto the wrong join."""
        df = extract_features(conn, 2024)
        jj = df[df["gsis_id"] == "00-0036322"]
        if len(jj) == 0:
            pytest.skip("Justin Jefferson not present in 2024 WR features")
        row = jj.iloc[0]
        # Jefferson 2024: 153 targets (actual). Accept a generous band
        # to absorb filter differences (garbage-time, 2-pt, etc.).
        assert 120 <= row["n_targets"] <= 180
        assert row["rec_epa_per_target"] > 0

    def test_separation_coverage_on_qualified_wrs(self, conn, has_2024_wr_data) -> None:
        """NGS publishes separation for effectively all volume WRs.
        Asserting >=95% on the qualified cohort catches a regression
        where NGS ingestion silently drops the receiving table."""
        df = extract_features(conn, 2024)
        qualified = df[df["n_targets"] >= 50]
        assert len(qualified) >= 30, (
            f"expected at least 30 qualified WRs in 2024, got {len(qualified)}"
        )
        coverage = qualified["separation"].notna().mean()
        assert coverage >= 0.95, (
            f"NGS separation coverage regressed: {coverage:.2%} of qualified WRs have a value"
        )

    def test_xyac_coverage_on_wr_receptions(self, conn, has_2024_wr_data) -> None:
        """nflfastR xYAC should score the majority of WR receptions.

        WR coverage is lower than RB coverage because xYAC doesn't
        score certain deep-shot / spike / end-of-half situations, and
        WR target profiles are more diverse. On 2024, aggregate
        coverage for 30+ reception WRs lands around 95% and median
        per-player coverage around 96%, with some deep-threats as low
        as 78%. This assertion guards against a regression where
        ``xyac_mean_yardage`` silently stops being populated — a
        silent break would drop aggregate coverage to ~0.
        """
        df = extract_features(conn, 2024)
        route_runners = df[df["n_receptions"] >= 30]
        assert len(route_runners) >= 20, (
            f"expected at least 20 WRs with 30+ receptions in 2024, got {len(route_runners)}"
        )
        total_recs = int(route_runners["n_receptions"].sum())
        total_xyac = int(route_runners["n_rec_with_xyac"].sum())
        aggregate = total_xyac / max(total_recs, 1)
        assert aggregate >= 0.85, (
            f"aggregate xYAC coverage regressed: {aggregate:.2%} "
            f"({total_xyac}/{total_recs}) over WRs with 30+ receptions"
        )

    def test_fumble_totals_are_sane(self, conn, has_2024_wr_data) -> None:
        """WR fumble totals land in a plausible band. Guards against
        `fumble` quietly collapsing to all-NULL."""
        df = extract_features(conn, 2024)
        total = int(df["n_fumbles"].sum())
        assert 5 <= total <= 200, f"WR fumble total out of band: {total}"

    def test_target_earn_rate_distribution(self, conn, has_2024_wr_data) -> None:
        """Target earn rate should have a sensible distribution for
        qualified WRs — usually 0.10-0.30 for real WR1/WR2 roles."""
        df = extract_features(conn, 2024)
        qualified = df[df["n_targets"] >= 50].dropna(subset=["target_earn_rate"])
        median = qualified["target_earn_rate"].median()
        assert 0.10 <= median <= 0.25, (
            f"qualified-WR median target earn rate out of band: {median:.3f}"
        )


class TestWriteResults:
    def test_roundtrip_into_tables(self, conn, has_2024_wr_data) -> None:
        # Sentinel season so we don't collide with real data.
        features = extract_features(conn, 2024).head(20).copy()
        graded = compute_grades(features)

        n_components, n_grades = write_results(conn, graded, 1997)

        # 6 WR v1 components per player.
        assert n_components == 6 * len(graded)
        assert n_grades == graded["grade"].notna().sum()

        grade_row = conn.execute(
            text(
                "SELECT composite_grade, qualified, data_tier "
                "FROM season_grades WHERE season=1997 AND position=:p LIMIT 1"
            ),
            {"p": POSITION},
        ).first()
        assert grade_row is not None
        assert 0 <= grade_row[0] <= 100
        # 1997 predates the EPA model era -> tier 3.
        assert grade_row[2] == 3
