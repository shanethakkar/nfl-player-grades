# Database

Postgres is the single source of truth for data. The Python pipeline writes to it; the Next.js app reads from it.

## Layout

```
db/
├── migrations/   # Versioned SQL, applied in lexical order
└── seeds/        # Static reference data (teams, divisions)
```

## Conventions

- **One migration per logical change.** Name them `NNNN_description.sql` where `NNNN` is a zero-padded sequence.
- **Forward-only.** No down migrations in v1; if a migration is wrong, ship a new one that fixes it.
- **Idempotent where practical** (`CREATE TABLE IF NOT EXISTS`, etc.) so re-running against an existing DB is safe during development.
- **Seeds are separate and ordered.** Schema changes go in `migrations/`, data goes in `seeds/`. Seed files are applied in lexical order, so prefix with `NN_` when one seed depends on another (e.g. `01_teams.sql` must run before `02_team_aliases.sql`).

## Applying migrations locally

```bash
# Against the docker-compose Postgres
psql "$DATABASE_URL" -f db/migrations/0001_init.sql
psql "$DATABASE_URL" -f db/seeds/teams.sql
```

With docker-compose, anything in `db/migrations/` is auto-applied on first container start via the Postgres entrypoint.

## Production

Apply the same migration files against Supabase/Neon using `psql` or their web SQL editor. Track applied migrations in a simple table (to be added when we need it — overkill for solo dev right now).
