# ADR-0023 — K v1 Grading Formula

**Status:** Accepted (v1 audit-first release — 2026-05-14)
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

## Components (v1, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `k_fg_pct_40_plus` | (made_40-49 + made_50+) / (att_40-49 + att_50+) | **+0.40** | higher = better |
| `k_fg_pct` | fg_made / fg_att | **+0.25** | higher = better |
| `k_pat_pct` | pat_made / pat_att | **+0.15** | higher = better |
| `k_fg_long` | longest FG made (yards) | **+0.10** | higher = better |

Sum |weights| = 0.90. Normalized dynamically by `composite.combine`.

**Relative shares:** long-range accuracy 44%, overall accuracy 28%, XP accuracy 17%, power 11%.

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
| `k_fg_pct_40_plus` | 8 attempts (40+) | Matches the minimum sample we trust for the 40+ bucket |
| `k_fg_pct` | 12 attempts | Light shrinkage — starters have ~30 attempts |
| `k_pat_pct` | 15 attempts | XPs are 30-50/season; pull toward league mean ~0.97 |
| `k_fg_long` | 5 attempts (fg_att proxy) | Power surfaces in few attempts; minimal shrink |

---

## Design Rationale

**Long-range accuracy primary (`k_fg_pct_40_plus`, 44%):** The exhaustive audit found this is both the highest-validity signal (+0.126 vs next-year Pro Bowl) and the cleanest discriminator. Everyone makes short FGs (league average ~95% on 0-39 yards); the kickers who differentiate themselves do so from 40+. Combining the 40-49 and 50+ buckets (rather than weighting them separately) trades some "elite long" signal for much more stable per-kicker samples (8-15 attempts vs 3-8 for 50+ alone).

**Overall FG% second (`k_fg_pct`, 28%):** Weak audit signal in isolation (YoY r = -0.013, validity r = +0.052) but kept on **definitional grounds**: it's the conventional kicker headline metric every football fan recognizes. Per the locked-plan principle "grading is a definition, not an estimator," we weight overall accuracy meaningfully even though Pro Bowl voters don't reward it strongly relative to other signals. Removing it would produce a formula that no casual reader would understand.

**XP accuracy (`k_pat_pct`, 17%):** Has the highest YoY r in the formula (+0.211). Since the 2015 rule change moved XPs to ~33-yard FGs, they have meaningful variance and aren't free points. Reliable XP kickers have reliable form.

**Long FG (`k_fg_long`, 11%):** YoY r = +0.206 (leg strength persists). Validity ≈ 0 because a long FG attempt is partly opportunity, but as a power proxy in a multi-component formula it captures real ceiling. Small weight reflects the validity caveat.

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

**v2 candidates (not for v1):**
- `k_xfg_made_over_expected`: distance-adjusted accuracy (requires a baseline xFG model).
- Kickoff metrics post-2024 rule change (touchback rate, hangtime if data becomes available).
- Wind/weather-adjusted FG% (requires per-game weather ingest).

Any v2 add will go through the same four-criterion audit before shipping.
