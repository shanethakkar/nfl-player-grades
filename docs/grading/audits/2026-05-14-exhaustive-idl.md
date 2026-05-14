# iDL Exhaustive Candidate Audit — 2026-05-14

Eighth production audit. **Fourth defensive position** (after CB, S, EDGE). Ten candidates scored: 4 currently-shipped + 5 PFR-derived + 1 nflvs aggregate.

**Cohort:** qualified iDL-seasons 2018-2024 (n=563 for snap-based candidates, n=311 for pressure-conversion candidates with min 10 pressures).

Tool: `nflgrades audit-candidates --position iDL`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped:** | | | | | | | |
| `idl_pressure_rate` | 563 | **+0.689** | 0.01 | +0.766 | idl_sack_rate | **+0.460** | HIGHEST validity in formula |
| `idl_sack_rate` | 563 | +0.450 | 0.00 | +0.762 | idl_pressure_rate | **+0.394** | Strong validity, under-weighted |
| `idl_tfl_rate` | 563 | +0.371 | 0.00 | +0.711 | idl_sack_rate | +0.260 | Real signal but lower validity than design assumed |
| `idl_missed_tackle_rate` | 563 | +0.080 | 0.08 | −0.289 | idl_pressure_rate | −0.125 | Weak YoY (noise threshold), sign correct |
| **PFR-derived:** | | | | | | | |
| `idl_qb_hits_per_snap` | 563 | +0.507 | 0.01 | +0.779 | idl_pressure_rate | +0.316 | SUBSUMED (sub-component of pressure_rate) |
| `idl_hurries_per_snap` | 563 | +0.428 | 0.00 | +0.709 | idl_pressure_rate | +0.365 | SUBSUMED (sub-component of pressure_rate) |
| `idl_tackles_per_snap` | 563 | **+0.516** | 0.02 | **+0.532** | idl_pressure_rate | **+0.281** | **STRONG ADD — independent signal, real validity** ← v1.2 SHIPPED |
| `idl_sack_per_pressure` | 311 | **+0.008** | 0.11 | +0.722 | idl_sack_rate | +0.069 | NOISE — finishing rate doesn't persist at iDL sample sizes |
| `idl_hit_per_pressure` | 311 | +0.182 | 0.14 | −0.302 | idl_sack_rate | −0.052 | Near-zero validity |
| **nflvs aggregate:** | | | | | | | |
| `idl_forced_fumble_per_snap` | 563 | +0.096 | 0.00 | +0.269 | idl_pressure_rate | +0.218 | Rare-event noise (YoY below threshold) |

## Key findings

### Finding 1 — Weights were MIS-ORDERED vs validity

| | Weight order (v1.1) | Validity order |
|---|---|---|
| **Primary** | tfl (0.35) | **pressure (+0.460)** |
| **Secondary** | pressure (0.30) | **sack (+0.394)** |
| **Tertiary** | sack (0.15) | **tfl (+0.260)** |

The v1 design assumed "iDL = primarily run-stop TFL" (Aaron Donald, Chris Jones design intent). Pro Bowl voters reward interior PRESSURE more — and the YoY data confirms pressure is also vastly more reliable (+0.689 vs +0.371 for TFL). Both criteria (predictive validity and reliability) point the same direction: pressure should be primary, not TFL.

This is the same lesson as TE v1.2 (separation has negative validity for TE — design intent didn't match voter consensus), generalizing: when validity disagrees with design, the design often reflects an older positional archetype that the modern Pro Bowl voting has moved past.

### Finding 2 — Tackles-per-snap is a real iDL signal too

Same finding as EDGE v1.2: combined tackle volume per snap captures activity / chase-tackles that pressure/sack/TFL miss. iDL audit confirms this is cross-position true.

- YoY +0.516 (strong reliability)
- Validity +0.281 (moderate, positive direction)
- Max correlation with existing components only +0.532 — independent signal
- Elite iDLs show up in the box score as tackle volume too, not only on behind-LOS plays

## Verdict notes

**Rebalance: pressure 0.30 → 0.35, tfl 0.35 → 0.25, sack 0.15 → 0.20.** ← v1.2 SHIPPED
- Three-way swap brings the weights into alignment with the validity ordering.
- TFL stays meaningful (0.25 = 28% of total) — iDL run-stop matters more than EDGE run-stop, just not the most.

**ADD `idl_tackles_per_snap` at +0.05.** ← v1.2 SHIPPED
- Independent signal with moderate validity. Path B addition (no new ingest — comb_tackles was already pulled by the iDL grader as missed_tackle denominator).

**`idl_missed_tackle_rate` — KEEP at −0.05.**
- Validity −0.125 (sign correct: more misses → less Pro Bowl), but YoY +0.080 is in the noise zone. Already lowered in v1.1 from −0.15 → −0.05 per the cross-position YoY audit. No further change.

## Rejected new candidates

**`idl_qb_hits_per_snap`** (validity +0.316) — REJECT. +0.779 correlation with pressure_rate. QB hits are mechanically a sub-component of pressures.

**`idl_hurries_per_snap`** (validity +0.365) — REJECT. +0.709 correlation with pressure_rate. Sub-component.

**`idl_sack_per_pressure`** (validity +0.069) — REJECT. **YoY r = +0.008 — pure noise.** At iDL sample sizes (typical 5-10 pressures per season for many qualified DTs), the "finishing rate" does not persist year to year. This differs from EDGE where sack_per_pressure had +0.122 YoY (still rejected for subsumption, but at least reliable). At iDL, even the noise floor is failed.

**`idl_hit_per_pressure`** (validity −0.052) — REJECT. Near-zero validity. Same consolation-prize interpretation as EDGE: turning pressures into hits rather than sacks doesn't correlate with elite reputation.

**`idl_forced_fumble_per_snap`** (validity +0.218) — REJECT. YoY r = +0.096 (below noise threshold). The validity signal is mostly sack co-occurrence (strip-sacks). Typical iDL has 1-2 forced fumbles per season; sample too small to carry weight.

## What this audit confirms

1. **The design "iDL = run-stop primarily" is outdated.** Modern Pro Bowl voting rewards interior pressure (Aaron Donald → Chris Jones → Quinnen Williams → Dexter Lawrence lineage). The reliability data backs this: pressure_rate has YoY +0.689 vs tfl_rate's +0.371. Pressure is the more stable AND more validated signal. The v1.2 rebalance corrects this.

2. **The sub-component trap appears at every DL position.** qb_hits and hurries are inside pressures by construction. We've now seen this rejected at both EDGE and iDL. The pairwise-correlation criterion (independence) catches this every time.

3. **Tackles-per-snap generalizes across DL positions.** First found at EDGE v1.2, confirmed at iDL v1.2. The skill of "showing up on every play" is real and voter-rewarded for both DL types, distinct from pure pressure metrics.

4. **`sack_per_pressure` is noise at iDL, signal at EDGE.** Interior players have fewer pressures per season (lower base rate), so the conversion ratio is dominated by variance. EDGE's higher pressure counts make the ratio meaningful (though still subsumed by sack_rate).

## Decision: iDL v1.2 weight change

| Component | v1.1 | v1.2 | Share v1.1 | Share v1.2 |
|---|---:|---:|---:|---:|
| **`idl_pressure_rate`** | +0.30 | **+0.35** | 35% | **39%** |
| **`idl_tfl_rate`** | +0.35 | **+0.25** | 41% | **28%** |
| **`idl_sack_rate`** | +0.15 | **+0.20** | 18% | **22%** |
| **`idl_tackles_per_snap`** | — | **+0.05** | — | **6%** |
| `idl_missed_tackle_rate` | −0.05 | −0.05 | 6% | 6% |

Sum |w|: 0.85 → 0.90.

**Validity gate:** iDL composite vs next-year Pro Bowl correlation **+0.457 → +0.475 (+0.018)**. **Biggest validity gain from any defensive audit so far.** The rebalance was the right call — voters reward what the data says they reward.

**Face-check 2024:** Top 8 are all 2024 Pro Bowl / All-Pro caliber:
1. Leonard Williams (career year, 11 sacks)
2. Dexter Lawrence (1st Team All-Pro)
3. Chris Jones (Pro Bowl)
4. Braden Fiske (DROY runner-up, rookie)
5. DeForest Buckner (Pro Bowl)
6. Cameron Heyward (Pro Bowl, late-career resurgence)
7. Vita Vea (Pro Bowl)
8. Quinnen Williams (Pro Bowl)

Coherent with consensus.

## Pattern across audited positions

| Position | Validity (v1) | Validity (post-audit) | Change | Audit type |
|---|---:|---:|---:|---|
| **iDL** | **+0.457** | **+0.475** | **+0.018** | **Path A+B (rebalance + new component)** |
| TE | +0.384 | +0.407 | +0.023 | Path A |
| WR | +0.280 | +0.300 | +0.020 | Path A |
| RB | +0.243 → +0.247 (v1.3) | +0.259 (v1.4) | +0.016 | Path B |
| QB | +0.237 | +0.244 | +0.007 | Path A |
| EDGE | +0.420 | +0.424 | +0.004 | Path B |
| S | +0.253 | +0.255 | +0.002 | Path A |
| CB | +0.219 | +0.220 | +0.001 | Path A |

iDL was the highest-validity baseline. The post-audit gain is **largest among defensive positions** because the rebalance corrected a structural design assumption (run-stop primacy) rather than just adding a small new component. Path A rebalances driven by validity findings can produce meaningful lifts when the existing formula's ordering was wrong.
