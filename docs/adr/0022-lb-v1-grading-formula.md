# ADR-0022 — LB v1 Grading Formula

**Status:** Accepted (revised 2026-05-14 — see *Revision History*)
**Date:** 2026-05-14

---

## Context

Off-ball linebackers are a multi-skill position — run defense, coverage, and situational pass rush. Unlike EDGE/iDL (pass-rush primary) or CB/S (coverage primary), LBs are graded across all three phases.

The biggest risk is **misclassification**: nflverse roster data classifies 3-4 OLB pass rushers (T.J. Watt, Micah Parsons, Haason Reddick, Andrew Van Ginkel) as `LB` rather than `EDGE`. Without a filter, those players would dominate the LB leaderboard with high TFL/pressure rates from pass-rush work, not LB skill.

---

## Data Sources

| Source | Columns | Coverage |
|---|---|---|
| `pfr_advstats_def` → `pfr_def_lb` | tackles, missed tackles, pressures, sacks, targets, completions allowed, yards allowed, TDs allowed, INTs | 2018+ |
| `nflvs_player_stats` → `pfr_def_lb` | TFL, PBU (pass defended), fumbles forced | 2018+ |
| `player_seasons` | snaps_defense | 2016+ |

PBU data confirmed populated for off-ball LBs (Fred Warner 5-12 PBUs/yr, Roquan Smith 3-8 PBUs/yr; median qualified LB has 3 PBUs/year, only 7-14% have zero).

---

## Components

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `lb_tfl_rate` | tfl / snaps_defense | **+0.20** | higher = better |
| `lb_passer_rating_allowed` | NFL passer rating on targeted throws | **−0.27** | lower = better |
| `lb_missed_tackle_rate` | missed / (comb + missed) | **−0.15** | lower = better |
| `lb_pbu_rate` | pbu / targets | **+0.08** | higher = better |
| `lb_tackle_rate` | comb_tackles / snaps_defense | **+0.13** | higher = better |
| `lb_pressure_rate` | pressures / snaps_defense | **+0.07** | higher = better |

Sum |weights| = 0.90. Normalized dynamically by `composite.combine`.

**Relative shares:** run defense ~45% (TFL 22% + tackle 14% + missed tackle penalty 17%), coverage ~39% (passer rating 30% + PBU 9%), pass rush ~8%.

**Passer rating allowed** is computed season-long from `(completions_allowed, targets, yards_allowed, tds_allowed, ints)` using the standard NFL passer rating formula. PBU rate is PBU-only (not PBU+INT) because INTs are already captured inside passer rating allowed (a single INT lowers rating by ~25 points); double-counting would over-reward turnover-heavy LBs.

---

## Qualification

| Threshold | Value | Notes |
|---|---|---|
| MIN snaps to grade | 200 | |
| QUALIFIED snaps | **600** | Raised from 400 (other positions) |
| Full confidence snaps | **900** | Raised proportionally |
| MIN targets (absolute) | 15 | Off-ball role filter |
| MIN target rate | **3.5%** | Off-ball role filter (targets / snaps) |

**Why 600-snap qualified threshold (vs 400 for EDGE/iDL/S):** LB per-snap rate stats are heavily inflated by limited-snap rotational specialists (sub-package run stuffers, nickel coverage LBs) whose narrow usage produces per-snap rates that every-down LBs can't match. At a 400-snap threshold, the top-10 LB leaderboard was dominated by 400-500 snap role players over 1000-snap workhorses like Bobby Wagner and Demario Davis. Raising to 600 suppresses this artifact.

---

## Shrinkage k Values

| Component | k | Rationale |
|---|---|---|
| `lb_tfl_rate` | 300 snaps | Rare event (~1% of snaps for elite); heavy pull |
| `lb_passer_rating_allowed` | 50 targets | Passer rating swings 25+ points on one TD or INT; heavy shrinkage |
| `lb_missed_tackle_rate` | 100 tackle attempts | LBs make 80-180 tackles; moderate shrinkage |
| `lb_pbu_rate` | 40 targets | Rare event rate per target |
| `lb_tackle_rate` | 200 snaps | Volume signal, moderate stability |
| `lb_pressure_rate` | 200 snaps | Most LBs near zero; shrink toward LB mean |

---

## OLB Misclassification Filter

**Problem:** nflverse classifies 3-4 OLB pass rushers as `LB`. Without filtering, they dominate the LB leaderboard via pass-rush production.

**Filter:** A player must satisfy **all** of:
1. `position_played = 'LB'`
2. `snaps_defense >= 200` (MIN to grade)
3. `targets >= 15` (absolute floor)
4. `targets / snaps_defense >= 0.035` (target rate floor)

**Why a target-rate filter, not a raw-target threshold:** A raw threshold like "targets >= 20" lets pass-rush OLBs sneak through on incidental zone drops. Example: Andrew Van Ginkel 2024 had 22 targets (just above a 20 threshold) but only 922 snaps — a 2.4% target rate. Pure off-ball LBs run 5-9% target rate regardless of total snap count. The 3.5% threshold cleanly separates the two cohorts.

Players failing the filter are **not graded as LB** for that season. They may or may not be graded as EDGE depending on their EDGE-eligibility (`position_played = 'EDGE'` is required; LB-classified pass rushers like T.J. Watt are not graded by any position grader in v1 — same gap noted in ADR-0020).

---

## Design Rationale

**Passer rating allowed dominant (−0.27):** Industry-standard NFL coverage metric. Combines comp%, yards per attempt, TDs, and INTs into one number that captures the full extent of coverage damage. The single cleanest LB skill signal in our dataset: rewards forced incompletions (PBUs lower comp%), penalizes TDs allowed (yds/tgt didn't), and rewards turnovers (INTs hammer the rating by ~25 points each). Weighted heaviest of any component because of how well it tracks consensus elite coverage.

**TFL rate (+0.20):** Cleanest LB run-defense signal — actual play-making behind the LOS, harder to inflate via team-context than raw tackle volume. Slightly de-weighted from initial draft (0.22 → 0.20) to make room for passer rating allowed.

**PBU rate (+0.08) — PBU-only, not PBU+INT:** INTs are already captured inside passer rating allowed. Keeping PBU as a separate component still credits the active "broke up the catch" play (passer rating only captures it indirectly via comp%) without double-counting interceptions.

**Missed tackle rate penalty (−0.15):** LBs make the most tackles of any position; misses cost the most. Same penalty weight as Safety.

**Tackle rate (+0.13):** Raw tackle volume has team-context contamination (bad defenses see more snaps, more plays). Meaningful but not dominant.

**Pressure rate small (+0.07):** Most off-ball LBs rarely rush. Fred Warner / Roquan Smith have 5-12 pressures/yr on 1000 snaps (0.5-1.2% rate) vs. 4-6% for EDGE. The 7% weight rewards blitz-heavy MLBs (Patrick Queen, Kaden Elliss-type) without overstating the position-wide impact.

---

## Known Limitations

**LB grades are noisier YoY than QB/WR/CB grades.** Multiple sources of noise:
- Coverage target samples are small (30-90/yr).
- Scheme assignment shapes which LB is on the field for which plays.
- Yards-per-target is partially zone-dependent.
- TFL volume depends on DL play (penetration creates LB cleanup TFLs).

Expected YoY r band: 0.35-0.50. Wider/lower than offensive skill positions. Below 0.35 → formula issue or filter problem. Above 0.55 → suspicious (likely measuring usage rather than skill).

**Per-snap rate vs. holistic film grade:** PFF-style snap-level film grading captures technique on every rep including snaps where the LB isn't directly involved in a stat. We can't replicate that with publicly available stats. v1 measures per-snap statistical efficiency, which favors highly productive LBs and slightly disadvantages well-positioned LBs whose work is more about preventing plays than making them.

**Some recognizable LBs may grade lower than fan/expert consensus.** Fred Warner and Roquan Smith both had statistically below-average 2024 seasons relative to their peaks; our formula reflects the stats, not reputation. This is a feature, not a bug, but worth noting for users surprised by individual rankings.

**Pass-rush OLB classification gap (carried from ADR-0020):** T.J. Watt, Micah Parsons, Haason Reddick, etc. are not graded by any v1 position grader. Addressed when manual depth-chart role data or improved nflverse classification becomes available.

---

## Alternatives Considered

**400-snap qualified threshold:** Initial draft used 400. Rejected after face-check showed top-10 dominated by 400-500 snap role specialists (Leo Chenal, Edgerrin Cooper, Devin Bush) over every-down workhorses. 600-snap threshold restored consensus-style results (Zack Baun #1 in 2024).

**Raw-target threshold for OLB filter:** Rejected. 20-target threshold let Andrew Van Ginkel (22 targets, 27 pressures, 11.5 sacks) grade as the #1 LB. Target-rate filter (3.5%) handles all snap-count edge cases.

**Equal coverage / run weights (50/50):** Considered. Rejected because LBs are primarily second-level run defenders by role (50%+ of their snaps are run plays); 50% run / 37% coverage matches positional usage.

**Including completion% allowed:** Considered. Rejected because LB completion% is heavily zone-affected — passer rating allowed captures completion% as one of its four sub-components alongside yards, TDs, and INTs, in a more skill-isolated way.

**Yards per target allowed as primary coverage metric:** Used in the initial v1 release; replaced with passer rating allowed (see Revision History). Yards/target ignored TDs allowed (the premium negative outcome) and didn't reward INTs, leaving meaningful coverage skill un-measured.

---

## Revision History

**2026-05-14 (initial release):** Used `lb_yards_per_target_allowed` (−0.20) and `lb_pbu_int_rate` (+0.13). Face-check on 2024 / 2023 showed elite consensus LBs (Fred Warner in his All-Pro 2023 season, Roquan Smith) graded lower than expected because yards/target is heavily scheme-dependent for LBs and doesn't capture TDs allowed or INT events.

**2026-05-14 (passer rating revision):** Replaced `lb_yards_per_target_allowed` with `lb_passer_rating_allowed` (weight −0.27, increased from −0.20). Split `lb_pbu_int_rate` → `lb_pbu_rate` (PBU-only, weight 0.08, decreased from 0.13) since INTs are now captured inside passer rating allowed. Reduced `lb_tfl_rate` from 0.22 → 0.20 to absorb the redistributed weight. Sanity-checked vs. 2025 CB and Safety cohorts — passer rating allowed produced clean signal at all three positions; flagged as candidate for CB v1.1 and Safety v1.1.

Face-check after revision: 2024 top 10 has Zack Baun #1, T.J. Edwards #2, Bobby Wagner #6 — all consensus picks. 2023 has Fred Warner #5 (All-Pro year), up from outside top 15 in the initial release. 2025 has Devin Lloyd #1 (5 INTs, elite coverage year).
