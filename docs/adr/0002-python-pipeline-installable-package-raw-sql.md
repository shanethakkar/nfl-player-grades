# 0002 - Python pipeline as installable package + raw SQL

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

The Python side has to:

- Pull large DataFrames from `nfl_data_py`
- Compute statistical components and grades on those DataFrames
- Bulk-write results to Postgres

Two architectural questions:

1. **Loose scripts** in `scripts/` versus an **installable package** with a
   CLI entry point.
2. **SQLAlchemy ORM models** versus **raw SQL + pandas `to_sql`**.

## Decision

**Installable package.** `pipeline/` has a `pyproject.toml` defining the
`nfl_grades` package. After `pip install -e ".[dev]"`, the user gets:

- `from nfl_grades.grading import sigmoid` works from anywhere
- `nflgrades` CLI command (defined in `nfl_grades.cli:main`)
- Tests can `import nfl_grades` without path hacks
- The package can be reused from notebooks, CI jobs, and scheduled runs

**Raw SQL + pandas.** No `Base = declarative_base()`, no `class Player(Base)`.
Pipeline code uses:

- `pandas.read_sql` / `df.to_sql` for bulk reads/writes
- `sqlalchemy.text("...")` + the engine from `nfl_grades.db` for one-off
  statements
- `nfl_grades.db.session()` context manager for transactional work

## Consequences

**Easier:**
- The CLI gives us one obvious entry point per stage (`nflgrades ingest`,
  `nflgrades grade`, etc.) instead of a sprawl of `python scripts/*.py`.
- Bulk DataFrame writes via `to_sql` are 10-100x faster than ORM `add_all`
  for the row counts we deal with (tens of millions of PBP rows).
- Schema lives in SQL only (ADR 0001). No risk of "ORM model says X, DB
  says Y" drift.

**Harder:**
- No automatic relationship traversal (`player.seasons[0].grades`). We don't
  need it — every analytical query is a SQL JOIN.
- No Alembic auto-generation from models. We use a tiny custom migration
  runner instead — see ADR 0006.

**Explicitly given up:**
- ORM ergonomics. We're a data-analysis pipeline, not a CRUD app.
