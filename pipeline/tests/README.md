# tests/

Mirrors the package layout under `src/nfl_grades/`:

```
tests/
├── conftest.py
├── test_config.py              # top-level modules tested at the root
├── grading/
│   ├── test_sigmoid.py
│   ├── test_empirical_bayes.py
│   └── test_composite.py
├── ingest/
│   └── test_pbp.py
├── components/
└── career/
```

Each subpackage gets an `__init__.py` so pytest picks them up cleanly. Keep
test names matching the source: `src/nfl_grades/grading/sigmoid.py` ->
`tests/grading/test_sigmoid.py`.

## Before you run pytest: it hits Neon (production)

DB-backed tests (`tests/ingest/test_{rosters_db,snap_counts,depth_charts}.py`,
parts of `tests/grading/test_{qb,rb,wr,te}.py`) connect via `get_engine()`,
which reads `DATABASE_URL` from the root `.env`. That `.env` currently points
at **Neon**, not local Docker. The tests wrap every write in a transaction
that rolls back, so nothing persists, but they still run against production.
To use local Docker instead, set `DATABASE_URL` in the shell first (see
`.env.example`).

The pure grading tests (`tests/grading/test_{scoring,composite,sigmoid,zscore,empirical_bayes}.py`)
touch no database.

## Known failures (as of 2026-09-27, before issue #6)

The full suite is 206 passed / 7 failed. These 7 were failing before the
Grading v2 work and are **not** regressions:

| Test | Cause |
|---|---|
| `grading/test_composite.py::TestCombine::test_wr_v1_weights_example` | Hard-coded expected value from pre-retune WR weights (WR v1.3). |
| `grading/test_composite.py::TestCombine::test_te_v1_weights_example` | Same, TE weights (TE v1.2). |
| `grading/test_composite.py::TestCombine::test_te_v1_blocking_weights_example` | Same, TE blocking weights. |
| `ingest/test_depth_charts.py::TestSelectSnapshot::test_new_format_picks_latest_timestamp` | Fixture inserts into `players` without `slug`, now NOT NULL. |
| `ingest/test_depth_charts.py::TestReplaceSnapshot::test_insert_then_replace_is_idempotent` | Same `slug` fixture drift. |
| `ingest/test_snap_counts.py::TestUpdatePlayerSeasons::test_updates_only_matching_rows` | Same `slug` fixture drift. |
| `ingest/test_snap_counts.py::TestUpdatePlayerSeasons::test_no_matching_player_season_row_is_silent` | Same `slug` fixture drift. |

If you fix one, delete its row. If the count goes above 7, you broke something.

## Scoring regression check

`scripts/verify_scoring_regression.py` (read-only) rescores every stored
position-season from stored z-scores through `grading.scoring.score()` and
compares against stored grades. Since #6 standardized the Composite
(ADR-0028), values change by design; the check is that rankings don't.
Among players with every Component the season has, Spearman(stored, new)
must be 1.0. It also reports how far players missing a Component move
(their weights now renormalize instead of zero-filling) and the share of
qualified players at 90+ before and after.

Before the #6 Neon restatement, all 108 position-seasons passed. Almost
every player missing a Component is unqualified; the exception is 11
qualified RBs without NGS RYOE (2019, 2021, 2022), whose percentiles
moved by at most ~9 points. Once Neon is restated, "stored" and "new" match and the check
passes trivially until the next scoring change.
