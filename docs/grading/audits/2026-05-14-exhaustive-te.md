# TE Exhaustive Candidate Audit — 2026-05-14

Fourth production application of the four-criterion audit framework. 22 plausible TE candidate stats scored against reliability + cross-sectional discrimination + independence + predictive validity.

**Cohort:** qualified TE-seasons 2017-2024 (n=332 for stat_components, n=278 for NGS 2017+, n=138 for FTN 2022+, n=258 for PFR 2018+).

Tool: `nflgrades audit-candidates --position TE`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped (re-scored with self-excluded):** | | | | | | | |
| `te_drop_rate` | 138 | +0.128 | 0.03 | −0.234 | te_success_rate_per_target | −0.020 | NOISE (light weight ok) |
| `te_rec_epa_per_target` | 332 | +0.365 | 0.21 | **+0.723** | te_success_rate_per_target | +0.165 | MEANINGFUL OVERLAP |
| `te_separation` | 332 | +0.413 | 0.55 | +0.201 | te_yac_over_expected_per_rec | **−0.053** | Strong YoY, NEGATIVE validity (style not skill) |
| `te_success_rate_per_target` | 332 | +0.428 | 0.07 | **+0.723** | te_rec_epa_per_target | +0.112 | MEANINGFUL OVERLAP |
| `te_target_earn_rate` | 332 | **+0.610** | 0.05 | −0.135 | te_separation | **+0.301** | **STRONG ADD candidate** |
| `te_yac_over_expected_per_rec` | 332 | +0.485 | 1.29 | +0.431 | te_rec_epa_per_target | **+0.183** | STRONG ADD candidate flag (already in formula) |
| **nflvs-derived:** | | | | | | | |
| `te_td_rate` | 332 | +0.096 | 0.03 | +0.445 | te_rec_epa_per_target | +0.020 | NOISE |
| `te_first_down_rate` | 332 | +0.371 | 0.07 | +0.789 | te_rec_epa_per_target | +0.201 | MEANINGFUL OVERLAP |
| `te_yards_per_target` | 332 | +0.434 | 1.32 | +0.748 | te_rec_epa_per_target | +0.252 | MEANINGFUL OVERLAP |
| `te_catch_rate` | 332 | +0.369 | 0.07 | +0.546 | te_success_rate_per_target | +0.089 | Independent / weak validity |
| `te_target_share` | 332 | +0.612 | 0.05 | **+0.978** | te_target_earn_rate | +0.304 | STRONG REDUNDANCY (duplicate) |
| `te_air_yards_share` | 332 | +0.699 | 0.06 | +0.818 | te_target_earn_rate | +0.299 | MEANINGFUL OVERLAP |
| **NGS receiving (2017+):** | | | | | | | |
| `te_ngs_cushion` | 278 | +0.322 | 0.51 | −0.138 | te_yac_over_expected_per_rec | −0.053 | Defense-driven |
| `te_ngs_intended_air_yards` | 278 | +0.613 | 1.68 | −0.361 | te_separation | +0.076 | Style marker |
| `te_ngs_yac_above_expectation` | 278 | +0.490 | 0.79 | +0.726 | te_yac_over_expected_per_rec | +0.213 | MEANINGFUL OVERLAP (duplicate of our YAC-OE) |
| `te_ngs_air_yards_share` | 278 | +0.583 | 5.55 | +0.756 | te_target_earn_rate | +0.329 | MEANINGFUL OVERLAP |
| `te_ngs_catch_pct` | 278 | +0.364 | 6.69 | +0.545 | te_success_rate_per_target | +0.080 | Independent / weak validity |
| **FTN charting (2022+):** | | | | | | | |
| `te_ftn_contested_rate` | 138 | +0.394 | 0.07 | −0.467 | te_separation | +0.001 | Inverse of separation |
| `te_ftn_created_reception_rate` | 138 | +0.306 | 0.03 | −0.199 | te_separation | +0.006 | Zero validity |
| **PFR advanced (2018+):** | | | | | | | |
| `te_pfr_broken_tackle_per_rec` | 258 | +0.419 | 0.04 | +0.431 | te_yac_over_expected_per_rec | +0.117 | Independent / weak validity |
| `te_pfr_drop_pct` | 258 | +0.186 | 0.03 | +0.641 | te_drop_rate | −0.012 | NOISE |
| `te_pfr_receiving_rat` | 258 | +0.287 | 10.21 | +0.771 | te_rec_epa_per_target | +0.213 | MEANINGFUL OVERLAP (QB-driven) |

## Per-candidate verdict + reasoning

### Currently shipped — v1.2 decisions

**`te_target_earn_rate` — BUMP from 0.10 → 0.15.** (same as WR v1.3)
- The strongest signal in the formula by validity (+0.301) and YoY (+0.610). Same finding pattern as WR.
- New share: 16% of formula. Validity-gated.

**`te_rec_epa_per_target` — KEEP at 0.35.**
- Modest YoY (+0.365) and validity (+0.165). Heavily redundant with success_rate (+0.723).
- Fix the redundancy on the success_rate side.

**`te_success_rate_per_target` — LOWER from 0.08 → 0.05.** (same as WR/QB/RB pattern)
- EPA-vs-success-rate redundancy now confirmed at FOUR positions:
  - QB EPA ↔ success_rate: r = +0.883
  - WR rec_epa ↔ success_rate: r = +0.763
  - RB rush_epa ↔ rush_success_rate: r = +0.713
  - **TE rec_epa ↔ success_rate: r = +0.723**
- Structurally guaranteed (success_rate = fraction of positive-EPA plays).
- Bounded at 0.05 weight.

**`te_yac_over_expected_per_rec` — KEEP at 0.27.**
- Modest YoY (+0.485), modest validity (+0.183), reasonably independent (max_r +0.431).
- Real receiving signal. "STRONG ADD" flag in the audit is because the four-criterion score qualifies — but it's already in the formula.

**`te_separation` — KEEP at 0.07 (despite negative validity).**
- Strong YoY (+0.413) but **NEGATIVE Pro Bowl validity (−0.053).**
- Interpretation: TE Pro Bowl voters reward tight-window catchers (Kelce/Andrews/Kittle archetype — high contested rate, lower separation) over open-route runners (2nd-tier TEs on bad teams who run free against zone coverage).
- Strong YoY says we're measuring real skill. Don't reverse-engineer validity — that would be chasing voter taste. Document and keep.
- Same philosophical call as WR separation (validity +0.003) — keep at current weight.

**`te_drop_rate` — KEEP at −0.05.**
- YoY +0.128, validity −0.020 (essentially zero). At light weight; the v1.1 audit justified it on face-check + cross-sectional + measurement-error caveat.

### Rejected new candidates (documented)

**`te_target_share` — REJECT (duplicate, max_r +0.978 with target_earn_rate).**

**`te_ngs_yac_above_expectation` — REJECT (duplicate of our YAC-OE, +0.726).**

**`te_first_down_rate`, `te_yards_per_target`, `te_catch_rate`, `te_air_yards_share`** — all reject for max_r > 0.6 with EPA or earn_rate. Standard EPA-family overlaps.

**`te_pfr_receiving_rat` — REJECT.** +0.771 with EPA, mostly QB-driven (passer rating when targeted reflects QB more than receiver).

**`te_td_rate` — NOISE.** YoY +0.096. Same low-frequency pattern as QB/WR/RB TD-rate candidates.

**`te_ngs_cushion`, `te_ngs_intended_air_yards`** — defense-driven / style markers. Same rejection pattern as WR.

**`te_ftn_contested_rate`** — −0.467 with separation (inverse), validity essentially zero. Same as WR.

**`te_ftn_created_reception_rate`** — validity +0.006 (zero). Skip.

**`te_pfr_drop_pct`** — NOISE (YoY +0.186, validity essentially zero). Our FTN drop_rate is the better source.

### Borderline (documented gap)

**`te_pfr_broken_tackle_per_rec` — DOCUMENT as known gap; don't ship.**
- YoY +0.419 (modest), max_r +0.431 (independent enough), validity +0.117 (weak).
- Captures YAC-via-tackle-breaking — same conceptual gap we documented for QB rush_epa and WR broken_tackle.
- The RB equivalent (yards_after_contact) had STRONGER validity (+0.192) which made it worth a Path B ship. The TE version's validity is +0.117 — borderline. Not worth a separate PFR rec ingest module + grader change for a weak validity signal.

## What this audit confirms

1. **EPA-vs-success-rate redundancy is now confirmed at all 4 receiver/passer positions** — QB (0.88), WR (0.76), RB (0.71), TE (0.72). The pattern is mathematical; the methodology should treat both components as candidates for the same skill-slot, with success_rate getting the lighter weight.

2. **target_earn_rate is consistently underweighted at WR and TE.** Both had this as the strongest validity signal in the audit. Bumping both from 0.10 to 0.15 is the same finding applied twice.

3. **TE has a distinctive separation profile** — slightly NEGATIVE validity. This is a position-specific finding (WR was +0.003 — also weak but not negative). TE separation reflects archetype (open-route vs tight-window) more than skill at the qualified level.

4. **No Path B candidates emerged.** Unlike RB (where yards_after_contact had +0.192 validity), TE's broken-tackle-per-rec is only +0.117. Documented as gap.

## Decision: TE v1.2 weight changes

| Component | v1.1 | v1.2 | Share v1.1 | Share v1.2 |
|---|---:|---:|---:|---:|
| `te_rec_epa_per_target` | 0.35 | 0.35 | 38% | 37% |
| `te_yac_over_expected_per_rec` | 0.27 | 0.27 | 29% | 29% |
| `te_separation` | 0.07 | 0.07 | 8% | 7% |
| **`te_target_earn_rate`** | 0.10 | **0.15** | 11% | **16%** |
| **`te_success_rate_per_target`** | 0.08 | **0.05** | 9% | **5%** |
| `te_drop_rate` | −0.05 | −0.05 | 5% | 5% |

Sum |w|: 0.92 → 0.94.

For the **blocking_te tier-2** path, the redistribution of target_earn_rate weight scales proportionally: 0.15 redistributed across EPA + YAC in 0.35:0.27 proportion → EPA = 0.435, YAC = 0.335, separation = 0.07, success_rate = 0.05, drop_rate = −0.05.

## Validity gate

- Baseline: TE composite vs next-year Pro Bowl = +0.384 (strongest validity among offensive positions in pre-audit baseline)
- After v1.2: **+0.407 (+0.023 improvement)** — **strongest single-change Path A gain in any audit so far.**

Other positions unchanged. The shift toward earn_rate (highest-validity signal) measurably improves alignment with consensus-elite recognition.

## Face-check 2024

Preview vs current top 10:

| Rank | Player | v1.1 → v1.2 | Note |
|---:|---|---|---|
| 1 | George Kittle | 89.7 → 88.9 (−0.7) | All-Pro, holds #1 |
| 2 | Tucker Kraft | 86.2 → 85.2 (−1.0) | holds #2 |
| 3 | Jonnu Smith | 72.1 → 71.8 | was #5 |
| 4 | Isaiah Likely | 73.1 → 71.5 | was #3 |
| 5 | Mark Andrews | 72.6 → 70.7 | was #4 |
| 6 | Trey McBride | 60.6 → 63.3 (+2.7) | was #9 |
| 7 | Dallas Goedert | 61.8 → 62.0 | hold |
| 8 | Sam LaPorta | 61.7 → 61.7 | hold |

**Notable: Brock Bowers rises 18 → 13** (+2.98). Addresses one of the known face-check misses — Bowers was undergraded by the v1.1 efficiency-heavy formula despite his elite target volume. Now reflected.

**Travis Kelce moves 29 → 28** (+2.33). Still low because his per-target efficiency is below average for a Pro Bowl TE, but he gets some target_earn credit back.

## Pattern across all four offense audits

| Position | EPA↔success r | success_rate weight change | target_earn change |
|---|---:|---|---|
| QB | +0.883 | 0.25 → 0.10 | n/a (no earn component) |
| RB | +0.713 (rush) | 0.14 → 0.05 | n/a (no earn component) |
| WR | +0.763 | 0.08 → 0.05 | 0.10 → 0.15 |
| TE | +0.723 | 0.08 → 0.05 | 0.10 → 0.15 |

Consistent application of the methodology across offensive positions.
