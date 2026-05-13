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


# ---------------------------------------------------------------------------
# CB v1 (ADR-0018).
# ---------------------------------------------------------------------------
# Data source: PFR advanced defensive coverage stats (pfr_def_coverage table)
# + nflverse player stats (def_pass_defended for PBU) + player_seasons
# (snaps_defense for target rate denominator).
# Coverage begins 2018 — earliest year PFR published per-CB target/comp data.
#
# Negative weights = lower is better (fewer completions/YAC/targets is good).
# Positive weights = higher is better (more INTs/PBUs is good).
#
# Formula rationale (ADR-0018):
#   comp_pct_allowed (31%): primary coverage quality signal — did the CB win
#     the rep? Most direct measure available.
#   yac_per_rec_allowed (26%): post-catch damage. Captures cushion allowed and
#     tackling quality at the catch point. Different from comp% — a CB can
#     allow the catch but limit YAC.
#   target_rate (11%): targets per defensive snap. Elite CBs get avoided;
#     QBs scheme away from them. Independent of what happens when they do
#     throw — comp% doesn't capture avoidance. Denominator: defensive snaps
#     (not coverage snaps, which aren't in the data) so it conflates avoidance
#     with role depth. Modest weight reflects this limitation.
#   int_rate (14%): INTs per target. Highly variable but the ultimate positive
#     play. k=80 shrinks heavily for low-target CBs.
#   pbu_rate (17%): pass breakups per target. ~3× more frequent than INTs so
#     more stable. Captures active coverage that stops plays short of INT.
#     Higher weight than INT because reliability is better at same k.
#
# TD rate was dropped in v1.1: TDs allowed are rare (2–5/season), highly
# variable (r<0.15 YoY), and partially redundant with comp% and YAC. At 7%
# weight, noise contribution exceeded signal contribution.
#
# The composite combiner normalizes by sum of |weights|, so magnitudes here
# are proportional shares, not percentage points.
# ---------------------------------------------------------------------------

CB_COMPONENT_COMP_PCT_ALLOWED: str = "cb_comp_pct_allowed"
CB_COMPONENT_YAC_PER_REC_ALLOWED: str = "cb_yac_per_rec_allowed"
CB_COMPONENT_TARGET_RATE: str = "cb_target_rate"
CB_COMPONENT_INT_RATE: str = "cb_int_rate"
CB_COMPONENT_PBU_RATE: str = "cb_pbu_rate"

CB_V1_WEIGHTS: dict[str, float] = {
    CB_COMPONENT_COMP_PCT_ALLOWED:    -0.22,
    CB_COMPONENT_YAC_PER_REC_ALLOWED: -0.18,
    CB_COMPONENT_TARGET_RATE:         -0.08,
    CB_COMPONENT_INT_RATE:             0.10,
    CB_COMPONENT_PBU_RATE:             0.12,
}

# Empirical Bayes shrinkage strengths.
# - comp% and YAC: k=50 targets (~3-game workload).
# - INT and PBU rates: k=80 (rare/noisy events, r<0.25 YoY).
# - target_rate: k=150 snaps. QB avoidance is more stable than rate stats
#   (scheme-driven, not event-driven), so less shrinkage is needed; but the
#   snap denominator doesn't isolate coverage snaps, warranting some pull
#   toward the mean for low-snap players.
CB_V1_SHRINKAGE_K: dict[str, float] = {
    CB_COMPONENT_COMP_PCT_ALLOWED:    50.0,
    CB_COMPONENT_YAC_PER_REC_ALLOWED: 50.0,
    CB_COMPONENT_TARGET_RATE:         150.0,
    CB_COMPONENT_INT_RATE:            80.0,
    CB_COMPONENT_PBU_RATE:            80.0,
}

# Which raw computed column in the feature DataFrame pairs with each component.
CB_V1_RAW_VALUE_COLS: dict[str, str] = {
    CB_COMPONENT_COMP_PCT_ALLOWED:    "comp_pct_allowed",
    CB_COMPONENT_YAC_PER_REC_ALLOWED: "yac_per_rec_allowed",
    CB_COMPONENT_TARGET_RATE:         "target_rate",
    CB_COMPONENT_INT_RATE:            "int_rate",
    CB_COMPONENT_PBU_RATE:            "pbu_rate",
}

# Sample-size denominator for each component's EB shrinkage.
# target_rate uses snaps_defense (not targets) because its natural
# denominator is opportunities to be targeted, not actual targets.
CB_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    CB_COMPONENT_COMP_PCT_ALLOWED:    "targets",
    CB_COMPONENT_YAC_PER_REC_ALLOWED: "targets",
    CB_COMPONENT_TARGET_RATE:         "snaps_defense",
    CB_COMPONENT_INT_RATE:            "targets",
    CB_COMPONENT_PBU_RATE:            "targets",
}

# Qualification thresholds.
# - MIN_TARGETS_TO_GRADE: below this, we skip the CB entirely (too small).
# - QUALIFIED_MIN_TARGETS: the main leaderboard threshold. CBs below this
#   appear with a "low volume" badge, not in the qualified percentile pool.
# - CONFIDENCE_FULL_TARGETS: targets at which confidence reaches 1.0.
CB_V1_MIN_TARGETS_TO_GRADE: int = 25
CB_V1_QUALIFIED_MIN_TARGETS: int = 30
CB_V1_CONFIDENCE_FULL_TARGETS: int = 60

# Role strings stored in season_grades.role. Based on slot_pct from PFR.
CB_ROLE_OUTSIDE: str = "outside_cb"
CB_ROLE_SLOT:    str = "slot_cb"
CB_ROLE_HYBRID:  str = "hybrid_cb"

# Slot snap percentage thresholds (fraction, not percent).
# CB is classified outside if slot_pct < SLOT_LO, slot if > SLOT_HI,
# hybrid otherwise. NULL slot_pct → role = None (unknown).
CB_V1_SLOT_LO: float = 0.35
CB_V1_SLOT_HI: float = 0.65


# ---------------------------------------------------------------------------
# Safety v1 (ADR-0019).
# ---------------------------------------------------------------------------
# Data sources:
#   - Coverage stats (targets, completions, yards, ints): pfr_advstats_def
#   - Pass breakups (PBU): nflverse def_pass_defended
#   - Tackles, TFL, sacks: nflverse player_stats
#   - Missed tackles: pfr_advstats_def (NULL-neutralized if absent)
#   - Defensive snaps: player_seasons.snaps_defense
#
# Coverage begins 2018 (PFR per-player data limitation).
#
# Formula: 70% coverage / 30% tackling (sum |abs| = 0.82).
# Negative weights = lower is better. Positive = higher is better.
#
# Coverage (70% of 0.82 = 0.574):
#   comp_pct_allowed (16%):   primary coverage quality — did the S win the rep?
#   yards_per_target (10%):   total yards per target; simpler than YAC split
#                              at safety depth, catches are often gain-seekers.
#   pbu_rate (18%):           pass breakups per target; playmaking, ~3× INT rate.
#   int_rate (16%):           INTs per target; turnover creation.
#   target_rate (10%):        QB avoidance. Elite safeties get schemed around.
#
# Tackling (30% of 0.82 = 0.246):
#   tackles_per_snap (9%):    coverage + run support combined.
#   missed_tackle_rate (11%): technique, key for a position that defends space.
#   backfield_disruption (11%): TFL + sacks per snap; pass-rush versatility.
#
# The combiner normalizes by sum of |weights| so magnitudes are proportional.
# ---------------------------------------------------------------------------

S_COMPONENT_COMP_PCT_ALLOWED: str = "s_comp_pct_allowed"
S_COMPONENT_YARDS_PER_TARGET: str = "s_yards_per_target_allowed"
S_COMPONENT_PBU_RATE: str = "s_pbu_rate"
S_COMPONENT_INT_RATE: str = "s_int_rate"
S_COMPONENT_TARGET_RATE: str = "s_target_rate"
S_COMPONENT_TACKLES_PER_SNAP: str = "s_tackles_per_snap"
S_COMPONENT_MISSED_TACKLE_RATE: str = "s_missed_tackle_rate"
S_COMPONENT_BACKFIELD_DISRUPTION: str = "s_backfield_disruption_per_snap"

S_V1_WEIGHTS: dict[str, float] = {
    S_COMPONENT_COMP_PCT_ALLOWED:  -0.13,
    S_COMPONENT_YARDS_PER_TARGET:  -0.08,
    S_COMPONENT_PBU_RATE:           0.15,
    S_COMPONENT_INT_RATE:           0.13,
    S_COMPONENT_TARGET_RATE:       -0.08,
    S_COMPONENT_TACKLES_PER_SNAP:   0.07,
    S_COMPONENT_MISSED_TACKLE_RATE:-0.09,
    S_COMPONENT_BACKFIELD_DISRUPTION: 0.09,
}

# Empirical Bayes shrinkage strengths.
# Coverage rates use targets as pseudo-sample denominator (consistent with CB).
# Tackling rates use snaps_defense.
# - comp% / yards-per-target (k=50 targets): moderate shrinkage, reasonable
#   stability after ~3 games of targets.
# - PBU / INT rates (k=80 targets): heavy shrinkage; rare, noisy events.
# - target_rate (k=150 snaps): scheme-driven avoidance, less snap noise than
#   event-driven rates; denominator includes run-defense snaps.
# - tackles_per_snap (k=200 snaps): stable across weeks once sample grows.
# - missed_tackle_rate (k=100 tackle_attempts): moderate shrinkage; technique
#   is a real skill but luck (bounce, angle) introduces noise.
# - backfield_disruption (k=300 snaps): TFL + sacks are rare per-snap; heavy
#   shrinkage needed to avoid over-weighting early multi-sack games.
S_V1_SHRINKAGE_K: dict[str, float] = {
    S_COMPONENT_COMP_PCT_ALLOWED:   50.0,
    S_COMPONENT_YARDS_PER_TARGET:   50.0,
    S_COMPONENT_PBU_RATE:           80.0,
    S_COMPONENT_INT_RATE:           80.0,
    S_COMPONENT_TARGET_RATE:       150.0,
    S_COMPONENT_TACKLES_PER_SNAP:  200.0,
    S_COMPONENT_MISSED_TACKLE_RATE:100.0,
    S_COMPONENT_BACKFIELD_DISRUPTION: 300.0,
}

# Raw computed column in the feature DataFrame for each component.
S_V1_RAW_VALUE_COLS: dict[str, str] = {
    S_COMPONENT_COMP_PCT_ALLOWED:    "comp_pct_allowed",
    S_COMPONENT_YARDS_PER_TARGET:    "yards_per_target_allowed",
    S_COMPONENT_PBU_RATE:            "pbu_rate",
    S_COMPONENT_INT_RATE:            "int_rate",
    S_COMPONENT_TARGET_RATE:         "target_rate",
    S_COMPONENT_TACKLES_PER_SNAP:    "tackles_per_snap",
    S_COMPONENT_MISSED_TACKLE_RATE:  "missed_tackle_rate",
    S_COMPONENT_BACKFIELD_DISRUPTION:"backfield_disruption_per_snap",
}

# Sample-size denominator for each component's EB shrinkage.
# missed_tackle_rate uses tackle_attempts (= comb + missed), the natural
# denominator for that rate.
S_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    S_COMPONENT_COMP_PCT_ALLOWED:    "targets",
    S_COMPONENT_YARDS_PER_TARGET:    "targets",
    S_COMPONENT_PBU_RATE:            "targets",
    S_COMPONENT_INT_RATE:            "targets",
    S_COMPONENT_TARGET_RATE:         "snaps_defense",
    S_COMPONENT_TACKLES_PER_SNAP:    "snaps_defense",
    S_COMPONENT_MISSED_TACKLE_RATE:  "tackle_attempts",
    S_COMPONENT_BACKFIELD_DISRUPTION:"snaps_defense",
}

# Qualification thresholds (snap-based, unlike CB's target-based).
# - MIN_SNAPS_TO_GRADE: below this, skip entirely.
# - QUALIFIED_MIN_SNAPS: the main leaderboard threshold.
# - CONFIDENCE_FULL_SNAPS: snaps at which confidence reaches 1.0.
S_V1_MIN_SNAPS_TO_GRADE: int = 200
S_V1_QUALIFIED_MIN_SNAPS: int = 400
S_V1_CONFIDENCE_FULL_SNAPS: int = 700
