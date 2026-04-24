# 0013 - QB v1 grading formula

- **Status**: Accepted (supersedable — v1 of the formula)
- **Date**: 2026-04-23
- **Supersedes**: None
- **Formalizes**: `docs/grading/qb-v1-proposal.md` (strawman approved
  by the user 2026-04-23)

## Context

First concrete grading formula the pipeline needs to compute. Scope
limited to the QB position so we can ship a full vertical slice
(ingest → features → grades → UI) and iterate on the formula once real
numbers are on screen.

## Decision

### Composite

```
grade = sigmoid(composite_z)

composite_z = 0.50 * z(shrunk_EPA_per_dropback)
            + 0.25 * z(shrunk_CPOE)
            + 0.25 * z(shrunk_success_rate)
```

- `z()` = within-position, within-season standardization.
- `sigmoid()` = existing `grading/sigmoid.py`, tuned so
  `z = 0 → 50`, `z = +2 → ~90`, `z = -2 → ~10`.
- z-score mean/SD computed from **qualified** QBs only (see below).

### Per-component definitions (before shrinkage)

| Component | Raw value | Sample space |
|---|---|---|
| `qb_epa_per_dropback` | mean of `plays.epa` | dropbacks (post-filter) |
| `qb_cpoe` | mean of `plays.cpoe` | pass attempts only (CPOE is null on sacks/scrambles) |
| `qb_success_rate` | mean of `plays.success` | dropbacks (post-filter) |

### Filter

A play counts toward the grade iff ALL:

```
plays.season_type = 'REG'
plays.qb_dropback  = TRUE
plays.aborted_play = FALSE
plays.two_point_attempt = FALSE
NOT garbage_time
```

**Garbage-time** (ADR-0013 formalizes the proposal's rule):

```
garbage_time =
    (qtr >= 4 AND ABS(score_differential) > 21)
 OR (qtr  = 4 AND game_seconds_remaining < 300
                 AND ABS(score_differential) > 14)
```

Chosen over the `wp < 0.05 OR wp > 0.95` convention because nflverse
WP is aggressive about locking in late-game outcomes, and we'd rather
err on the side of keeping a legitimate play than dropping one.

### Empirical Bayes shrinkage

Per component, before z-scoring:

```
shrunk = (n * raw + k * mu_league) / (n + k)
```

- `n` = sample size for that component (dropbacks for EPA + success
  rate; pass attempts for CPOE — CPOE is null on sacks/scrambles so
  we use only the plays where it's defined).
- `mu_league` = league mean of the raw component **among all QBs**,
  weighted by their sample size (volume-weighted, not simple average).
- `k` shrinkage strength:
  - `k = 150` for EPA/db and success rate
  - `k = 100` for CPOE (lower variance, less shrinkage needed)

### Qualified threshold

- `qualified = TRUE` iff `n_dropbacks >= 200` in the regular season.
- All QBs with any dropbacks get a row in `season_grades`, but those
  below the threshold have `qualified = FALSE` — the UI can de-
  emphasize them.
- Unqualified QBs still get shrunk / z-scored so their grade is on
  the same 0–100 scale.

### Position assignment

A player grades as QB iff they're in `player_seasons.position_played =
'QB'` for that season. If a player appears at multiple positions, they
only grade at each position they occupied. Non-QBs with a passing play
(e.g. wildcat RB throws) don't get a QB grade — the QB feature query
joins against `player_seasons.position_played`.

### What opponent adjustment?

**None for v1.** Deferred. The composite runs off raw EPA, no
defense-strength normalization. Revisit in v2 once face-validity
feedback shows whether it's missing.

### Confidence

`season_grades.confidence` is set to `min(1, n_dropbacks / 300)`.
Rough proxy — 300 dropbacks is roughly half a full-season starter's
workload; anyone at/above that gets `confidence = 1`.

### Data tier

Per ADR-0003:

- 2016+: tier 1 (full PBP + NGS available)
- 2006–2015: tier 2 (PBP available, no NGS — not relevant to the
  v1 formula since we don't use NGS)
- pre-2006: tier 3 (no EPA model — cannot grade with this formula)

For now we only compute grades for seasons that have PBP ingested. The
`data_tier` column on `season_grades` records which tier the grade
belongs to.

## Consequences

**Testability:** Each stage (filter, shrinkage, z-score, composite,
sigmoid) is a pure function on a DataFrame. Component tests verify the
math, integration tests verify the top-10 list looks sane.

**Iteration:** If we decide CPOE is overweighted, that's a single
coefficient change in `grading/qb.py`. If we want to add opponent
adjustment later, it's a new column on `stat_components` — no schema
change. The formula is a library, not an API.

**Superseded when:** We add NGS-derived components (time-to-throw,
aggressiveness), opponent adjustment, or a defensibly-tuned inverse-
variance weighting. Those go in v2 and get their own ADR.

## References

- `docs/grading/qb-v1-proposal.md` — the strawman user approved
- ADR-0003 — data tiering for missing historical coverage
- ADR-0007 — originally sketched inverse-noise weighting; v1 skips this
  intentionally for explainability
- `db/migrations/0001_init.sql` — `stat_components` and `season_grades`
  tables (pre-existing)
