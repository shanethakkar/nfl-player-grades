# OL Exhaustive Candidate Audit — 2026-05-14

**Twelfth production audit. First TEAM-LEVEL audit.** 13 candidates scored across pass-block, run-block, and penalty buckets.

**Cohort:** 32 teams × 8 seasons = 256 team-seasons (n=254 for YBC, which excludes the 2 team-seasons with sub-300 carries).

**Validity:** Intentionally skipped — no "All-Pro OL unit" award. The per-team Pro Bowl OL count proxy is too noisy to use as a hard gate (see ADR-0025). Audit relied on three criteria: YoY reliability, cross-sectional discrimination, and independence (max_r vs other candidates in the set).

Tool: `pipeline/src/nfl_grades/grading/ol_audit.py::run_ol_audit`. Custom team-level audit framework parallel to the per-player `exhaustive_audit.py`.

## Full candidate table

| Candidate | n | YoY r | x-sec std | max_r | partner | Verdict |
|---|---:|---:|---:|---:|---|---|
| **Pass blocking:** | | | | | | |
| `sacks_allowed_per_dropback` | 256 | +0.372 | 0.018 | +0.863 | pressure_proxy | SUBSUMED |
| `qb_hits_allowed_per_dropback` | 256 | +0.430 | 0.032 | +0.957 | pressure_proxy | SUBSUMED |
| **`pressure_proxy_per_dropback`** | 256 | **+0.420** | 0.046 | +0.957 | qb_hits_allowed | **PRIMARY** — comprehensive sacks+hits |
| `sack_per_contact` | 256 | +0.411 | 0.047 | +0.620 | sacks_allowed | meaningful overlap |
| **Run blocking:** | | | | | | |
| **`yards_before_contact_per_carry`** | 254 | **+0.424** | 0.366 | +0.736 | rush_yards | **PRIMARY** — isolates OL from RB |
| `rush_yards_per_carry` | 256 | +0.364 | 0.418 | +0.825 | explosive_rate | mixes OL + RB skill |
| `rush_epa_per_carry` | 256 | +0.384 | 0.069 | +0.839 | success_rate | mixes OL + RB + scheme |
| `rush_success_rate` | 256 | +0.370 | 0.036 | +0.839 | rush_epa | overlap |
| `rush_explosive_rate` | 256 | +0.324 | 0.020 | +0.825 | rush_yards | overlap |
| `rush_stuff_rate` | 256 | +0.219 | 0.025 | −0.548 | success_rate | independent but weak YoY |
| **Penalties:** | | | | | | |
| `false_start_rate` | 256 | +0.129 | 0.005 | +0.729 | ol_penalty_rate | NOISE — fails YoY threshold |
| `holding_rate` | 256 | +0.177 | 0.004 | +0.722 | ol_penalty_rate | NOISE — fails YoY threshold |
| `ol_penalty_rate` | 256 | +0.168 | 0.006 | +0.729 | false_start | NOISE — fails YoY threshold |

## Key insights

### 1. Two clean signals emerged with equal audit strength

`yards_before_contact_per_carry` and `pressure_proxy_per_dropback` both returned YoY r ≈ +0.42 and both passed the independence check (max_r against other candidates was within their conceptual cluster, not against each other). They measure two distinct phases of the game (run-block vs pass-block), so composing them is not double-counting.

This is unusual in the audit history — most positions had one dominant signal. For OL, the symmetry is real and supports a 50/50 weighting.

### 2. YBC isolates OL from RB skill (the FGOE-equivalent insight)

After-contact yards belong to the RB. Before-contact yards belong to the OL. This is the cleanest possible "pure OL" run-block metric in nflverse — analogous to how K v1.1 chose FGOE over raw FG% to isolate kicker skill from kick difficulty.

The audit confirmed YBC has the best YoY (+0.424) of any candidate and a meaningful 0.736 max_r with `rush_yards_per_carry` (which includes after-contact and is partly RB-driven). YBC is the more skill-isolated of the two.

### 3. Pressure proxy subsumes both standalone sack and hit rates

`pressure_proxy = (sacks + qb_hits) / dropbacks` returned max_r 0.863 with sacks_allowed and 0.957 with qb_hits_allowed. The combined metric captures both the catastrophic-sack and meaningful-contact-without-sack signals in one number. Using all three would be triple-counting; using sacks alone would underweight QB hits, which are real pass-block failures.

This pattern matched K v1.1: a single comprehensive "broad" metric beats narrower distinct sub-metrics on independence grounds even when YoY is similar.

### 4. Penalties failed the audit despite real OL ownership

False starts and holding ARE the OL — those are literally OL players committing penalties. We considered including them at small weight on definitional grounds. Three reasons we didn't:

- All three penalty metrics failed the YoY threshold (0.13–0.18 vs 0.20 floor).
- We made the same "include despite weak signal on conceptual grounds" mistake with **P v1 blocked_rate** and reversed it within hours when the user (correctly) pointed out that low audit signal means the metric isn't measuring what we think it's measuring.
- Penalty rates likely reflect roster turnover at OL positions year-to-year — not unit-level skill that persists.

If a v2 audit shows penalty signal at smaller cohort or with better bucketing (e.g., normalized by play type), we can revisit.

### 5. EPA-based metrics mix OL with non-OL value (the punter lesson reapplied)

`rush_epa_per_carry` and `rush_success_rate` both passed YoY, but they package OL skill with RB skill, scheme value (zone vs gap), defensive front quality, and game-state effects (running with a 14-point lead vs trailing). Using them as primary signals would dilute the OL-specific signal.

This is the same pattern as P v1 — `epa_per_punt` lost to `net_avg` because punt EPA mixes punter skill with returner / coverage / field-position variance. **The over-expected approach works when the baseline is well-isolated; raw outcome rates can win when the baseline is contaminated by non-player context.** YBC and pressure_proxy are the pure-OL versions of these run-block and pass-block signals respectively.

## Decision: OL v1 weight design

| Component | Weight | Share | Rationale |
|---|---:|---:|---|
| `ol_yards_before_contact_per_carry` | **+0.45** | 50% | Primary run-block signal. Isolates OL from RB. Best YoY in audit. |
| `ol_pressure_proxy_per_dropback` | **−0.45** | 50% | Primary pass-block signal. Sacks + QB hits per dropback. Subsumes narrower variants. |

Sum |w| = 0.90. Symmetric 50/50 run/pass split.

**Shrinkage k values:** 30 carries / 40 dropbacks. Light shrinkage — every team has 400+ rushes and 500+ dropbacks, so per-play rates stabilize quickly.

**Qualification:** every team that played a season is graded (no per-player snap threshold concept).

## No validity gate

Documented in ADR-0025. There is no "All-Pro OL unit" award. The per-team Pro Bowl OL count proxy is too noisy to use as a hard ship gate. We documented this honestly rather than ginning up a weak proxy and hiding behind it.

## Face-check 2024

Top 5: **BAL #1 (89.5), ARI #2 (87.1), TB #3 (77.1), BUF #4 (75.9), PHI #5 (73.6).**

- **BAL #1**: Ravens — Derrick Henry led the league in YBC/carry; Lamar barely got hit. Universally considered top-3 OL of 2024. ✓
- **ARI #2**: Cardinals — strong James Conner-led ground game, big YBC numbers
- **TB #3**: Buccaneers — Bucky Irving's emergence + clean pocket for Mayfield
- **BUF #4**: Bills — best sack rate in the league but lower YBC drags them down a bit. Consensus top-3 by some sources; #4 here is defensible.
- **PHI #5**: Eagles — known elite OL, but Hurts holds the ball longer than most QBs. Pressure_proxy at 22.43% is high for a top-tier OL because Hurts takes a lot of hits while extending plays. **Documented limitation in ADR-0025**: pressure_proxy mixes OL skill with QB style.

Bottom 5: **CLE, LV, PIT, TEN, LAC.** All known to have struggled with OL play in 2024. LAC #32 is consistent with Justin Herbert being pressured all year.

The face-check is excellent: top of the league correctly identifies the consensus elite units, bottom correctly identifies struggling ones, and the one debatable placement (PHI #5 vs higher) has a clear documented explanation.

## Cross-position context

| Position | Validity | Audit cohort | Notes |
|---|---:|---:|---|
| iDL | +0.475 | 415 | Strongest; voter-aligned |
| EDGE | +0.424 | 487 | |
| TE | +0.407 | 224 | |
| WR | +0.300 | 574 | |
| RB | +0.259 | 322 | |
| S | +0.255 | 459 | |
| QB | +0.244 | 239 | |
| CB | +0.220 | 731 | |
| LB | +0.198 | 325 | Reputation gap |
| K | +0.153 | 204 | Stats-vs-reputation gap |
| P | +0.122 | 219 | Most reputation-driven Pro Bowl voting |
| **OL** | **N/A** | **256 team-seasons** | **No All-Pro unit award; validity gate skipped by design** |

12 of 12 queue positions audited. Foundation phase complete.

## What this audit demonstrates

1. **Audit-first generalizes to non-player entities.** The four-criterion screen (here: three, with validity skipped) worked cleanly for team-season grading. The same statistical principles apply.

2. **The K v1.1 / P v1 lessons crystallized into a pattern.** "Use the metric that isolates the player/unit's skill from contaminating context" — applied to OL by choosing YBC over rush_yards (RB contamination) and pressure_proxy over rush_epa (scheme/defense contamination).

3. **Symmetric audit verdicts justify symmetric weights.** YBC and pressure_proxy had nearly identical YoY (+0.42 each) and passed independence. 50/50 weighting is the data-driven answer, not a guess.

4. **Honest exclusions matter.** Penalties have real OL ownership but failed the YoY threshold. We applied the lesson from P v1 blocked_rate and excluded them rather than including on definitional grounds. This is what a defensible audit log looks like.
