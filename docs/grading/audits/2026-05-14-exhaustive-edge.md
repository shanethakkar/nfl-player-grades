# EDGE Exhaustive Candidate Audit — 2026-05-14

Seventh production audit. **Third defensive position** (after CB and S). Ten candidates scored: 4 currently-shipped + 5 PFR-derived + 1 nflvs aggregate.

**Cohort:** qualified EDGE-seasons 2018-2024 (n=508 for snap-based candidates, n=342 for pressure-conversion candidates with min 15 pressures).

Tool: `nflgrades audit-candidates --position EDGE`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped:** | | | | | | | |
| `edge_pressure_rate` | 508 | **+0.633** | 0.01 | +0.723 | edge_sack_rate | **+0.291** | Strong (primary signal) |
| `edge_sack_rate` | 508 | +0.423 | 0.00 | +0.769 | edge_tfl_rate | **+0.330** | Strongest validity in formula |
| `edge_tfl_rate` | 508 | +0.351 | 0.01 | +0.758 | edge_sack_rate | +0.285 | Real signal; expected DL co-occurrence |
| `edge_missed_tackle_rate` | 508 | +0.212 | 0.07 | −0.189 | edge_sack_rate | −0.056 | Sign correct, weak validity (same DB-position pattern) |
| **PFR-derived:** | | | | | | | |
| `edge_qb_hits_per_snap` | 508 | +0.516 | 0.01 | +0.735 | edge_pressure_rate | +0.179 | SUBSUMED by pressure_rate (it IS a sub-component) |
| `edge_hurries_per_snap` | 508 | +0.302 | 0.01 | +0.706 | edge_pressure_rate | +0.163 | SUBSUMED by pressure_rate |
| `edge_tackles_per_snap` | 508 | **+0.520** | 0.02 | **+0.468** | edge_tfl_rate | **+0.216** | **STRONG ADD — independent signal, real validity** ← v1.1 SHIPPED |
| `edge_sack_per_pressure` | 342 | +0.122 | 0.09 | +0.689 | edge_sack_rate | +0.128 | Subsumed; "finishing" already in sack_rate |
| `edge_hit_per_pressure` | 342 | +0.350 | 0.12 | −0.282 | edge_sack_rate | **−0.038** | NEAR-ZERO validity; voters don't reward this slice |
| **nflvs aggregate:** | | | | | | | |
| `edge_forced_fumble_per_snap` | 508 | +0.219 | 0.00 | +0.444 | edge_sack_rate | +0.141 | Rare-event noise (typical EDGE: 1-2 FF/season) |

## Verdict notes

**`edge_tackles_per_snap` — ADD at +0.05.** ← v1.1 SHIPPED
- YoY +0.520 (strong reliability), validity +0.216 (moderate-good and CORRECT sign).
- Max correlation with existing components only **+0.468** (with tfl_rate) — meaningfully INDEPENDENT signal. The other PFR candidates (qb_hits, hurries, sack_per_pressure) all hit +0.69-0.74 correlation, marking them as redundant sub-components.
- Captures activity level / chase-tackles / ahead-of-LOS plays — skills the current 89%-behind-LOS formula misses.
- Voter mechanism: elite EDGEs aren't just "pressure guys" — they show up in the box score as tackle volume too.

**`edge_pressure_rate` — KEEP at +0.35.**
- Strongest YoY in the audit (+0.633), validity +0.291. Primary signal. The +0.723 correlation with sack_rate is intentional (sacks are a subset of pressures, and we want to extra-weight sacks).

**`edge_sack_rate` — KEEP at +0.30.**
- Highest validity in the formula (+0.330). Premium outcome. Intentional overlap with pressure_rate (sacks are pressures + finish).

**`edge_tfl_rate` — KEEP at +0.15.**
- YoY +0.351, validity +0.285. Real signal. The high correlations with sack_rate (+0.758) and pressure_rate are the "good DL does all DL things" pattern, not redundancy.

**`edge_missed_tackle_rate` — KEEP at −0.10.**
- Validity −0.056 (weak), but sign is correct (more misses → less Pro Bowl). YoY +0.212 confirms it's a real skill, not noise. Same DB-position pattern as CB/S/iDL (voters don't reward fundamentals at defensive positions; weight is kept on skill-tree grounds).

## Rejected new candidates

**`edge_qb_hits_per_snap`** (validity +0.179) — REJECT. Correlation +0.735 with pressure_rate. QB hits are mathematically a sub-component of pressures (pressures = sacks + QB hits + hurries). Adding it would double-count.

**`edge_hurries_per_snap`** (validity +0.163) — REJECT. Same logic, +0.706 correlation with pressure_rate. Sub-component.

**`edge_sack_per_pressure`** (validity +0.128) — REJECT. Correlation +0.689 with sack_rate. The "finishing rate" insight is real but already captured by the standalone sack_rate weight.

**`edge_hit_per_pressure`** (validity −0.038) — REJECT. Validity essentially zero AND slightly negative. The interpretation: players who turn pressures into QB hits (rather than sacks) may be just-missing the sack. It's a consolation-prize metric voters don't reward. Counter-intuitively, the "elite" finishers turn pressures into sacks, not hits.

**`edge_forced_fumble_per_snap`** (validity +0.141) — REJECT. Rare-event noise: typical qualified EDGE has 1-2 forced fumbles per season. The validity signal is mostly driven by sack co-occurrence (strip-sacks). Same rejection as Safety/CB rare-event candidates.

## What this audit confirms

1. **EDGE formula was largely correct.** The four existing components all have real validity (+0.285 to +0.330 for the positive ones). The audit surfaced one viable add, not a wholesale rebalance.

2. **The "sub-component trap" at defensive positions.** Three of the rejected candidates (qb_hits, hurries, sack_per_pressure) are mechanically inside existing components. They look attractive in isolation but their independence score (correlation 0.69-0.74) disqualifies them. Same pattern as CB/S where individual PFR coverage stats were subsumed by passer_rating_allowed.

3. **Tackle volume is a real EDGE skill, not just an LB stat.** This is the new insight. Pro Bowl voters reward EDGE players who show up in the box score with combined-tackle volume — chase tackles, RB at the catch point, screen-pass tackles. The current formula's 89%-behind-LOS focus was missing this layer. v1.1 adds it at +0.05 (small enough not to dominate, large enough to surface).

4. **Rare-event aggregates underperform at qualified-EDGE sample sizes.** Forced fumbles per snap, with typical 1-2 events per season, can't carry weight. The same applies at S/CB/iDL.

## Decision: EDGE v1.1 weight change

| Component | v1 | v1.1 | Share v1 | Share v1.1 |
|---|---:|---:|---:|---:|
| `edge_pressure_rate` | +0.35 | +0.35 | 39% | 37% |
| `edge_sack_rate` | +0.30 | +0.30 | 33% | 32% |
| `edge_tfl_rate` | +0.15 | +0.15 | 17% | 16% |
| **`edge_tackles_per_snap`** | — | **+0.05** | — | **5%** |
| `edge_missed_tackle_rate` | −0.10 | −0.10 | 11% | 11% |

Sum |w|: 0.90 → 0.95.

**Validity gate:** EDGE composite vs next-year Pro Bowl correlation **+0.420 → +0.424**. Small but real improvement, expected for a 5%-weight add of a moderate-validity signal. Holds; no rollback.

**Face-check 2024:** Top 5 are all Pro Bowl / All-Pro caliber: Trey Hendrickson (#1, 17.5 sacks, 1st Team All-Pro), Myles Garrett, Will Anderson Jr., Micah Parsons, Nik Bonitto (2nd Team All-Pro). T.J. Watt grades #15 (down sack year — 11.5 vs his career norm), correctly reflecting his 2024 production rather than his reputation. Coherent.

## How EDGE compares across the audited positions

| Position | Validity (v1) | Validity (post-audit) | Change | Audit type |
|---|---:|---:|---:|---|
| TE | +0.384 | +0.407 | +0.023 | Path A (rebalance) |
| RB | +0.243 → +0.247 (v1.3) | +0.259 (v1.4) | +0.016 | Path B (new component) |
| QB | +0.237 | +0.244 | +0.007 | Path A |
| **EDGE** | **+0.420** | **+0.424** | **+0.004** | **Path B (new component)** |
| WR | +0.280 | +0.300 | +0.020 | Path A |
| S | +0.253 | +0.255 | +0.002 | Path A (target_rate cleanup) |
| CB | +0.219 | +0.220 | +0.001 | Path A (target_rate cleanup) |

EDGE was already the highest-validity audit target (after iDL +0.457). Marginal gains diminish as baseline validity rises — adding a +0.05-weight component to an already-strong formula naturally produces a small absolute lift. The audit's main value is **methodological**: documenting that we exhaustively considered qb_hits, hurries, sack_per_pressure, hit_per_pressure, and forced_fumbles, and showing why they didn't make the formula.
