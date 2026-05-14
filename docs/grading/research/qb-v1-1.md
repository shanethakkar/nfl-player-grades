# QB v1.1 — Research + Implementation (2026-05-14)

Status: **SHIPPED**. First production application of the four-criterion exhaustive audit framework. Re-graded QB 2016-2025 on Neon; validity improved +0.237 → +0.244.

## Conclusion

**Lower `qb_success_rate` from +0.25 → +0.10.** Keep `qb_epa_per_dropback` at +0.50 and `qb_cpoe` at +0.25. Sum |w| 1.00 → 0.85.

| Component | v1 | v1.1 | Effective share v1 | Effective share v1.1 |
|---|---:|---:|---:|---:|
| `qb_epa_per_dropback` | 0.50 | 0.50 | 50% | **59%** |
| `qb_cpoe` | 0.25 | 0.25 | 25% | **29%** |
| `qb_success_rate` | 0.25 | **0.10** | 25% | **12%** |

## Process — the exhaustive audit

This was the first position audited with the full four-criterion framework ([`audit-playbook.md`](../audit-playbook.md)). The methodology:

1. **Inventory every plausible QB candidate stat** from each data source (nflvs / NGS / PFR / pbp).
2. **Score each on four criteria** via `nflgrades audit-candidates --position QB`:
   - Reliability (YoY r)
   - Cross-sectional discrimination
   - Independence from existing components (max |r|)
   - Predictive validity (next-year Pro Bowl r)
3. **Document the verdict** per candidate — including rejected ones. The audit log is the methodology defense.

**Result:** 19 candidates scored. Full table in [`audits/2026-05-14-exhaustive-qb.md`](../audits/2026-05-14-exhaustive-qb.md).

## Key findings

### The three current components

| Component | YoY r | max \|r\| existing | partner | Validity r | Action |
|---|---:|---:|---|---:|---|
| `qb_epa_per_dropback` | +0.415 | +0.863 | qb_success_rate | **+0.158** (best) | KEEP at 0.50 |
| `qb_cpoe` | +0.377 | +0.726 | qb_success_rate | +0.146 | KEEP at 0.25 |
| `qb_success_rate` | +0.467 | +0.848 | qb_epa_per_dropback | +0.130 (worst) | **LOWER to 0.10** |

The 0.848 redundancy between EPA and success rate is mathematical: success_rate is "fraction of plays with positive EPA," EPA per dropback is the *mean* EPA. Same skill, two vantage points.

### No new candidates added

The audit found no compelling new components. Most interesting near-misses:

- **`qb_td_rate`** — highest validity of any candidate (+0.260), but +0.729 with EPA. Adding it would mostly double-count outcome value and chase consensus signal (TDs drive Pro Bowl voting).
- **`qb_rush_epa_per_rush`** — only candidate measuring a *skill not in current formula* (mobile QB value). Independent (max_r −0.08), modest YoY (0.398), weak validity (+0.04). **Documented as known limitation; not shipped in v1.1.** Pro Bowl voters reward passing, so validity is weak — but Lamar/Allen/Hurts are getting incomplete credit.
- **`qb_pfr_pressure_rate_faced`** — strong YoY (0.553), independent, but partly OL quality and partly QB pocket presence. Can't cleanly attribute with public data.

### Noise rejections

- **`qb_int_rate`** — NOISE (YoY 0.165, validity −0.150). Rare event; already in EPA.
- **`qb_sack_fumble_rate`** — NOISE (YoY 0.096). Rare-event-compounded-with-rare-event.
- **`qb_ngs_aggressiveness`** — **negative validity** (−0.213). Style, not skill.
- **`qb_ngs_time_to_throw`** — most stable YoY in audit (0.667!) but **validity 0.114** — pure style indicator. Mahomes (long) and Burrow (quick) both win Pro Bowls.

## Validity-gated shipping

The v1.1 change went through the validity gate:

- **Baseline:** QB composite vs next-year Pro Bowl: +0.237
- **After regrade:** QB composite vs next-year Pro Bowl: +0.244 (improved by +0.007)
- **Other positions:** unchanged (only QB weights touched)

This is the first weight change shipped with validity as an objective decision criterion. The change improved the formula's external alignment — not just an internal cleanup.

## Face-check 2024 top 10

Top 5 unchanged from v1: Lamar Jackson (MVP), Jared Goff (All-Pro), Joe Burrow (comeback year), Tua Tagovailoa (efficient when healthy), Josh Allen (MVP). All consensus-elite QBs.

Biggest movers:

**Up (more explosive than consistent):**
- Derek Carr +3.37 (had strong per-attempt EPA on a bad team)
- Russell Wilson +3.35
- Jalen Hurts +2.46 (Super Bowl QB)
- Justin Herbert +2.37
- Bryce Young +2.56 (improved late-season)

**Down (more consistent than explosive):**
- Matthew Stafford −2.91
- Mason Rudolph −2.81
- Kyler Murray −2.72
- Drake Maye −2.50 (rookie)
- Kirk Cousins −2.39

The pattern is exactly what we'd predict from the redundancy structure: lowering success_rate weight removes its smoothing effect, so QBs with high EPA volatility (explosive plays + some bad plays) rise relative to QBs with consistent-but-not-explosive profiles.

## Known limitations preserved

- **Mobile-QB gap.** Rush EPA isn't in the formula. Lamar/Allen/Hurts under-graded relative to consensus by this design choice. Documented as future work.
- **Pro Bowl voting bias.** Validity ceiling is ~0.50 because voters reward narrative + visibility + team success. r=0.244 is "very strong" for QB.

## What this audit confirms about the methodology

1. **Two independent diagnostics converged.** The pairwise correlation audit and the exhaustive candidate audit both flagged the same fix from different angles. That's the kind of convergent evidence that gives confidence in a weight change.

2. **The four-criterion framework works end-to-end.** From candidate inventory → scoring → verdict → ship → validity recheck. The process took ~half a day for QB; each subsequent position should be faster.

3. **Validity is the right decision criterion.** Without it, we'd be guessing whether the change is an improvement. With it, we have a single number that says "this change moves the formula toward consensus elite better than before."

4. **Most candidates fail.** Of 19 stats scored, exactly zero new ones got added to the formula. That's the methodology working — exhaustive scanning surfaces the surprises, but the surprises are mostly "we already had the right components."

## Tooling first-use notes

- **`nflgrades audit-candidates --position QB`** ran 19 candidates in ~20 seconds (cached nflverse data; first run for a season can take longer).
- **`nflgrades validity`** baseline-vs-postship comparison was instantaneous.
- **`nflgrades preview` → edit weights.py → `sync_weights_to_web.py` → `regrade`** workflow shipped the change in ~2 minutes mechanical.

The methodology is now production-tested. QB sets the template for positions 5-12.
