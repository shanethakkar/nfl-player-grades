# ADR-0021 — iDL v1 Grading Formula

**Status:** Accepted  
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

## Components

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `idl_tfl_rate` | tfl / snaps_defense | +0.35 | higher = better |
| `idl_pressure_rate` | pressures / snaps_defense | +0.30 | higher = better |
| `idl_sack_rate` | sacks / snaps_defense | +0.15 | higher = better |
| `idl_missed_tackle_rate` | missed / (comb + missed) | −0.15 | lower = better |

Sum |weights| = 0.95. Normalized dynamically by `composite.combine`.

**Relative shares:** TFL 37%, pressure 32%, sack 16%, missed tackles −16%.

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
| pressure_rate | 200 snaps | Moderate stability (r ≈ 0.5 YoY) |
| sack_rate | 350 snaps | Rarer events; heavier pull toward mean |
| missed_tackle_rate | 100 tackle_attempts | Real skill signal; moderate shrinkage |

---

## Design Rationale

**TFL rate dominant (37%):** Interior penetration that results in a TFL is the defining play for elite iDL players. Aaron Donald, Chris Jones, and Dexter Lawrence generate TFLs at rates well above average. Unlike EDGE where pass rush is the primary skill, for iDL the ability to defeat blocks and disrupt the run is the primary differentiator.

**Pressure rate second (32%):** Interior pressure matters — collapsing the pocket forces quicker throws and disrupts timing. Weighted lower than TFL because interior pressure rates are structurally lower than EDGE pressure rates (the center and two guards all work against the same DT that only one tackle faces).

**Sack rate third (16%):** Interior sacks are premium plays. Weighted substantially lower than EDGE (16% vs 33%) because structural sack rates are lower for iDL — Chris Jones had 38 pressures but only 5.5 sacks in a typical season. The position does generate interior sacks, but they're rarer by design.

**Missed tackle rate penalty (−16%):** Weighted slightly higher than EDGE (−16% vs −11%) because iDL make more tackles at the line of scrimmage where misses are especially costly. Symmetrically weighted with the sack component.

**iDL vs EDGE weighting difference:** The key flip is TFL over pressure as the dominant component. EDGE rushers live primarily in the pass-rush role; iDL players are deployed equally in run and pass situations and must excel at both.

---

## Known Limitations

**No pass-rush snap denominator:** Total defensive snaps is used. iDL players may be subbed out in passing situations less often than EDGE rushers, so this conflation is less severe for iDL than for EDGE.

**Position classification:** Uses `player_seasons.position_played = 'iDL'` from our roster data. Nose tackles (NT) in 3-4 schemes are classified as iDL and included — they typically have lower pressure rates but may have high TFL rates on run downs.

**Data begins 2018:** PFR per-player advanced stats start in 2018. Seasons 2016–2017 cannot be graded.

---

## Alternatives Considered

**Equal weights (pressure ≈ TFL ≈ 0.30):** Reviewed. Rejected because TFL is the primary iDL differentiator and should be weighted more heavily — it's a harder play to make for an interior lineman and more directly measures the iDL skill set.

**Using EDGE weights for iDL:** Rejected. Applying the EDGE formula (pressure-dominant) to iDL undersells interior run-stopping and would rank players more similarly to EDGE rushers than their actual role warrants.
