# 0010 - Use nflreadpy (official nflverse) instead of nfl_data_py

- **Status**: Accepted
- **Date**: 2026-04-23
- **Supersedes**: implicit choice of `nfl_data_py` in earlier scaffolding

## Context

The original pipeline scaffolding picked `nfl_data_py` as the data-source
client (mentioned in `data-sources.md`, `pipeline/README.md`, and
`pyproject.toml`'s `[ingest]` extra). This was the de-facto standard for
Python access to nflverse data for several years.

Two things forced a re-evaluation:

1. **Python 3.13 incompatibility.** `nfl_data_py 0.3.3` (the latest release,
   shipped in early 2024) caps its dependencies at `numpy<2.0`. Our stack
   is Python 3.13 with `numpy>=2.1` (which is required for Python 3.13
   wheels — there are no `numpy<2` wheels for cp313). `pip install
   ".[ingest]"` fails with `ResolutionImpossible`.
2. **`nflreadpy` exists and is the official successor.** Released
   September 2025 by Tan Ho (nflverse maintainer), `nflreadpy` is a Python
   port of `nflreadr` (the canonical R package for nflverse data). It pulls
   from the same `nflverse-data` GitHub releases — the actual data source
   is identical.

Comparison:

| Aspect                   | `nfl_data_py 0.3.3`             | `nflreadpy 0.1.5`                          |
|--------------------------|---------------------------------|--------------------------------------------|
| Maintainer               | Cooper Adams (community)        | Tan Ho (nflverse core team)                |
| Last release             | Feb 2024                        | Nov 2025 (5 releases in 3 months)          |
| Python 3.13              | broken (`numpy<2` pin)          | supported, classifier present              |
| DataFrame backend        | pandas                          | polars (with `.to_pandas()` method)        |
| Data source              | nflverse-data releases          | nflverse-data releases (same)              |
| Caching                  | none                            | built-in (memory or filesystem)            |
| API surface              | `import_pbp_data`, `import_seasonal_rosters`, ... | `load_pbp`, `load_rosters`, ... |
| Coverage                 | PBP, NGS, rosters, snaps, etc. | PBP, NGS, rosters, snaps, FTN, contracts, draft, injuries, ... (superset) |

The "Beta" status warning on `nflreadpy` is real but the API mirrors
`nflreadr` exactly, so the contract is well-defined and the underlying
data files are the same we'd be reading either way.

## Decision

**Use `nflreadpy` for all nflverse data access.** Specifically:

- `pipeline/pyproject.toml` `[ingest]` extra: `nflreadpy>=0.1.5`,
  `polars>=1.0`, `pyarrow>=18.0`.
- All ingest modules (`ingest/pbp.py`, `ingest/rosters.py`, etc.) call
  `nflreadpy.load_*` functions.
- The `cache_or_fetch` helper from ADR 0009 wraps `nflreadpy` calls and
  converts polars → pandas at the boundary so the rest of the pipeline
  stays pandas-based (we have no reason to rewrite the math layer in
  polars yet).
- `nflreadpy`'s built-in cache is **disabled**
  (`NFLREADPY_CACHE=off`); we control caching ourselves via parquet files
  + manifest per ADR 0009. Two cache layers would be redundant and the
  manifest needs the raw network fetch to record correctly.
- Function-name mapping is documented in `docs/data-sources.md`
  (`import_pbp_data` → `load_pbp`, `import_seasonal_rosters` → `load_rosters`,
  etc.).

## Consequences

**Easier:**

- Python 3.13 just works. We keep the modern numpy/pandas/scipy stack
  without downgrading.
- We're tracking the same library as the R-side nflverse community uses,
  which means R-language docs and examples translate almost directly.
- Active development: bugs and data updates land in weeks, not years.
- Polars is faster than pandas for the kinds of bulk reads ingest does
  (10-50M PBP rows). Even though we convert to pandas, the read+parse step
  is faster.

**Harder:**

- We pull in `polars` (~50MB) and `pyarrow` (~30MB) at the ingest extra.
  Acceptable: ingest is a power-user/CI workload, not a thin import.
- Polars → pandas conversion at the ingest boundary is one extra `.to_pandas()`
  call. Effectively free (zero-copy via Arrow when possible).
- "Beta" library risk: API could shift between 0.x releases. Mitigated by
  pinning a minimum version and keeping the wrapper layer (`_cache`) thin
  enough that an API change is one-file fix.

**Explicitly given up:**

- `nfl_data_py` ecosystem familiarity. Function-name muscle memory needs
  retraining (`import_pbp_data` → `load_pbp`). Net cost: a doc table.
- Pandas-native reads. We could keep using pandas directly via
  `pd.read_parquet` on nflverse parquet URLs, but then we'd be
  re-implementing the discovery/versioning logic that `nflreadpy` already
  handles. Not worth it.

## What this changes in the repo

- `pipeline/pyproject.toml` `[ingest]` extra
- `docs/data-sources.md` — function-name mapping, `nflreadpy` references
- `pipeline/README.md` — replace `nfl_data_py` mentions
- `pipeline/src/nfl_grades/ingest/__init__.py` docstring
- `AGENTS.md` — convention #5 already cites ADR 0009; nothing to change
  beyond the data-source name
- `docs/adr/0009` — still correct (parquet caching strategy is
  source-agnostic); leave it alone

## What this does NOT change

- The grading methodology, schema, ADRs 0001–0008.
- ADR 0009's three-layer separation. Parquet on disk, manifest sidecar,
  typed Postgres — all independent of which Python client we use to fetch.
