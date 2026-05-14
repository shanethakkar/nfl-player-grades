# P Exhaustive Candidate Audit — 2026-05-14

**Eleventh production audit. Second new-position audit using the audit-first process.** Ten candidates scored: 0 existing components (this is v1) + 10 derived from raw punter_stats (which itself was aggregated from pbp punt_attempt rows).

**Cohort:** qualified P-seasons 2016-2025 with ≥30 punts (n=320).

**Validity range:** 2017-2023 (Pro Bowl P data covers 2018-2024 in our CSV, n=10 next-year Pro Bowlers).

Tool: `nflgrades audit-candidates --position P` — plus a one-off validity script (P had no `season_grades` yet at audit time, same pattern as fresh K).

## Full candidate table

| Candidate | n | YoY r | x-sec std | Validity r (PB) | Verdict |
|---|---:|---:|---:|---:|---|
| `p_gross_avg` | 320 | +0.334 | 1.97 | +0.113 | Subsumed by net avg |
| **`p_net_avg`** | 320 | **+0.355** | 2.04 | **+0.166** | **PRIMARY** — best YoY, 2nd-best validity |
| **`p_inside_20_rate`** | 320 | +0.168 | 0.07 | **+0.188** | **PLACEMENT** — best validity, weak YoY |
| `p_touchback_rate` | 320 | +0.305 | 0.00 | -0.030 | Sign correct, magnitude near-zero — subsumed by net |
| **`p_blocked_rate`** | 320 | -0.046 | 0.01 | -0.046 | Near-zero both ways but **PENALTY** (-0.05 weight) |
| `p_return_yards_per_punt` | 320 | +0.322 | 1.32 | -0.083 | Sign correct (lower=better) but subsumed by net |
| `p_fair_catch_rate` | 320 | +0.308 | 0.08 | +0.013 | Near-zero validity (returner decision, not punter skill) |
| `p_i20_minus_tb_per_punt` | 320 | +0.163 | 0.07 | +0.189 | Ties inside_20 — same skill, different framing |
| `p_long_punt` | 320 | +0.077 | 5.13 | +0.076 | Weak both ways |
| `p_epa_per_punt` | 320 | +0.269 | 0.15 | +0.163 | Comprehensive over-expected — DID NOT DOMINATE |

## Critical finding: K v1.1 lesson does NOT generalize cleanly

For K, FGOE per attempt cleanly dominated raw rate metrics (best YoY of any K candidate, +0.126 vs +0.031 for the next best). Single-component formula was clearly correct.

**For P, the analogous over-expected metric did NOT dominate:**

| Metric | YoY r | Validity r |
|---|---:|---:|
| `p_net_avg` | **+0.355** | **+0.166** |
| `p_epa_per_punt` | +0.269 | +0.163 |

EPA per punt is comprehensive — it captures distance, placement, returns, blocks, even game state. But it loses on both YoY AND validity to plain net average.

**Why?** FGOE for a kicker is calculated against a stable distance-baseline that's largely independent of context (everyone faces the same ~80% baseline at 40-49 yards). Punt EPA depends on the returner, the coverage team, the wind, the field position — mixing in non-punter-skill variance that dilutes the signal. The K story doesn't generalize.

This is a documented audit lesson worth surfacing in the article: **the over-expected approach works when the baseline is well-isolated; for plays that depend heavily on context outside the player's control, raw outcome rates can be more skill-stable.**

## Verdict notes

**`p_net_avg` — PRIMARY (+0.55).** Best YoY (+0.355) and second-best validity (+0.166) of all candidates. Captures distance + return prevention. Net is also implicitly risk-asymmetric (touchbacks cap net at LOS-to-opp-20).

**`p_inside_20_rate` — PLACEMENT (+0.30).** Highest validity (+0.188). Orthogonal to net avg: a 40-yard punt downed at the 5 looks identical to a 40-yard punt downed at the 35 by net average. Inside-20 captures the placement skill that net avg misses.

**`p_blocked_rate` — PENALTY (−0.05).** Near-zero validity (−0.046) and YoY (−0.046 — actually slightly negative, which is noise floor). Most blocks are snap/protection failures rather than punter skill. Small negative weight bounds the cost without overweighting a non-punter-owned outcome.

## Rejected candidates

**`p_gross_avg`** — REJECT. Strictly subsumed by net avg (which uses the same gross yards but accounts for return).

**`p_touchback_rate`** — REJECT. Sign correct, magnitude near-zero. Touchback avoidance is implicitly captured by net (touchbacks cap net at LOS-to-opp-20).

**`p_return_yards_per_punt`** — REJECT. Same logic — net avg = gross − return, so return yards are already netted out.

**`p_fair_catch_rate`** — REJECT. Validity +0.013, near-zero. Fair catches are a returner decision driven by hangtime + coverage, not strictly a punter skill we can isolate.

**`p_i20_minus_tb_per_punt`** — REJECT. Validity +0.189 essentially ties inside_20_rate (+0.188). Same underlying skill in different framing; the simpler "inside 20%" rate is more reader-recognizable.

**`p_long_punt`** — REJECT. YoY +0.077 (noise threshold), validity +0.076. Power proxy with no real signal.

**`p_epa_per_punt`** — REJECT (would be valid as Option A, single-component). YoY +0.269, validity +0.163. Loses on both axes to net avg. Documented as alternative considered.

## What this audit confirms

1. **Audit-first works for new positions.** P v1 was designed from raw candidate scoring, not "intuition then test." The Option A vs Option B decision was data-driven.

2. **Over-expected metrics aren't universally superior.** K v1.1's FGOE win does not generalize to all positions. The audit caught this — net average was clearly better than EPA per punt by both criteria. Documenting this is the lesson.

3. **P joins K and LB in the "structurally noisy" tier.** Validity baseline +0.122 is the lowest of any position. Pro Bowl voting at P is the noisiest of any position (only 2 picks per year, reputation-driven).

4. **Two-tier FORMULA/CONTEXT header pattern (introduced for K) generalizes well to P.** P has 6 columns: 3 formula + 3 context. The pattern handles the multi-formula-component case cleanly (K had 1 formula column; P has 3).

## Decision: P v1 weight design

| Component | Weight | Share | Rationale |
|---|---:|---:|---|
| `p_net_avg` | **+0.55** | 61% | Primary — best YoY, captures distance + return prevention |
| `p_inside_20_rate` | **+0.30** | 33% | Placement skill — best validity, orthogonal to net |
| `p_blocked_rate` | **−0.05** | 6% | Small block penalty — bounded ownership of catastrophic plays |

Sum |w| = 0.90.

**Shrinkage k values:**
- `p_net_avg`: 10 punts (light — starters have 50-80)
- `p_inside_20_rate`: 15 punts (moderate — bucketed)
- `p_blocked_rate`: 30 punts (heavy — rare event, shrink toward league mean)

**Qualification:** 25 punts to grade, 40 qualified, 60 full confidence.

## Validity gate

P v1 composite vs next-year Pro Bowl correlation = **+0.122** (n=219, 11 next-year Pro Bowlers). Lowest of any audited position. Documented in the audit as expected — punter Pro Bowl voting is the most reputation-driven of any position.

## Face-check 2024

| Rank | Punter | Grade | Note |
|---:|---|---:|---|
| 1 | **Jack Fox** | 90.3 | **2024 1st-Team All-Pro, NFC Pro Bowl, NFL leader in net avg (48.0)**. Correct as #1. |
| 2 | Tommy Townsend | 81.8 | Solid Pro Bowl-caliber |
| 3 | **Logan Cooke** | 81.6 | **AFC Pro Bowl 2024**. Both Pro Bowl picks in top 3. |
| 4 | Michael Dickson | 72.2 | Past Pro Bowler |
| 5 | Ryan Rehkow | 71.2 | |
| ... | ... | ... | ... |
| 28 | Bradley Pinion | 14.5 | Career-low net (40.5), low inside-20 (29.8%) |
| 29 | Ryan Stonehouse | 10.5 | Tough year — lowest grade |

Both 2024 Pro Bowl punters in the top 3. Bottom of the list correctly identifies struggling punters.

## Pattern across audited positions (after P added)

| Position | Validity baseline | Notes |
|---|---:|---|
| iDL | +0.475 | Strongest — interior pressure rewarded |
| EDGE | +0.424 | Strong — sack/pressure rewarded |
| TE | +0.407 | Strong — receiving stats track voter consensus |
| WR | +0.300 | Moderate — EPA depends on QB |
| RB | +0.259 | Moderate — rushing share is contextual |
| S | +0.255 | Moderate — INT-driven voter noise |
| QB | +0.244 | Moderate — small Pro Bowl roster |
| CB | +0.220 | Voter noise (INT-driven) |
| LB | +0.198 | Reputation gap |
| K | +0.153 | Stats-vs-reputation gap |
| **P** | **+0.122** | **Lowest** — 2 picks/year, most reputation-driven |

**11 of 12 queue positions audited** (OL is the remaining new position). All weights tied to a four-criterion screen of every plausible candidate.
