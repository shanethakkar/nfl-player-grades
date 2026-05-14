# ADR-0022 — LB v1 Grading Formula

**Status:** Accepted (v1.2 rebalance from exhaustive audit — 2026-05-14)
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

## Components (v1.2, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `lb_tfl_rate` | tfl / snaps_defense | **+0.20** | higher = better |
| `lb_passer_rating_allowed` | NFL passer rating on targeted throws | **−0.15** | lower = better |
| `lb_missed_tackle_rate` | missed / (comb + missed) | **−0.15** | lower = better |
| `lb_pbu_rate` | pbu / targets | **+0.05** | higher = better |
| `lb_tackle_rate` | comb_tackles / snaps_defense | **+0.13** | higher = better |
| `lb_pressure_rate` | pressures / snaps_defense | **+0.10** | higher = better |

Sum |weights| = 0.78. Normalized dynamically by `composite.combine`.

**Relative shares:** run defense ~58% (TFL 26% + tackle 17% + missed tackle penalty 19% — implicit, see math), coverage ~25% (passer rating 19% + PBU 6%), pass rush ~13%.

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

Players failing the LB filter are **not graded as LB** for that season. They flow to the EDGE grader instead via the OLB-gap closure branch added in ADR-0020 v1.1 (2026-05-14): the EDGE grader UNIONs `pfr_def_lb` rows where `position_played='LB'`, `pressures ≥ 25`, and `target_rate < 3.5%`. The thresholds are mutually exclusive with the LB filter, so no player is graded twice.

---

## Design Rationale (v1.2)

**TFL rate primary positive (+0.20):** Cleanest LB run-defense signal — actual play-making behind the LOS, harder to inflate via team-context than raw tackle volume. Now the largest positive weight after the v1.2 rebalance lowered passer_rating_allowed.

**Passer rating allowed (−0.15, lowered in v1.2):** Industry-standard NFL coverage metric. Combines comp%, yards per attempt, TDs, and INTs into one number. **v1.2 lowered the weight from −0.27 to −0.15** because the exhaustive audit revealed both weak reliability (YoY +0.146, just above noise threshold) AND weak predictive validity (−0.071) at LB-specific sample sizes. LBs have ~15-25 targets/qualified season vs 50-120 for DBs, so the same metric is structurally noisier here. Still the primary coverage signal, but right-sized.

**Pressure rate (+0.10, bumped in v1.2):** Most off-ball LBs rarely rush — Fred Warner / Roquan Smith have 5-12 pressures/yr on 1000 snaps (0.5-1.2% rate) vs. 4-6% for EDGE. **v1.2 bumped the weight from +0.07 to +0.10** because the audit revealed pressure_rate has the HIGHEST positive validity (+0.149) of any LB component but was the LOWEST-weighted positive component. Same iDL-style mis-order pattern, but smaller magnitude (kept conservative because base rates are low). Rewards blitz-heavy MLBs (Patrick Queen, Kaden Elliss) without overstating position-wide impact.

**PBU rate (+0.05) — PBU-only, not PBU+INT:** INTs are already captured inside passer rating allowed. Keeping PBU as a separate component still credits the active "broke up the catch" play without double-counting interceptions.

**Missed tackle rate penalty (−0.15):** LBs make the most tackles of any position; misses cost the most. Same penalty weight as Safety.

**Tackle rate (+0.13):** Raw tackle volume has team-context contamination (bad defenses see more snaps, more plays). Audit confirmed strong YoY (+0.475 — highest in formula) but weak validity (+0.052 — voters don't reward tackle volume at LB). Meaningful for skill measurement but not dominant.

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

**Pass-rush OLB classification gap (carried from ADR-0020):** ~~Original v1 limitation~~ — **closed 2026-05-14**. T.J. Watt, Micah Parsons, Brian Burns, Nik Bonitto, Jared Verse, Josh Sweat, and ~25 others per season are now graded as EDGE via the OLB-gap closure branch in ADR-0020 v1.1.

---

## Alternatives Considered

**400-snap qualified threshold:** Initial draft used 400. Rejected after face-check showed top-10 dominated by 400-500 snap role specialists (Leo Chenal, Edgerrin Cooper, Devin Bush) over every-down workhorses. 600-snap threshold restored consensus-style results (Zack Baun #1 in 2024).

**Raw-target threshold for OLB filter:** Rejected. 20-target threshold let Andrew Van Ginkel (22 targets, 27 pressures, 11.5 sacks) grade as the #1 LB. Target-rate filter (3.5%) handles all snap-count edge cases.

**Equal coverage / run weights (50/50):** Considered. Rejected because LBs are primarily second-level run defenders by role (50%+ of their snaps are run plays); 50% run / 37% coverage matches positional usage.

**Including completion% allowed:** Considered. Rejected because LB completion% is heavily zone-affected — passer rating allowed captures completion% as one of its four sub-components alongside yards, TDs, and INTs, in a more skill-isolated way.

**Yards per target allowed as primary coverage metric:** Used in the initial v1 release; replaced with passer rating allowed (see Revision History). Yards/target ignored TDs allowed (the premium negative outcome) and didn't reward INTs, leaving meaningful coverage skill un-measured.

---

## Revision History

### v1.2 (2026-05-14) — exhaustive audit rebalance

Two-component rebalance driven by the exhaustive candidate audit ([../grading/audits/2026-05-14-exhaustive-lb.md](../grading/audits/2026-05-14-exhaustive-lb.md)). 19 candidates were scored against four criteria.

**(a) `lb_passer_rating_allowed`: -0.27 → -0.15.** Was the heaviest component (32% of formula). Audit revealed:
- YoY +0.146 (just above noise threshold — vs +0.143 at S/CB but with structurally larger samples there)
- Validity -0.071 (sign correct, magnitude tiny — vs -0.178 at S/CB)
- The metric is genuinely noisier at LB sample sizes (15-25 targets/season per qualified LB vs 50-120 for DBs)
- Pro Bowl voters reward LB coverage less than they reward DB coverage

Right-sized to its real signal strength. Still primary coverage signal at 19% of formula share.

**(b) `lb_pressure_rate`: +0.07 → +0.10.** Modest bump. Audit revealed:
- Highest positive validity in the formula (+0.149)
- Strong YoY (+0.407)
- Was the LOWEST-weighted positive component despite being most voter-validated

Conservative bump (vs iDL's larger +0.05 swing) because LB base pressure rates are very low and over-weighting could push blitz-specialists too high.

**No new components added.** The 6-component LB formula was confirmed structurally complete by the audit. All 13 new candidates were rejected:
- PFR passer-rating sub-components (comp_pct, yards/tgt, int_rate, td_rate): subsumed (+0.51-0.63 correlation with PR_allowed)
- Pass-rush sub-components (qb_hits, hurries, sack_rate): subsumed by pressure_rate (+0.70+ correlation)
- sack_per_pressure, hit_per_pressure: small samples or near-zero validity
- forced_fumble_per_snap, int_per_snap: rare-event noise (xsect 0.00)
- adot_allowed, yac_per_target_allowed: noise / subsumed

**LB has a structural validity ceiling.** Baseline +0.179 is the lowest of any audited position because Pro Bowl voting at LB is driven more by reputation than by box-score stats (the well-known "stats vs reputation" gap). Roquan Smith — universally regarded top-3 LB — grades #19 in 2024 because his box-score numbers don't reflect his consensus standing. No formula change can fix this without encoding reputation directly.

**Validity gate:** LB composite vs next-year Pro Bowl correlation **+0.179 → +0.198 (+0.019)**. Strongest *relative* gain (+11%) of any defensive audit. Largest absolute Path A rebalance in the system. Holds; no rollback.

**Face-check 2024:** Top 2 unchanged in spirit — Zack Baun (DPOY runner-up, 1st-Team All-Pro) #1, Blake Cashman (Pro Bowl) #2. Movers include Roquan Smith (rose from below-cohort-median because he was being penalized by coverage stats and rewarded modestly by pressure). Notable stats-vs-reputation gap persists for Smith (#19).

**Weight totals:** v1.1 sum |abs| = 0.87 → v1.2 sum |abs| = 0.78.

### v1.1 (2026-05-14, second revision) — `lb_pbu_rate` weight lowered (noise)

**Lowered `lb_pbu_rate` from +0.08 → +0.05.** Sum |w| drops 0.90 → 0.87.

**Why:** Cross-position YoY audit found mean YoY r = 0.085 — noise. Light weight bounds noise without removing the signal completely.

### v1.0 (2026-05-14) — initial release + passer-rating revision

**2026-05-14 (initial release):** Used `lb_yards_per_target_allowed` (−0.20) and `lb_pbu_int_rate` (+0.13). Face-check on 2024 / 2023 showed elite consensus LBs (Fred Warner in his All-Pro 2023 season, Roquan Smith) graded lower than expected because yards/target is heavily scheme-dependent for LBs and doesn't capture TDs allowed or INT events.

**2026-05-14 (passer rating revision):** Replaced `lb_yards_per_target_allowed` with `lb_passer_rating_allowed` (weight −0.27, increased from −0.20). Split `lb_pbu_int_rate` → `lb_pbu_rate` (PBU-only, weight 0.08, decreased from 0.13) since INTs are now captured inside passer rating allowed. Reduced `lb_tfl_rate` from 0.22 → 0.20 to absorb the redistributed weight. Sanity-checked vs. 2025 CB and Safety cohorts — passer rating allowed produced clean signal at all three positions; flagged as candidate for CB v1.1 and Safety v1.1.

Face-check after revision: 2024 top 10 has Zack Baun #1, T.J. Edwards #2, Bobby Wagner #6 — all consensus picks. 2023 has Fred Warner #5 (All-Pro year), up from outside top 15 in the initial release. 2025 has Devin Lloyd #1 (5 INTs, elite coverage year).

### v1.1 (2026-05-14, second revision) — `lb_pbu_rate` weight lowered (noise)

**Lowered `lb_pbu_rate` from +0.08 → +0.05.** Sum |w| drops 0.90 → 0.87; combiner normalizes so the signal-strong components get marginally more effective weight.

**Why:** Cross-position YoY audit (2026-05-14) found mean YoY r = 0.085 across 2018-2025 for lb_pbu_rate — same noise pattern as iDL missed_tackle_rate (0.080). Since INTs are already captured inside lb_passer_rating_allowed (the −0.27 component), lb_pbu_rate was already a narrow "broke up the catch" signal; with weak YoY it was barely carrying its weight.

**Why not removed entirely:** Schema-stable change preferred. Cross-sectional spread is real (active PBU plays show up in the data), so the metric captures *something*. Light weight (+0.05) bounds the noise contribution without removing a real signal-carrier completely. If a later audit shows persistent weak signal we can remove.

**Face-check 2024:** Top 4 unchanged (Baun, Edwards, Dean, Hicks). Movers small (±2.4 max) — expected from a small weight delta. No reshuffles in the top half of the cohort.

**Audit data:** `memory/project_cross_position_yoy_audit.md`. Shipped via the new preview/regrade workflow.
