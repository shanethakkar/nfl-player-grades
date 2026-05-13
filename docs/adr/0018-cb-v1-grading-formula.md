# ADR-0018: CB v1 Grading Formula

**Status:** Accepted (v1.1 — 2026-05-13)
**Date:** 2026-05-12

## Context

CB grading is the first defensive position in the system. The core challenge is
data: nflverse play-by-play records which defender broke up or intercepted a pass
(`pass_defense_1_player_id`, `interception_player_id`), but it does **not** record
which CB was in coverage on completions. This makes PBP-only CB metrics severely
biased — we can count PBUs and INTs, but not completions allowed or yards surrendered.

**Data sources:**
- **Coverage stats** (targets, completions, yards, YAC, TDs, INTs): PFR Advanced
  Defensive Stats via `nflreadpy.load_pfr_advstats(stat_type="def")`. The only
  free, publicly available source with full coverage-side metrics per CB per season.
- **Pass breakups (PBU):** nflverse weekly player stats via `nflreadpy.load_player_stats()`,
  column `def_pass_defended`. PFR's advstats `bats` column is batted passes at the
  line of scrimmage (a pass-rush stat), not coverage PBUs — confirmed by inspection.
  nflverse box-score stats have ~95%+ of CB starters with non-zero PBU totals.
- **Defensive snap counts:** `player_seasons.snaps_defense`, populated by the
  snap-counts ingest. Used as the denominator for target rate.

**Coverage:** 2018+ only. PFR began publishing per-CB target/completion data in 2018.
Seasons 2016–2017 have no CB grades.

## Decision

### Metric Set (v1.1)

| Component | Weight | k (shrinkage) | Direction | Rationale |
|---|---|---|---|---|
| `cb_comp_pct_allowed` | −0.22 | 50 targets | Lower is better | Primary coverage quality signal. Completion % allowed is the most direct measure of whether the CB won his rep. k=50 ≈ half-season of targets. Highest weight in the formula. |
| `cb_yac_per_rec_allowed` | −0.18 | 50 targets | Lower is better | Post-catch YAC reflects cushion allowed and tackling quality near the catch point — a distinct skill from preventing the catch. If a CB allows completions but limits YAC, they're still doing something right. PFR publishes this for most seasons; missing values are NaN-neutralized. |
| `cb_target_rate` | −0.08 | 150 snaps | Lower is better | Targets per defensive snap. Elite CBs get avoided — QBs scheme away from them before the ball is snapped, independent of what happens when they do throw. This signal is not captured by comp% (which only measures targeted plays). Denominator is defensive snaps (not coverage snaps, which are unavailable in public data), so the metric conflates avoidance with role depth; modest weight reflects this limitation. |
| `cb_int_rate` | +0.10 | 80 targets | Higher is better | INTs per target. Highly variable — luck (drops, tipped balls) dominates at low sample sizes — but the ultimate positive play: a turnover that ends the drive. k=80 shrinks heavily for low-target CBs. |
| `cb_pbu_rate` | +0.12 | 80 targets | Higher is better | Pass breakups per target. ~3× more frequent than INTs and more stable (higher YoY r at the same k). Active defense that stops the play without a turnover. Weighted above INT because its reliability justifies more composite influence. Sourced from nflverse `def_pass_defended`. |

**Weight magnitudes:** comp% 31% + YAC 26% + PBU 17% + INT 14% + target rate 11% = 100%
(the combiner normalizes by sum of |weights| = 0.70).

### Why no tackling component?

Tackling is what happens when coverage fails — a CB who tackles well after allowing
a completion is still worse than one who didn't allow it. Comp% and YAC already
penalize the underlying event. Adding tackling would partially reward CBs for the
failure that led to the tackle opportunity. There is also a role confound: slot CBs
make more tackles than outside CBs by position geography, not skill.

### Why no TD rate component? (removed in v1.1)

TD rate was in the original v1 formula at −0.07. It was dropped because:
1. **Rarity:** a CB allows 2–5 TDs per season. Even with k=80 shrinkage, this
   is dominated by noise (r<0.15 YoY).
2. **Redundancy:** a CB who allows TDs is already penalized via comp% (the catch
   happened) and YAC (it went to the end zone). The formula double-counted bad
   outcomes in a noisy, rare-event-driven way.
3. At 7% weight, the noise contribution exceeded the signal contribution for any
   CB with fewer than ~8 TDs allowed (essentially all of them).

The 0.07 was reallocated: +0.03 to `cb_pbu_rate` (0.09→0.12) and the remaining
0.04 absorbed by the new `cb_target_rate` component.

### Why comp% weight held at −0.22?

The original v1.0 formula had comp% at −0.22 and no target rate. When target rate
was added (−0.08), comp% could have been trimmed to avoid over-weighting coverage
outcome signals. However: comp% and target rate measure different things (what
happens on targeted plays vs. how often the QB throws his way at all), so they
are not redundant. Keeping comp% at −0.22 preserves its role as the dominant
single signal while target rate adds orthogonal avoidance information.

### Qualification

- **Minimum targets to appear:** 25 (appears in the system with "low volume" badge).
- **Qualified threshold:** 30 targets (included in the percentile pool).
- **Confidence full at:** 60 targets (~4 targets per game for a full-season starter).

### Role Classification

CBs are classified based on `slot_pct` from PFR:

| Role | Condition |
|---|---|
| `outside_cb` | slot_pct < 35% |
| `hybrid_cb` | 35% ≤ slot_pct ≤ 65% |
| `slot_cb` | slot_pct > 65% |

Role is **label-only** — z-scores are computed against the full CB pool, not within
role cohorts. With ~30–60 qualified CBs per season, splitting further would make
z-scores unstable. The role label lets fans understand why a Patrick Surtain grade
looks different from a Darius Slay grade.

### Shrinkage k rationale

- **comp% and YAC (k=50 targets):** Moderate shrinkage. After ~50 targets (~3 games
  of coverage), a CB's comp% is reliable enough that the empirical prior carries
  half the weight.
- **INT and PBU rates (k=80 targets):** High shrinkage because these are rare/noisy
  events (r<0.25 YoY). A CB with 30 targets and 3 INTs looks elite but may just
  have been lucky; k=80 pulls that toward the mean.
- **target_rate (k=150 snaps):** QB avoidance is more stable than rate stats
  (scheme-driven, not event-driven), so less shrinkage is warranted. However, the
  snap denominator includes snaps where the CB was in run defense or box alignment,
  not purely in coverage — k=150 provides modest pull toward the mean for low-snap
  players where this noise is largest.

### Empirical Bayes shrinkage denominator

The "sample size" for EB shrinkage is:
- **targets** for comp%, YAC, INT rate, PBU rate — the natural denominator for
  these per-target rates.
- **snaps_defense** for target_rate — the natural denominator for a per-snap rate.

YAC's rate denominator is completions, but its EB denominator is targets — this
ensures YAC shrinks at the same rate as comp% for a given number of targets.

### NaN Handling

Standard NaN-neutralization policy (ADR-0015): if a component's z-score is NaN
(due to missing source data), it is replaced with 0.0 before entering the composite.
The raw NULL is preserved in `stat_components.z_score` so the UI renders "—".

Known NaN sources:
- `cb_yac_per_rec_allowed`: NULL in `pfr_def_coverage.yac` for some seasons.
- `cb_pbu_rate`: NULL for CBs absent from nflverse player_stats (edge cases).
- `cb_target_rate`: NULL if `snaps_defense = 0` (player_seasons not yet populated).

## Alternatives Considered

**PBP `pass_defense_1_player_id` for PBU:** Only captures ~31% of incompletions
(drops, overthrows, and throwaways get no credit). Too noisy and biased against
CBs who contest uncredited balls. Rejected.

**PFR `bats` column for PBU:** Confirmed via data inspection to be batted passes
at the line of scrimmage (pass-rush stat), not coverage PBUs. Most safeties and
CBs have 0 `bats`. Rejected — using nflverse `def_pass_defended` instead.

**Yards per target instead of comp% + YAC:** Simpler, but merges two different
skills into one opaque number. They have different YoY reliability and warrant
different k values. The decomposed form also gives the player profile page more
granular insight per component.

**TD rate in the formula:** Included in v1.0; removed in v1.1. See rationale above.

**Targets per coverage snap (not defensive snap):** More precise than targets per
defensive snap, but coverage snap counts are not available in any free public
dataset. The full PFR advstats feed lacks a coverage-snaps column; participation
data identifies FS/SS designations per play but does not cleanly distinguish
"in coverage" from "in the box." Deferred to v2 if data becomes available.

**Role-bucketed z-scoring (outside vs. slot):** Correct in principle — an outside
CB's comp% should be compared to other outside CBs. Deferred because with ~30–60
qualified CBs per season, splitting further produces unstable z-scores. The role
label provides context without distorting the z-score distribution.

## Consequences

- CB grades available from 2018–present.
- Pipeline requires three nflreadpy sources: `load_pfr_advstats(stat_type="def")`
  for coverage stats, `load_player_stats()` for PBU (`def_pass_defended`), and
  `player_seasons.snaps_defense` (populated by the snap-counts ingest) for target rate.
- Historical seasons 2016–2017 return no CB grades.
- YAC component may be absent in some early seasons (2018–2019). PBU component may
  be absent for edge-case CBs not in the nflverse player_stats source. Target rate
  component is absent if snap-counts ingest has not been run for a season. All are
  NaN-neutralized gracefully.
- v1.1 formula changes require re-running `nflgrades grade --position CB` for all
  2018–2025 seasons to update stat_components and season_grades.
