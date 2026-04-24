# 0009 - Raw nflverse data cached as parquet; only typed tables in Postgres

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

Every ingest module pulls a DataFrame from `nfl_data_py` (play-by-play,
rosters, depth charts, NGS passing/receiving/rushing, weekly snap counts,
schedules) and eventually has to populate our typed tables (`players`,
`player_seasons`, `depth_charts`, `stat_components`, etc.).

The question: **what happens to the raw DataFrame between the network call
and the typed insert?** Three real options:

1. **Direct ETL.** Pull from `nfl_data_py`, transform in memory, write typed
   rows. Discard the raw DataFrame.
2. **Raw tables in Postgres.** Persist the raw DataFrame to `raw_pbp`,
   `raw_rosters`, etc. (text/jsonb-heavy schemas). Transform reads from
   those raw tables and writes to typed tables.
3. **Parquet on disk.** Cache the raw DataFrame to
   `pipeline/.cache/raw/{source}/{season}.parquet`. Transform reads from
   parquet and writes typed rows to Postgres.

Things that matter for our project:

- **PBP is large.** ~50k rows × 300+ columns per season × 10 seasons is the
  bulk of our raw data. Most of those columns we never use.
- **Iteration speed dominates.** Tuning grade weights or the garbage-time
  filter means re-running transforms many times per session. Re-downloading
  PBP each time would kill the loop. `nfl_data_py.import_pbp_data([2024])`
  takes ~30s; across 10 seasons that's 5 minutes per iteration.
- **Upstream churn happens.** `nfl_data_py` corrects historical data and
  occasionally renames columns. A snapshot of "what we believed the schema
  was on date X" is valuable for debugging "why did this player's grade
  change?"
- **Postgres is for the product, not the archive.** The web app, indexes,
  and analytical queries all target typed tables. Mixing 100M+ raw PBP rows
  in the same DB blows up backups, dump sizes, and query planner headroom.
- **Pure-function math (ADR 0007).** Transforms take DataFrames in and
  return DataFrames out. They don't care whether the source was a live API
  call, a parquet file, or a SQL query.

## Decision

**Three-layer separation:**

1. **Raw layer — parquet on disk.** Every `nfl_data_py` call funnels
   through a `cache_or_fetch(source, season)` helper that:
   - Returns `pd.read_parquet(...)` if the file exists.
   - Otherwise calls the upstream function, writes the parquet, returns the
     DataFrame.
   - Path: `pipeline/.cache/raw/{source}/{season}.parquet` (already in
     `.gitignore`, configurable via `PIPELINE_CACHE_DIR`).
2. **Manifest — JSON sidecar.** `pipeline/.cache/raw/manifest.json` records
   `{source, season, fetched_at, nfl_data_py_version, row_count, sha256}`
   per file. Lets us detect upstream churn without re-downloading and
   surfaces stale caches in `nflgrades validate`.
3. **Typed layer — Postgres.** Only schema-defined tables live in Postgres
   (`db/migrations/*.sql`). No `raw_*` tables, no `jsonb` columns holding
   raw payloads.

**CLI behavior:**

- `nflgrades ingest <source> --seasons 2024,2025` uses the cache by default.
- `nflgrades ingest <source> --refresh` ignores the cache, re-fetches, and
  rewrites parquet + manifest.
- `nflgrades ingest --refresh-stale` re-fetches anything where the manifest
  shows the cached `nfl_data_py` version differs from the installed one.

**Audit trail in Postgres:** the existing `pipeline_runs` table records
each ingest invocation (`stage='ingest:{source}'`, `season`, `rows_written`,
`status`). The `pipeline_runs` row says *we ingested season X on date Y*;
the parquet file holds *what we actually saw*.

## Consequences

**Easier:**

- Re-running grading on new parameters costs the transform time only — no
  network, no waiting on `nfl_data_py`.
- Notebooks load raw with one line: `pd.read_parquet(cache_path("pbp", 2024))`.
- Reproducing a historical grade is `git checkout <sha>` + the parquet
  files; the database can be rebuilt from those two inputs alone.
- Postgres backups stay small (~tens of MB for the typed product) instead of
  carrying GBs of raw PBP we never query in SQL.
- If we ever need ad-hoc SQL over raw, DuckDB reads the parquet directly
  (`duckdb.sql("SELECT * FROM 'pipeline/.cache/raw/pbp/2024.parquet'")`).
  We don't have to commit to that now.

**Harder:**

- Raw isn't backed up automatically. **Acceptable:** raw is regenerable
  from `nfl_data_py` for any season we cover. The cost of a wiped cache is
  one slow re-ingest, not data loss.
- Two storage systems instead of one. **Acceptable:** the boundary is
  obvious — anything inside `ingest/cache_or_fetch(...)` reads/writes
  parquet, everything downstream reads from typed Postgres.
- Detecting upstream column renames isn't automatic. The manifest catches
  *fetched-with-different-version*; the schema-mapping code in `ingest/`
  catches *renamed-column* loudly when it tries to access the missing key.
  Both are acceptable failure modes — loud and early.

**Explicitly given up:**

- **Raw-in-DB convenience.** Some teams like being able to `psql` into a
  `raw_pbp` table mid-debug. We're a pandas pipeline; you'd open a notebook
  and `pd.read_parquet` instead. If this ever becomes painful, expose raw
  via a DuckDB-backed FDW or a thin `raw` schema — don't migrate the
  primary store.
- **Streaming ingest.** Parquet is batch-oriented. We have no streaming
  use case (NFL data lands once a week); revisit if that changes.

## Implementation notes (non-binding)

- `cache_or_fetch` lives in `nfl_grades.ingest._cache` and is the only
  module allowed to import `nfl_data_py`. Every concrete ingester
  (`ingest/pbp.py`, `ingest/rosters.py`, ...) calls it with its source key.
- The manifest is rewritten atomically (write to `manifest.json.tmp`,
  rename) so a Ctrl-C mid-update can't corrupt it.
- Parquet uses pyarrow with default compression (snappy). Don't override
  unless we hit a real size or speed problem.
- Cache invalidation policy: never automatic. Refresh is always an
  explicit CLI flag. We'd rather work on stale data than silently re-run
  ingest under a developer.
