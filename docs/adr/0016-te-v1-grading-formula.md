# 0016 — TE v1 grading formula

- **Status**: Accepted (v1.2 revision — 2026-05-14)
- **Date**: 2026-04-23
- **Companion to**: ADR-0013 (QB), 0014 (RB), 0015 (WR); ADR-0003 (data tier); ADR-0009 (parquet cache)

## Context

TE grades must reflect **receiving** only in v1: public data does not support a
repeatable blocking grade (no PFF-style charting). Role labels and
`data_tier_reason` communicate what the number measures (see **Role** and
**data_tier** below).

## Decision — composite (tier 1, full six components)

Same structure as WR v1 with **separation at 7%** (WR uses 10%). NGS separation
is **WR-coverage-geometry** calibrated; TE-vs-LB/S matchups are noisier in the
same metric — **downweight, do not drop**.

| Component | Weight |
|-----------|--------|
| `te_rec_epa_per_target` | 0.35 |
| `te_yac_over_expected_per_rec` | 0.27 |
| `te_separation` | 0.07 |
| `te_target_earn_rate` | 0.10 |
| `te_success_rate_per_target` | 0.08 |
| `te_drop_rate` (v1.1) | -0.05 |

Sum of magnitudes `|w| = 0.92` (signed sum `0.82`; composite normalizer uses
**sum of absolute weights** — see `test_signed_weights_normalize_by_magnitude`
and TE tests in `test_composite.py`). v1 used `te_fumble_rate` at −0.05 in
the slot now held by `te_drop_rate`; same magnitude, different component.
See "Revision history" below.

The earlier "0.95" figure in this ADR was a copy-paste artifact from WR v1
(WR has separation at 0.10 → WR `|w| = 0.95`); TE separation is downweighted
to 0.07 for NGS-calibration reasons, giving `|w| = 0.92`.

**YAC weight = WR (27%)**: do **not** increase TE YAC weight on intuition alone;
if TE YAC YoY correlation meaningfully exceeds WR YAC in validation, consider
v1.1 weight shift with evidence.

### Tier 2 — `role = blocking_te`

Target earn rate is **role-dominated** for Y-heavy TEs. Omit **earn** from the
composite; redistribute **0.10** to EPA and YAC in proportion **0.35∶0.27**
(→ **0.406** and **0.314**). Other components unchanged. The component row for
`te_target_earn_rate` is still written with **raw / shrunk / z**;
`stat_components.used_in_composite = false` for that row.

Because the redistribution **preserves magnitude**, tier-2 has the same
`|w| = 0.92` and signed sum `0.82` as tier-1 — on an all-z=1 TE the two
dicts both produce `0.82 / 0.92 ≈ 0.8913`. The dicts differ by *where the
earn mass lands*, not by total weight.

### Filters, features

- Receiving filter: same as WR/RB receiving (`RB_REC_FILTER_SQL`).
- Features: plays + `ngs_receiving` (week=0) for separation; `plays` for
  xYAC-based YAC-over-expected; `player_seasons` summed `snaps_offense` for role.
- Fumble denominator: **receptions**.

### Qualification

- **15** targets minimum to emit a grade row.
- **40** targets for `qualified`.
- **Confidence** = `min(1, targets / 70)`.

### Shrinkage (per-position `k`)

TE **target earn** `k = 100` team pass attempts (vs WR **200**) — smaller
cross-player dispersion in earn rate. Other components align with WR (EPA 50,
YAC 30, separation 40, success 50, fumble 100).

### Role buckets

- `receiving_te`: target share ≥ 0.10 (targets / offensive snaps, season).
- `balanced_te`: 0.05 ≤ share < 0.10, or low-snap / low-rate catch-alls.
- `blocking_te`: share < 0.05 **and** offensive snaps ≥ 200.

### `data_tier` and `data_tier_reason`

Era leg: `_era_tier_for_season` in `grading/era_tier.py` → `(tier, reason)` with
`reason = era_pre_ngs` when tier ≥ 2 from era alone.

TE merge (grading-only):

- If `role == blocking_te` and era tier **1** → `data_tier = 2`,
  `data_tier_reason = role_blocking_te`.
- If `role == blocking_te` and era tier **≥ 2** → keep era tier,
  `data_tier_reason = era_and_role`.
- Else → era `(tier, reason)` only.

Non-TE positions: `role` NULL; `data_tier` / `data_tier_reason` from era tuple
only.

### Schema (migration 0006)

`season_grades.role`, `season_grades.data_tier_reason`,
`stat_components.used_in_composite`.

### Pure blocking TEs (< 15 targets)

No `season_grades` row. Team/roster UI must not hide these players when built
(see plan / UX note).

### Validation

Target TE YoY **r** band **0.40–0.55** (slightly below WR); interpret like ADR-0015.

### Deferred

Blocking grade, alignment splits, red-zone split, target-per-route earn rate,
CB matchup, etc.

## References

- `pipeline/src/nfl_grades/grading/te.py`
- `pipeline/src/nfl_grades/grading/era_tier.py`
- `docs/adr/0003-data-tier-and-qualified-as-first-class-columns.md`

## Revision history

### v1.1 (2026-05-14) — drop_rate in, fumble_rate out

**Replaced `te_fumble_rate` (−0.05) with `te_drop_rate` (−0.05).** Same magnitude in the same slot. Sum |weights| unchanged at 0.92.

**Why fumble out:** YoY r for TE fumble rate across 2020-2025 oscillated around zero (+0.01, +0.20, +0.07, −0.25, +0.36, mean ≈ +0.08). ~50% of qualified TEs had 0 fumbles in a season; max 3. Same noise pattern as WR fumble rate. Fumbles still penalized implicitly via `te_rec_epa_per_target` (a fumble play has negative EPA).

**Why drops in:** Drops are the only TE-skill gap v1 didn't measure. FTN charting (`ftn_receiving_charting`, 2022+) already integrated for WR v1.1. TE drop_rate YoY r across 2022-2025: +0.33, +0.02, +0.04 (mean +0.13). Modest signal, just below the 0.20 threshold for "meaningful." Correlation with other TE components (2024, n=34) all below |r|=0.40 — independent skill dimension. Face-check passes: 2024 best hands Hooper/Akins/Moreau/Likely (0 drops); worst Cade Otton 7/59 (11.9%), David Njoku 7/74 (9.5%).

**Why −0.05, not heavier:** Initially considered −0.10 on the structural argument that TE separation is downweighted vs WR (0.07 vs 0.10) and on the position-emphasis intuition that hands matter more for TEs. Pulled back to −0.05 after a self-audit found that WR v1.1 had added `wr_drop_rate` at −0.08 without running the YoY noise check on it. When run after the fact, WR drop_rate YoY mean r ≈ +0.09 — indistinguishable from the fumble rate we removed. By the methodology's own threshold (|r| < 0.20 → "weight tiny ≤0.05 or remove"), the WR weight was over-weighted. Applying the rule consistently across positions: both TE and WR drop_rate land at −0.05. WR re-shipped as v1.2 (ADR-0015) the same day. See `memory/project_te_v1_1_research.md` for the full audit, including the measurement-error-suppression caveat that justifies inclusion at light weight despite weak YoY.

**Pre-2022 seasons:** FTN data starts 2022. For 2016-2021 TE seasons, `te_drop_rate` is NaN-neutralized to 0 composite contribution. Grade is computed from the remaining 5 components only.

**Blocking-TE tier-2:** Drop_rate stays at −0.05 in `TE_V1_BLOCKING_WEIGHTS` (same as `TE_V1_WEIGHTS`). Target-earn redistribution (→ EPA 0.406, YAC 0.314) unchanged.

**Schema:** No migration needed — `ftn_receiving_charting` already exists from WR v1.1 (migration 0014). TE grader joins it via `player_id + season`.

**Follow-up:** the WR drop_rate gap exposed a methodology hole — additions skipped the YoY noise check that removals applied. A cross-position audit (every component × every shipped position) is queued before any more positions ship. See `memory/project_pending_audits.md`.

### v1.2 (2026-05-14) — `target_earn_rate` bumped, `success_rate` lowered (exhaustive audit)

**Two weight changes:**

- **`te_target_earn_rate`** bumped from +0.10 → **+0.15** (effective share 11% → 16%).
- **`te_success_rate_per_target`** lowered from +0.08 → **+0.05** (effective share 9% → 5%).

Sum |weights| 0.92 → 0.94. Other components unchanged.

For the **blocking_te tier-2** path, the redistribution of `target_earn_rate` weight scales: 0.15 redistributed to EPA + YAC in 0.35:0.27 proportion → EPA = **0.435**, YAC = **0.335**, separation = 0.07, success_rate = 0.05, drop_rate = −0.05.

**Why:** TE exhaustive candidate audit ([`docs/grading/audits/2026-05-14-exhaustive-te.md`](../grading/audits/2026-05-14-exhaustive-te.md)) scored 22 plausible TE candidates. Two key findings:

1. **`te_target_earn_rate` is the strongest signal in the formula** — Pro Bowl validity r = **+0.301** (highest of any candidate, current or proposed) and YoY r = +0.610 (also highest among current components). At v1.1's 0.10 weight (11% share), it was meaningfully underweighted. Same finding pattern as WR v1.3.

2. **EPA-vs-success-rate redundancy at TE** — max |r| = +0.723 with `te_rec_epa_per_target`. Same mathematical pattern now confirmed at FOUR positions (QB 0.88, WR 0.76, RB 0.71, TE 0.72). Bounded at 0.05.

**Validity gate passed (strongest Path A gain in any audit so far):** TE composite vs next-year Pro Bowl correlation **+0.384 → +0.407** (+0.023 improvement). TE was already the strongest offensive position in pre-audit baseline; now it's even stronger.

**Face-check 2024:**

| Rank | Player | v1.1 grade | v1.2 grade | Δ |
|---:|---|---:|---:|---:|
| 1 | George Kittle | 89.7 | 88.9 | −0.7 |
| 2 | Tucker Kraft | 86.2 | 85.2 | −1.0 |
| 3 | Jonnu Smith | 72.1 | 71.8 | −0.3 |
| 4 | Isaiah Likely | 73.1 | 71.5 | −1.6 |
| 5 | Mark Andrews | 72.6 | 70.7 | −1.9 |
| 6 | Trey McBride | 60.6 | 63.3 | **+2.7** |

**Brock Bowers rises 18 → 13** (+2.98). One of the known face-check misses — Bowers was undergraded by v1.1's efficiency-heavy formula despite elite target volume (153 targets as a rookie). The earn_rate bump partially corrects this.

**Audit also found and documented:**

- `te_separation` has **NEGATIVE Pro Bowl validity (−0.053)**. Interpretation: TE voters reward tight-window catchers (Kelce/Andrews/Kittle) over open-route runners. Strong YoY (+0.413) says we're measuring real skill. **Kept at 0.07** — don't reverse-engineer validity.
- `te_pfr_broken_tackle_per_rec`: independent signal (max_r +0.43), modest YoY (+0.419), weak validity (+0.117). Same YAC-skill gap as the QB rush/WR broken-tackle/RB-pre-v1.4 patterns. **Documented as future consideration; not shipped** — validity isn't strong enough to justify a Path B schema change (vs RB yards_after_contact which had +0.192).
- 18 other candidates rejected with documented reasoning. Full table in the audit log.

**Pattern across offensive positions** (all 4 now audited):

| Position | EPA↔success r | success_rate change | target_earn change |
|---|---:|---|---|
| QB | +0.883 | 0.25 → 0.10 | n/a |
| RB | +0.713 | 0.14 → 0.05 | n/a |
| WR | +0.763 | 0.08 → 0.05 | 0.10 → 0.15 |
| TE | +0.723 | 0.08 → 0.05 | 0.10 → 0.15 |

Consistent application of the methodology. The EPA-vs-success-rate redundancy is a structural pattern, not a coincidence.
