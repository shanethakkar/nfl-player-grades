# Methodology

This document is the source of truth for how grades are computed. The
`/methodology` page on the site renders from here. If you change how grades
work, update this file first. For the full decision record behind any
specific choice, each section links out to the relevant ADR.

## Scope (v1)

- **Time range:** 2016-present. QB, RB, WR, TE, K and P are graded for
  2016-2025; CB, S, EDGE, iDL, LB and OL for 2018-2025 (PFR advanced
  defense and pass-rush data start in 2018).
- **Positions graded:** QB, RB, WR, TE, CB, S, EDGE, iDL, LB, K, P, plus
  OL as a team-level unit (see [§Position tiers](#position-tiers)).
- **Depth charts:** end-of-most-recent-regular-season snapshots (no live
  in-season scraping).
- **Opponent adjustment:** not applied in v1 — v1 favors
  explainability over full context adjustment; v2 adds it. See
  [ADR-0013 §Explicitly deferred](#adr-0013).

## Position tiers

Position tiers describe the **quality of public data** at each position,
which bounds how precise a grade at that position can be. This is a
design tier, not the per-season `data_tier` column (which tracks
per-season feature availability; see
[ADR-0003](#adr-0003)).

| Tier | Positions                | Status  | Notes                                     |
|------|--------------------------|---------|-------------------------------------------|
| 1    | QB, RB, WR, TE           | Shipped | Rich PBP + NGS data                       |
| 2    | CB, S, EDGE              | Shipped | PFR coverage / pass-rush charting (2018+) |
| 3    | OL, iDL, off-ball LB, K, P | Shipped | Proxy stats; OL graded per team, not per player |

## Per-season grading pipeline

For each `(season, position, player)` the pipeline produces one
`season_grades` row and N `stat_components` rows (one per component):

1. **Extract raw component stats** from PBP, NGS, and PFR-derived data
   (one SQL query per position — see `pipeline/src/nfl_grades/grading/<position>.py`).
2. **Apply garbage-time filter** on play-by-play components: plays in
   the 4th quarter or later with a margin over 21, or in the last 5
   minutes of the 4th with a margin over 14, are dropped
   (`grading/filters.py`, ADR-0013). Win probability is not used.
3. **Empirical Bayes shrinkage** toward positional mean, weighted by
   snaps / opportunities. Shrinkage strengths `k` are hand-tuned per
   component using year-over-year reliability. See
   [ADR-0013](#adr-0013), [ADR-0014](#adr-0014),
   [ADR-0015](#adr-0015), [ADR-0016](#adr-0016).
4. **Z-score within (season, position)** using the plain (unweighted)
   mean and sample SD of the qualified players. Every player, qualified
   or not, is z-scored against that distribution.
5. **Hand-picked weights** combine component z-scores into a composite
   z. v1 deliberately chose explainable weights over inverse-noise /
   YoY-stability weights; see
   [ADR-0013 §Weights](#adr-0013) for the reasoning.
6. **Composite** = signed weighted sum ÷ sum of |weights|, taken over
   the components the player actually has. The magnitude-sum denominator
   lets negative-weighted components (fumble rate) contribute their
   designed share. A missing component (no NGS row, drops before 2022,
   RB yards after contact before 2018) drops out and the remaining
   weights are renormalized, rather than being scored as league average
   ([ADR-0028](#adr-0028)).
7. **Standardize** the composite: divide it by its SD over the qualified
   players of that position-season, so it has unit SD at every position
   ([ADR-0028](#adr-0028)). Without this, a position whose components
   are weakly correlated (LB, S) has a narrow composite and can never
   reach 90, while one with strongly correlated components (iDL) grades
   generously. A position-season with fewer than 10 qualified players is
   not graded at all, rather than grading everyone 50.

### Composite → grade

```
grade = 100 / (1 + exp(-k * (z - z0)))
```

Parameters: `k = 1.15`, `z0 = 0` — tuned so `z = 0 → 50` and
`z = +2 → ≈90`. Bounded 0–100. Because `z` is the standardized composite,
a 90 (`z ≈ 1.91`) is about the 97th percentile of qualified players at
every position and season. See [ADR-0008](#adr-0008) for the parameter
selection and [ADR-0028](#adr-0028) for the standardization.

## Qualification thresholds

Each position has two thresholds:

- **Minimum to grade at all** — below this, no `season_grades` row is
  written. Keeps low-sample noise out of the leaderboards and the
  z-score population.
- **Qualified for leaderboard** — above this, `qualified = true`.
  Non-qualified rows are stored for reference and shown "below the
  fold" on the leaderboard.

| Pos  | Min to grade | Qualified | Unit |
|------|--------------|-----------|------|
| QB   | 1            | 200       | dropbacks |
| RB   | 30           | 120       | touches |
| WR   | 20           | 50        | targets |
| TE   | 15           | 40        | targets |
| CB   | 25           | 30        | targets in coverage |
| S    | 200          | 400       | defensive snaps |
| EDGE | 200          | 400       | defensive snaps |
| iDL  | 200          | 400       | defensive snaps |
| LB   | 200          | 600       | defensive snaps |
| K    | 10           | 20        | FG attempts |
| P    | 25           | 40        | punts |
| OL   | —            | all 32    | team units |

Thresholds live in `pipeline/src/nfl_grades/grading/weights.py`.

Blocking TEs (<15 targets) have no `season_grades` row; their season
is visible on team rosters but they are not ranked against receiving
TEs.

## Role-specific grading (TE only)

TE v1 is the one position where role changes the composite. See
[ADR-0016](#adr-0016):

- `receiving_te` / `balanced_te`: full 6-component composite.
- `blocking_te`: same components, but `te_target_earn_rate` is stored
  (`used_in_composite = false`) and its weight is redistributed to
  EPA/target and YAC-over-expected in proportion. A pure blocker
  shouldn't be penalized for low target earn rate — that's the job.

Role is stored on `season_grades.role`; the reason for any data-tier
bump is stored on `season_grades.data_tier_reason`.

## Career grade

1-D Kalman filter treating each season grade as a noisy observation
of evolving true skill. Output: posterior mean (grade) and posterior
standard deviation (uncertainty). Rendered as `93 ± 4`.

Not yet implemented in the current build. Season grades now cover
2016-2025 (ten seasons), so career grades are unblocked and become the
next grading workstream.

## Cross-position comparability

- **Ordinally comparable**: a 90 is ~97th percentile of qualified
  players at every graded position and season, because the composite is
  standardized before the sigmoid ([ADR-0028](#adr-0028)).
- **NOT cardinally comparable**: a 92 QB contributes more to winning
  than a 92 TE. Positions have different leverage.
- No combined "best player in NFL" ranking in v1.

## Validation

Run on every grading rebuild:

- **Face validity**: top 10 at each position eyeballed. The one
  published face-check —
  [ADR-0017](#adr-0017) — identified
  offense-context contamination in high-volume receivers on bad-QB
  offenses, documented as a v1 limitation.
- **Year-over-year correlation**: expected ~0.5–0.6 for QBs, lower
  for noisier positions. See each grading ADR's §Validation.
- **Predictive validity**: this-year grades predicting next-year
  outcomes (pending — unblocked by the 2016-2025 backfill).
- **External benchmarks**: Pro Bowls, All-Pros, public top-100 lists
  (pending).

## Explicit v1 limitations

- **No opponent adjustment.** Grades reflect raw-context performance,
  not matchup-adjusted. Per-component pre-adjusted flags
  (`*_PRE_ADJUSTED` in `pipeline/src/nfl_grades/grading/weights.py`)
  document which NGS inputs are *already* adjusted upstream so v2
  doesn't double-adjust.
- **No QB-context adjustment for receivers.** Per-target efficiency
  components are treated as receiver skill, so high-volume receivers
  whose targets are forced by bad QB play grade lower than tape
  suggests. See
  [ADR-0017](#adr-0017) for the
  specific confound and the v1.5 candidate fixes. The player page
  surfaces this context inline when it applies (Brock Bowers LV 2024,
  David Njoku CLE 2024, etc.).
- **No role-based position classification at scale.** TE is the only
  position that gets a role (`receiving` / `balanced` / `blocking`);
  WR slot-vs-boundary and RB zone-vs-gap distinctions are deferred.
- **Depth charts are end-of-season snapshots only.** Not live-updated
  in-season.
- **Grades within position only.** A WR 85 and a RB 85 are not the
  same quality of performance in absolute terms.

## Deferred (v2+)

- **Unit-level RAPM for opponent adjustment.**
- **Full hierarchical Bayesian model** with proper per-stat
  likelihoods.
- **Role-based positions from snap-level alignment data.**
- **Live depth chart updates.**
- **Player comparison tool with trajectories.**
- **FTN-powered v1.5 for WR/TE** (drop rate, contested catch,
  created reception, screen-excluded EPA/target). See
  [2026-04-24 YPRR feasibility memo](../exploration/2026-04-24-yprr-feasibility.md)
  for the plan shape.
- **QB-quality-conditional z-scoring** for receiver composites
  (the real fix for the ADR-0017 confound).
