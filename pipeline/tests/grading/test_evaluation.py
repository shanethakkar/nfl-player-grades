"""Tests for the reputation-free evaluation harness (ADR-0029): synthetic
Component panels with known structure in, Reliability / Portability /
prediction estimates out."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_grades.grading import evaluation as ev
from nfl_grades.grading.evaluation import Estimate, Formula, WindowReport
from nfl_grades.grading.qb import _COMPONENT_SPECS as QB_SPECS
from nfl_grades.grading.qb import compute_grades as qb_compute_grades
from nfl_grades.grading.scoring import MIN_QUALIFIED_COHORT
from nfl_grades.grading.weights import QB_V1_SHRINKAGE_K, QB_V1_WEIGHTS

SEASONS = range(2016, 2026)
# Huge samples and a tiny k: shrinkage is negligible, so the synthetic
# values reach the composite unchanged.
BIG_N = 1_000_000.0
TINY_K = {"skill": 1.0, "noise": 1.0, "team": 1.0}


def _exact_sd(draws: np.ndarray, sd: float) -> np.ndarray:
    """Rescale draws to exactly the given SD, so expected correlations are
    exact rather than subject to one draw's sample variance."""
    return (draws - draws.mean()) / draws.std() * sd


def _synthetic(
    rng: np.random.Generator,
    *,
    n_players: int = 60,
    skill_sd: float = 0.0,
    team_sd: float = 0.0,
    noise_sd: float = 1.0,
    change_rate: float = 0.0,
    n_teams: int = 32,
    component: str = "skill",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A one-Component panel: each half-season value is player skill + team
    offset + independent noise; the full season is the mean of the halves.
    Each season a player moves to a random other team with ``change_rate``."""
    skill = _exact_sd(rng.normal(size=n_players), skill_sd)
    offsets = _exact_sd(rng.normal(size=n_teams), team_sd)
    team = rng.integers(0, n_teams, n_players)
    panel_rows, roster_rows = [], []
    for season in SEASONS:
        if season > SEASONS.start:
            moves = rng.random(n_players) < change_rate
            team = np.where(moves, (team + rng.integers(1, n_teams, n_players)) % n_teams, team)
        for p in range(n_players):
            odd, even = skill[p] + offsets[team[p]] + rng.normal(0, noise_sd, 2)
            for split, raw in (("odd", odd), ("even", even), ("full", (odd + even) / 2)):
                panel_rows.append((p, season, split, component, raw, BIG_N))
            roster_rows.append((p, season, f"T{team[p]}", True))
    panel = pd.DataFrame(
        panel_rows, columns=["player_id", "season", "split", "component", "raw", "n"]
    )
    roster = pd.DataFrame(roster_rows, columns=["player_id", "season", "team", "qualified"])
    return panel, roster


def _evaluate(panel, roster, current, proposed=None, **kwargs) -> dict[str, WindowReport]:
    reports = ev.evaluate(
        panel,
        roster,
        current,
        proposed=proposed,
        primary=kwargs.pop("primary", "skill"),
        n_boot=kwargs.pop("n_boot", 400),
        **kwargs,
    )
    return {r.name: r for r in reports}


ONE_COMPONENT = Formula(weights={"skill": 1.0}, shrinkage_k=TINY_K)
ALL_SEASONS = {"all": SEASONS}


class TestHandComputed:
    def test_spearman_brown(self) -> None:
        assert ev.spearman_brown(0.5) == pytest.approx(2 / 3)
        assert ev.spearman_brown(0.0) == 0.0
        assert ev.spearman_brown(0.25, factor=3) == pytest.approx(0.75 / 1.5)

    def test_fisher_ci(self) -> None:
        # z = atanh(.5) = .5493, se = 1/sqrt(25) = .2 -> tanh(.5493 -/+ .392)
        lo, hi = ev.fisher_ci(0.5, 28)
        assert lo == pytest.approx(0.1560, abs=1e-4)
        assert hi == pytest.approx(0.7358, abs=1e-4)

    def test_reliability_ci_is_the_spearman_brown_of_the_fisher_interval(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0)
        est = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"]
        rel = est.current["reliability"]

        pairs = ev.reliability_pairs(ev.score_panel(panel, roster, ONE_COMPONENT), SEASONS)
        r = np.corrcoef(pairs["x"], pairs["y"])[0, 1]
        lo, hi = ev.fisher_ci(r, len(pairs))
        assert rel.n == len(pairs)
        assert rel.value == pytest.approx(ev.spearman_brown(r))
        assert (rel.lo, rel.hi) == pytest.approx((ev.spearman_brown(lo), ev.spearman_brown(hi)))


class TestReliability:
    def test_pure_noise_has_reliability_near_zero(self, rng) -> None:
        panel, roster = _synthetic(rng, n_players=250, noise_sd=1.0)

        rel = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"].current[
            "reliability"
        ]

        assert abs(rel.value) < 0.15
        assert rel.lo < 0 < rel.hi

    def test_equal_signal_and_half_season_noise_gives_two_thirds(self, rng) -> None:
        # Var(skill) = Var(noise per half) -> half-vs-half r = .5 -> SB = .667
        panel, roster = _synthetic(rng, n_players=150, skill_sd=1.0, noise_sd=1.0)

        rel = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"].current[
            "reliability"
        ]

        assert rel.value == pytest.approx(2 / 3, abs=0.06)


class TestPortability:
    def test_team_offsets_persist_for_stayers_but_not_changers(self, rng) -> None:
        panel, roster = _synthetic(rng, n_players=80, team_sd=1.5, noise_sd=0.5, change_rate=0.3)

        est = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"].current

        assert est["yoy_stayers"].value > 0.7
        assert abs(est["portability"].value) < 0.25
        assert est["portability"].n > 100

    def test_player_skill_carries_over_for_changers(self, rng) -> None:
        panel, roster = _synthetic(rng, n_players=80, skill_sd=1.5, noise_sd=0.5, change_rate=0.3)

        est = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"].current

        assert est["portability"].value > 0.7


class TestNextSeason:
    def test_stable_skill_predicts_next_season_primary_component(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0, noise_sd=0.5)

        est = _evaluate(panel, roster, ONE_COMPONENT, windows=ALL_SEASONS)["all"].current

        assert est["next_primary"].value > 0.7
        assert est["yoy"].value > 0.7


class TestHoldOut:
    def test_windows_only_see_their_own_seasons(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0, change_rate=0.2)
        before = _evaluate(panel, roster, ONE_COMPONENT)

        # Scramble every hold-out season's values and teams. Nothing in the
        # fit window may move, including YoY pairs ending in 2022.
        holdout = panel["season"] >= 2023
        scrambled = panel.copy()
        scrambled.loc[holdout, "raw"] = rng.normal(0, 5, int(holdout.sum()))
        shuffled_roster = roster.copy()
        later = roster["season"] >= 2023
        shuffled_roster.loc[later, "team"] = "NEW"
        after = _evaluate(scrambled, shuffled_roster, ONE_COMPONENT)

        assert after["fit"].current == before["fit"].current
        assert after["holdout"].current != before["holdout"].current

    def test_default_windows_are_2016_2022_fit_and_2023_2025_holdout(self) -> None:
        assert {"fit": range(2016, 2023), "holdout": range(2023, 2026)} == ev.WINDOWS

    def test_pairs_straddling_the_split_belong_to_neither_window(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0)
        scores = ev.score_panel(panel, roster, ONE_COMPONENT)

        fit = ev.yoy_pairs(scores, roster, ev.WINDOWS["fit"])
        holdout = ev.yoy_pairs(scores, roster, ev.WINDOWS["holdout"])

        assert fit["season"].max() == 2021  # 2021 -> 2022
        assert holdout["season"].min() == 2023  # 2023 -> 2024


class TestPairedDeltas:
    def test_identical_formulas_have_zero_delta(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0, change_rate=0.2)

        delta = _evaluate(panel, roster, ONE_COMPONENT, ONE_COMPONENT)["fit"].delta

        assert delta is not None
        for est in delta.values():
            assert (est.value, est.lo, est.hi) == (0.0, 0.0, 0.0)

    def test_candidate_component_can_be_scored(self, rng) -> None:
        # Current Formula is pure noise; the proposal adds a reliable
        # Candidate that the panel carries alongside it.
        noise, roster = _synthetic(rng, noise_sd=1.0, component="noise")
        skill, _ = _synthetic(rng, skill_sd=1.0, noise_sd=0.5, component="skill")
        panel = pd.concat([noise, skill], ignore_index=True)
        current = Formula(weights={"noise": 1.0}, shrinkage_k=TINY_K)
        proposed = Formula(weights={"noise": 0.2, "skill": 0.8}, shrinkage_k=TINY_K)

        report = _evaluate(panel, roster, current, proposed)["holdout"]

        assert report.delta is not None
        assert report.delta["reliability"].lo > 0.3
        assert report.proposed is not None
        assert report.proposed["reliability"].value > report.current["reliability"].value

    def test_bootstrap_is_reproducible_with_a_seed(self, rng) -> None:
        noise, roster = _synthetic(rng, noise_sd=1.0, change_rate=0.2, component="noise")
        skill, _ = _synthetic(rng, skill_sd=1.0, component="skill")
        panel = pd.concat([noise, skill], ignore_index=True)
        current = Formula(weights={"noise": 1.0}, shrinkage_k=TINY_K)
        proposed = Formula(weights={"skill": 1.0}, shrinkage_k=TINY_K)

        a = _evaluate(panel, roster, current, proposed, seed=3)["fit"].delta
        b = _evaluate(panel, roster, current, proposed, seed=3)["fit"].delta

        assert a == b


class TestScorePanel:
    def test_full_season_composite_matches_the_grader(self, rng) -> None:
        # The harness scores the current Formula exactly as production does.
        n = 60
        features = pd.DataFrame(
            {
                "player_id": range(n),
                "n_dropbacks": rng.integers(20, 650, n),
                "epa_per_dropback": rng.normal(0.05, 0.15, n),
                "cpoe": rng.normal(0, 4, n),
                "success_rate": rng.normal(0.45, 0.05, n),
            }
        )
        features["n_pass_attempts"] = (features["n_dropbacks"] * 0.9).astype(int)
        features.loc[0, ["cpoe"]] = np.nan  # a QB with no CPOE: weights renormalize
        graded = qb_compute_grades(features)

        panel = ev.melt_features(features, QB_SPECS, season=2024, split="full")
        roster = pd.DataFrame(
            {
                "player_id": features["player_id"],
                "season": 2024,
                "team": "T",
                "qualified": graded["qualified"],
            }
        )
        scores = ev.score_panel(panel, roster, Formula(QB_V1_WEIGHTS, QB_V1_SHRINKAGE_K))

        expected = graded.loc[graded["qualified"]].set_index("player_id")["composite_z"]
        got = scores.set_index("player_id")["composite"]
        pd.testing.assert_series_equal(got.sort_index(), expected.sort_index(), check_names=False)

    def test_missing_shrinkage_k_is_an_error(self, rng) -> None:
        panel, roster = _synthetic(rng, skill_sd=1.0)
        with pytest.raises(ValueError, match="shrinkage k"):
            ev.score_panel(panel, roster, Formula(weights={"skill": 1.0}, shrinkage_k={}))


def _window(**deltas: tuple[float, float, float]) -> WindowReport:
    metrics = ("reliability", "portability", "yoy", "next_primary")
    est = {m: Estimate(0.5, 0.4, 0.6, 100) for m in metrics}
    delta = {m: Estimate(0.0, -0.01, 0.01, 100) for m in metrics}
    for m, (v, lo, hi) in deltas.items():
        delta[m] = Estimate(v, lo, hi, 100)
    return WindowReport("holdout", range(2023, 2026), est, est, delta)


class TestShipRule:
    def test_passes_on_a_clear_improvement_with_no_regression(self) -> None:
        verdict = ev.ship_rule(_window(reliability=(0.05, 0.02, 0.08)))
        assert verdict.passes

    def test_fails_without_a_clear_improvement(self) -> None:
        verdict = ev.ship_rule(_window(reliability=(0.02, -0.01, 0.05)))
        assert not verdict.passes

    def test_fails_when_portability_drops_beyond_noise(self) -> None:
        verdict = ev.ship_rule(
            _window(reliability=(0.05, 0.02, 0.08), portability=(-0.10, -0.18, -0.02))
        )
        assert not verdict.passes

    def test_next_season_prediction_counts_as_an_improvement(self) -> None:
        verdict = ev.ship_rule(_window(next_primary=(0.04, 0.01, 0.07)))
        assert verdict.passes

    def test_fails_when_a_guarded_metric_cannot_be_estimated(self) -> None:
        nan = float("nan")
        verdict = ev.ship_rule(_window(reliability=(0.05, 0.02, 0.08), portability=(nan, nan, nan)))
        assert not verdict.passes
        assert any("Portability" in r for r in verdict.reasons)


class TestThinData:
    def test_window_without_data_reports_nan_instead_of_failing(self, rng) -> None:
        noise, roster = _synthetic(rng, noise_sd=1.0, component="noise")
        current = Formula(weights={"noise": 1.0}, shrinkage_k=TINY_K)

        reports = _evaluate(
            noise, roster, current, current, windows={"fit": SEASONS, "empty": range(2030, 2032)}
        )

        assert reports["empty"].delta is not None
        assert np.isnan(reports["empty"].delta["reliability"].value)
        assert reports["empty"].current["reliability"].n == 0

    def test_season_splits_below_the_minimum_cohort_are_not_scored(self, rng) -> None:
        # Production refuses to grade fewer than MIN_QUALIFIED_COHORT players.
        panel, roster = _synthetic(rng, n_players=MIN_QUALIFIED_COHORT - 1, skill_sd=1.0)

        assert ev.score_panel(panel, roster, ONE_COMPONENT).empty
