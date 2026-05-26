"""Per-position v1 grading weights.

v1 uses hand-picked weights (ADR-0013). Inverse-variance / YoY-stability
weighting is explicitly deferred — we want explainability first, then
tune once we have face-validity feedback.

Components here are the **stat_components.component_name** strings —
they must match what ``grading/qb.py`` et al. write to the DB.
"""

from __future__ import annotations

# QB v1.1 (ADR-0013, revised 2026-05-14): EPA 59% / CPOE 29% / success_rate 12%.
#
# v1.1 change: lowered qb_success_rate from 0.25 → 0.10. Cross-position
# correlation audit (2026-05-14) found qb_epa_per_dropback ↔ qb_success_rate
# at Pearson r = +0.883 — strongest redundancy in the entire system.
# Mathematically: success_rate ≈ fraction of plays with positive EPA;
# EPA per dropback = mean EPA. They measure the same skill from two
# vantage points. Exhaustive QB audit confirmed success_rate has the lowest
# validity of the three components (Pro Bowl r = +0.130 vs EPA +0.158
# and CPOE +0.146).
#
# Sum |w| drops 1.00 → 0.85; combiner normalizes so EPA effectively grows
# from 50% → 59% of the formula. CPOE keeps its 29% share. See
# `docs/grading/audits/2026-05-14-exhaustive-qb.md` for the full audit and
# rejected-candidates log.
QB_V1_WEIGHTS: dict[str, float] = {
    "qb_epa_per_dropback": 0.50,
    "qb_cpoe": 0.25,
    "qb_success_rate": 0.10,
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
# RB v1.4 (ADR-0014, revised 2026-05-14).
# ---------------------------------------------------------------------------
# v1.4 change (post-exhaustive-audit Path B ship): added
# rb_yards_after_contact_per_carry at +0.10. Highest-validity candidate of
# any audit so far (+0.192 vs next-year Pro Bowl, higher than any current
# RB component). YoY r +0.313, moderate overlap with RYOE (+0.596 —
# RYOE includes pre-contact OL yards; yards_after_contact isolates the
# post-contact RB-skill portion). Schema change: new pfr_rb_rush table
# + ingest module (pipeline/ingest/pfr_rush.py).
#
# Coverage: PFR rush data starts 2018; for 2016-2017 seasons the
# yards_after_contact component is NaN-neutralized (composite computed
# from remaining 6 components). Same pre-2018 handling pattern as WR
# drop_rate's pre-2022 NaN-neutralization.
# v1.1 (earlier 2026-05-14): removed rb_catch_pct (noise + redundant).
#   Weight redistributed: rb_yac_over_expected_per_rec 0.12 → 0.15.
#
# v1.2 (cross-position YoY audit): lowered rb_rec_epa_per_target +0.18 →
#   +0.05. Mean YoY r = 0.027 (worst signal in the entire grader system).
#   Freed weight shifted to rb_yac_over_expected_per_rec (+0.15 → +0.28).
#
# v1.3 (exhaustive RB audit 2026-05-14): lowered rb_rush_success_rate
#   from +0.14 → +0.05. The exhaustive audit confirmed the same EPA-vs-
#   success-rate redundancy pattern seen at QB and WR: max |r| = +0.713
#   with rb_rush_epa_per_attempt, and rush_success_rate had the LOWEST
#   validity of any current component (+0.079 vs next-year Pro Bowl).
#   Sum |w| drops 0.98 → 0.89; combiner renormalizes.
#
# KNOWN GAP (queued for follow-up): exhaustive audit identified
# `rb_pfr_yards_after_contact` as the highest-validity RB candidate
# (+0.192, higher than any current component) with modest YoY (+0.313)
# and only moderate overlap with RYOE (+0.596). Real post-contact RB
# skill not in formula. Requires a new ingest module for pfr_advstats
# rush (path B schema change). Tracked in pending.md.
#
# See docs/grading/audits/2026-05-14-exhaustive-rb.md for the full audit
# log (19 candidates scored).

# Component names — strings written to stat_components.component_name.
RB_COMPONENT_RYOE_PER_ATTEMPT: str = "rb_ryoe_per_attempt"
RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: str = "rb_rush_epa_per_attempt"
RB_COMPONENT_RUSH_SUCCESS_RATE: str = "rb_rush_success_rate"
RB_COMPONENT_REC_EPA_PER_TARGET: str = "rb_rec_epa_per_target"
RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "rb_yac_over_expected_per_rec"
RB_COMPONENT_YARDS_AFTER_CONTACT: str = "rb_yards_after_contact_per_carry"
RB_COMPONENT_FUMBLE_RATE: str = "rb_fumble_rate"

# Sum |abs| = 0.99 (combiner normalizes).
# Effective shares: RYOE 28%, rush_EPA 18%, rush_success 5%, rec_EPA 5%,
# YAC-OE 28%, yards_after_contact 10%, fumble_rate -5%.
RB_V1_WEIGHTS: dict[str, float] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: 0.28,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: 0.18,
    RB_COMPONENT_RUSH_SUCCESS_RATE: 0.05,
    RB_COMPONENT_REC_EPA_PER_TARGET: 0.05,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.28,
    RB_COMPONENT_YARDS_AFTER_CONTACT: 0.10,
    RB_COMPONENT_FUMBLE_RATE: -0.05,
}

# Empirical Bayes shrinkage strengths.
RB_V1_SHRINKAGE_K: dict[str, float] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: 100.0,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: 100.0,
    RB_COMPONENT_RUSH_SUCCESS_RATE: 100.0,
    RB_COMPONENT_REC_EPA_PER_TARGET: 40.0,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    # yards_after_contact: k=80 carries. Per-carry rate is more stable
    # than per-attempt EPA (post-contact yards are smaller-variance per
    # play than expected-points outcomes), so slightly less shrinkage.
    RB_COMPONENT_YARDS_AFTER_CONTACT: 80.0,
    RB_COMPONENT_FUMBLE_RATE: 200.0,
}

RB_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: "n_carries",
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: "n_carries",
    RB_COMPONENT_RUSH_SUCCESS_RATE: "n_carries",
    RB_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    RB_COMPONENT_YARDS_AFTER_CONTACT: "n_pfr_carries",
    RB_COMPONENT_FUMBLE_RATE: "n_touches",
}

RB_V1_RAW_VALUE_COLS: dict[str, str] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: "ryoe_per_attempt",
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: "rush_epa_per_attempt",
    RB_COMPONENT_RUSH_SUCCESS_RATE: "rush_success_rate",
    RB_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    RB_COMPONENT_YARDS_AFTER_CONTACT: "yards_after_contact_per_carry",
    RB_COMPONENT_FUMBLE_RATE: "fumble_rate",
}

# NGS RYOE/att and YAC-over-expected are pre-adjusted upstream by NGS's
# own models. When opponent adjustment is added in v2, these components
# must be SKIPPED (flag = True) to avoid double-adjusting.
RB_V1_PRE_ADJUSTED: dict[str, bool] = {
    RB_COMPONENT_RYOE_PER_ATTEMPT: True,
    RB_COMPONENT_RUSH_EPA_PER_ATTEMPT: False,
    RB_COMPONENT_RUSH_SUCCESS_RATE: False,
    RB_COMPONENT_REC_EPA_PER_TARGET: False,
    RB_COMPONENT_YAC_OVER_EXPECTED_PER_REC: True,
    RB_COMPONENT_YARDS_AFTER_CONTACT: False,
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
# WR v1.3 (ADR-0015, revised 2026-05-14).
# ---------------------------------------------------------------------------
# v1.1 changes (shipped earlier 2026-05-14):
#   - Added wr_drop_rate from FTN per-play charting joined to PBP.
#   - Removed wr_fumble_rate (-0.05). YoY noise, max 1-2 fumbles per WR.
#
# v1.2 change (TE v1.1 self-audit, same day):
#   - Lowered wr_drop_rate from -0.08 → -0.05. v1.1 added it without YoY
#     check; mean YoY r = +0.09 indistinguishable from removed fumble rate.
#
# v1.3 change (WR exhaustive audit, same day):
#   - Bumped wr_target_earn_rate from +0.10 → +0.15. The audit found
#     earn_rate had the highest validity in the formula (Pro Bowl r +0.285)
#     and highest YoY r (+0.682) — strongest signal underweighted at 11%.
#     Now 15% of formula.
#   - Lowered wr_success_rate_per_target from +0.08 → +0.05. Same EPA-vs-
#     success-rate redundancy pattern as QB (max |r| = +0.746 with
#     rec_epa_per_target). Bounded at light weight.
#
# Sum |w| 0.95 → 0.97. No net "added weight" — earn_rate gains +0.05,
# success_rate gives up 0.03; the remaining 0.02 raises the magnitude
# slightly (formula's signal-to-noise improves). See
# docs/grading/audits/2026-05-14-exhaustive-wr.md for the full audit log
# (22 candidates scored, including documented rejections of NGS YAC,
# contested catch rate, broken-tackles-per-reception, etc.).
#
# FTN drop data starts 2022; for 2016-2021 the drop_rate component is
# NaN-neutralized to 0 contribution (grade comes from the other 5
# components only).

# Component names — part of the public contract with the web app.
WR_COMPONENT_REC_EPA_PER_TARGET: str = "wr_rec_epa_per_target"
WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "wr_yac_over_expected_per_rec"
WR_COMPONENT_SEPARATION: str = "wr_separation"
WR_COMPONENT_TARGET_EARN_RATE: str = "wr_target_earn_rate"
WR_COMPONENT_SUCCESS_RATE_PER_TARGET: str = "wr_success_rate_per_target"
WR_COMPONENT_DROP_RATE: str = "wr_drop_rate"

# Sum |abs| = 0.97 (combiner normalizes).
# Effective shares: EPA 36%, YAC 28%, separation 10%, target_earn 15%,
# success_rate 5%, drop_rate -5%.
WR_V1_WEIGHTS: dict[str, float] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: 0.35,
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.27,
    WR_COMPONENT_SEPARATION: 0.10,
    WR_COMPONENT_TARGET_EARN_RATE: 0.15,
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.05,
    WR_COMPONENT_DROP_RATE: -0.05,
}

# Empirical Bayes shrinkage strengths.
# - drop_rate: k=50 catchable balls. FTN is conservative; some WRs at 0
#   drops are real, some are data gaps. Moderate shrinkage avoids
#   over-rewarding "0 drops on 35 catchable balls" noise.
WR_V1_SHRINKAGE_K: dict[str, float] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: 50.0,
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    WR_COMPONENT_SEPARATION: 40.0,
    WR_COMPONENT_TARGET_EARN_RATE: 200.0,
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: 50.0,
    WR_COMPONENT_DROP_RATE: 50.0,
}

WR_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    WR_COMPONENT_SEPARATION: "n_targets",
    WR_COMPONENT_TARGET_EARN_RATE: "n_team_pass_att_active",
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: "n_targets",
    # Drop rate denominator is catchable balls (only well-thrown passes
    # count as drop opportunities). NaN for pre-2022 seasons.
    WR_COMPONENT_DROP_RATE: "n_catchable_balls",
}

WR_V1_RAW_VALUE_COLS: dict[str, str] = {
    WR_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    WR_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    WR_COMPONENT_SEPARATION: "separation",
    WR_COMPONENT_TARGET_EARN_RATE: "target_earn_rate",
    WR_COMPONENT_SUCCESS_RATE_PER_TARGET: "success_rate_per_target",
    WR_COMPONENT_DROP_RATE: "drop_rate",
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
    WR_COMPONENT_DROP_RATE: False,
}

# ADR-0015: two qualification tiers.
WR_V1_MIN_TARGETS_TO_GRADE: int = 20
WR_V1_QUALIFIED_MIN_TARGETS: int = 50

# Confidence scales to 1.0 at 100 targets (~6 per game, "real starter
# usage" rather than WR1 workload).
WR_V1_CONFIDENCE_FULL_TARGETS: int = 100


# ---------------------------------------------------------------------------
# TE v1.2 (ADR-0016, revised 2026-05-14).
# ---------------------------------------------------------------------------
# v1.1 changes:
#   - Removed te_fumble_rate (-0.05). YoY mean r ≈ +0.08, oscillates;
#     50% of qualified TEs have 0 fumbles. Same noise pattern as WR fumble.
#   - Added te_drop_rate from FTN at -0.05. YoY mean r = +0.13 (modest).
#     Light weight justified by independence + face-check + measurement-
#     error caveat at low catchable-ball denominators.
#
# v1.2 changes (TE exhaustive audit 2026-05-14):
#   - Bumped te_target_earn_rate from +0.10 → +0.15. The exhaustive audit
#     found earn_rate is the strongest signal in the formula (validity
#     +0.301 vs next-year Pro Bowl, YoY r +0.610) — underweighted at 11%.
#     Now 16% of formula. Same finding as WR v1.3.
#   - Lowered te_success_rate_per_target from +0.08 → +0.05. Same EPA-vs-
#     success-rate redundancy pattern confirmed at TE (max |r| = +0.723).
#     Now confirmed at all 4 receiver/passer positions (QB +0.88, WR +0.76,
#     RB +0.71, TE +0.72). Bounded at light weight.
#
# Sum |w| 0.92 → 0.94. blocking_te tier-2 redistribution updated to match:
# the 0.15 of target_earn_rate is redistributed to EPA + YAC in 0.35:0.27
# proportion → EPA 0.435, YAC 0.335.
#
# v1.2 audit also found:
#   - te_separation has slightly NEGATIVE Pro Bowl validity (-0.053).
#     Interpretation: TE Pro Bowl voters reward tight-window catchers
#     (Kelce/Andrews/Kittle archetype) over open-route runners. Kept at
#     0.07 anyway — strong YoY (+0.413) says we're measuring real skill;
#     don't reverse-engineer validity.
#   - 22 candidates scored, no new components added. te_pfr_broken_tackle_
#     per_rec documented as YAC-skill gap (similar to RB's pre-v1.4 state).
#
# FTN drop data starts 2022; for 2016-2021 the drop_rate component is
# NaN-neutralized to 0 contribution.

TE_COMPONENT_REC_EPA_PER_TARGET: str = "te_rec_epa_per_target"
TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: str = "te_yac_over_expected_per_rec"
TE_COMPONENT_SEPARATION: str = "te_separation"
TE_COMPONENT_TARGET_EARN_RATE: str = "te_target_earn_rate"
TE_COMPONENT_SUCCESS_RATE_PER_TARGET: str = "te_success_rate_per_target"
TE_COMPONENT_DROP_RATE: str = "te_drop_rate"

# Sum of |weights| = 0.94. Separation 7% (vs WR 10%) — NGS metric is
# WR-geometry-calibrated; TE matchups are noisier in the same number.
TE_V1_WEIGHTS: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 0.35,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.27,
    TE_COMPONENT_SEPARATION: 0.07,
    TE_COMPONENT_TARGET_EARN_RATE: 0.15,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.05,
    TE_COMPONENT_DROP_RATE: -0.05,
}

# Blocking-TE (role) path: omit earn in composite; redistribute the 0.15
# target_earn_rate weight to EPA+YAC in proportion 0.35/0.62 and 0.27/0.62.
#   EPA: 0.35 + 0.15*(0.35/0.62) = 0.435
#   YAC: 0.27 + 0.15*(0.27/0.62) = 0.335
TE_V1_BLOCKING_WEIGHTS: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 0.435,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 0.335,
    TE_COMPONENT_SEPARATION: 0.07,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 0.05,
    TE_COMPONENT_DROP_RATE: -0.05,
}

# Per-position shrinkage: TE target earn k=100 (vs WR 200) for smaller
# cross-player dispersion in earn-rate. Drop_rate k=30 — TE catchable-ball
# denominators (median ~47) are smaller than WR (~75), so light shrinkage
# avoids over-rewarding "0 drops on 27 catchable balls" noise.
TE_V1_SHRINKAGE_K: dict[str, float] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: 50.0,
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: 30.0,
    TE_COMPONENT_SEPARATION: 40.0,
    TE_COMPONENT_TARGET_EARN_RATE: 100.0,
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: 50.0,
    TE_COMPONENT_DROP_RATE: 30.0,
}

TE_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: "n_targets",
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "n_rec_with_xyac",
    TE_COMPONENT_SEPARATION: "n_targets",
    TE_COMPONENT_TARGET_EARN_RATE: "n_team_pass_att_active",
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: "n_targets",
    # NaN for pre-2022 seasons (FTN coverage gap).
    TE_COMPONENT_DROP_RATE: "n_catchable_balls",
}

TE_V1_RAW_VALUE_COLS: dict[str, str] = {
    TE_COMPONENT_REC_EPA_PER_TARGET: "rec_epa_per_target",
    TE_COMPONENT_YAC_OVER_EXPECTED_PER_REC: "yac_over_expected_per_rec",
    TE_COMPONENT_SEPARATION: "separation",
    TE_COMPONENT_TARGET_EARN_RATE: "target_earn_rate",
    TE_COMPONENT_SUCCESS_RATE_PER_TARGET: "success_rate_per_target",
    TE_COMPONENT_DROP_RATE: "drop_rate",
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
# CB v1.1 (ADR-0018, revised 2026-05-14).
# ---------------------------------------------------------------------------
# Data source: PFR advanced defensive coverage stats (pfr_def_coverage table —
# includes comp%, yards, YAC, TDs, INTs) + nflverse player stats
# (def_pass_defended for PBU) + player_seasons (snaps_defense).
# Coverage begins 2018.
#
# Negative weights = lower is better. Positive weights = higher is better.
#
# v1.1 swap: replaced comp_pct_allowed (-0.22) + int_rate (+0.10) with a
# single passer_rating_allowed component (-0.35). Rationale:
#   - passer rating allowed naturally captures comp%, yds/att, TDs allowed,
#     and INTs as four sub-components.
#   - v1 didn't penalize TDs allowed at all. v1.1 does (heavily — a TD swings
#     passer rating ~20 points).
#   - INTs are now captured inside passer rating; v1.1 keeps pbu_rate
#     separately for the active "broke up the catch" play.
#
# Formula rationale:
#   passer_rating_allowed (50%): industry-standard coverage damage metric.
#     The single cleanest CB skill signal. k=40 targets (heavy shrinkage
#     because passer rating swings 25+ points off one TD or INT).
#   yac_per_rec_allowed (21%): post-catch damage. Captures cushion and tackle
#     quality at the catch point. Distinct from passer rating (which is
#     yards/attempt, not yards-after-catch).
#   target_rate (11%): elite CBs get avoided; QBs scheme away from them.
#     Independent of what happens when they're targeted.
#   pbu_rate (17%): active play that broke up the catch. INT events are
#     in passer rating; PBU rate captures the rest.
#
# The composite combiner normalizes by sum of |weights|.
# ---------------------------------------------------------------------------

CB_COMPONENT_PASSER_RATING_ALLOWED: str = "cb_passer_rating_allowed"
CB_COMPONENT_YAC_PER_REC_ALLOWED: str = "cb_yac_per_rec_allowed"
CB_COMPONENT_TARGET_RATE: str = "cb_target_rate"
CB_COMPONENT_PBU_RATE: str = "cb_pbu_rate"

# v1.2 (2026-05-14, exhaustive CB audit): lowered target_rate from -0.08
# to -0.05. Audit found target_rate validity vs next-year Pro Bowl is
# +0.013 — essentially zero, and the sign disagrees with our design
# weight direction (we treat lower target rate as better; voters apparently
# don't see it that way at the qualified-CB level where all top CBs face
# similar target volume). Bounded at light weight.
CB_V1_WEIGHTS: dict[str, float] = {
    CB_COMPONENT_PASSER_RATING_ALLOWED: -0.35,
    CB_COMPONENT_YAC_PER_REC_ALLOWED:   -0.15,
    CB_COMPONENT_TARGET_RATE:           -0.05,
    CB_COMPONENT_PBU_RATE:               0.12,
}

# Empirical Bayes shrinkage strengths.
# - passer_rating_allowed: k=40. Heavy shrinkage because PR swings 25+ pts
#   on one TD or INT for a 50-target sample.
# - YAC: k=50 targets.
# - PBU: k=80 (rare/noisy events).
# - target_rate: k=150 snaps. Scheme-driven, more stable than event rates.
CB_V1_SHRINKAGE_K: dict[str, float] = {
    CB_COMPONENT_PASSER_RATING_ALLOWED: 40.0,
    CB_COMPONENT_YAC_PER_REC_ALLOWED:   50.0,
    CB_COMPONENT_TARGET_RATE:           150.0,
    CB_COMPONENT_PBU_RATE:              80.0,
}

CB_V1_RAW_VALUE_COLS: dict[str, str] = {
    CB_COMPONENT_PASSER_RATING_ALLOWED: "passer_rating_allowed",
    CB_COMPONENT_YAC_PER_REC_ALLOWED:   "yac_per_rec_allowed",
    CB_COMPONENT_TARGET_RATE:           "target_rate",
    CB_COMPONENT_PBU_RATE:              "pbu_rate",
}

CB_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    CB_COMPONENT_PASSER_RATING_ALLOWED: "targets",
    CB_COMPONENT_YAC_PER_REC_ALLOWED:   "targets",
    CB_COMPONENT_TARGET_RATE:           "snaps_defense",
    CB_COMPONENT_PBU_RATE:              "targets",
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

S_COMPONENT_PASSER_RATING_ALLOWED: str = "s_passer_rating_allowed"
S_COMPONENT_PBU_RATE: str = "s_pbu_rate"
S_COMPONENT_TARGET_RATE: str = "s_target_rate"
S_COMPONENT_TACKLES_PER_SNAP: str = "s_tackles_per_snap"
S_COMPONENT_MISSED_TACKLE_RATE: str = "s_missed_tackle_rate"
S_COMPONENT_BACKFIELD_DISRUPTION: str = "s_backfield_disruption_per_snap"

# v1.1 (2026-05-14): replaced comp_pct_allowed + yards_per_target + int_rate
# with a single passer_rating_allowed component. INTs are now captured inside
# passer rating (hammers it ~25 pts per INT), so PBU rate dropped from
# pbu+int bundle (v1: 0.15) → PBU-only (v1.1: 0.12).
# v1.2 (2026-05-14, exhaustive Safety audit): lowered s_target_rate from
# -0.08 to -0.05. Same pattern as CB v1.2 — validity essentially zero
# (-0.006) with disagreeing sign. At qualified-S level, top safeties face
# similar target volumes; "avoidance" doesn't differentiate.
S_V1_WEIGHTS: dict[str, float] = {
    S_COMPONENT_PASSER_RATING_ALLOWED: -0.30,
    S_COMPONENT_PBU_RATE:               0.12,
    S_COMPONENT_TARGET_RATE:           -0.05,
    S_COMPONENT_TACKLES_PER_SNAP:       0.07,
    S_COMPONENT_MISSED_TACKLE_RATE:    -0.09,
    S_COMPONENT_BACKFIELD_DISRUPTION:   0.09,
}

# Empirical Bayes shrinkage strengths.
# - passer_rating_allowed (k=40 targets): heavy shrinkage; PR swings ~25 pts
#   off one TD or INT in a 50-target sample.
# - PBU rate (k=80 targets): rare events.
# - target_rate (k=150 snaps): scheme-driven avoidance.
# - tackles_per_snap (k=200 snaps): stable once sample grows.
# - missed_tackle_rate (k=100 tackle_attempts): moderate shrinkage.
# - backfield_disruption (k=300 snaps): TFL + sacks rare per-snap.
S_V1_SHRINKAGE_K: dict[str, float] = {
    S_COMPONENT_PASSER_RATING_ALLOWED:  40.0,
    S_COMPONENT_PBU_RATE:               80.0,
    S_COMPONENT_TARGET_RATE:           150.0,
    S_COMPONENT_TACKLES_PER_SNAP:      200.0,
    S_COMPONENT_MISSED_TACKLE_RATE:    100.0,
    S_COMPONENT_BACKFIELD_DISRUPTION:  300.0,
}

S_V1_RAW_VALUE_COLS: dict[str, str] = {
    S_COMPONENT_PASSER_RATING_ALLOWED: "passer_rating_allowed",
    S_COMPONENT_PBU_RATE:              "pbu_rate",
    S_COMPONENT_TARGET_RATE:           "target_rate",
    S_COMPONENT_TACKLES_PER_SNAP:      "tackles_per_snap",
    S_COMPONENT_MISSED_TACKLE_RATE:    "missed_tackle_rate",
    S_COMPONENT_BACKFIELD_DISRUPTION:  "backfield_disruption_per_snap",
}

S_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    S_COMPONENT_PASSER_RATING_ALLOWED: "targets",
    S_COMPONENT_PBU_RATE:              "targets",
    S_COMPONENT_TARGET_RATE:           "snaps_defense",
    S_COMPONENT_TACKLES_PER_SNAP:      "snaps_defense",
    S_COMPONENT_MISSED_TACKLE_RATE:    "tackle_attempts",
    S_COMPONENT_BACKFIELD_DISRUPTION:  "snaps_defense",
}

# Qualification thresholds (snap-based, unlike CB's target-based).
# - MIN_SNAPS_TO_GRADE: below this, skip entirely.
# - QUALIFIED_MIN_SNAPS: the main leaderboard threshold.
# - CONFIDENCE_FULL_SNAPS: snaps at which confidence reaches 1.0.
S_V1_MIN_SNAPS_TO_GRADE: int = 200
S_V1_QUALIFIED_MIN_SNAPS: int = 400
S_V1_CONFIDENCE_FULL_SNAPS: int = 700


# ---------------------------------------------------------------------------
# EDGE v1.2 (ADR-0020, revised 2026-05-14 via exhaustive audit).
# ---------------------------------------------------------------------------
# Data sources:
#   - Pressures, sacks, QB hits, hurries, tackles, missed tackles:
#     pfr_advstats_def → pfr_def_pass_rush table (2018+)
#   - TFL (run stops, sacks excluded): nflvs_player_stats → pfr_def_pass_rush
#   - Defensive snaps: player_seasons.snaps_defense
#
# Coverage begins 2018 (PFR per-player data limitation).
#
# v1.1 (2026-05-14): OLB-gap closure — EDGE grader now reads from both
# pfr_def_pass_rush AND pfr_def_lb (LB-tagged pass-rush OLBs like T.J. Watt,
# Micah Parsons, Burns). No weight change.
#
# v1.2 (2026-05-14): added edge_tackles_per_snap at +0.05 from the
# exhaustive audit. Validity +0.216 (moderate), YoY +0.520 (strong
# reliability), max correlation with existing components only +0.468 vs
# tfl_rate (independent signal — captures chase-tackles and ahead-of-LOS
# plays that pressure/sack/TFL don't). Rejected new candidates:
# qb_hits_per_snap, hurries_per_snap (subsumed by pressure_rate, +0.71-0.73
# correlation); sack_per_pressure (subsumed by sack_rate, +0.689);
# hit_per_pressure (validity -0.038, near-zero signal);
# forced_fumble_per_snap (rare-event noise, validity +0.141).
#
# v1.2 weight breakdown:
# edge_pressure_rate (37%): pressures (sacks+hits+hurries) per snap.
#   Primary signal — total pass rush impact per opportunity.
# edge_sack_rate (32%): sacks per snap. Premium outcome; extra credit
#   for converting pressure to sacks. Intentional overlap with pressure_rate
#   to weight the highest-value plays more heavily.
# edge_tfl_rate (16%): run-stop TFLs (sacks excluded) per snap.
#   EDGE rushers set the edge on run plays; elite ones generate real TFLs.
# edge_tackles_per_snap (5%): combined tackles per snap. Captures activity
#   level / chase tackles that don't show up as behind-LOS plays.
# edge_missed_tackle_rate (11%): missed / (comb + missed). Technique
#   penalty. k=100 tackle_attempts — moderate shrinkage, some real skill.
#
# nflvs TFL is reported separately from sacks (confirmed by inspection:
# Dexter Lawrence 2024 had 9.0 sacks but only 8 TFL, proving sacks are
# NOT counted in def_tackles_for_loss). No double-count risk.
# ---------------------------------------------------------------------------

EDGE_COMPONENT_PRESSURE_RATE: str = "edge_pressure_rate"
EDGE_COMPONENT_SACK_RATE: str = "edge_sack_rate"
EDGE_COMPONENT_TFL_RATE: str = "edge_tfl_rate"
EDGE_COMPONENT_TACKLES_PER_SNAP: str = "edge_tackles_per_snap"
EDGE_COMPONENT_MISSED_TACKLE_RATE: str = "edge_missed_tackle_rate"

EDGE_V1_WEIGHTS: dict[str, float] = {
    EDGE_COMPONENT_PRESSURE_RATE:      0.35,
    EDGE_COMPONENT_SACK_RATE:          0.30,
    EDGE_COMPONENT_TFL_RATE:           0.15,
    EDGE_COMPONENT_TACKLES_PER_SNAP:   0.05,
    EDGE_COMPONENT_MISSED_TACKLE_RATE: -0.10,
}

EDGE_V1_SHRINKAGE_K: dict[str, float] = {
    EDGE_COMPONENT_PRESSURE_RATE:      200.0,
    EDGE_COMPONENT_SACK_RATE:          350.0,
    EDGE_COMPONENT_TFL_RATE:           300.0,
    EDGE_COMPONENT_TACKLES_PER_SNAP:   200.0,
    EDGE_COMPONENT_MISSED_TACKLE_RATE: 100.0,
}

EDGE_V1_RAW_VALUE_COLS: dict[str, str] = {
    EDGE_COMPONENT_PRESSURE_RATE:      "pressure_rate",
    EDGE_COMPONENT_SACK_RATE:          "sack_rate",
    EDGE_COMPONENT_TFL_RATE:           "tfl_rate",
    EDGE_COMPONENT_TACKLES_PER_SNAP:   "tackles_per_snap",
    EDGE_COMPONENT_MISSED_TACKLE_RATE: "missed_tackle_rate",
}

EDGE_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    EDGE_COMPONENT_PRESSURE_RATE:      "snaps_defense",
    EDGE_COMPONENT_SACK_RATE:          "snaps_defense",
    EDGE_COMPONENT_TFL_RATE:           "snaps_defense",
    EDGE_COMPONENT_TACKLES_PER_SNAP:   "snaps_defense",
    EDGE_COMPONENT_MISSED_TACKLE_RATE: "tackle_attempts",
}

EDGE_V1_MIN_SNAPS_TO_GRADE: int = 200
EDGE_V1_QUALIFIED_MIN_SNAPS: int = 400
EDGE_V1_CONFIDENCE_FULL_SNAPS: int = 700


# ---------------------------------------------------------------------------
# iDL v1.2 (ADR-0021, revised 2026-05-14 via exhaustive audit).
# ---------------------------------------------------------------------------
# Data sources: same pfr_def_pass_rush table as EDGE (both are DL).
#
# v1.1 (cross-position audit 2026-05-14): idl_missed_tackle_rate lowered
# from -0.15 → -0.05.
#
# v1.2 (2026-05-14, exhaustive audit): two-part change.
#
# (a) Rebalance pressure/TFL/sack. The audit revealed weights were
#     MIS-ORDERED vs predictive validity:
#       Current weights: tfl 0.35 > pressure 0.30 > sack 0.15
#       Pro Bowl validity: pressure +0.460 > sack +0.394 > tfl +0.260
#     The original design assumed "iDL = primarily run-stop." Pro Bowl
#     voters reward interior PRESSURE more (the Aaron Donald / Chris
#     Jones / Quinnen Williams archetype that dominates modern Pro Bowl
#     iDL selections). pressure_rate also has YoY +0.689 — substantially
#     more reliable than tfl_rate (+0.371). The rebalance brings the
#     formula in line with both validity and reliability.
#
# (b) Add idl_tackles_per_snap at +0.05. YoY +0.516, validity +0.281,
#     max correlation +0.532 — independent signal. Same finding as EDGE
#     v1.2: tackle volume captures activity / chase-tackles that
#     pressure/sack/TFL miss. Voters reward iDLs who show up across the
#     box score.
#
# Rejected new candidates: qb_hits_per_snap (+0.779 with pressure_rate,
# subsumed), hurries_per_snap (+0.709 with pressure_rate), sack_per_pressure
# (YoY +0.008 — pure noise at iDL sample sizes), hit_per_pressure (validity
# -0.052, near-zero), forced_fumble_per_snap (YoY +0.096, rare-event noise).
#
# v1.2 weight breakdown:
# idl_pressure_rate (37%): total pressures per snap. Now primary signal
#   matching validity. Interior pressure is the modern iDL skill voters reward.
# idl_tfl_rate (26%): run-stop TFLs per snap. De-prioritized but still real
#   signal — iDL run-stop matters more than EDGE run-stop, just not the most.
# idl_sack_rate (21%): sacks per snap. Validity +0.394 justified the bump.
#   Premium event; intentional partial overlap with pressure_rate.
# idl_tackles_per_snap (5%): combined tackles per snap. Activity-level signal.
# idl_missed_tackle_rate (-5%): technique penalty, light weight per YoY noise.
#
# Sum |abs| = 0.90. Normalized dynamically by composite.combine.
# ---------------------------------------------------------------------------

IDL_COMPONENT_TFL_RATE: str = "idl_tfl_rate"
IDL_COMPONENT_PRESSURE_RATE: str = "idl_pressure_rate"
IDL_COMPONENT_SACK_RATE: str = "idl_sack_rate"
IDL_COMPONENT_TACKLES_PER_SNAP: str = "idl_tackles_per_snap"
IDL_COMPONENT_MISSED_TACKLE_RATE: str = "idl_missed_tackle_rate"

IDL_V1_WEIGHTS: dict[str, float] = {
    IDL_COMPONENT_PRESSURE_RATE:      0.35,
    IDL_COMPONENT_TFL_RATE:           0.25,
    IDL_COMPONENT_SACK_RATE:          0.20,
    IDL_COMPONENT_TACKLES_PER_SNAP:   0.05,
    IDL_COMPONENT_MISSED_TACKLE_RATE: -0.05,
}

IDL_V1_SHRINKAGE_K: dict[str, float] = {
    IDL_COMPONENT_TFL_RATE:           300.0,
    IDL_COMPONENT_PRESSURE_RATE:      200.0,
    IDL_COMPONENT_SACK_RATE:          350.0,
    IDL_COMPONENT_TACKLES_PER_SNAP:   200.0,
    IDL_COMPONENT_MISSED_TACKLE_RATE: 100.0,
}

IDL_V1_RAW_VALUE_COLS: dict[str, str] = {
    IDL_COMPONENT_TFL_RATE:           "tfl_rate",
    IDL_COMPONENT_PRESSURE_RATE:      "pressure_rate",
    IDL_COMPONENT_SACK_RATE:          "sack_rate",
    IDL_COMPONENT_TACKLES_PER_SNAP:   "tackles_per_snap",
    IDL_COMPONENT_MISSED_TACKLE_RATE: "missed_tackle_rate",
}

IDL_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    IDL_COMPONENT_TFL_RATE:           "snaps_defense",
    IDL_COMPONENT_PRESSURE_RATE:      "snaps_defense",
    IDL_COMPONENT_SACK_RATE:          "snaps_defense",
    IDL_COMPONENT_TACKLES_PER_SNAP:   "snaps_defense",
    IDL_COMPONENT_MISSED_TACKLE_RATE: "tackle_attempts",
}

IDL_V1_MIN_SNAPS_TO_GRADE: int = 200
IDL_V1_QUALIFIED_MIN_SNAPS: int = 400
IDL_V1_CONFIDENCE_FULL_SNAPS: int = 700


# ---------------------------------------------------------------------------
# LB v1.2 (ADR-0022, revised 2026-05-14 via exhaustive audit).
# ---------------------------------------------------------------------------
# v1.1 (cross-position audit 2026-05-14): lb_pbu_rate lowered from +0.08
# → +0.05. Noise pattern.
#
# v1.2 (2026-05-14, exhaustive audit): rebalance two components.
#
#   (a) lb_passer_rating_allowed: -0.27 → -0.15. Was the heaviest
#       component (32% of formula) but had both weak reliability
#       (YoY +0.146, near noise threshold) AND weak predictive validity
#       (-0.071, sign correct but magnitude tiny). At LB sample sizes
#       (15-25 targets/season per qualified LB) the metric is structurally
#       noisier than at S/CB. Right-sized to its real signal strength.
#
#   (b) lb_pressure_rate: +0.07 → +0.10. Modest bump. It had the
#       HIGHEST positive validity (+0.149) of any LB component but was
#       the LOWEST-weighted positive component. Same iDL-style mis-order
#       pattern, but smaller in magnitude — kept conservative.
#
# Rejected new candidates (article-defensible log):
#   - PFR passer-rating sub-components (comp_pct, yards/tgt, int_rate,
#     td_rate): all +0.51-0.63 correlation with passer_rating_allowed,
#     subsumed by it.
#   - Pass-rush sub-components (qb_hits, hurries, sack_rate): all
#     +0.70-0.73 correlation with pressure_rate, subsumed.
#   - sack_per_pressure, hit_per_pressure: small n (135), weak validity.
#   - forced_fumble_per_snap, int_per_snap: rare-event noise.
#   - adot_allowed, yac_per_target_allowed: noise / subsumed.
#
# No new components added — LB had the richest existing formula (6
# components) and the audit confirmed it's structurally complete. The
# value is the rebalance.
#
# Note: LB has the WEAKEST baseline validity (+0.179) of any audited
# position — the well-known "stats vs reputation" gap for LBs. The
# v1.2 rebalance modestly improves alignment with voter consensus
# without abandoning the design intent (LBs ARE coverage-graded, just
# less heavily than v1 assumed).
#
# v1.2 weight breakdown:
# lb_tfl_rate (26%): run-stop TFLs per snap. Cleanest run-defense signal.
# lb_passer_rating_allowed (-19%): NFL passer rating allowed when targeted.
# lb_missed_tackle_rate (-19%): technique penalty.
# lb_pbu_rate (6%): PBU per target. Active play that broke up the catch.
# lb_tackle_rate (17%): tackles per snap. Volume signal.
# lb_pressure_rate (13%): situational pass rush. Highest positive validity.
#
# Sum |abs| = 0.78. Normalized dynamically by composite.combine.
# ---------------------------------------------------------------------------

LB_COMPONENT_TFL_RATE: str = "lb_tfl_rate"
LB_COMPONENT_PASSER_RATING_ALLOWED: str = "lb_passer_rating_allowed"
LB_COMPONENT_MISSED_TACKLE_RATE: str = "lb_missed_tackle_rate"
LB_COMPONENT_PBU_RATE: str = "lb_pbu_rate"
LB_COMPONENT_TACKLE_RATE: str = "lb_tackle_rate"
LB_COMPONENT_PRESSURE_RATE: str = "lb_pressure_rate"

LB_V1_WEIGHTS: dict[str, float] = {
    LB_COMPONENT_TFL_RATE:              0.20,
    LB_COMPONENT_PASSER_RATING_ALLOWED: -0.15,
    LB_COMPONENT_MISSED_TACKLE_RATE:    -0.15,
    LB_COMPONENT_PBU_RATE:              0.05,
    LB_COMPONENT_TACKLE_RATE:           0.13,
    LB_COMPONENT_PRESSURE_RATE:         0.10,
}

LB_V1_SHRINKAGE_K: dict[str, float] = {
    LB_COMPONENT_TFL_RATE:              300.0,   # rare event, heavy shrink
    LB_COMPONENT_PASSER_RATING_ALLOWED: 50.0,    # in target attempts; passer rating swings hard on TDs/INTs
    LB_COMPONENT_MISSED_TACKLE_RATE:    100.0,   # in tackle attempts
    LB_COMPONENT_PBU_RATE:              40.0,    # in target attempts
    LB_COMPONENT_TACKLE_RATE:           200.0,
    LB_COMPONENT_PRESSURE_RATE:         200.0,
}

LB_V1_RAW_VALUE_COLS: dict[str, str] = {
    LB_COMPONENT_TFL_RATE:              "tfl_rate",
    LB_COMPONENT_PASSER_RATING_ALLOWED: "passer_rating_allowed",
    LB_COMPONENT_MISSED_TACKLE_RATE:    "missed_tackle_rate",
    LB_COMPONENT_PBU_RATE:              "pbu_rate",
    LB_COMPONENT_TACKLE_RATE:           "tackle_rate",
    LB_COMPONENT_PRESSURE_RATE:         "pressure_rate",
}

LB_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    LB_COMPONENT_TFL_RATE:              "snaps_defense",
    LB_COMPONENT_PASSER_RATING_ALLOWED: "targets",
    LB_COMPONENT_MISSED_TACKLE_RATE:    "tackle_attempts",
    LB_COMPONENT_PBU_RATE:              "targets",
    LB_COMPONENT_TACKLE_RATE:           "snaps_defense",
    LB_COMPONENT_PRESSURE_RATE:         "snaps_defense",
}

LB_V1_MIN_SNAPS_TO_GRADE: int = 200
# Raised vs other defensive positions (400 → 600) because LB rate stats are
# heavily inflated by limited-snap role specialists (sub-package run stuffers,
# nickel coverage LBs) whose narrow usage produces per-snap rates that
# every-down LBs can't match. 600 snaps = ~10 full games of every-down play.
LB_V1_QUALIFIED_MIN_SNAPS: int = 600
LB_V1_CONFIDENCE_FULL_SNAPS: int = 900

# Off-ball role filter: targets / snaps_defense must exceed this.
# Pure off-ball LBs see 5-9% target rate; pass-rush OLBs misclassified as
# LB (e.g. Andrew Van Ginkel: 22 targets / 922 snaps = 2.4%) see 1-3%.
# Threshold of 3.5% cleanly separates the two groups.
LB_V1_MIN_TARGET_RATE_FOR_OFFBALL: float = 0.035
# Also require an absolute minimum of targets so a 200-snap player with
# 8 targets (4% rate) doesn't sneak in on a noise sample.
LB_V1_MIN_TARGETS_FOR_OFFBALL: int = 15


# ---------------------------------------------------------------------------
# K v1.1 (ADR-0023, revised 2026-05-14 same-day via FGOE design correction).
# ---------------------------------------------------------------------------
# Placekicker grading. Scope: FG accuracy + XP accuracy.
# Kickoffs intentionally excluded — 2024 dynamic kickoff rule change broke
# continuity of touchback/return rates.
#
# Data source: kicker_stats (ingested from nflvs_player_stats, season totals).
# Coverage: 2016+.
#
# v1 → v1.1 (same-day correction): the v1 formula used raw make-rate metrics
# (fg_pct, fg_pct_40_plus, pat_pct, fg_long), which actively PUNISHED kickers
# for attempting risky long FGs — a 60-yard miss hurt fg_pct identically to a
# 30-yard miss. A kicker whose coach never let them try past 45 looked better
# than a kicker who attempted (and made some) 60-yarders.
#
# v1.1 replaces this with a single principled metric:
#   k_fg_over_expected_per_att
#
# Computed per kicker per season:
#   expected_makes = sum over distance buckets of (attempts_b × baseline_b)
#                  + pat_att × baseline_xp
#   total_makes    = fg_made + pat_made
#   fgoe           = total_makes − expected_makes
#   fgoe_per_att   = fgoe / (fg_att + pat_att)
#
# League baselines (K_V1_1_BASELINES below) come from kicker_stats 2016-2024.
#
# Math automatically rewards making hard kicks heavily (60-yard make = +0.60
# over expected) and penalizes missing easy kicks heavily (XP miss = -0.94
# over expected). Risk-asymmetric by construction — no extra weighting needed.
#
# Single-component formula (weight 1.0). The audit log shows raw FG%, FG% 40+,
# fg_long, pat_pct (standalone), fg_pct_short, fg_pct_50_plus, gwfg_pct, and
# fg_att_per_game were all considered and rejected — either subsumed by FGOE
# or pure noise. See docs/grading/audits/2026-05-14-exhaustive-k.md.
# ---------------------------------------------------------------------------

K_COMPONENT_FGOE_PER_ATT: str = "k_fg_over_expected_per_att"

K_V1_WEIGHTS: dict[str, float] = {
    K_COMPONENT_FGOE_PER_ATT: 1.0,
}

K_V1_SHRINKAGE_K: dict[str, float] = {
    # 15 attempts of pseudo-sample — kickers with low workload are shrunk
    # toward the league mean (FGOE = 0).
    K_COMPONENT_FGOE_PER_ATT: 15.0,
}

K_V1_RAW_VALUE_COLS: dict[str, str] = {
    K_COMPONENT_FGOE_PER_ATT: "fgoe_per_att",
}

K_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    K_COMPONENT_FGOE_PER_ATT: "total_att",  # fg_att + pat_att
}

# League baselines used to compute expected FG makes by distance.
# Computed from kicker_stats 2016-2024 (n_att shown). Frozen as constants
# so grades are reproducible season-to-season without recomputing the
# baseline (era-fixed yardstick).
K_V1_1_BASELINES: dict[str, float] = {
    "fg_0_19":  1.0000,   # n=42
    "fg_20_29": 0.9838,   # n=2093
    "fg_30_39": 0.9362,   # n=2587
    "fg_40_49": 0.7956,   # n=2662
    "fg_50_59": 0.6903,   # n=1563
    "fg_60_plus": 0.4000, # n=65
    "xp":       0.9431,   # n=10941 (post-2015)
}

# Qualification thresholds — FG-attempt based.
K_V1_MIN_FG_ATT_TO_GRADE: int = 10        # rookie / mid-season callup floor
K_V1_QUALIFIED_MIN_FG_ATT: int = 20       # main leaderboard threshold
K_V1_CONFIDENCE_FULL_FG_ATT: int = 30     # full confidence (career-year starter)


# ---------------------------------------------------------------------------
# P v1.1 (ADR-0024, revised 2026-05-14 same-day — blocked_rate removed).
# ---------------------------------------------------------------------------
# Punter grading. Scope: distance + return prevention + placement.
# Hangtime intentionally excluded — not in nflverse data.
#
# Data source: punter_stats (aggregated from pbp punt_attempt rows by
# punter_player_id). Coverage: 2016+.
#
# v1 → v1.1 (same-day): removed `p_blocked_rate` (-0.05) from the formula.
# The audit had already shown blocked_rate was near-zero on both YoY (-0.046)
# and validity (-0.046) — it was kept at small weight on "punter conceptually
# owns the play" grounds. v1.1 drops it: most blocks are snap/protection
# failures rather than punter skill, and the event is so rare (1-2 per
# punter per season) that the small negative weight was punishing punters
# for their teammates' mistakes without measuring real punter skill.
# Block% remains visible on the leaderboard as a CONTEXT column (pulled
# directly from punter_stats raw counts) but is not scored.
#
# Audit findings (see audits/2026-05-14-exhaustive-p.md):
# Unlike K (where FGOE per attempt cleanly dominated all alternatives),
# the EPA-per-punt over-expected metric did NOT dominate raw rate metrics
# for P. EPA at the punt level mixes punter skill with opponent quality,
# field position, and game state — diluting the punter-skill signal.
#
# Best individual signals from audit:
#   - p_net_avg:        YoY +0.355 (best YoY), validity +0.166 (2nd best)
#   - p_inside_20_rate: YoY +0.168, validity +0.188 (best)
#   - p_epa_per_punt:   YoY +0.269, validity +0.163 (didn't dominate)
#
# Weight breakdown (sum |abs| = 0.85):
#   p_net_avg (65%):        primary distance + return prevention signal
#   p_inside_20_rate (35%): placement skill (orthogonal to net)
#
# Rejected from v1.1 (in addition to v1's audit log):
#   p_blocked_rate: removed per "blocks are not punter skill" framing.
# ---------------------------------------------------------------------------

P_COMPONENT_NET_AVG: str = "p_net_avg"
P_COMPONENT_INSIDE_20_RATE: str = "p_inside_20_rate"

P_V1_WEIGHTS: dict[str, float] = {
    P_COMPONENT_NET_AVG:        0.55,
    P_COMPONENT_INSIDE_20_RATE: 0.30,
}

P_V1_SHRINKAGE_K: dict[str, float] = {
    # Light shrinkage for net_avg — starters have 50-80 punts.
    P_COMPONENT_NET_AVG:        10.0,
    # Inside-20 is bucketed (~30% league-wide); moderate shrinkage.
    P_COMPONENT_INSIDE_20_RATE: 15.0,
}

P_V1_RAW_VALUE_COLS: dict[str, str] = {
    P_COMPONENT_NET_AVG:        "net_avg",
    P_COMPONENT_INSIDE_20_RATE: "inside_20_rate",
}

P_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    P_COMPONENT_NET_AVG:        "punts",
    P_COMPONENT_INSIDE_20_RATE: "punts",
}

# Qualification thresholds — punt-count based.
P_V1_MIN_PUNTS_TO_GRADE: int = 25         # rookie / mid-season callup floor
P_V1_QUALIFIED_MIN_PUNTS: int = 40        # main leaderboard threshold
P_V1_CONFIDENCE_FULL_PUNTS: int = 60      # full confidence (career-year starter)


# ---------------------------------------------------------------------------
# OL v1 (ADR-0025, 2026-05-14, audit-first design — TEAM-LEVEL grading).
# ---------------------------------------------------------------------------
# Offensive line is graded as a UNIT per (team_id, season), not per-player.
# nflverse data does not attribute pressures, sacks, or run-blocking lanes to
# specific OL players. Without paid PFF data, individual OL grading is not
# computable. Instead we grade the OL UNIT — which is how analysts and
# coaches actually discuss OL ("Eagles OL was elite in 2024").
#
# Storage: dedicated team_ol_stats / team_ol_components / team_ol_grades
# tables (migration 0018). Player-grading tables are not touched.
#
# Audit findings (2026-05-14, see audits/2026-05-14-exhaustive-ol.md):
# 13 candidates scored. Two clear winners with both YoY ≈ +0.42 and clean
# audit verdicts:
#   - yards_before_contact_per_carry: isolates OL run-blocking from RB
#       after-contact value. Best pure-OL run signal.
#   - pressure_proxy_per_dropback: (sacks + qb_hits) / dropbacks.
#       Comprehensive pass-block signal; sacks-only and hits-only are
#       subsumed (max_r ≈ 0.86–0.96 with this).
#
# Rejected: rush_yards/EPA/success/explosive (all mix OL with RB/scheme),
# stuff_rate (independent but YoY +0.219), false_start/holding/penalty rate
# (all YoY < 0.20 — noise). Penalties are real OL responsibility but the
# YoY signal isn't there at the team-season grain (likely roster turnover).
#
# Validity gate intentionally skipped per the locked plan — there is no
# "All-Pro OL unit" award and the per-team Pro Bowl OL count proxy is too
# noisy to use as a hard gate. See ADR-0025 for the rationale.
#
# Weight breakdown (sum |abs| = 0.90, 50/50 run/pass split):
#   ol_yards_before_contact_per_carry (50%): primary run-block signal
#   ol_pressure_proxy_per_dropback (-50%): primary pass-block signal
# ---------------------------------------------------------------------------

OL_COMPONENT_YBC_PER_CARRY: str = "ol_yards_before_contact_per_carry"
OL_COMPONENT_PRESSURE_PROXY: str = "ol_pressure_proxy_per_dropback"

OL_V1_WEIGHTS: dict[str, float] = {
    OL_COMPONENT_YBC_PER_CARRY:    0.45,
    OL_COMPONENT_PRESSURE_PROXY:  -0.45,
}

OL_V1_SHRINKAGE_K: dict[str, float] = {
    # Light shrinkage — every team has 400-550 rushes / 500-700 dropbacks
    # per season, so the per-play rate stabilizes quickly. We just want to
    # bound noise from a low-volume team-season.
    OL_COMPONENT_YBC_PER_CARRY:   30.0,   # in carries
    OL_COMPONENT_PRESSURE_PROXY:  40.0,   # in dropbacks
}

OL_V1_RAW_VALUE_COLS: dict[str, str] = {
    OL_COMPONENT_YBC_PER_CARRY:    "ybc_per_carry",
    OL_COMPONENT_PRESSURE_PROXY:   "pressure_proxy_per_dropback",
}

OL_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    OL_COMPONENT_YBC_PER_CARRY:    "rushes",
    OL_COMPONENT_PRESSURE_PROXY:   "dropbacks",
}

# Qualification: every team that played a season counts (32/season).
# We don't use a "min plays" gate the way per-player positions do because
# all teams have full-season volume.
OL_V1_QUALIFIED: bool = True


# ---------------------------------------------------------------------------
# Team v1 overall grading — ADR-0026
#
# Position weights within each phase, and phase weights into the overall.
# All derived empirically — see docs/grading/audits/2026-05-25-team-weights.md
# for the audit (ridge regression of team success on snap-weighted per-
# position grades + cap-allocation cross-check).
# ---------------------------------------------------------------------------

TEAM_V1_OFFENSE_WEIGHTS: dict[str, float] = {
    "QB": 0.45,
    "OL": 0.25,
    "WR": 0.13,
    "RB": 0.09,
    "TE": 0.08,
}

TEAM_V1_DEFENSE_WEIGHTS: dict[str, float] = {
    "EDGE": 0.24,
    "CB":   0.24,
    "LB":   0.22,
    "S":    0.20,
    "iDL":  0.10,
}

TEAM_V1_ST_WEIGHTS: dict[str, float] = {
    "K": 0.52,
    "P": 0.48,
}

TEAM_V1_PHASE_WEIGHTS: dict[str, float] = {
    "offense": 0.55,
    "defense": 0.40,
    "st":      0.05,
}
