"""Per-position v1 grading weights.

v1 uses hand-picked weights (ADR-0013). Inverse-variance / YoY-stability
weighting is explicitly deferred — we want explainability first, then
tune once we have face-validity feedback.

Components here are the **stat_components.component_name** strings —
they must match what ``grading/qb.py`` et al. write to the DB.
"""

from __future__ import annotations

# ADR-0013: QB v1 weights. 50% EPA / 25% CPOE / 25% success rate.
QB_V1_WEIGHTS: dict[str, float] = {
    "qb_epa_per_dropback": 0.50,
    "qb_cpoe": 0.25,
    "qb_success_rate": 0.25,
}

# Empirical Bayes shrinkage strengths (ADR-0013). Units = "equivalent
# pseudo-sample size" — 150 dropbacks ≈ 5 games' worth.
QB_V1_SHRINKAGE_K: dict[str, float] = {
    "qb_epa_per_dropback": 150.0,
    "qb_cpoe": 100.0,
    "qb_success_rate": 150.0,
}

# ADR-0013: qualified = 200+ dropbacks for the regular season.
QB_V1_QUALIFIED_MIN_DROPBACKS: int = 200

# Confidence scales to 1.0 at 300 dropbacks (~half a starter's season).
QB_V1_CONFIDENCE_FULL_DROPBACKS: int = 300


# ---------------------------------------------------------------------------
# RB v1 (ADR-0014).
# ---------------------------------------------------------------------------

# Component names — these strings are written to stat_components.component_name
# and string-matched by the web app, so they're part of the public contract.
RB_COMPONENT_RYOE_PER_ATTEMPT: str = "rb_ryoe_per_attempt"
RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: str = "rb_rush_epa_per_attempt"
RB_COMPONENT_RUSH_SUCCESS_RATE: str = "rb_rush_success_rate"
RB_COMPONENT_REC_EPA_PER_TARGET: str = "rb_rec_epa_per_target"
RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "rb_yac_over_expected_per_rec"
RB_COMPONENT_CATCH_PCT: str = "rb_catch_pct"
RB_COMPONENT_FUMBLE_RATE: str = "rb_fumble_rate"

# ADR-0014: weights sum to 1.0. Rush 60% / Rec 35% / Security 5% (negative).
# Fumble rate enters with a *negative* weight — fewer fumbles is better.
RB_V1_WEIGHTS: dict[str, float] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: 0.28,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: 0.18,
    RB_COMPONENT_RUSH_SUCCESS_RATE: 0.14,
    RB_COMPONENT_REC_EPA_PER_TARGET: 0.18,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.12,
    RB_COMPONENT_CATCH_PCT: 0.05,
    RB_COMPONENT_FUMBLE_RATE: -0.05,
}

# Empirical Bayes shrinkage strengths. Larger k = more pull toward the
# league mean for low-sample players. Fumble rate gets a large k because
# year-over-year reliability of fumble rate is poor (~r=0.1-0.2) even
# with the recovery coin-flip removed by using `fumble` rather than
# `fumble_lost`.
RB_V1_SHRINKAGE_K: dict[str, float] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: 100.0,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: 100.0,
    RB_COMPONENT_RUSH_SUCCESS_RATE: 100.0,
    RB_COMPONENT_REC_EPA_PER_TARGET: 40.0,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    RB_COMPONENT_CATCH_PCT: 40.0,
    RB_COMPONENT_FUMBLE_RATE: 200.0,
}

# Which `n` column in the feature DataFrame pairs with each component.
# extract_features() must populate these columns.
RB_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: "n_carries",
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: "n_carries",
    RB_COMPONENT_RUSH_SUCCESS_RATE: "n_carries",
    RB_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    # YAC-over-expected is derived from plays.xyac_mean_yardage, so the
    # relevant n is receptions where the xYAC model produced a prediction.
    # In practice this is ~99% of RB completions, but we track the exact
    # count so shrinkage reflects measured receptions.
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    RB_COMPONENT_CATCH_PCT: "n_targets",
    RB_COMPONENT_FUMBLE_RATE: "n_touches",
}

# Which raw-value column in the feature DataFrame pairs with each component.
RB_V1_RAW_VALUE_COLS: dict[str, str] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: "ryoe_per_attempt",
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: "rush_epa_per_attempt",
    RB_COMPONENT_RUSH_SUCCESS_RATE: "rush_success_rate",
    RB_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    RB_COMPONENT_CATCH_PCT: "catch_pct",
    RB_COMPONENT_FUMBLE_RATE: "fumble_rate",
}

# NGS RYOE/att and YAC-over-expected are already context-adjusted upstream
# by Next Gen Stats' own models. When opponent adjustment is added in v2,
# these components must be SKIPPED (flag = True) to avoid double-adjusting.
# Purely documentary for v1 (no opp-adj implemented yet), but baked in now
# so v2 doesn't have to retrofit.
RB_V1_PRE_ADJUSTED: dict[str, bool] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: True,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: False,
    RB_COMPONENT_RUSH_SUCCESS_RATE: False,
    RB_COMPONENT_REC_EPA_PER_TARGET: False,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: True,
    RB_COMPONENT_CATCH_PCT: False,
    RB_COMPONENT_FUMBLE_RATE: False,
}

# ADR-0014: three separate qualification concepts.
# - MIN_TOUCHES_TO_GRADE: below this we skip entirely.
# - QUALIFIED_MIN_TOUCHES: appears in main leaderboard; used for z-score
#   population.
# - RUSHING_SUB_MIN_CARRIES / RECEIVING_SUB_MIN_TARGETS: thresholds for
#   displaying the per-skill sub-grades on the player page.
RB_V1_MIN_TOUCHES_TO_GRADE: int = 30
RB_V1_QUALIFIED_MIN_TOUCHES: int = 120
RB_V1_RUSHING_SUB_MIN_CARRIES: int = 80
RB_V1_RECEIVING_SUB_MIN_TARGETS: int = 40

# Confidence scales to 1.0 at 250 touches (~full-season starter workload).
RB_V1_CONFIDENCE_FULL_TOUCHES: int = 250


# ---------------------------------------------------------------------------
# WR v1 (ADR-0015).
# ---------------------------------------------------------------------------

# Component names — part of the public contract with the web app.
WR_COMPONENT_REC_EPA_PER_TARGET: str = "wr_rec_epa_per_target"
WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "wr_yac_over_expected_per_rec"
WR_COMPONENT_SEPARATION: str = "wr_separation"
WR_COMPONENT_TARGET_EARN_RATE: str = "wr_target_earn_rate"
WR_COMPONENT_SUCCESS_RATE_PER_TARGET: str = "wr_success_rate_per_target"
WR_COMPONENT_FUMBLE_RATE: str = "wr_fumble_rate"

# ADR-0015: sum of magnitudes = 0.95 (composite combiner normalizes by
# magnitude sum, so fumble contributes at its designed 5.3% share).
# Rough shape: 62% outcome (EPA + YAC), 28% process + usage
# (separation + earn rate + success), 5% ball security (negative).
WR_V1_WEIGHTS: dict[str, float] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: 0.35,
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.27,
    WR_COMPONENT_SEPARATION: 0.10,
    WR_COMPONENT_TARGET_EARN_RATE: 0.10,
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.08,
    WR_COMPONENT_FUMBLE_RATE: -0.05,
}

# Empirical Bayes shrinkage strengths. Target earn rate uses "team pass
# attempts while active" as its sample unit (the natural denominator of
# the rate), not games — the EB formulation wants to shrink toward
# league-mean target share weighted by the number of observations.
# Separation's k is slightly lower than EPA/success because NGS
# separation has higher year-over-year reliability than raw per-play
# efficiency metrics (a player's movement skill is more stable than
# their play-to-play outcomes).
WR_V1_SHRINKAGE_K: dict[str, float] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: 50.0,
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    WR_COMPONENT_SEPARATION: 40.0,
    WR_COMPONENT_TARGET_EARN_RATE: 200.0,
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: 50.0,
    WR_COMPONENT_FUMBLE_RATE: 100.0,
}

# Which `n` column in the feature DataFrame pairs with each component.
# extract_features() must populate these columns.
WR_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    # YAC-over-expected is derived from plays.xyac_mean_yardage (same
    # pattern as RB v1.1), so n is completions where xYAC was scored.
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    WR_COMPONENT_SEPARATION: "n_targets",
    # Team pass attempts while the WR was active — the natural
    # denominator of target earn rate and the right EB sample unit.
    WR_COMPONENT_TARGET_EARN_RATE: "n_team_pass_att_active",
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: "n_targets",
    # WRs only touch the ball on completions, so fumble denominator is
    # receptions (not targets). Keeps the rate comparable across
    # possession/deep-threat archetypes.
    WR_COMPONENT_FUMBLE_RATE: "n_receptions",
}

# Which raw-value column in the feature DataFrame pairs with each component.
WR_V1_RAW_VALUE_COLS: dict[str, str] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    WR_COMPONENT_SEPARATION: "separation",
    WR_COMPONENT_TARGET_EARN_RATE: "target_earn_rate",
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: "success_rate_per_target",
    WR_COMPONENT_FUMBLE_RATE: "fumble_rate",
}

# YAC-over-expected (xYAC model) and separation (NGS's DB-proximity
# model) are already context-adjusted upstream. When opponent adjustment
# lands in v2, these two must be SKIPPED to avoid double-adjusting.
WR_V1_PRE_ADJUSTED: dict[str, bool] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: False,
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: True,
    WR_COMPONENT_SEPARATION: True,
    WR_COMPONENT_TARGET_EARN_RATE: False,
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: False,
    WR_COMPONENT_FUMBLE_RATE: False,
}

# ADR-0015: two qualification tiers.
WR_V1_MIN_TARGETS_TO_GRADE: int = 20
WR_V1_QUALIFIED_MIN_TARGETS: int = 50

# Confidence scales to 1.0 at 100 targets (~6 per game, "real starter
# usage" rather than WR1 workload).
WR_V1_CONFIDENCE_FULL_TARGETS: int = 100


# ---------------------------------------------------------------------------
# TE v1 (ADR-0016).
# ---------------------------------------------------------------------------

TE_COMPONENT_REC_EPA_PER_TARGET: str = "te_rec_epa_per_target"
TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "te_yac_over_expected_per_rec"
TE_COMPONENT_SEPARATION: str = "te_separation"
TE_COMPONENT_TARGET_EARN_RATE: str = "te_target_earn_rate"
TE_COMPONENT_SUCCESS_RATE_PER_TARGET: str = "te_success_rate_per_target"
TE_COMPONENT_FUMBLE_RATE: str = "te_fumble_rate"

# Sum of |weights| = 0.95. Separation 7% (vs WR 10%) — NGS metric is
# WR-geometry-calibrated; TE matchups are noisier in the same number.
TE_V1_WEIGHTS: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 0.35,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.27,
    TE_COMPONENT_SEPARATION: 0.07,
    TE_COMPONENT_TARGET_EARN_RATE: 0.10,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.08,
    TE_COMPONENT_FUMBLE_RATE: -0.05,
}

# Blocking-TE (role) path: omit earn in composite; redistribute 0.10 to
# EPA+YAC in proportion 0.35/0.62 and 0.27/0.62.
TE_V1_BLOCKING_WEIGHTS: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 0.406,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.314,
    TE_COMPONENT_SEPARATION: 0.07,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.08,
    TE_COMPONENT_FUMBLE_RATE: -0.05,
}

# Per-position shrinkage: TE target earn k=100 (vs WR 200) for smaller
# cross-player dispersion in earn-rate.
TE_V1_SHRINKAGE_K: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 50.0,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    TE_COMPONENT_SEPARATION: 40.0,
    TE_COMPONENT_TARGET_EARN_RATE: 100.0,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 50.0,
    TE_COMPONENT_FUMBLE_RATE: 100.0,
}

TE_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    TE_COMPONENT_SEPARATION: "n_targets",
    TE_COMPONENT_TARGET_EARN_RATE: "n_team_pass_att_active",
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: "n_targets",
    TE_COMPONENT_FUMBLE_RATE: "n_receptions",
}

TE_V1_RAW_VALUE_COLS: dict[str, str] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    TE_COMPONENT_SEPARATION: "separation",
    TE_COMPONENT_TARGET_EARN_RATE: "target_earn_rate",
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: "success_rate_per_target",
    TE_COMPONENT_FUMBLE_RATE: "fumble_rate",
}

# Role labels stored on season_grades.role (app convention).
TE_ROLE_RECEIVING: str = "receiving_te"
TE_ROLE_BALANCED: str = "balanced_te"
TE_ROLE_BLOCKING: str = "blocking_te"

# data_tier_reason (ADR-0016) — not enum in DB, strings only.
TE_TIER_REASON_ROLE_BLOCKING: str = "role_blocking_te"
TE_TIER_REASON_ERA_AND_ROLE: str = "era_and_role"

# Min targets 15; qualified 40; confidence 70.
TE_V1_MIN_TARGETS_TO_GRADE: int = 15
TE_V1_QUALIFIED_MIN_TARGETS: int = 40
TE_V1_CONFIDENCE_FULL_TARGETS: int = 70

# Role thresholds (target share = targets / offensive snaps, season).
TE_V1_TARGET_RATE_RECEIVING: float = 0.10
TE_V1_TARGET_RATE_BALANCED_LO: float = 0.05
TE_V1_MIN_SNAPS_FOR_BLOCKING_LABEL: int = 200
