# ADR-0020 — EDGE v1 Grading Formula

**Status:** Accepted (v1.1 OLB-gap closure — 2026-05-14)
**Date:** 2026-05-13

---

## Context

EDGE rushers are the primary pass-rush specialists on the defensive line. Grading them requires quantifying pass-rush production (pressures, sacks) and run-stop ability (TFLs), normalized by opportunity (defensive snaps).

---

## Data Sources

| Source | Columns | Coverage |
|---|---|---|
| `pfr_advstats_def` → `pfr_def_pass_rush` | pressures, sacks, QB hits, hurries, comb_tackles, missed_tackles | 2018+ |
| `nflvs_player_stats` → `pfr_def_pass_rush` | tfl (def_tackles_for_loss, sacks excluded) | 2018+ |
| `player_seasons` | snaps_defense | 2016+ |

**TFL double-count confirmation:** `nflvs_player_stats.def_tackles_for_loss` is confirmed to NOT include sacks. Verified empirically: Dexter Lawrence (2024) had 9.0 sacks but only 8 TFL, proving the two fields are reported separately. No overlap between `edge_sack_rate` and `edge_tfl_rate`.

---

## Components

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `edge_pressure_rate` | pressures / snaps_defense | +0.35 | higher = better |
| `edge_sack_rate` | sacks / snaps_defense | +0.30 | higher = better |
| `edge_tfl_rate` | tfl / snaps_defense | +0.15 | higher = better |
| `edge_missed_tackle_rate` | missed / (comb + missed) | −0.10 | lower = better |

Sum |weights| = 0.90. Normalized dynamically by `composite.combine`.

**Relative shares:** pressure 39%, sack 33%, TFL 17%, missed tackles −11%.

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
| pressure_rate | 200 snaps | Moderate stability (r ≈ 0.5 YoY) |
| sack_rate | 350 snaps | Rarer events; heavier pull toward mean |
| tfl_rate | 300 snaps | Low per-snap frequency; needs shrinkage |
| missed_tackle_rate | 100 tackle_attempts | Real skill signal; moderate shrinkage |

---

## Design Rationale

**Pressure rate dominant (39%):** Total pressures (sacks + QB hits + hurries) is the most complete per-snap pass-rush signal available without pass-rush snap denominators. Weighting it most heavily captures the full spectrum of a rusher's production.

**Sack rate separate (33%):** Intentional partial overlap with pressure rate. Sacks are the premium outcome — the weight difference rewards players who convert pressure into sacks at a higher rate. Trey Hendrickson (54 pressures, 17.5 sacks, 2024) grades higher than a player with 54 pressures and 7 sacks, as intended.

**TFL rate included (17%):** EDGE rushers set the edge on run plays. Elite rushers like Myles Garrett (22 TFL, 2023) generate meaningful run-stop production beyond just pass rush. Excluding TFL would undervalue complete DEs.

**Missed tackle rate penalty (−11%):** Technique matters for edge rushers who must disengage and pursue in space. Weight kept modest (lower than Safety's −11%) because edge rushers make fewer total tackles and the metric is noisier per position.

---

## Known Limitations

**OLB gap (3-4 schemes):** ~~Original v1 limitation~~ — **closed in v1.1 (2026-05-14)**. The EDGE grader now reads from both `pfr_def_pass_rush` (EDGE-tagged) and `pfr_def_lb` (LB-tagged pass-rush OLBs with ≥25 pressures and target rate <3.5%). See Revision History.

**No pass-rush snap denominator:** Total defensive snaps is used as denominator. This conflates run-defense snaps (where pressure rate is irrelevant) with pass-rush snaps. Elite rushers who are subbed out on early downs may be slightly penalized. Pass-rush snap data is not available in public data sources.

**Data begins 2018:** PFR per-player advanced stats start in 2018. Seasons 2016–2017 cannot be graded.

---

## Alternatives Considered

**Pressure rate only (no sack split):** Simpler but loses information about conversion efficiency. Rejected because sack rate is meaningfully independent — two players with identical pressure rates can have very different sack counts.

**Equalizing pressure and sack weights (0.35 / 0.35):** Reviewed per external feedback. Rejected because pressure rate captures more signal than sack rate alone (higher volume, more stable YoY), so it warrants a higher weight.

**Excluding TFL from EDGE:** Initial proposal excluded TFL. Added after review — elite edge rushers do generate real TFL volume on run downs, and excluding it understates their defensive value.

---

## Revision History

### v1.1 (2026-05-14) — OLB-gap closure

Closed the original v1 limitation where nflverse-classified `LB` pass rushers (T.J. Watt, Micah Parsons, Brian Burns, Nik Bonitto, Jared Verse, Josh Sweat, etc.) received **no grades** at any position. They failed the LB grader's target-rate filter (≥3.5%) for being pass-rushers, and the EDGE grader didn't see them because their `position_played` tag was `LB`. ~15-30 elite edge rushers per season were missing from the system.

**Fix:** The EDGE feature SQL now UNIONs two branches:
1. EDGE-tagged players from `pfr_def_pass_rush` (original v1 source).
2. LB-tagged pass-rush OLBs from `pfr_def_lb`, filtered to:
   - `position_played = 'LB'`
   - `pressures ≥ 25` (real pass-rush production — separates them from blitz-heavy MLBs)
   - `target_rate < 0.035` (matches the LB grader's exclusion threshold — no player is graded in both)

Both branches feed the same EDGE composite formula. `pfr_def_lb` and `pfr_def_pass_rush` have the same column shape for the components EDGE uses (pressures, sacks, comb_tackles, missed_tackles, tfl), so no other code changes were needed.

**Verification:** No player appears in both LB and EDGE for any season post-fix (the filter thresholds are designed to be mutually exclusive: LB requires target rate ≥3.5%, EDGE-via-OLB-branch requires target rate <3.5%).

**Face-check after fix:**
- Micah Parsons now graded all 5 seasons (2021 LB 83.9, 2022-2025 EDGE 70.5/81.9/86.8/85.6) instead of just 2.
- 2025 EDGE top 5: Garrett, Parsons, Sweat, Muhammad, Bonitto, Burns.
- 2024 EDGE top 5: Hendrickson, Garrett, Anderson, Parsons, Bonitto.
- 2023 EDGE top 5: Bryce Huff (DPOY runner-up), T.J. Watt, Hendrickson, Hines-Allen, Greenard.

All consensus elite pass rushers now appear in the EDGE leaderboard.

**Why this works data-side without new ingest:** `pfr_def_lb` was already populated for all LB-tagged players with PFR pass-rush data starting in 2018. The fix is purely a query-side change to the EDGE grader. No migration, no re-ingest, ~30 lines of SQL added.
