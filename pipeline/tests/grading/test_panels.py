"""Tests for the evaluation harness's database panels (grading.panels).

The DB-backed tests read 2024 from whatever ``DATABASE_URL`` points at and
roll back. The reproduction test needs that season graded with the current
code: a stale database fails it, as it should.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from nfl_grades.db import get_engine
from nfl_grades.grading import evaluation, panels
from nfl_grades.grading.weights import TE_ROLE_BALANCED, TE_ROLE_BLOCKING

SEASON = 2024


class TestTeQualified:
    def test_a_qualified_blocking_te_is_an_error(self) -> None:
        # The harness scores every TE on the receiving Formula, which is
        # only right while no Qualified TE is blocking.
        features = pd.DataFrame(
            {"n_targets": [60, 10], "role": [TE_ROLE_BLOCKING, TE_ROLE_BLOCKING]}
        )
        with pytest.raises(ValueError, match="blocking"):
            panels.POSITIONS["TE"].qualified(features)

    def test_unqualified_blocking_tes_are_fine(self) -> None:
        features = pd.DataFrame(
            {"n_targets": [60, 10], "role": [TE_ROLE_BALANCED, TE_ROLE_BLOCKING]}
        )
        assert panels.POSITIONS["TE"].qualified(features).tolist() == [True, False]


@pytest.fixture(scope="module")
def conn():
    try:
        with get_engine().connect() as connection:
            tx = connection.begin()
            try:
                yield connection
            finally:
                tx.rollback()
    except OperationalError as e:
        pytest.skip(f"Postgres unavailable: {e}")


def test_half_season_ryoe_is_shrunk_by_its_ngs_attempts(conn) -> None:
    # Half-season RYOE comes from NGS weekly rows (10+ carry games only),
    # so its sample size is their attempts, not every carry. The full
    # season keeps the grader's sample size.
    panel = panels.load(conn, panels.POSITIONS["RB"], seasons=[SEASON]).panel
    n = panel.pivot_table(index=["split", "player_id"], columns="component", values="n")
    ryoe, carries = n["rb_ryoe_per_attempt"], n["rb_rush_epa_per_attempt"]
    pd.testing.assert_series_equal(ryoe.loc["full"], carries.loc["full"], check_names=False)
    # Per back, NGS attempts can exceed the grader's carries (no garbage-time
    # filter), but the skipped light games leave clearly fewer overall.
    for split in ("odd", "even"):
        assert ryoe.loc[split].sum() < 0.9 * carries.loc[split].sum()


@pytest.mark.parametrize("position", ["RB", "WR", "TE"])
class TestLoad:
    def test_every_formula_component_in_every_split(self, conn, position) -> None:
        source = panels.POSITIONS[position]
        data = panels.load(conn, source, seasons=[SEASON])
        for split in evaluation.SPLITS:
            rows = data.panel[data.panel["split"] == split]
            assert set(rows["component"]) == set(source.weights), split
        assert data.roster["qualified"].sum() >= 30
        assert data.roster.loc[data.roster["qualified"], "team"].notna().all()

    def test_full_season_reproduces_stored_grades(self, conn, position) -> None:
        stored = pd.DataFrame(
            conn.execute(
                text("""
                    SELECT g.player_id, g.composite_z, sc.component_name, sc.raw_value
                    FROM season_grades g
                    JOIN stat_components sc
                      ON sc.player_id = g.player_id AND sc.season = g.season
                    WHERE g.season = :season AND g.position = :position AND g.qualified
                      AND g.through_week IS NULL
                """),
                {"season": SEASON, "position": position},
            ).mappings()
        )
        if stored.empty:
            pytest.skip(f"no stored {position} grades for {SEASON}")

        source = panels.POSITIONS[position]
        data = panels.load(conn, source, seasons=[SEASON])
        scores = evaluation.score_panel(data.panel, data.roster, source.formula)
        full = scores[scores["split"] == "full"].set_index("player_id")["composite"]
        expected = stored.drop_duplicates("player_id").set_index("player_id")["composite_z"]
        assert sorted(full.index) == sorted(expected.index)
        np.testing.assert_allclose(full.loc[expected.index], expected, atol=1e-9)

        raw = data.panel[data.panel["split"] == "full"].merge(
            stored.rename(columns={"component_name": "component"}),
            on=["player_id", "component"],
        )
        assert len(raw) == len(stored)
        np.testing.assert_allclose(
            raw["raw"].to_numpy(float), raw["raw_value"].to_numpy(float), atol=1e-9
        )
