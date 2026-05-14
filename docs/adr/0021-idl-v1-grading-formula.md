# ADR-0021 — iDL v1 Grading Formula

**Status:** Accepted (v1.2 rebalance + tackle-volume add — 2026-05-14)
**Date:** 2026-05-14

---

## Context

Interior defensive linemen (iDL) are the run-stuffers and interior pass rushers on the defensive line. Their primary value is stopping the run at the line of scrimmage (TFLs) and collapsing the pocket from the inside. Grading them requires weighting run-stop production more heavily than for EDGE rushers, while still capturing pass-rush impact.

---

## Data Sources

| Source | Columns | Coverage |
|---|---|---|
| `pfr_advstats_def` → `pfr_def_pass_rush` | pressures, sacks, QB hits, hurries, comb_tackles, missed_tackles | 2018+ |
| `nflvs_player_stats` → `pfr_def_pass_rush` | tfl (def_tackles_for_loss, sacks excluded) | 2018+ |
| `player_seasons` | snaps_defense | 2016+ |

Same `pfr_def_pass_rush` table as EDGE — the ingest covers all DL (both iDL and EDGE position codes) and the grader filters by `player_seasons.position_played = 'iDL'`.

**TFL double-count:** `nflvs_player_stats.def_tackles_for_loss` does NOT include sacks (same confirmation as EDGE — see ADR-0020). No overlap between `idl_sack_rate` and `idl_tfl_rate`.

---

## Components (v1.2, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `idl_pressure_rate` | pressures / snaps_defense | **+0.35** | higher = better |
| `idl_tfl_rate` | tfl / snaps_defense | **+0.25** | higher = better |
| `idl_sack_rate` | sacks / snaps_defense | **+0.20** | higher = better |
| `idl_tackles_per_snap` | comb_tackles / snaps_defense | **+0.05** | higher = better |
| `idl_missed_tackle_rate` | missed / (comb + missed) | −0.05 | lower = better |

Sum |weights| = 0.90. Normalized dynamically by `composite.combine`.

**Relative shares:** pressure 39%, TFL 28%, sack 22%, tackles 6%, missed tackles −6%.

---

## Qualification (snap-based)

| Threshold | Snaps |
|---|---|
| MIN to grade | 200 |
| QUALIFIED (main leaderboard) | 400 |
| Full confidence | 700 |

---

## Shrinkage k Values

| Component | k | Rationale |
|---|---|---|
| tfl_rate | 300 snaps | Low per-snap frequency (~1–2%); needs heavy pull toward mean |
| pressure_rate | 200 snaps | Moderate stability (r ≈ 0.69 YoY — strong) |
| sack_rate | 350 snaps | Rarer events; heavier pull toward mean |
| tackles_per_snap | 200 snaps | Stable signal (YoY +0.516); matches pressure_rate's stability tier |
| missed_tackle_rate | 100 tackle_attempts | Real skill signal; moderate shrinkage |

---

## Design Rationale (v1.2)

**Pressure rate primary (39%):** The exhaustive audit (2026-05-14) revealed pressure_rate is both the most reliable iDL signal (YoY r = +0.689 vs TFL's +0.371) AND the most predictive of Pro Bowl voting (validity +0.460 vs TFL's +0.260). The original v1 design assumed "iDL = run-stop primarily," but modern Pro Bowl voting rewards the interior pass-rush archetype (Aaron Donald → Chris Jones → Quinnen Williams → Dexter Lawrence). v1.2 elevates pressure to the primary signal to match both reliability and voter consensus.

**TFL rate secondary (28%):** Still a meaningful iDL signal — elite interior players DO generate TFLs at well-above-average rates, and run-stop is a genuine part of the job. Just not the most reliable or most voter-rewarded skill. Kept at substantial weight (28% vs EDGE's 16%) to preserve the design principle that iDL run-stop matters more than EDGE run-stop.

**Sack rate third (22%):** Validity audit returned +0.394 — the second-highest in the formula. v1.2 raised it from 15% to 22% to reflect this. Interior sacks remain rarer than EDGE sacks structurally, but the play, when it happens, is a premium signal of elite interior pass rush.

**Tackles per snap (+0.05, v1.2 add):** Captures activity / chase-tackles that pressure/sack/TFL miss. The exhaustive audit found this is an independent signal (max correlation +0.532 with pressure_rate) with real validity (+0.281) and strong reliability (YoY +0.516). Voters reward iDLs who show up across the box score. Same finding as EDGE v1.2.

**Missed tackle rate penalty (−5%):** Lowered from −0.15 → −0.05 in v1.1 (cross-position YoY audit) because YoY r = +0.080 — barely above noise. v1.2 audit confirms validity is weak (−0.125, sign correct). Kept at −0.05 on skill-tree grounds.

**iDL vs EDGE weighting difference:** In v1.2 the two DL formulas have converged in structure (pressure-dominant) but diverge in TFL share: iDL at 28% vs EDGE at 16%. This is the right amount of differentiation — iDL run-stop matters more, just not enough to be the primary signal.

---

## Component Overlap (intentional)

The three positive components (tfl_rate, pressure_rate, sack_rate) measure overlapping aspects of "backfield disruption" and correlate strongly. Confirmed empirically by the 2026-05-14 pairwise correlation audit (qualified iDL-seasons pooled 2018-2025, z-score correlation):

| Pair | Pearson r |
|---|---:|
| tfl_rate ↔ sack_rate | +0.737 |
| pressure_rate ↔ sack_rate | +0.778 |
| tfl_rate ↔ pressure_rate | +0.574 |

The 0.80 of total positive weight (tfl 0.35 + pressure 0.30 + sack 0.15) carries roughly 0.50–0.60 worth of *independent* signal. Interior linemen who beat blocks tend to do all three — make TFLs on runs, generate pressures on passes, and convert some pressures into sacks. The formula weights them separately so each play-type contributes to the grade, but the underlying skill they tap is largely shared.

This is **intentional**: weighting only one (say, TFL) would undercount pass-rush interior penetration; weighting only pressure would miss run-stop production. Documenting this here so a future audit doesn't try to "fix" the correlation by dropping a component.

Same pattern as EDGE (see [ADR-0020 § Component Overlap](0020-edge-v1-grading-formula.md#component-overlap-intentional)). CB/S/LB formulas do not have this pattern — their components were designed to be more independent. See [../grading/audits/2026-05-14-correlation.md](../grading/audits/2026-05-14-correlation.md) for cross-position context.

---

## Known Limitations

**No pass-rush snap denominator:** Total defensive snaps is used. iDL players may be subbed out in passing situations less often than EDGE rushers, so this conflation is less severe for iDL than for EDGE.

**Position classification:** Uses `player_seasons.position_played = 'iDL'` from our roster data. Nose tackles (NT) in 3-4 schemes are classified as iDL and included — they typically have lower pressure rates but may have high TFL rates on run downs.

**Data begins 2018:** PFR per-player advanced stats start in 2018. Seasons 2016–2017 cannot be graded.

---

## Alternatives Considered

**Equal weights (pressure ≈ TFL ≈ 0.30):** Reviewed. Rejected because TFL is the primary iDL differentiator and should be weighted more heavily — it's a harder play to make for an interior lineman and more directly measures the iDL skill set.

**Using EDGE weights for iDL:** Rejected. Applying the EDGE formula (pressure-dominant) to iDL undersells interior run-stopping and would rank players more similarly to EDGE rushers than their actual role warrants.

---

## Revision History

### v1.2 (2026-05-14) — exhaustive audit rebalance + tackle-volume add

Two-part change driven by the exhaustive candidate audit ([../grading/audits/2026-05-14-exhaustive-idl.md](../grading/audits/2026-05-14-exhaustive-idl.md)). Ten candidates were scored against four criteria.

**(a) Rebalance of existing positive weights.** The audit revealed the v1.1 weights were MIS-ORDERED relative to both reliability and predictive validity:

| | Weight order (v1.1) | Validity r | YoY r |
|---|---|---:|---:|
| Should be primary | tfl_rate (0.35) | +0.260 | +0.371 |
| Should be secondary | pressure_rate (0.30) | **+0.460** | **+0.689** |
| Tertiary | sack_rate (0.15) | +0.394 | +0.450 |

The v1 design assumption "iDL = primarily run-stop TFL" reflected an older positional archetype. Modern Pro Bowl voting (Donald → Jones → Quinnen Williams → Dexter Lawrence) rewards interior pressure more, and the YoY data confirms pressure is also the more reliable signal. v1.2 reorders:

- `idl_pressure_rate`: 0.30 → **0.35** (now primary)
- `idl_tfl_rate`: 0.35 → **0.25** (de-emphasized but still meaningful)
- `idl_sack_rate`: 0.15 → **0.20** (validity-justified bump)

**(b) Add `idl_tackles_per_snap` at +0.05.** Independent signal (max correlation +0.532 with pressure_rate), real validity (+0.281), strong reliability (YoY +0.516). Same finding as EDGE v1.2 — tackle volume captures activity / chase-tackles that pressure/sack/TFL miss. Path B add (no new ingest — comb_tackles was already pulled by the iDL grader as the missed_tackle denominator); just added `tackles_per_snap = comb_tackles / snaps_defense` to extract_features.

**Rejected candidates (documented in audit doc):**
- `idl_qb_hits_per_snap` (+0.779 correlation with pressure_rate — sub-component)
- `idl_hurries_per_snap` (+0.709 correlation with pressure_rate — sub-component)
- `idl_sack_per_pressure` (YoY r = +0.008 — pure noise at iDL sample sizes; differs from EDGE where this had +0.122 YoY but was still rejected for subsumption)
- `idl_hit_per_pressure` (validity −0.052, near-zero)
- `idl_forced_fumble_per_snap` (YoY +0.096 below noise threshold; validity mostly co-occurrence with sack)

**Validity gate:** iDL composite vs next-year Pro Bowl correlation **+0.457 → +0.475 (+0.018)**. **Biggest validity gain from any defensive audit so far.** The rebalance was the right call — voters reward what the data says they reward.

**Face-check 2024:** Top 8 are all 2024 Pro Bowl / All-Pro caliber — Leonard Williams #1 (career year, 11 sacks), Dexter Lawrence (1st Team All-Pro), Chris Jones, Braden Fiske (DROY runner-up), DeForest Buckner, Cameron Heyward, Vita Vea, Quinnen Williams. Coherent.

**Weight totals:** v1.1 sum |abs| = 0.85 → v1.2 sum |abs| = 0.90.

### v1.1 (2026-05-14) — `idl_missed_tackle_rate` weight lowered (noise)

**Lowered `idl_missed_tackle_rate` from −0.15 → −0.05.** Sum |w| drops 0.95 → 0.85; combiner normalizes so the three signal-strong positive components (tfl_rate, pressure_rate, sack_rate) get more effective weight.

**Why:** Cross-position YoY audit (2026-05-14) found mean YoY r = 0.080 across 2018-2025 for iDL missed_tackle_rate — one of the lowest signals in the entire grader system, below even the WR/TE drop_rate components at ~0.13. At −0.15 weight this was disproportionate noise contribution. Light weight (−0.05) preserves the technique-penalty direction without overweighting noise.

**Why not removed entirely:** Schema-stable change is preferred (pure weight tweak via the new preview/regrade workflow, per `memory/reference_formula_iteration_workflow.md`). Mean r 0.080 isn't zero — there's *some* in-season signal, just weak YoY. Light weight bounds the noise contribution while keeping the component available if we want to revisit later.

**Face-check 2024:** Top 3 unchanged (Leonard Williams, Chris Jones, Dexter Lawrence). Biggest movers up are interior linemen who'd been penalized for high missed-tackle rates: Quinnen Williams #16 → #9 (+7.84), Solomon Thomas #37 → #28 (+9.23), Jalen Carter #23 → #13 (+7.76). Coherent — these are players whose technique reputation isn't "missed tackler" but our noisy metric was treating them as such.

**Audit data:** `memory/project_cross_position_yoy_audit.md`. Shipped via `nflgrades preview` → edit `weights.py` → `sync_weights_to_web.py` → `nflgrades regrade` per season (the new workflow). End-to-end ~30 seconds.
