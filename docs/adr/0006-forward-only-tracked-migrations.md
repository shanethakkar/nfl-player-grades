# 0006 - Forward-only migrations with `schema_migrations` tracking

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

We need a migration story. Options:

1. **Alembic.** Standard for SQLAlchemy projects. Auto-generation from ORM
   models. We have no ORM models (ADR 0002), so the auto-generation isn't
   useful.
2. **Raw `psql -f` per file**, no tracking. Simple but easy to apply the
   same migration twice or skip one.
3. **A tiny custom runner** that tracks applied migrations in a
   `schema_migrations` table and refuses to re-apply or run modified files.

## Decision

**Option 3.** `pipeline/src/nfl_grades/migrate.py` (~80 lines) does:

- Creates `schema_migrations(filename PRIMARY KEY, sha256, applied_at)` if
  it doesn't exist.
- Lists `db/migrations/*.sql` lexically.
- For each file: skip if applied with matching sha; error if applied with
  *different* sha (someone edited an applied migration); apply otherwise.
- Each migration runs in its own transaction.
- Optional `--seeds` flag also runs `db/seeds/*.sql` (idempotent, re-runs
  every time).

Migrations are **forward-only**. To fix a bad migration, ship a new one
(`0007_fix_bad_constraint.sql`).

## Consequences

**Easier:**
- Deploying to Supabase/Neon is `nflgrades migrate`. Same code as local.
- New developers' first command is obvious and safe.
- Sha tracking catches "I edited an applied migration" mistakes loudly
  instead of silently going out of sync.

**Harder:**
- No down migrations. Acceptable: in 6 years of running this kind of
  pipeline, down migrations are almost always the wrong tool — you ship a
  forward fix instead.
- No model -> migration auto-generation. We don't want it; we'd rather
  hand-write SQL and review it.

**Explicitly given up:**
- Alembic ecosystem (branching, multiple heads, etc.). We have one head
  and we ship to it. If this ever stops being true, revisit.

## Edge cases

- `0001_init.sql` is currently editable because nothing has been applied
  anywhere yet. **The moment it's applied to any environment, it becomes
  immutable.**
- The `schema_migrations` table is not itself in a migration file — the
  migration runner creates it on first invocation. That's intentional;
  bootstrapping a tracking table inside a tracked migration is a chicken-
  and-egg problem we don't need.
