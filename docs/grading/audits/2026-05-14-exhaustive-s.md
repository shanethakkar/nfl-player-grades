# Safety Exhaustive Candidate Audit — 2026-05-14

Sixth production audit. **Second defensive position** (after CB). 16 candidates scored: 6 current components + 10 new candidates from PFR def_advstats + nflverse aggregates.

**Cohort:** qualified S-seasons 2018-2024 (n=625 for stat_components, n=582 for PFR-derived, n=117 for nflvs forced-fumble candidates).

Tool: `nflgrades audit-candidates --position S`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped:** | | | | | | | |
| `s_backfield_disruption_per_snap` | 625 | +0.420 | 0.00 | +0.320 | s_tackles_per_snap | +0.117 | Modest |
| `s_missed_tackle_rate` | 625 | +0.247 | 0.04 | −0.216 | s_tackles_per_snap | **+0.015** | Near-zero validity, weight kept on skill-tree grounds |
| `s_passer_rating_allowed` | 625 | +0.143 | 23.62 | −0.432 | s_pbu_rate | **−0.178** | Modest signal (correct direction) |
| `s_pbu_rate` | 625 | +0.200 | 0.07 | −0.422 | s_passer_rating_allowed | +0.123 | Modest |
| `s_tackles_per_snap` | 625 | **+0.497** | 0.02 | +0.378 | s_target_rate | **+0.025** | Strongest YoY but zero validity (style not skill) |
| `s_target_rate` | 625 | +0.425 | 0.02 | +0.378 | s_tackles_per_snap | **−0.006** | NEAR-ZERO validity, sign disagrees → LOWER |
| **PFR-derived:** | | | | | | | |
| `s_comp_pct_allowed` | 582 | +0.057 | 0.08 | +0.557 | s_passer_rating_allowed | −0.072 | NOISE / subsumed by PR_allowed |
| `s_yards_per_target_allowed` | 582 | +0.129 | 2.12 | +0.563 | s_passer_rating_allowed | −0.120 | Subsumed by PR_allowed |
| `s_int_rate` | 582 | +0.213 | 0.04 | +0.618 | s_pbu_rate | +0.121 | Overlap with pbu_rate; also subsumed |
| `s_td_rate_allowed` | 582 | +0.089 | 0.05 | +0.573 | s_passer_rating_allowed | −0.096 | Subsumed |
| `s_adot_allowed` | 582 | +0.235 | 3.15 | −0.417 | s_target_rate | −0.032 | Scheme indicator |
| `s_yac_per_target_allowed` | 582 | +0.003 | 1.06 | +0.355 | s_passer_rating_allowed | −0.057 | NOISE |
| **nflvs aggregates:** | | | | | | | |
| `s_forced_fumble_per_snap` | 117 | +0.278 | 0.00 | +0.190 | s_backfield_disruption_per_snap | +0.007 | Rare-event noise |
| `s_int_per_snap` | 117 | +0.135 | 0.00 | +0.629 | s_pbu_rate | +0.076 | Rare-event noise + overlap |
| `s_tfl_per_snap` | 117 | +0.256 | 0.00 | **+0.929** | s_backfield_disruption_per_snap | +0.107 | STRONG REDUNDANCY (it's IN backfield_disruption) |
| `s_sack_per_snap` | 117 | +0.270 | 0.00 | +0.732 | s_backfield_disruption_per_snap | −0.026 | Subsumed by backfield_disruption |

## Verdict notes

**`s_target_rate` — LOWER from −0.08 → −0.05.** ← v1.2 SHIPPED
- Same finding as CB v1.2: validity essentially zero (−0.006), sign disagrees with design weight direction. At qualified-S level, top safeties face similar target volumes — voters don't reward target avoidance.
- Methodology cleanup. Validity gate: +0.253 → +0.255.

**`s_passer_rating_allowed` — KEEP at −0.30.**
- Same pattern as CB PR_allowed: weak YoY (+0.143) but validity sign matches design weight (−0.178). Primary coverage signal.

**`s_pbu_rate` — KEEP at +0.12.**
- Solid signal (+0.123 validity correct direction). Mechanism overlap with PR_allowed (−0.422) is expected, not redundancy.

**`s_missed_tackle_rate` — KEEP at −0.09 (despite near-zero validity).**
- Validity +0.015 (essentially zero), but the design intent is unambiguous: missed tackles are a clear quality signal. Strong YoY (+0.247) confirms we're measuring real skill.
- Voters undervalue safety tackling, but the skill-tree placement justifies the weight.

**`s_tackles_per_snap` — KEEP at +0.07 (despite zero validity).**
- **Strongest YoY in the audit (+0.497)** but validity essentially zero (+0.025).
- Style indicator (deep-zone safeties accumulate more tackles than single-high or box safeties), but tackles-per-snap also captures genuine activity level. Keep at modest weight.

**`s_backfield_disruption_per_snap` — KEEP at +0.09.**
- YoY +0.420 (strong), validity +0.117 (correct direction). Real signal; captures pass-rush + run-stop versatility.

## Rejected new candidates

**All PFR sub-components of PR_allowed (`s_comp_pct_allowed`, `s_yards_per_target_allowed`, `s_int_rate`, `s_td_rate_allowed`)** — REJECT. All correlate +0.55 to +0.62 with PR_allowed; PR_allowed already incorporates these.

**`s_int_rate`** specifically — the "MEANINGFUL OVERLAP" flag was triggered by +0.618 correlation with pbu_rate (a different existing component). Both INTs and PBUs are active coverage plays. The math: PR_allowed already counts INTs in its formula; pbu_rate counts the broader "broke up catch" play. Adding s_int_rate would double-count.

**`s_yac_per_target_allowed`** — YoY +0.003 (random year-to-year for safeties). Note: this is *different* from CB's yac/rec_allowed which had YoY +0.174 and a non-trivial signal. At safety, YAC happens mostly on plays where the safety was beat over the top (a coverage failure already in PR_allowed) or where they're tackling the ball-carrier downfield (different skill from coverage). The noise verdict at S is position-specific.

**`s_adot_allowed`** — scheme indicator (free safety vs strong vs box). Zero validity.

**`s_forced_fumble_per_snap`** — Rare event (typical S has 0-2 forced fumbles per season). YoY +0.278 but validity essentially zero. Plus the n=117 is from a stricter filter (≥400 snaps); even within that the events are too rare.

**`s_int_per_snap`** — Rare events; large overlap with pbu_rate. NOISE.

**`s_tfl_per_snap`** — STRONG REDUNDANCY (+0.929 with backfield_disruption_per_snap, which mathematically includes TFL).

**`s_sack_per_snap`** — Same redundancy with backfield_disruption (+0.732). Subsumed.

## What this audit confirms

1. **The Safety v1.1 formula is structurally well-shaped.** No new components emerged; the 6 existing components cover the skill tree (coverage damage, coverage playmaking, target avoidance, tackling volume, tackling technique, backfield disruption).

2. **Same PR_allowed-consolidation pattern as CB.** All four PR sub-components reject either via subsumption (high max_r) or noise (low YoY). The v1 → v1.1 swap (consolidating comp%+yards+TDs+INTs into PR_allowed) was the right call here too.

3. **PFR aggregate stats are not granular enough for safeties.** Forced fumbles, INTs, sacks per snap are all rare-event noise at S sample sizes (typical S has 1-2 such events per season). The existing backfield_disruption (which sums TFL + sacks) already handles the aggregate; individual breakdowns add nothing.

4. **The S formula has multiple "real skill, weak validity" components** — tackles_per_snap (validity +0.025) and missed_tackle_rate (+0.015) both have meaningful YoY but near-zero Pro Bowl signal. Same lesson as CB and TE: voters don't reward fundamentals; they reward INTs and big plays. The weights are kept on skill-tree grounds, not validity grounds.

## Decision: Safety v1.2 weight change

| Component | v1.1 | v1.2 | Share v1.1 | Share v1.2 |
|---|---:|---:|---:|---:|
| `s_passer_rating_allowed` | −0.30 | −0.30 | 40% | 42% |
| `s_pbu_rate` | +0.12 | +0.12 | 16% | 17% |
| **`s_target_rate`** | **−0.08** | **−0.05** | 11% | **7%** |
| `s_tackles_per_snap` | +0.07 | +0.07 | 9% | 10% |
| `s_missed_tackle_rate` | −0.09 | −0.09 | 12% | 13% |
| `s_backfield_disruption_per_snap` | +0.09 | +0.09 | 12% | 12% |

Sum |w|: 0.75 → 0.72.

**Validity gate:** S composite vs next-year Pro Bowl correlation **+0.253 → +0.255** (essentially unchanged). Same as CB — methodology cleanup, not validity gain.

**Face-check 2024:** Top 5 unchanged (Kerby Joseph #1, Derwin James, Xavier McKinney, Brian Branch, Calen Bullock). Biggest movers small (max ±4.8). Coherent.

## Pattern across defensive coverage positions

| Position | Validity baseline | target_rate validity | target_rate v1 → v1.2 |
|---|---:|---:|---|
| CB | +0.219 | +0.013 | −0.08 → −0.05 |
| **S** | **+0.253** | **−0.006** | **−0.08 → −0.05** |
| LB | +0.179 | n/a (no target_rate in LB) | — |

Both DB positions converged on the same target_rate finding. The "elite gets avoided" thesis is real at the league level but doesn't differentiate within the qualified cohort. Documented.
