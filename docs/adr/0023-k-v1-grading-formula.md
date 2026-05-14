# ADR-0023 — K v1 Grading Formula

**Status:** Accepted (v1.1 FGOE correction — 2026-05-14)
**Date:** 2026-05-14

---

## Context

Kickers are the first new graded position added under the "do it right" audit-first methodology (master plan locked 2026-05-14). Every weight in K v1 was decided after running the four-criterion exhaustive candidate audit ([../grading/audits/2026-05-14-exhaustive-k.md](../grading/audits/2026-05-14-exhaustive-k.md)), not designed first and audited later.

**v1 scope:** placekicking only (FG + XP). Kickoffs deferred to v2 because the 2024 dynamic-kickoff rule change broke year-over-year continuity of touchback/return rates. A future v2 add can revisit kickoff metrics once 2-3 years of post-rule-change data exists.

---

## Data Sources

| Source | Columns | Coverage |
|---|---|---|
| `nflvs_player_stats` → `kicker_stats` | fg_att, fg_made (overall and by distance bucket), pat_att, pat_made, fg_long, gwfg_att, gwfg_made | 2016+ |

Grain: one row per (player_id, season). Ingest filters to `position='K'`, `season_type='REG'`, sums per-game counts to season totals.

---

## Components (v1.1, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `k_fg_over_expected_per_att` | `(total_makes − expected_makes) / total_att` where `expected_makes = Σ attempts_bucket × baseline_bucket` (FG buckets + XP folded in) | **+1.00** | higher = better |

Single-component formula. Sum \|weights\| = 1.00. No normalization needed.

### League baselines (computed from kicker_stats 2016-2024)

| Distance bucket | Baseline make rate | n_att in baseline window |
|---|---:|---:|
| 0-19 yd | 100.0% | 42 |
| 20-29 yd | 98.4% | 2,093 |
| 30-39 yd | 93.6% | 2,587 |
| 40-49 yd | 79.6% | 2,662 |
| 50-59 yd | 69.0% | 1,563 |
| 60+ yd | 40.0% | 65 |
| XP (post-2015 rule) | 94.3% | 10,941 |

Baselines are frozen as constants (`K_V1_1_BASELINES` in `weights.py`) so grades reproduce season-to-season without recomputing the baseline (era-fixed yardstick).

### Per-attempt mechanics

- **60-yard make** → +0.60 over expected (large reward)
- **60-yard miss** → -0.40 (modest penalty — it was hard)
- **30-yard make** → +0.06 (tiny reward — expected)
- **20-yard miss** → -0.98 (massive penalty — easy kick)
- **XP make** → +0.06 (rounding error, basically free)
- **XP miss** → -0.94 (heavily penalized)

This is **risk-asymmetric by construction**. A kicker like Brandon Aubrey who attempts 15 FGs from 50+ doesn't get punished for the misses (low expected baselines) but is heavily rewarded for the makes. A kicker whose coach never lets them try past 45 doesn't get a "safe" path to a high grade — they earn what they kick.

---

## Qualification (FG-attempt based)

| Threshold | FG attempts |
|---|---|
| MIN to grade | 10 |
| QUALIFIED (main leaderboard) | 20 |
| Full confidence | 30 |

**Why FG-attempt based, not snap-based:** Kickers don't have meaningful snap counts (special teams only). FG attempts directly measure the workload that produces our component metrics.

---

## Shrinkage k Values

| Component | k | Rationale |
|---|---|---|
| `k_fg_over_expected_per_att` | 15 attempts (FG + XP total) | Low-workload kickers (rookies, injury fill-ins) get pulled toward FGOE = 0 (league mean) |

---

## Design Rationale (v1.1)

**Single principled metric.** The v1.1 formula is one number — FG Over Expected per attempt — that comprehensively captures kicker skill:

- **Accuracy:** automatic. Every kick is scored vs its distance baseline.
- **Range:** automatic. Making a 55-yarder is worth ~9x more than making a 25-yarder.
- **Risk-asymmetry:** automatic. A 60-yard miss costs little (it was hard); an XP miss is devastating (it shouldn't have been).
- **XPs:** folded in as a 7th distance bucket (post-2015 rule, ~94% baseline). Missing XPs hurts the grade as much as it should.

**No additional components needed.** The v1.1 audit confirmed every other plausible kicker metric is either subsumed by FGOE/att or pure noise:

- `k_fg_pct` (overall): redundant with FGOE (which uses the same makes but weights by difficulty)
- `k_fg_pct_40_plus` (the v1 primary): redundant — FGOE handles 40+ explicitly via buckets and is more granular
- `k_pat_pct`: folded INTO FGOE as the XP bucket
- `k_fg_long`: validity ≈ 0; conceptual "power" is already expressed through FGOE on 50+ attempts
- `k_gwfg_pct`: noise (n=49, validity 0.000)
- `k_fg_pct_short`: anti-skill (negative YoY due to regression to ceiling)

The methodology page surfaces context columns (raw FG%, longest FG, XP%) on the leaderboard for reader recognition, but they're labeled CONTEXT (not in formula) via the two-tier header. The grade itself is FGOE/att alone.

---

## Rejected Candidates (audit log)

Documented in the audit doc; summarized here for the article-defensibility goal:

- **`k_fg_pct_short`** (0-39 yards): YoY r = -0.135. **Negative YoY** — regression to ceiling, not a skill signal. Excluded.
- **`k_fg_pct_50_plus`**: YoY r = +0.004 (essentially zero), small samples (3-8 attempts). Subsumed by `k_fg_pct_40_plus`.
- **`k_fg_pct_40_49`**: Smaller sub-bucket of `k_fg_pct_40_plus`. Subsumed.
- **`k_gwfg_pct`**: Validity r = 0.000, n=49. Pure noise (game-winning FGs are 2-5 per kicker per season).
- **`k_fg_att_per_game`**: Usage marker — good teams attempt more FGs because they drive deeper. Not a skill signal.

---

## NaN Handling

Standard NaN-neutralization (ADR-0015): if a component's z-score is NaN (missing source data), it's replaced with 0.0 before entering the composite.

Known NaN sources:
- `k_fg_pct_40_plus`: NaN if the kicker had zero 40+ attempts (rare; happens for backup kickers in committees).
- `k_fg_long`: NaN if no FG attempts. Filtered out by the MIN_FG_ATT_TO_GRADE threshold (10).
- `k_pat_pct`: NaN if zero XP attempts (extremely rare; offensive scheme dependent).

---

## Alternatives Considered

**Expected FG% (xFG) model:** A distance-adjusted accuracy metric (compare actual makes to expected makes from league baseline rates by distance). More sophisticated than `k_fg_pct_40_plus` alone, and would handle distance distribution differences across kickers. Rejected for v1 to keep the formula transparent and bound to raw nflverse columns. Candidate for v2 if validity gap warrants it.

**Including `k_gwfg_pct` at light weight:** Tempting because "clutch kicker" is a real concept fans believe in. Rejected because the audit returned validity r = 0.000 (no signal) and n=49 (only kickers with multiple GWFG attempts). Reputation-driven, not stat-driven.

**Including kickoff metrics (touchback rate, hangtime):** Rejected for v1 because the 2024 dynamic-kickoff rule change made touchback rate non-comparable to pre-2024 data. Will revisit after 2-3 post-change seasons.

**Snap-based qualification:** Kickers don't have meaningful snap counts. FG-attempt threshold is the right denominator.

---

## Known Limitations

**Lowest validity baseline of any graded position (+0.165).** Documented honestly in the audit doc. Kicker stats are structurally noisy:
- Small per-season samples (~30 FG attempts)
- Distance distribution varies by team (some kickers get more long opportunities)
- Pro Bowl K voting is reputation-driven (only 2 K Pro Bowls/year out of ~30 qualified)

**`k_fg_pct` carries weak audit signal** but is kept on definitional grounds (reader-recognizable). Future audits may reduce its weight if the validity gap doesn't close.

**No wind/weather/dome adjustment.** Outdoor kickers in Buffalo / Cleveland / Chicago face harder conditions than indoor kickers in Dallas / Detroit / Indianapolis. An adjusted-environment FG% would be a v2 candidate but requires per-game weather data we don't currently ingest.

**Coverage starts 2016.** nflvs_player_stats has older data but we cap at 2016 to match coverage with other position grades.

**Pre-2015 XP attempts are noisier as a signal** because XPs were 19-yard FGs (~99% league-wide). The 2016+ data covers the post-rule-change era exclusively.

---

## Consequences

- K grades available from 2016 onward (2016-2025 graded as of v1 ship).
- Pipeline requires: `kicker_stats` table (migration 0016), `nflvs_player_stats` ingest (already running for other positions).
- To regenerate grades: `nflgrades grade --season <year> --position K` for each season 2016-2025.
- The lowest baseline validity becomes the "K floor" for cross-position comparisons. Documenting this is part of the audit-first article-defensibility goal.

---

## Future Work

**v2 candidates (not for v1.1):**
- Kickoff metrics post-2024 rule change (touchback rate, hangtime if data becomes available).
- Wind/weather/dome-adjusted baselines (requires per-game weather ingest). Currently baselines are pooled across all stadiums/conditions, which mildly disadvantages outdoor cold-weather kickers (Buffalo, Cleveland, Chicago) vs indoor kickers (Detroit, Atlanta, Indy).
- Per-attempt model: instead of bucketed baselines, fit a smooth function `p_make(distance)` from PBP-level FG data. Marginal precision gain; v1.1's bucketed approach is interpretable and matches how kickers are discussed.

Any v2 add will go through the same four-criterion audit before shipping.

---

## Revision History

### v1.1 (2026-05-14) — FGOE design correction (same-day)

**Replaced the v1 formula entirely.** v1's four-component design (`k_fg_pct_40_plus` +0.40, `k_fg_pct` +0.25, `k_pat_pct` +0.15, `k_fg_long` +0.10) actively punished kickers who attempted long FGs. A 60-yard miss hurt v1's `k_fg_pct` and `k_fg_pct_40_plus` identically to a 35-yard miss, even though the former is league-average difficulty and the latter is a near-certain make. **Brandon Aubrey is the case study:** in 2024 he attempted 15 FGs from 50+ (most in the league) and made most of them; v1 graded him #4 because the missed long-range attempts dragged his raw rates down. A kicker whose coach never sent them past 45 looked better.

**v1.1 fix:** single component, `k_fg_over_expected_per_att`. Each kick is compared to the league baseline for its distance (computed from 2016-2024 data and frozen as constants). Risk-asymmetric by construction.

**Audit support:** the v1 audit had already shipped FGOE as a candidate. Its YoY r = +0.126 is the **highest of any K candidate** (next best `k_pat_pct` at +0.211 was disqualified as standalone since it doesn't capture FG range). Validity r = +0.091 is moderate — within the noise floor for K, but the philosophical case carries. See `docs/grading/audits/2026-05-14-exhaustive-k.md`.

**Face-check 2024 (v1 → v1.1 movement):**
- Chris Boswell: #1 → #1 (1st-Team All-Pro, consensus #1, formula agrees both ways)
- **Brandon Aubrey: #4 → #2** (the headline correction — formula now rewards his 50+ make rate properly)
- Nick Folk: #2 → #3
- Wil Lutz: #5 → #4
- Justin Tucker (historic collapse): #28 → #23 — still well below average, but FGOE penalizes his misses less because some were long
- Jake Moody, Dustin Hopkins: bottom 2 in both versions (lost their jobs)
- Cameron Dicker (NFC Pro Bowl): #8 → #10 — his lower FG attempt count hurts him slightly more under FGOE

**Validity gate:** v1 composite r = +0.165 → v1.1 r = +0.153 (-0.012). Slight drop in Pro Bowl-prediction strength, well within noise floor for the K validity ceiling. Pro Bowl voting at K is reputation-driven; the drop reflects that voters reward FG% more than FGOE (which is a known voter behavior, not a formula flaw). The philosophical correctness of FGOE is the test, not validity for this position.

**Leaderboard UI change:** added a two-tier "FORMULA / CONTEXT" header pattern to the K leaderboard (PFF-style grouped header). The single FGOE/att column sits under FORMULA; raw FG%, FG% 40+, XP%, and longest FG are shown under CONTEXT for reader recognition without being scored. Pattern is K-only for now; could generalize to other positions later.

### v1.0 (2026-05-14, deprecated same-day)

Initial release with four raw make-rate components. Replaced within hours by v1.1 after recognizing the risk-aversion flaw. Documented here for the audit log.
