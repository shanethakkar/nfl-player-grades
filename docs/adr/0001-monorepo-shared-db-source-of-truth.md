# 0001 - Monorepo with shared `db/` as schema source of truth

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

This project has two distinct codebases:

- A **Python pipeline** that ingests data from `nfl_data_py` and writes
  per-season + career grades to Postgres.
- A **Next.js web app** that reads from Postgres and renders teams, depth
  charts, and grades.

Both touch the same database schema. We considered:

1. **Two repos** (pipeline + web), each with its own copy of the schema.
2. **Monorepo** with a shared `db/` directory holding SQL migrations.
3. **Schema-first ORM** (Drizzle in TS, then introspect from Python; or
   SQLAlchemy in Python with TS clients consuming an OpenAPI spec).

## Decision

**Monorepo. SQL migrations in `db/migrations/` are the single source of
truth.** Both Python and TypeScript follow that schema; neither owns it.

The TS side gets type safety via `nflgrades gen-types`, which introspects
the live DB and emits `web/src/types/db.generated.ts`. The Python side uses
raw SQL + pandas (no ORM models — see ADR 0002).

## Consequences

**Easier:**
- One PR can include a schema change + the pipeline change that uses it +
  the web change that displays it. No cross-repo coordination.
- New contributors (and AI agents) see the whole system in one tree.
- `docker compose up -d` brings up Postgres with migrations auto-applied,
  giving both halves a working environment instantly.

**Harder:**
- Repo grows two ecosystems' worth of tooling (npm + pip). Mitigated by
  keeping each in its own directory with its own README.
- Can't independently version the two halves. We don't need to.

**Explicitly given up:**
- Schema-first ORMs (Drizzle, Prisma) where the ORM file generates
  migrations. They'd push us to TS-first thinking, which is wrong here:
  the data pipeline is the primary writer and the analyst-friendly layer.
  See ADR 0002.
