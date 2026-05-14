"""Tests for TE v1 grading (ADR-0016)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.grading.te import (
    assign_te_role,
    compute_grades,
    compute_te_data_tier_and_reason,
    extract_features,
    write_results,
)
from nfl_grades.grading.weights import TE_COMPONENT_TARGET_EARN_RATE, TE_ROLE_BLOCKING


def _synth_te_cohort(
    n: int = 20,
    *,
    n_blocking: int = 2,
    seed: int = 0,
) -> pd.DataFrame:
    """Synthetic TE features with a few blocking-TE style rows (low
    target share, many snaps) for path coverage.
    """
    rng = np.random.default_rng(seed)
    n_targets = rng.integers(20, 120, size=n)
    snaps = np.clip((n_targets / rng.uniform(0.04, 0.22)).astype(int), 50, 800)
    n_receptions = (n_targets * 0.68).astype(int)
    n_rec_with_xyac = n_receptions
    n_team_pass = (n_targets * rng.uniform(3.0, 6.0)).astype(int)
    # FTN drop charting (2022+): catchable balls ≈ targets * 0.75, drops 0-4.
    n_catchable = (n_targets * 0.75).astype(int)
    n_drops = rng.integers(0, 4, size=n)
    drop_rate = n_drops / np.maximum(n_catchable, 1)
    skill = np.linspace(1.0, -0.5, n)
    rec_epa = 0.12 + 0.08 * skill
    yac_oe = 0.1 * skill
    succ = 0.5 + 0.03 * skill
    sep = 2.5 + 0.2 * skill
    for i in range(n_blocking):
        n_targets[i] = 25
        snaps[i] = 450
        n_receptions[i] = 16
        n_rec_with_xyac[i] = 16
        n_team_pass[i] = 550
        n_catchable[i] = 19
    df = pd.DataFrame(
        {
            "player_id": range(1, n + 1),
            "gsis_id": [f"00-{i:07d}" for i in range(n)],
            "full_name": [f"TE {i}" for i in range(n)],
            "n_targets": n_targets,
            "n_receptions": n_receptions,
            "n_rec_with_xyac": n_rec_with_xyac,
            "n_team_pass_att_active": n_team_pass,
            "snaps_offense": snaps,
            "n_catchable_balls": n_catchable,
            "n_drops": n_drops,
            "rec_epa_per_target": rec_epa,
            "yac_over_expected_per_rec": yac_oe,
            "success_rate_per_target": succ,
            "separation": sep,
            "target_earn_rate": n_targets / np.maximum(n_team_pass, 1),
            "drop_rate": drop_rate,
        }
    )
    df["role"] = [
        assign_te_role(int(r["n_targets"]), int(r["snaps_offense"])) for _, r in df.iterrows()
    ]
    return df


class TestComputeGrades:
    def test_blocking_uses_different_composite(self) -> None:
        base = _synth_te_cohort(seed=1)
        s = 2024
        a = compute_grades(base, s)
        # Same features, forced blocking role -> TE_V1_BLOCKING_WEIGHTS path
        b = base.copy()
        b.loc[0, "role"] = TE_ROLE_BLOCKING
        g = compute_grades(b, s)
        assert a.loc[0, "role"] != TE_ROLE_BLOCKING
        assert g.loc[0, "role"] == TE_ROLE_BLOCKING
        assert a.loc[0, "grade"] != g.loc[0, "grade"]
        assert 0 <= g.loc[0, "grade"] <= 100

    def test_tier_reason_blocking_modern_era(self) -> None:
        assert compute_te_data_tier_and_reason(2024, TE_ROLE_BLOCKING) == (2, "role_blocking_te")

    def test_qualified_40(self) -> None:
        g = compute_grades(_synth_te_cohort(seed=2), 2023)
        assert (g.loc[g["n_targets"] >= 40, "qualified"]).all()
        assert not (g.loc[g["n_targets"] < 40, "qualified"]).any()


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
def has_te_data(conn):
    n = conn.execute(text("SELECT COUNT(*) FROM plays WHERE season=2024 AND pass_attempt")).scalar()
    ngs = conn.execute(
        text("SELECT COUNT(*) FROM ngs_receiving WHERE season=2024 AND week=0")
    ).scalar()
    if not n or not ngs:
        pytest.skip("ingest 2024 pbp + ngs for TE tests")
    return True


class TestExtractFeatures:
    def test_not_empty_2024(self, conn, has_te_data) -> None:
        df = extract_features(conn, 2024)
        assert not df.empty
        assert (df["n_targets"] >= 15).all()
        assert "role" in df.columns
        assert "snaps_offense" in df.columns


class TestWriteResults:
    def test_roundtrip(self, conn, has_te_data) -> None:
        f = extract_features(conn, 2024).head(12).copy()
        g = compute_grades(f, 2024)
        n_c, n_g = write_results(conn, g, 1994)
        assert n_c == 6 * len(g)
        assert n_g == g["grade"].notna().sum()

        # ADR-0016: blocking TEs write used_in_composite=FALSE on the
        # te_target_earn_rate row only. All other components are TRUE, and
        # non-blocking TEs are TRUE for every component. Use season_grades.role
        # as the source of truth for the classification we just wrote.
        n_blocking = conn.execute(
            text(
                "SELECT COUNT(*) FROM season_grades "
                "WHERE season = :s AND position = 'TE' AND role = :r"
            ),
            {"s": 1994, "r": TE_ROLE_BLOCKING},
        ).scalar()

        earn_false = conn.execute(
            text(
                "SELECT COUNT(*) FROM stat_components "
                "WHERE season = :s AND component_name = :c "
                "AND used_in_composite IS NOT TRUE"
            ),
            {"s": 1994, "c": TE_COMPONENT_TARGET_EARN_RATE},
        ).scalar()
        assert earn_false == n_blocking

        other_false = conn.execute(
            text(
                "SELECT COUNT(*) FROM stat_components "
                "WHERE season = :s AND component_name <> :c "
                "AND used_in_composite IS NOT TRUE"
            ),
            {"s": 1994, "c": TE_COMPONENT_TARGET_EARN_RATE},
        ).scalar()
        assert other_false == 0
