# 0007 - Pure-function grading math, DB I/O isolated to `ingest/`

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

The grading pipeline has many moving parts: empirical Bayes shrinkage,
opponent adjustment, z-score within position, inverse-noise composite
weighting, sigmoid mapping to 0-100, Kalman smoothing across seasons. We
need to be able to:

- Tune parameters interactively in notebooks
- Unit-test math without spinning up Postgres
- Re-run grading on cached/synthetic data
- Compare two grading variants side-by-side without committing one to disk

If grading code calls into the database, all of this gets harder.

## Decision

**Modules under `grading/`, `career/`, `components/`, and `adjust/` are pure
functions.** They take pandas DataFrames and return pandas DataFrames. They
must not import from `nfl_grades.db` or `nfl_grades.ingest`.

DB I/O lives in two places only:

- `nfl_grades.ingest.*` — reads from `nfl_data_py`, writes to raw tables
- The CLI commands in `nfl_grades.cli` — orchestrate by reading from DB,
  passing DataFrames to the pure functions, writing results back

Concretely: `grading/empirical_bayes.shrink(df, ...)` returns a Series. The
CLI does `df = pd.read_sql(...); shrunk = shrink(df); df.to_sql(...)`.

## Consequences

**Easier:**
- Tests for grading math are pure-Python, no fixtures, no test DB. See
  `pipeline/tests/grading/test_sigmoid.py` for the pattern.
- Notebooks can iterate on math by passing in any DataFrame, including
  hand-constructed ones for edge cases.
- A future "grade variant comparison" feature is just calling the same
  pure function with two parameter sets and diffing the outputs.

**Harder:**
- The CLI is responsible for the orchestration glue. That code is less
  interesting and less tested. Acceptable; it's mostly two-liners.

**Enforcement:**
- ADR-only for now. If we get tempted to add a DB call inside `grading/`,
  the import would be the obvious red flag in code review. If this becomes
  a recurring problem, add an `import-linter` rule.
