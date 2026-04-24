# Methodology

This document is the source of truth for how grades are computed. The
`/methodology` page on the site renders from here (once MDX is wired up in
build step 10). If you change how grades work, update this file first.

## Scope (v1)

- **Time range:** 2016–present (NGS era, consistent methodology).
- **Coverage:** all positions, with explicit data-quality tiers.
- **Depth charts:** end-of-most-recent-regular-season snapshots (no live
  in-season scraping).

## Position tiers

| Tier | Positions             | Notes                                                         |
|------|-----------------------|---------------------------------------------------------------|
| 1    | QB, RB, WR, TE        | Rich data; full pipeline incl. opponent adjustment            |
| 2    | CB, S, EDGE           | Decent data                                                   |
| 3    | OL, iDL, off-ball LB, ST | Proxy stats; directional, not precise                      |

Tier 2 and 3 grades carry a badge in the UI.

## Per-season grading pipeline

For each (season, position, player):

1. Compute raw component stats from PBP / NGS / PFR.
2. Apply garbage-time filter (WP between 0.05 and 0.95) to efficiency components.
3. Apply team-level opponent adjustment (Tier 1 only in v1).
4. Empirical Bayes shrinkage toward positional mean, weighted by snaps/opportunities.
5. Z-score within (season, position).
6. Weight components by inverse-noise (YoY reliability).
7. Composite weighted sum -> single z.

### Composite -> grade

```
grade = 100 / (1 + exp(-k * (z - z0)))
```

Tuned so z=0 -> 50 and z=+2 -> ~90. Bounded 0-100.

## Career grade

1D Kalman filter treating each season grade as a noisy observation of evolving
true skill. Output: posterior mean (grade) and posterior std dev (uncertainty).
Rendered as `93 +/- 4`.

## Sample size

Every position has a minimum snaps/opportunities threshold. Below threshold,
the season exists in data but is shown as "insufficient sample".

## Cross-position comparability

- Ordinally comparable: a 92 is ~98th percentile at any position.
- NOT cardinally comparable: a 92 QB contributes more to winning than a 92 CB.
- No combined "best player in NFL" ranking in v1.

## Validation

Run on every grading rebuild:

- **Face validity:** top 10 at each position eyeballed.
- **Year-over-year correlation:** expected ~0.5-0.6 for QBs, lower for noisier positions.
- **Predictive validity:** this-year grades predicting next-year outcomes.
- **External benchmarks:** Pro Bowls, All-Pros, public top-100 lists.

## Explicit v1 limitations

- No individual-player matchup adjustment for trenches or coverage (data limit).
- No role-based position classification (uses listed position).
- Depth charts are end-of-season snapshots only.
- Tier 3 grades are directional.
- Grades within position only.

## Deferred (v2+)

- Unit-level RAPM for opponent adjustment.
- Full hierarchical Bayesian model with proper per-stat likelihoods.
- Role-based positions from snap-level alignment data.
- Live depth chart updates.
- Player comparison tool with trajectories.
