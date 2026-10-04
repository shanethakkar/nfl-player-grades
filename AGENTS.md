# AGENTS.md

> **You're an AI agent working on this repo. Read this file first.** It tells
> you what the project is, where things live, what's already decided, and
> what's currently in progress so you don't redo work or fight the
> architecture.

## What this is

NFL Player Grades — a web app that grades every NFL player on a 0–100 scale
using advanced stats, with depth charts and per-season + career grades for
all 32 teams.

- Data: `nflreadpy` (PBP, NGS, rosters, depth charts, snaps, FTN charting, PFR advanced stats)
- Pipeline: Python (pandas, numpy, scipy, scikit-learn) -> Postgres
- Web: Next.js 15 App Router on Vercel, reads from Postgres
- Time range: 2016–present (NGS era)

## Where to read next

| If you want to know... | Read |
|---|---|
| **Why** the project is structured the way it is | `docs/adr/` (start with `README.md`) |
| **How** grades are computed | `docs/methodology.md` |
| **What** the database schema is | `db/migrations/0001_init.sql` and `docs/schema.md` |
| **Which** data sources are pulled and how | `docs/data-sources.md` |
| **What** the build order is | `README.md` (top-level) |

**The ADRs in `docs/adr/` are the source of truth for design decisions.** If
you're about to suggest a structural change, check there first — odds are it
was already considered.

## Current state (update when you make progress)

| Component | Status | Notes |
|---|---|---|
| Repo scaffolding | DONE | Monorepo with `pipeline/`, `web/`, `db/`, `docs/` |
| Database schema | DONE (migrations 0001–0027) | `db/migrations/` |
| Migration tooling | DONE | `nflgrades migrate [--seeds]` |
| TS type codegen | DONE | `nflgrades gen-types [--check]` |
| `pipeline/ingest/*` | DONE | One module per nflverse source, all through `ingest._cache` |
| `pipeline/grading/*` | DONE | Graders for QB, RB, WR, TE, CB, S, EDGE, iDL, LB, K, P, OL (team-level) and team grades (ADRs 0013–0026). All score through `grading.scoring` (ADR-0028) |
| Provisional grades | DONE | In-season grades "through week N", pro-rated thresholds (ADR-0031) |
| Weekly refresh | DONE | `nflgrades weekly --season N`; GitHub Actions schedule in `.github/workflows/weekly.yml` |
| `pipeline/components/*` | UNUSED | Graders compute Components inline |
| `pipeline/career/kalman.py` | STUB | `NotImplementedError` — build step 8 |
| `pipeline/validation/*` | STUB | Empty `__init__.py` only |
| `pipeline/adjust/*` | STUB | Empty `__init__.py` only — build step 7 |
| Web | DONE | Leaderboards, player and team pages, methodology, OG images |
| Season grades coverage | DONE | 2016–2025 completed for every position (OL, CB/S/EDGE/iDL/LB from 2018); in-progress season Provisional |
| Tests | PARTIAL | Grading + composite + scoring + some integration (`pipeline/tests/`). **Read `pipeline/tests/README.md` before running pytest**: DB tests hit Neon via root `.env`, and 7 known pre-existing failures are listed there |
| Env / tooling | DONE | `uv` system-wide; `pipeline/.venv` on Python 3.13; `uv sync --extra ingest --extra dev` clean; `.vscode/settings.json` pins the interpreter |
| Git | DONE | `main`, remote `origin` on GitHub |
| CI | PARTIAL | Weekly grading workflow only; no test CI yet |

## Conventions you must follow

### Python pipeline

1. **All env access goes through `nfl_grades.config.settings`.** Never read
   `os.environ` directly.
2. **All DB access goes through `nfl_grades.db.session()` or `get_engine()`.**
   No ad-hoc `create_engine` calls.
3. **Grading math is pure.** Modules under `grading/`, `career/`,
   `components/`, and `adjust/` take DataFrames and return DataFrames. They
   must not import from `db.py` or `ingest/`. This is enforced by ADR 0007.
4. **Every pipeline stage logs a row to `pipeline_runs`** (status `running` ->
   `ok`/`error`, with `rows_written`). The web app uses this for freshness.
5. **Raw downloads cache as parquet under `PIPELINE_CACHE_DIR/raw/{source}/{season}.parquet`**
   (gitignored). All `nflreadpy` calls go through `ingest._cache.cache_or_fetch`;
   never call `nflreadpy` directly from a transform or a notebook. Only
   typed tables live in Postgres — no `raw_*` tables. See ADR 0009.
6. **Use `from __future__ import annotations`** at the top of every module
   (already idiomatic in this repo).

7. **Refresh an in-progress season with `nflgrades weekly --season N`**, not
   individual `ingest` / `grade` commands. It downloads every source once,
   caps them at the last completed week, refuses to run if a source lags,
   and writes every grade in one transaction (ADR-0031). It runs every
   Wednesday in season on GitHub Actions against Neon; re-run it by hand
   from the Actions tab ("Weekly grades" → Run workflow).

### Database

1. **Migrations are forward-only.** To fix a bad migration, ship a new one.
   Once `0001` has been applied to any environment, never edit it. See ADR 0006.
2. **Schema lives in SQL, not in Python or TS.** No SQLAlchemy ORM models,
   no Drizzle/Prisma. See ADR 0001.
3. **Historical team abbreviations resolve through `team_aliases`.** Never
   hardcode `SD`, `OAK`, `STL` etc. anywhere outside the seed file. See
   ADR 0004.

### Web

1. **Server components by default.** Only mark `'use client'` when you need
   interactivity.
2. **All DB access goes through `web/src/lib/db.ts`** (the `sql` singleton).
3. **Types come from `web/src/types/index.ts`**, which curates the
   auto-generated `db.generated.ts`. If you change the schema, run
   `nflgrades gen-types` and update `index.ts` to match. See ADR 0005.
4. **Tailwind only for styling** in v1. No CSS-in-JS.

### When the schema changes

1. Add a new file `db/migrations/NNNN_what_changed.sql` (don't edit existing
   ones).
2. `nflgrades migrate`
3. `nflgrades gen-types`
4. Update `web/src/types/index.ts` to add/curate any new types.
5. Update `docs/schema.md`.

### When you make a non-trivial design choice

Write an ADR. Even if it's a one-paragraph "we picked X over Y because Z."
Future-you (and future-me) will thank present-you. Format: see
`docs/adr/README.md`.

## Things that are explicitly out of scope for v1

These were considered and deferred. **Do not implement them without first
re-reading the relevant ADR / methodology section.**

- Unit-level RAPM for opponent adjustment (we do team-level only)
- Hierarchical Bayesian model with proper per-stat likelihoods (we do
  empirical Bayes shrinkage)
- Role-based position classification (we use the listed position)
- Live in-season depth chart updates (we do end-of-season snapshots)
- Cross-position MVP-style ranking (grades are within-position only)
- Player comparison tool (UI feature deferred to v2)
- ORM (Drizzle, SQLAlchemy ORM models, Prisma) — see ADR 0001
- Auto-generated TS types as the source of truth (we use a guardrail
  pattern instead) — see ADR 0005
- Raw nflverse data persisted in Postgres tables (we cache as parquet on
  disk; only typed tables in DB) — see ADR 0009

## Tone for your responses

- This is a solo project. The user is technical. Be direct, no hedging.
- When asked "is this solid?", actually critique it. Sycophancy is worse
  than useless.
- Don't add CI / shadcn / connection pooling / monitoring / auth before
  they're needed. YAGNI.
- When you write code, follow the conventions above. When something feels
  off, check the ADRs before deviating.
