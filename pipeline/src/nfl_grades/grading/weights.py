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
# EDGE v1 (ADR-0020).
# ---------------------------------------------------------------------------
# Data sources:
#   - Pressures, sacks, QB hits, hurries, tackles, missed tackles:
#     pfr_advstats_def → pfr_def_pass_rush table (2018+)
#   - TFL (run stops, sacks excluded): nflvs_player_stats → pfr_def_pass_rush
#   - Defensive snaps: player_seasons.snaps_defense
#
# Coverage begins 2018 (PFR per-player data limitation).
#
# Formula: 72% pass rush / 17% run stop / 11% technique penalty.
# Sum |abs| = 0.90. Positive weights = higher is better.
# Negative weight = lower is better (missed tackles).
#
# edge_pressure_rate (39%): pressures (sacks+hits+hurries) per snap.
#   Primary signal — total pass rush impact per opportunity.
# edge_sack_rate (33%): sacks per snap. Premium outcome; extra credit
#   for converting pressure to sacks. Intentional overlap with pressure_rate
#   to weight the highest-value plays more heavily.
# edge_tfl_rate (17%): run-stop TFLs (sacks excluded) per snap.
#   EDGE rushers set the edge on run plays; elite ones generate real TFLs.
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
EDGE_COMPONENT_MISSED_TACKLE_RATE: str = "edge_missed_tackle_rate"

EDGE_V1_WEIGHTS: dict[str, float] = {
    EDGE_COMPONENT_PRESSURE_RATE:      0.35,
    EDGE_COMPONENT_SACK_RATE:          0.30,
    EDGE_COMPONENT_TFL_RATE:           0.15,
    EDGE_COMPONENT_MISSED_TACKLE_RATE: -0.10,
}

EDGE_V1_SHRINKAGE_K: dict[str, float] = {
    EDGE_COMPONENT_PRESSURE_RATE:      200.0,
    EDGE_COMPONENT_SACK_RATE:          350.0,
    EDGE_COMPONENT_TFL_RATE:           300.0,
    EDGE_COMPONENT_MISSED_TACKLE_RATE: 100.0,
}

EDGE_V1_RAW_VALUE_COLS: dict[str, str] = {
    EDGE_COMPONENT_PRESSURE_RATE:      "pressure_rate",
    EDGE_COMPONENT_SACK_RATE:          "sack_rate",
    EDGE_COMPONENT_TFL_RATE:           "tfl_rate",
    EDGE_COMPONENT_MISSED_TACKLE_RATE: "missed_tackle_rate",
}

EDGE_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    EDGE_COMPONENT_PRESSURE_RATE:      "snaps_defense",
    EDGE_COMPONENT_SACK_RATE:          "snaps_defense",
    EDGE_COMPONENT_TFL_RATE:           "snaps_defense",
    EDGE_COMPONENT_MISSED_TACKLE_RATE: "tackle_attempts",
}

EDGE_V1_MIN_SNAPS_TO_GRADE: int = 200
EDGE_V1_QUALIFIED_MIN_SNAPS: int = 400
EDGE_V1_CONFIDENCE_FULL_SNAPS: int = 700


# ---------------------------------------------------------------------------
# iDL v1.1 (ADR-0021, revised 2026-05-14).
# ---------------------------------------------------------------------------
# Data sources: same pfr_def_pass_rush table as EDGE (both are DL).
# TFL is the primary iDL differentiator; pass rush down-weighted vs EDGE.
#
# v1.1 (cross-position audit 2026-05-14): idl_missed_tackle_rate lowered
# from -0.15 → -0.05. Mean YoY r = 0.080 across 2018-2025 (one of the
# weakest signals in the entire system, below even WR/TE drop_rate at
# ~0.13). At -0.15 weight this was disproportionate noise contribution to
# the composite. Light weight bounds noise; not removed entirely because
# missed-tackle technique still has *some* in-season signal (mean r 0.080
# isn't zero, just low). Sum |w| drops 0.95 → 0.85; the combiner normalizes
# so the three signal-strong positive components (tfl, pressure, sack) get
# more effective weight. See project_cross_position_yoy_audit.md.
#
# idl_tfl_rate (35%): run-stop TFLs per snap. Interior penetration is what
#   separates elite DTs (Aaron Donald, Chris Jones) from average starters.
# idl_pressure_rate (30%): total pressures per snap. Interior pressure
#   counts but is rarer — an elite DT's pass-rush rate is lower than EDGE.
# idl_sack_rate (15%): sacks per snap. Interior sacks are premium but
#   structurally rarer than EDGE sacks; weighted lower than EDGE.
# idl_missed_tackle_rate (-5%): technique penalty, light weight per YoY noise.
#
# Sum |abs| = 0.85. Normalized dynamically by composite.combine.
# ---------------------------------------------------------------------------

IDL_COMPONENT_TFL_RATE: str = "idl_tfl_rate"
IDL_COMPONENT_PRESSURE_RATE: str = "idl_pressure_rate"
IDL_COMPONENT_SACK_RATE: str = "idl_sack_rate"
IDL_COMPONENT_MISSED_TACKLE_RATE: str = "idl_missed_tackle_rate"

IDL_V1_WEIGHTS: dict[str, float] = {
    IDL_COMPONENT_TFL_RATE:           0.35,
    IDL_COMPONENT_PRESSURE_RATE:      0.30,
    IDL_COMPONENT_SACK_RATE:          0.15,
    IDL_COMPONENT_MISSED_TACKLE_RATE: -0.05,
}

IDL_V1_SHRINKAGE_K: dict[str, float] = {
    IDL_COMPONENT_TFL_RATE:           300.0,
    IDL_COMPONENT_PRESSURE_RATE:      200.0,
    IDL_COMPONENT_SACK_RATE:          350.0,
    IDL_COMPONENT_MISSED_TACKLE_RATE: 100.0,
}

IDL_V1_RAW_VALUE_COLS: dict[str, str] = {
    IDL_COMPONENT_TFL_RATE:           "tfl_rate",
    IDL_COMPONENT_PRESSURE_RATE:      "pressure_rate",
    IDL_COMPONENT_SACK_RATE:          "sack_rate",
    IDL_COMPONENT_MISSED_TACKLE_RATE: "missed_tackle_rate",
}

IDL_V1_SAMPLE_SIZE_COLS: dict[str, str] = {
    IDL_COMPONENT_TFL_RATE:           "snaps_defense",
    IDL_COMPONENT_PRESSURE_RATE:      "snaps_defense",
    IDL_COMPONENT_SACK_RATE:          "snaps_defense",
    IDL_COMPONENT_MISSED_TACKLE_RATE: "tackle_attempts",
}

IDL_V1_MIN_SNAPS_TO_GRADE: int = 200
IDL_V1_QUALIFIED_MIN_SNAPS: int = 400
IDL_V1_CONFIDENCE_FULL_SNAPS: int = 700


# ---------------------------------------------------------------------------
# LB v1.1 (ADR-0022, revised 2026-05-14).
# ---------------------------------------------------------------------------
# v1.1 (cross-position audit 2026-05-14): lb_pbu_rate lowered from +0.08
# → +0.05. Mean YoY r = 0.085 across 2018-2025 — same noise pattern as
# idl_missed_tackle_rate. INTs are already captured inside passer_rating_
# allowed (which has more material weight), so pbu_rate was already a
# narrow "broke up the catch" play signal; with weak YoY it's barely
# carrying its weight. Not removed entirely because the cross-sectional
# spread is real (active plays show up) — light weight bounds noise.
# Sum |w| drops 0.90 → 0.87. See project_cross_position_yoy_audit.md.
# ---------------------------------------------------------------------------
# Off-ball linebackers. Multi-skill position covering run defense, coverage,
# and situational pass rush. Filter: target_rate >= 3.5% to exclude
# pass-rush OLBs misclassified as LB (T.J. Watt, Micah Parsons, etc.).
#
# Weight split: ~45% run defense, ~35% coverage, ~8% pass rush, 17% technique
# penalty.
#
# lb_tfl_rate (20%): run-stop TFLs per snap. Cleanest run-defense signal —
#   actual play-making behind the LOS.
# lb_passer_rating_allowed (-27%): NFL passer rating allowed when targeted.
#   Combines comp%, yards, TDs, and INTs into one industry-standard metric.
#   Heavily weighted because it's the cleanest LB coverage skill signal:
#   penalizes TDs allowed (yds/tgt didn't), rewards INTs, and rewards
#   forced incompletions all in one number.
# lb_missed_tackle_rate (-15%): technique penalty. LBs make the most
#   tackles of any position; missed ones cost the most.
# lb_pbu_rate (8%): PBU per target. Active play that broke up the catch.
#   INTs already captured inside passer rating allowed, so INT removed
#   from this component (vs original pbu_int_rate) to avoid double-count.
# lb_tackle_rate (13%): tackles per snap. Volume signal — bad LBs simply
#   don't accumulate tackles. Some team-context noise accepted for v1.
# lb_pressure_rate (7%): situational pass rush. Real signal for
#   blitz-heavy MLBs but near-zero for most LBs; small weight reflects.
#
# Sum |abs| = 0.90. Normalized dynamically by composite.combine.
# ---------------------------------------------------------------------------

LB_COMPONENT_TFL_RATE: str = "lb_tfl_rate"
LB_COMPONENT_PASSER_RATING_ALLOWED: str = "lb_passer_rating_allowed"
LB_COMPONENT_MISSED_TACKLE_RATE: str = "lb_missed_tackle_rate"
LB_COMPONENT_PBU_RATE: str = "lb_pbu_rate"
LB_COMPONENT_TACKLE_RATE: str = "lb_tackle_rate"
LB_COMPONENT_PRESSURE_RATE: str = "lb_pressure_rate"

LB_V1_WEIGHTS: dict[str, float] = {
    LB_COMPONENT_TFL_RATE:              0.20,
    LB_COMPONENT_PASSER_RATING_ALLOWED: -0.27,
    LB_COMPONENT_MISSED_TACKLE_RATE:    -0.15,
    LB_COMPONENT_PBU_RATE:              0.05,
    LB_COMPONENT_TACKLE_RATE:           0.13,
    LB_COMPONENT_PRESSURE_RATE:         0.07,
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
