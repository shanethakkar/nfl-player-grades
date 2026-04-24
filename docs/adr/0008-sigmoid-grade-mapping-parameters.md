# 0008 - Sigmoid grade mapping with k=1.15, z=0->50, z=+2->90

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

After computing a composite z-score per (player, season, position), we
need to map it onto the 0-100 grade scale users see. Options:

1. **Linear rescale**: `grade = 50 + 20*z`, clipped to [0, 100]. Simple,
   but cliffs at the boundaries and stretches the middle.
2. **Percentile-based**: `grade = 100 * percentile_rank(z)`. Self-rescaling
   year over year (a "90" never means the same thing twice).
3. **Sigmoid**: `grade = 100 / (1 + exp(-k * (z - z0)))`. Smooth, bounded,
   monotonic, never rescales.

## Decision

**Sigmoid with k=1.15 and z0=0.** Implementation in
`pipeline/src/nfl_grades/grading/sigmoid.py`.

Parameters chosen so that:
- z =  0 -> grade = 50
- z = +1 -> grade ~= 76
- z = +2 -> grade ~= 91
- z = -2 -> grade ~=  9

Rough interpretation: a "90" is roughly 2 standard deviations above the
positional mean — about the 97th percentile of qualified players.

## Consequences

**Easier:**
- Grades are stable across seasons. A 90 in 2018 means roughly the same
  thing as a 90 in 2024.
- Bounded [0, 100] without clipping artifacts.
- Smooth and monotonic — small z changes produce small grade changes.
- Same mapping works for every position.

**Harder:**
- Not directly interpretable as a percentile. We address this by storing
  `percentile` alongside `composite_grade` on `season_grades`.
- Tuning k requires balancing "spread between elite players" (higher k)
  against "starters cluster near 50" (lower k). 1.15 is the current sweet
  spot from synthetic-data tuning; will be re-checked once we have real
  QB grades to eyeball.

**Subject to revision:**
- This is the v1 default. If face-validity tests after build step 2 say
  "the top 10 QBs are all 95+ and indistinguishable," we lower k. If they
  say "Mahomes is 78," we raise k. Document changes by superseding this ADR.
