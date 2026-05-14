# LB Exhaustive Candidate Audit — 2026-05-14

Ninth production audit. **Fifth defensive position** (after CB, S, EDGE, iDL). **Final position in the master plan's exhaustive audit phase.** 19 candidates scored: 6 currently-shipped + 11 PFR-derived + 2 PFR-aggregate.

**Cohort:** qualified LB-seasons 2018-2024 (n=430 for snap-based candidates, n=135 for pressure-conversion candidates with min 8 pressures).

Tool: `nflgrades audit-candidates --position LB`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped:** | | | | | | | |
| `lb_tfl_rate` | 430 | +0.314 | 0.00 | +0.406 | lb_pressure_rate | +0.090 | Independent, weak validity |
| `lb_passer_rating_allowed` | 430 | **+0.146** | 15.19 | −0.387 | lb_pbu_rate | **−0.071** | OVER-WEIGHTED (weak YoY AND weak validity at -0.27) |
| `lb_missed_tackle_rate` | 430 | +0.232 | 0.03 | −0.257 | lb_tackle_rate | −0.072 | Independent, weak validity (DB-position pattern) |
| `lb_pbu_rate` | 430 | +0.085 | 0.04 | −0.389 | lb_passer_rating_allowed | +0.054 | NOISE (already at 0.05 from v1.1 reduction) |
| `lb_tackle_rate` | 430 | **+0.475** | 0.02 | −0.283 | lb_missed_tackle_rate | +0.052 | Strongest YoY in formula, weak validity |
| `lb_pressure_rate` | 430 | +0.407 | 0.00 | +0.407 | lb_tfl_rate | **+0.149** | **HIGHEST positive validity, UNDER-WEIGHTED (+0.07)** |
| **PFR passer-rating sub-components:** | | | | | | | |
| `lb_comp_pct_allowed` | 430 | +0.046 | 0.07 | +0.539 | lb_passer_rating_allowed | −0.055 | Subsumed by PR_allowed |
| `lb_yards_per_target_allowed` | 430 | +0.135 | 1.27 | +0.632 | lb_passer_rating_allowed | −0.039 | Subsumed by PR_allowed |
| `lb_int_rate` | 430 | +0.068 | 0.02 | −0.516 | lb_passer_rating_allowed | −0.021 | Subsumed by PR_allowed |
| `lb_td_rate_allowed` | 430 | +0.079 | 0.03 | +0.603 | lb_passer_rating_allowed | −0.091 | Subsumed by PR_allowed |
| **PFR pass-rush sub-components:** | | | | | | | |
| `lb_qb_hits_per_snap` | 430 | +0.298 | 0.00 | +0.730 | lb_pressure_rate | +0.113 | Subsumed by pressure_rate |
| `lb_hurries_per_snap` | 430 | +0.223 | 0.00 | +0.698 | lb_pressure_rate | +0.075 | Subsumed by pressure_rate |
| `lb_sack_rate` | 430 | +0.254 | 0.00 | +0.700 | lb_pressure_rate | +0.159 | Subsumed by pressure_rate |
| `lb_sack_per_pressure` | 135 | +0.221 | 0.13 | +0.268 | lb_tfl_rate | +0.092 | Independent but small n; weak validity |
| `lb_hit_per_pressure` | 135 | +0.245 | 0.16 | −0.152 | lb_passer_rating_allowed | −0.032 | Near-zero validity (same EDGE/iDL pattern) |
| **Splash-play candidates:** | | | | | | | |
| `lb_forced_fumble_per_snap` | 430 | +0.197 | 0.00 | +0.138 | lb_pressure_rate | +0.055 | NOISE (xsect 0.00, rare-event) |
| `lb_int_per_snap` | 430 | +0.085 | 0.00 | −0.501 | lb_passer_rating_allowed | −0.014 | NOISE / subsumed |
| **PFR coverage detail:** | | | | | | | |
| `lb_adot_allowed` | 400 | +0.193 | 1.45 | −0.187 | lb_tfl_rate | +0.038 | Scheme indicator, near-zero validity |
| `lb_yac_per_target_allowed` | 400 | +0.067 | 1.02 | +0.449 | lb_passer_rating_allowed | −0.042 | NOISE |

## Key findings

### Finding 1 — `lb_passer_rating_allowed` is structurally over-weighted

| Metric | LB | S (for comparison) | CB (for comparison) |
|---|---:|---:|---:|
| YoY r | +0.146 | +0.143 | +0.143 |
| Validity r | **−0.071** | **−0.178** | **−0.178** |
| Sample (targets/qualified season) | ~15-25 | ~50-70 | ~80-120 |
| Current weight | **-0.27 (32% of formula)** | -0.30 (42%) | -0.35 (50%) |

The metric is just as YoY-reliable for LB as for DBs, but the **predictive validity is half as strong** (−0.071 vs −0.178). Why? Two reasons:
1. **LBs have far fewer targets** (15-25 per qualified season vs 50-120 for DBs), so the per-player passer rating allowed is noisier even at qualified samples.
2. **Pro Bowl voters reward LB coverage less.** LBs are evaluated more by their highlight plays (sacks, INTs, splash tackles) than by their coverage-target damage.

The fix: lower `lb_passer_rating_allowed` weight from -0.27 to **-0.15**. Still primary coverage signal, but right-sized to its real signal strength at LB.

### Finding 2 — `lb_pressure_rate` is under-weighted (iDL-style mis-order)

`lb_pressure_rate` has the HIGHEST positive validity in the formula (+0.149) and a strong YoY (+0.407), but is the LOWEST-weighted positive component (+0.07, 8%). This is the same mis-order pattern caught at iDL v1.2 — pressure-related metrics under-weighted relative to validity.

The fix: bump `lb_pressure_rate` from +0.07 to **+0.10**. Modest because LB pressure samples are smaller than EDGE/iDL (most LBs have 5-15 pressures per season vs 30+ for pass rushers); we don't want to over-weight a metric that for many LBs is near zero.

### Finding 3 — LB has the weakest baseline validity for structural reasons

LB baseline validity is +0.179 — the lowest of any audited position:

| Position | Validity (v1) | "Stats vs reputation" gap |
|---|---:|---|
| iDL | +0.457 | minimal — pressure stats well-aligned |
| EDGE | +0.420 | minimal — sack/pressure stats well-aligned |
| TE | +0.384 | small — receiving stats align reasonably |
| WR | +0.280 | medium — EPA depends on QB |
| S | +0.253 | medium — voter noise (INT-driven) |
| RB | +0.243 | medium — rushing share is contextual |
| QB | +0.237 | medium — small Pro Bowl roster, surface stats matter |
| CB | +0.219 | high — voter noise (INT-driven, very high) |
| **LB** | **+0.179** | **highest — voters reward reputation more than box score** |

Roquan Smith, for example, is universally regarded as a top-3 LB but rarely grades top-10 in stat-based systems. His tackles and pressure rates are good but not elite; his Pro Bowl selections come from broader reputation. This is the structural ceiling on LB validity.

## Verdict notes

**`lb_passer_rating_allowed` — LOWER from -0.27 → -0.15.** ← v1.2 SHIPPED
- Weak YoY (just above noise) AND weak validity. Over-weighted at v1.

**`lb_pressure_rate` — BUMP from +0.07 → +0.10.** ← v1.2 SHIPPED
- Highest positive validity in formula; was lowest-weighted positive component.

**All other components — KEEP unchanged.**
- `lb_tfl_rate` (0.20): real signal (YoY +0.314, validity +0.090).
- `lb_missed_tackle_rate` (-0.15): real YoY (+0.232) but weak validity (-0.072 — sign correct). Same DB pattern; kept on skill-tree grounds.
- `lb_tackle_rate` (0.13): strongest YoY (+0.475) but weak validity (+0.052). Tackle volume is a real skill but voters discount it for LBs.
- `lb_pbu_rate` (0.05): already lowered in v1.1 from +0.08 → +0.05. Holds.

## Rejected new candidates

**PFR passer-rating sub-components** (`lb_comp_pct_allowed`, `lb_yards_per_target_allowed`, `lb_int_rate`, `lb_td_rate_allowed`) — REJECT. All +0.51 to +0.63 correlation with `lb_passer_rating_allowed`. Same subsumption pattern as CB v1.2 and S v1.2.

**PFR pass-rush sub-components** (`lb_qb_hits_per_snap`, `lb_hurries_per_snap`, `lb_sack_rate`) — REJECT. All +0.70+ correlation with `lb_pressure_rate`. Mechanical sub-components.

**`lb_sack_per_pressure`** — REJECT. n=135 (small), validity +0.092. Independent enough but the small sample and weak validity don't justify a new component.

**`lb_hit_per_pressure`** — REJECT. Validity −0.032, near-zero. Same EDGE/iDL pattern (turning pressures into hits isn't voter-rewarded).

**`lb_forced_fumble_per_snap`** — REJECT. Cross-sectional std 0.00 (extremely rare event), validity +0.055. Pure noise at qualified-LB sample sizes.

**`lb_int_per_snap`** — REJECT. Same as int_rate — subsumed by PR_allowed plus rare-event noise.

**`lb_adot_allowed`** — REJECT. Scheme indicator (matchup depth), validity +0.038 near-zero.

**`lb_yac_per_target_allowed`** — REJECT. YoY +0.067 noise; partially subsumed by PR_allowed.

## What this audit confirms

1. **The PR_allowed weight issue is position-size-dependent.** At DBs (50-120 targets/qualified season), PR_allowed is well-validated and weighted appropriately. At LB (15-25 targets), the metric is noisier and voters reward it less. The same component should be weighted **differently across positions** based on the underlying sample-size regime.

2. **The pressure_rate under-weight pattern generalizes across all DL+LB positions.** First found at iDL v1.2 (rebalance moved pressure 0.30→0.35), now confirmed at LB (pressure 0.07→0.10). Both formulas under-weighted what voters reward most among "behind-LOS" plays.

3. **The sub-component trap is universal across defensive positions.** PFR per-target stats (comp%, yds/tgt, INT rate, TD rate) get rejected at every position where passer_rating_allowed exists (CB, S, LB) for the same reason (mechanical subsumption). Same logic for QB hits/hurries vs pressure_rate at all three DL positions.

4. **LB has a structural validity ceiling.** No realistic re-weight or new component will close LB validity to EDGE/iDL levels because Pro Bowl voting is driven by LB reputation more than box-score stats. The v1.2 lift from +0.179 → +0.198 (+11%) is modest in absolute terms but is the largest *fractional* gain among defensive audits.

## Decision: LB v1.2 weight changes

| Component | v1.1 | v1.2 | Share v1.1 | Share v1.2 |
|---|---:|---:|---:|---:|
| `lb_tfl_rate` | +0.20 | +0.20 | 23% | 26% |
| **`lb_passer_rating_allowed`** | **-0.27** | **-0.15** | 31% | **19%** |
| `lb_missed_tackle_rate` | -0.15 | -0.15 | 17% | 19% |
| `lb_pbu_rate` | +0.05 | +0.05 | 6% | 6% |
| `lb_tackle_rate` | +0.13 | +0.13 | 15% | 17% |
| **`lb_pressure_rate`** | **+0.07** | **+0.10** | 8% | **13%** |

Sum |w|: 0.87 → 0.78.

**Validity gate:** LB composite vs next-year Pro Bowl correlation **+0.179 → +0.198 (+0.019)**. Strongest relative gain (+11%) of any defensive audit. Holds; no rollback.

**Face-check 2024 top 10:**
1. Zack Baun (DPOY runner-up, 1st-Team All-Pro)
2. Blake Cashman (Pro Bowl)
3. T.J. Edwards
4. Jordan Hicks
5. Kaden Elliss
6. Nakobe Dean
7. Quay Walker (Pro Bowl)
8. Bobby Wagner
9. Jordyn Brooks
10. Kyzir White

Top 2 are correct consensus #1 and #2 LBs of 2024. Notable absences: Roquan Smith (#19 — universally regarded top-3 LB; this is the structural stats-vs-reputation gap), Frankie Luvu (graded but lower; was selected to Pro Bowl from Commanders). The formula is not designed to predict Pro Bowl voting at LB — that would require encoding reputation directly. Documenting this gap is part of the article-defensibility goal.

## Pattern across all audited positions (final summary)

| Position | Validity (v1) | Validity (post-audit) | Change | Audit type |
|---|---:|---:|---:|---|
| iDL | +0.457 | +0.475 | +0.018 | Path A+B (rebalance + add) |
| TE | +0.384 | +0.407 | +0.023 | Path A |
| WR | +0.280 | +0.300 | +0.020 | Path A |
| RB | +0.243 → +0.247 (v1.3) | +0.259 (v1.4) | +0.016 | Path B |
| **LB** | **+0.179** | **+0.198** | **+0.019** | **Path A (rebalance)** |
| QB | +0.237 | +0.244 | +0.007 | Path A |
| EDGE | +0.420 | +0.424 | +0.004 | Path B |
| S | +0.253 | +0.255 | +0.002 | Path A |
| CB | +0.219 | +0.220 | +0.001 | Path A |

**All 9 positions audited.** Average validity lift: +0.012 (range +0.001 to +0.023). The audit framework's primary contribution is methodological — every weight in the system is now defensibly tied to a documented four-criterion screen of every plausible candidate.
