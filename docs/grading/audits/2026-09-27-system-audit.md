# Grading system audit — 2026-09-27

A full review of how grades are computed, how the current formulas were
arrived at, and whether they hold up empirically. It was done before the
2026 in-season (weekly) rollout. Every grade in the system came out of a
single day of audits (2026-05-14) run by an older model, and this revisits
that work.

**Verdict:** the architecture is sound and conventional:

> rate components → empirical-Bayes shrinkage → within-(season, position)
> z-score → weighted composite → sigmoid

The *calibration* and the *weight-selection process* are not sound. There
are also three correctness bugs. Opponent adjustment, the thing most
obviously "missing", turns out to be the **least** valuable fix. It matters
somewhat for QB and barely anywhere else.

All numbers below were computed read-only against production (Neon)
and the 2016–2025 pbp parquet cache. Recomputations were cross-checked
against stored values before use:
- stored z-scores reproduce `composite_z` at r = 1.000 for every position;
- the pbp rebuild of the QB, WR and TE composites matches production at r ≥ 0.999;
- the validity code reproduces the published numbers.

---

## 1. How the current system was built

| Pos | Formula (weights.py) | Origin of v1 | Revisions and the evidence used |
|---|---|---|---|
| QB | EPA/db .50, CPOE .25, success .10 | Priors ("rules of thumb", `qb-v1-proposal.md`) | v1.1: success .25→.10. Pairwise r .88 with EPA. Pro Bowl validity .237→.244. |
| RB | RYOE .28, rush EPA .18, SR .05, rec EPA .05, YAC-OE .28, YACon .10, fumble −.05 | Prior 60/35/5 rush/rec/security split | v1.1–1.4: catch% out, rec EPA cut, SR cut, YACon added. YAC-OE .28 is where freed weight was parked to *preserve* the 33% receiving prior. |
| WR | rec EPA .35, YAC-OE .27, sep .10, earn .15, SR .05, drop −.05 | Priors | v1.1–1.3: fumble out, drop added, earn .10→.15. Validity .280→.300. |
| TE | WR clone, sep .07; blocking path | Copied from WR | Same as WR. Validity .384→.407. |
| CB | PR allowed −.35, YAC/rec −.15, tgt rate −.05, PBU .12 | Priors + 2024 face-check ("Humphrey #13→#4") | v1.2: target rate cut. .219→.220. |
| S | PR allowed −.30, PBU .12, tgt −.05, tkl .07, MT −.09, backfield .09 | Priors + face-check | v1.2: target rate cut. |
| EDGE | pressure .35, sack .30, TFL .15, tkl .05, MT −.10 | Priors | v1.1: 3-4 OLBs moved in. v1.2: tackles added. |
| iDL | pressure .35, TFL .25, sack .20, tkl .05, MT −.05 | Priors | v1.2: reordered to match Pro Bowl validity ranking ("voters reward pressure"). |
| LB | TFL .20, PR −.15, MT −.15, PBU .05, tkl .13, pressure .10 | Priors + face-check. Qualification raised 400→600 because role players topped the list. | v1.2: PR −.27→−.15. |
| K | FGOE/att 1.00 | v1 raw rates; v1.1 first-principles rewrite the same day | — |
| P | net .55, inside-20 .30 | Audit-first | v1.1: block rate removed. |
| OL (team) | YBC/carry .45, pressure proxy −.45 | Audit (YoY + independence); 50/50 split "by symmetry" | — |
| Team | Position-weighted phases .55/.40/.05 | Ridge on same-season point differential + priors | Phase weights changed the same day. |

**The evaluation framework** (`audit-playbook.md`) uses four criteria:
1. YoY r ≥ .20
2. "Cross-sectional spread"
3. Max |r| with existing components < .60
4. Next-year Pro Bowl r ≥ .15

In practice, criterion 4 decided most revisions. The playbook also carves
out a "context-dependent skill" exception: a low-YoY component is kept at
full weight if it has spread and validity.

---

## 2. Findings, ranked by impact

### F1. Grade scales are not comparable across positions or eras (major)

The composite is Σ(wᵢ/Σ|w|)·zᵢ, a weighted *average* of z-scores. Its SD
is √(w′Rw), not 1, and it depends on how correlated each position's
components are. The sigmoid assumes SD = 1. Observed values, qualified
players only, 2016–2025:

| Pos | SD(composite_z) | p99 grade | max | % ≥ 90 | SDs needed for a 90 |
|---|---|---|---|---|---|
| K | 0.99 | 90.6 | 95.8 | 1.4% | 1.9 |
| QB | 0.92 | 90.2 | 94.2 | 1.5% | 2.1 |
| iDL | 0.84 | 94.8 | 98.3 | 3.2% | 2.3 |
| EDGE | 0.81 | 91.0 | 96.3 | 1.3% | 2.4 |
| CB | 0.70 | 88.3 | 91.8 | 0.4% | 2.7 |
| TE | 0.64 | 89.3 | 91.5 | 0.3% | 3.0 |
| WR | 0.63 | 86.1 | 90.5 | 0.1% | 3.0 |
| RB | 0.61 | 85.6 | 91.9 | 0.2% | 3.2 |
| S | 0.55 | 80.3 | 89.4 | **0** | 3.5 |
| LB | 0.47 | 82.8 | 88.6 | **0** | 4.1 |

- The √(w′Rw) prediction matches the observed SD to two decimals, so this is structural, not noise.
- **No LB or S has ever graded 90.**
- `methodology.md`'s claim that "a 92 is ~98th percentile at any position" is false.
- The same effect operates across eras. RB 2016–17 has 38% of its weight zero-filled (no RYOE or YACon data), so SD is 0.42 and the best 2016 RB maxes at 76.9.

**Fix:** divide `composite_z` by the qualified-cohort SD of the composite
before the sigmoid, and renormalize weights over the components actually
present (instead of filling missing components with 0). It is rank-preserving
within a position-season and makes the documented claim true by
construction. For in-season use, standardize with the pooled per-position SD
from completed seasons, not the week-3 cohort.

### F2. Much of the reliable signal at QB/WR/TE/CB is team context (major)

This is YoY of `composite_grade` for players who **stayed** on the same team
versus players who **changed** teams:

| Pos | Stayers r (n) | Changers r (n) |
|---|---|---|
| QB | 0.46 (188) | **0.01** (37) |
| TE | 0.56 (154) | **0.03** (31) |
| WR | 0.35 (413) | **0.10** (84) |
| CB | 0.23 (410) | **0.03** (143) |
| LB | 0.32 (186) | 0.05 (47) |
| iDL | 0.65 (239) | 0.36 (69) |
| EDGE | 0.63 (236) | 0.45 (78) |

Pooled across positions: stayers 0.39, changers 0.18. The changer n's are
small and changing teams is not random. The component-level pattern
separates the two explanations, though:

| Component | Stayers r | Changers r | |
|---|---|---|---|
| WR target earn rate | .68 | .63 | portable |
| EDGE pressure rate | .63 | .62 | portable |
| QB EPA/dropback | .43 | .10 | collapses |
| TE rec EPA/target | .42 | −.09 | collapses |
| CB PR allowed | .15 | −.04 | collapses |

Pure role flux would hit all components. Instead only the outcome-efficiency
ones collapse, which points to team context.

A receiver's EPA/target explains 24–26% of its variance from its QB's
EPA/dropback (8–10% leave-receiver-out). Receiver composite vs. own QB
composite: r ≈ 0.45.

### F3. Weights are inversely aligned with reliability at RB/WR/TE (major)

Split-half reliability (odd vs. even weeks, Spearman-Brown to full season):

| Pos | Component (share of weight) | Reliability |
|---|---|---|
| WR | rec EPA/target (38%) | **0.20** |
| WR | YAC-OE (29%) | 0.41 |
| WR | separation (11%) | 0.66 |
| WR | target earn rate (16%) | **0.88** |
| WR | **composite** | **0.44** |
| TE | rec EPA/tgt (39%) / YAC-OE (30%) / earn (17%) | 0.27 / 0.40 / 0.87 |
| TE | **composite** | **0.42** |
| RB | RYOE (33%) / YAC-OE (33%) / rush EPA (21%) | 0.24 / 0.17 / 0.32 |
| RB | **composite** | **0.35** |
| QB | EPA/db / CPOE / success | 0.61 / 0.54 / 0.65 |
| QB | **composite** | **0.62** |

About 68% of WR/TE weight sits on the two least reliable components. The
WR composite is half as reliable as target earn rate alone. The RB
composite is mostly noise within a season. These split-half numbers are
also an *upper* bound on individual skill, because both halves share the
QB and scheme.

The "context-dependent skill" exception is what kept these weights in
place. It rests on a raw-unit SD that is being used as a "discrimination"
measure (`exhaustive_audit._xsect_std`), which is unit-dependent. It also
treats wide spread in a noisy metric as evidence of skill, when that spread
*is* the noise.

Caveat on earn rate: it partly measures usage/role, and ADR-0015 capped
it for that reason. But it is the one receiver component that survives team
changes (F2), which is the best available evidence that it is attached to
the player.

### F4. The Pro Bowl validity gate cannot support the decisions made with it (major)

1. **It can't resolve the deltas.** Absolute r has SE ≈ 0.03–0.07. The
   paired bootstrap, clustered by player, on the shipped tweaks:

   | Change | Δr | 95% CI |
   |---|---|---|
   | QB v1.1 | +.007 | [.000, .014] |
   | EDGE v1.2 | +.005 | [.000, .009] |
   | CB v1.2 | +.001 | [−.003, .004] |
   | LB v1.2 | +.020 | [−.013, .051] |
   | WR v1.3 | +.020 | [.014, .026] |

   All of these are in-sample. The changes were chosen by looking at the
   same metric, and **no hold-out was ever run**. The playbook requires one
   for changes ≥ .10 of weight, but it wasn't possible anyway: the labels
   end at 2024 Pro Bowls, so the 2024–25 window has no next-year label.
2. **Candidate validity is computed with mislabeled rows.**
   `exhaustive_audit._validity_r` (lines 157–176) skips the season-window
   filter that `validity.compute_validity` applies. Seasons with no
   observable next-year Pro Bowl (2016, 2024, 2025) are counted as
   "not selected". About 105 of 344 QB rows are affected, about half of
   FTN-era rows and about a quarter of PFR-era rows. Every
   candidate accept/reject decision against the .15 threshold rests on
   biased numbers. This includes the rejection of QB rushing EPA.
3. **The name-only join ignores position** (`validity.build_panel`).
   Josh Allen QB and Josh Allen EDGE share selections. Byron Murphy CB and
   DT collide. ST selections count for position grades.
4. **It uses next-year selection.** Same-season r is roughly double for
   QB/K/P (.54 vs .24 for QB). Next-year selection mostly measures
   persistence plus reputation, and it mechanically rewards high-YoY volume
   stats.
5. **It tunes toward voters.** The iDL rebalance was justified as
   "voters reward pressure". iDL has the highest Pro Bowl validity (.475)
   and the lowest link to team success (r .12). Several designs were also
   tuned to 2024 face-checks (the CB/S/LB passer-rating swaps, LB 600-snap
   threshold, TE v1.2 "Bowers rises"), which contradicts the playbook's own
   rule against flattering known players.
6. A reputation-free check: grade in N predicts the next-season primary
   stat **no better than that stat predicts itself** at most positions:

   | Position | Grade → next-season stat | Stat → next-season stat |
   |---|---|---|
   | QB | .42 | .42 |
   | LB | .17 | .31 |
   | CB | −.12 | .11 |

### F5. QB grade excludes all scrambles (bug)

`filters.QB_DROPBACK_FILTER_SQL` requires `passer_player_id IS NOT NULL`,
and nflverse leaves that null on scrambles. In 2024 that drops all 1,062
scrambles, averaging **+0.54 EPA**, from QB EPA/dropback.
`qb-v1-proposal.md` explicitly says scrambles are included. Rough 2024
impact:

| QB | EPA/db | Rank |
|---|---|---|
| Daniels | .086 → .168 | 13 → 9 |
| Hurts | .115 → .184 | 10 → 6 |

Designed QB runs appear nowhere in the QB grade. QB rush EPA (YoY .40,
independent of the other components) was rejected on the buggy validity
number in F4.2.

### F6. Opponent adjustment: small effect, only worth it for QB full-season (the thing we expected to matter)

Method:
- Team-level additive model per season and play set: league + offense +
  defense, shrunk (λ ≈ 330–590 plays), leave-own-offense-out.
- Play value minus opponent defense rating, then the production shrinkage,
  z-score and weights.
- CB passer rating allowed and EDGE pressure/sack rates were adjusted the
  same way, using weekly PFR opponent data.

| Pos | Schedule SD / player SD | Spearman old vs adj | Mean \|Δgrade\| | Max \|Δgrade\| | YoY raw → adj |
|---|---|---|---|---|---|
| **QB** | 0.10 | 0.988 | **1.5** | **8.8** | **.428 → .450** (better in 7 of 9 pairs) |
| RB | 0.09 | 0.998 | 0.4 | 1.8 | .283 → .286 |
| WR | 0.05 | 0.999 | 0.4 | 1.8 | .322 → .325 |
| TE | 0.05 | 0.997 | 0.4 | 1.9 | .508 → .507 |
| CB | 0.06 | 0.998 | 0.7 | 3.1 | PR allowed .109 → .106 |
| EDGE | 0.09–0.11 | 0.996 | 1.1 | 5.3 | pressure .624 → .611 |

**In-season (weeks 3 and 6):** adjustment does not improve prediction of
rest-of-season performance. It doesn't even when using *oracle* end-of-season
defense ratings. For example, QB composite at week 3: raw .424 vs adjusted .414–.418.
Early-season noise is far larger than schedule strength.

Conclusion:
- **Don't adjust in-season.** Show strength-of-schedule faced as a context
  column instead.
- **Don't adjust RB/WR/TE/CB/EDGE.**
- **QB full-season adjustment is optional and low priority:** a real but
  small stability gain. Do it only as part of the QB rework (F5).
- Note: `stat_components.adjusted_value` currently stores the *shrunk*
  value, not an opponent-adjusted one. The `*_PRE_ADJUSTED` flags are unused,
  and their premise is wrong: RYOE, xYAC and separation adjust for play
  situation, not opponent.

### F7. Smaller issues

- **Shrinkage k is hand-set, never derived.** `methodology.md` claims k
  is "tuned using YoY"; it wasn't. The data-driven value is
  k = (per-play noise variance) / (true between-player variance), which
  split-half gives directly. This matters much more in-season: correct k is
  what makes week-3 grades appropriately conservative.
- **Missing components are filled with z = 0** before `composite.combine`,
  which was written to propagate NaN. For example, WR/TE drops pre-2022 (61%
  of WR rows) and RB RYOE/YACon 2016–17. Covered by the F1 fix.
- **Coverage stats are mostly noise.** CB PR allowed is 52% of the CB grade
  and S PR allowed is 42% of S. Their YoY is .11–.15, their portability is
  about 0, and their grade → next-season-stat correlation is negative. The
  "Tier 2/3 confidence badge" promised in `methodology.md` was never
  shipped.
- **Team grades:** weights are fit by regressing same-season point
  differential on grades built from same-season EPA, which is partly
  mechanical. `audit_team_weights.py:303` takes `abs(coef)`. ST weights come
  from R² .04. ADR-0026 and the weights audit disagree on phase weights.
  Sacks count in both QB EPA and the OL grade.
- **EDGE population leak:** Derrick Brown and A'Shawn Robinson (iDL) appear
  in 2025 EDGE grades.
- **FTN has `is_qb_fault_sack` and `is_interception_worthy` (2022+).** This
  contradicts the docs' "can't separate OL vs QB sacks" and "turnover-worthy
  plays are PFF-only".
- **Doc drift:** `methodology.md` still says 4 positions are shipped,
  describes a WP-based garbage-time rule (the code uses score/time) and a
  "variance-weighted" z mean (it's unweighted). ADR-0023 still describes
  K v1 limitations.

---

## 3. What holds up

- **Architecture.** Per-play rates, shrinkage, then within-season standardization is
  the right shape, and grading math is pure and isolated (ADR-0007).
- **Every formula input is a rate.** There are no volume totals, so partial
  seasons work mechanically once thresholds are pro-rated.
- **K FGOE** (difficulty-adjusted from first principles) and the **OL
  YBC / RB yards-after-contact split** are well-reasoned attribution choices.
- **Removals of rare-event noise** (WR fumble, RB catch%, P blocks) and
  **success-rate cuts** where it double-counts EPA are justified by mechanism,
  not just by the validity deltas.
- **QB** is the healthiest position: composite reliability .62, and all
  components are reasonably reliable.
- **EDGE/iDL** are strong and portable: YoY .58–.60, holding .36–.45 across
  team changes.

---

## 4. Recommendation

Ship in this order. Each step is independently useful.

1. **Fix the bugs.** Include QB scrambles (F5). Fix `_validity_r`'s season
   window and add position to the Pro Bowl join (F4.2–4.3). Remove the
   EDGE leak. These are small and uncontroversial.
2. **Fix the scale (F1).** Standardize the composite before the sigmoid,
   and renormalize weights over the components that are present. This is a
   pure math change and rank-preserving within position-season.
   `regrade` can apply it, but `preview`/`regrade` and web copy about
   "90 = 97th pct" need to agree.
3. **Replace the evaluation harness (F4) before touching weights.** New
   primary criteria, all reputation-free and all computable in-repo:
   - split-half reliability of the composite;
   - team-changer YoY (portability);
   - rest-of-season / next-season prediction.

   Keep same-season, position-matched Pro Bowl/All-Pro only as a face-validity
   check. Require a true hold-out: fit on 2016–2022, evaluate on 2023–2025.
4. **Re-derive shrinkage k from split-half variance (F7)** and **re-weight
   RB/WR/TE (F3)** under the new harness. Expect:
   - a large shift toward target earn rate and separation for WR/TE;
   - a teammate-relative or QB-residualized version of EPA/target instead of
     raw EPA/target, which is the actual fix for ADR-0017;
   - a smaller RB receiving share.

   Add QB rushing EPA as a candidate and re-test it with the corrected harness.
5. **Weekly in-season pipeline**, with the provisional label and pro-rated
   thresholds. Data-derived k (step 4) does most of the work of making
   early-season grades sensible.
6. **Deferred:**
   - QB opponent adjustment (F6): do it only if step 4's harness shows the
     +.02 YoY gain holds out-of-sample.
   - CB/S coverage-stat rework, possibly with a lower-confidence badge.
   - Team-grade weight refit.

Opponent adjustment beyond QB, unit-level RAPM and a hierarchical model
stay out of scope. This audit found no evidence that they would beat the
simpler fixes above.

## Reproducibility

The analysis scripts are in
[pipeline/scripts/audit_2026_09_27/](../../../pipeline/scripts/audit_2026_09_27/):
`opp_adj/` (`common.py`, `build_offense.py`, `analyze_full.py`,
`analyze_partial.py`, `analyze_defense.py`) and `reliability/`
(`t1_scale.py` … `t6_zero.py`). They were promoted in #12 as the starting
point for the evaluation harness (`nflgrades evaluate`).
