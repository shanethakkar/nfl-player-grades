# Architecture Decision Records

Each ADR captures one significant decision: why we faced it, what we picked,
and what trade-offs we accepted. Append-only, numbered. Don't edit accepted
ADRs in place — supersede them with a new one.

## Format

We use a stripped-down Michael Nygard template:

```markdown
# NNNN - Short title in imperative mood

- **Status**: Accepted | Superseded by NNNN | Deprecated
- **Date**: YYYY-MM-DD

## Context
What's the situation that forced a decision? What constraints matter?

## Decision
What did we pick? Be specific.

## Consequences
Trade-offs we accepted. What gets harder, what gets easier, what we've
explicitly given up.
```

## When to write one

- Picking between two reasonable options where the loser would have been fine
- Choosing not to use a popular tool or pattern (Drizzle, ORM, etc.)
- Setting a convention you'll want to point at when someone questions it
- Anything you'd be annoyed to re-litigate in 6 months

If a decision is one line and obvious ("we use TypeScript"), don't write an
ADR. If it took more than 5 minutes of thought, write one.

## Index

| #    | Title                                                         | Status   |
|------|---------------------------------------------------------------|----------|
| 0001 | Monorepo with shared `db/` as schema source of truth          | Accepted |
| 0002 | Python pipeline as installable package + raw SQL              | Accepted |
| 0003 | Data tier and `qualified` flag as first-class columns         | Accepted |
| 0004 | Normalize historical team abbreviations to current            | Accepted |
| 0005 | Hand-written TS types with codegen guardrail                  | Accepted |
| 0006 | Forward-only migrations with `schema_migrations` tracking     | Accepted |
| 0007 | Pure-function grading math, DB I/O isolated to `ingest/`      | Accepted |
| 0008 | Sigmoid grade mapping with k=1.15, z=0->50, z=+2->90          | Accepted |
| 0009 | Raw nflverse data cached as parquet; typed-only in Postgres   | Accepted |
| 0010 | Use `nflreadpy` (official nflverse) instead of `nfl_data_py`  | Accepted |
| 0011 | Store a thin `plays` table in Postgres, not full PBP fat   | Accepted |
| 0012 | Store NGS as three tables, not one unified fact table         | Accepted |
| 0013 | QB v1 grading formula                                        | Accepted |
| 0014 | RB v1 grading formula                                        | Accepted |
| 0015 | WR v1 grading formula                                        | Accepted |
| 0016 | TE v1 grading formula                                        | Accepted |
| 0017 | v1 face-check: offense-context contamination in high-volume receivers | Accepted |
