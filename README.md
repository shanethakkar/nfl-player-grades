# NFL Player Grades

A web app for browsing all 32 NFL teams, viewing depth charts and offensive/defensive starting lineups, and seeing every player graded on a 0–100 scale using advanced stats.

- **Per-season grades** from an empirical Bayes + sigmoid pipeline
- **Career grades** with uncertainty via Kalman-style recency weighting
- **Depth charts** (end-of-most-recent-regular-season snapshots)
- **Data-quality tiers** disclosed on every grade

## For AI agents and new contributors

**Read [`AGENTS.md`](./AGENTS.md) first.** It tells you what's built, what's
stubbed, and the conventions you must follow.

Design decisions live in [`docs/adr/`](./docs/adr/). Don't propose
structural changes without checking those first.

## Repository layout

```
nfl-player-grades/
├── AGENTS.md            # READ FIRST: project state + conventions
├── pipeline/            # Python: data ingestion + grading
├── db/                  # SQL migrations (source of truth for schema)
├── web/                 # Next.js App Router frontend + API routes
├── docs/
│   ├── adr/             # Architecture Decision Records
│   ├── methodology.md   # How grades are computed
│   ├── schema.md        # Entity diagram + read/write paths
│   └── data-sources.md  # Which nfl_data_py functions feed what
├── docker-compose.yml
└── .env.example
```

See each subdirectory's `README.md` for details.

## Quickstart

1. **Configure env**

   ```bash
   cp .env.example .env
   ```

2. **Start local Postgres**

   ```bash
   docker compose up -d db
   ```

3. **Set up the Python pipeline**

   ```bash
   cd pipeline
   python -m venv .venv
   .venv\Scripts\Activate.ps1        # Windows PowerShell
   # source .venv/bin/activate       # macOS / Linux
   pip install -e ".[dev]"
   ```

4. **Apply schema migrations + seeds**

   ```bash
   nflgrades migrate --seeds
   ```

5. **Generate web types from the live DB**

   ```bash
   nflgrades gen-types
   ```

6. **Run the web app**

   ```bash
   cd ../web
   cp .env.local.example .env.local
   npm install
   npm run dev
   ```

   Visit <http://localhost:3000>.

## Build order

| Step | Goal | Status |
|------|------|--------|
| 1 | Ingest 2024 + 2025 seasons end-to-end → Postgres, totals match nflverse | not started |
| 2 | Grade QBs only, tune until top-10 passes the eye test | not started |
| 3 | Extend grading to all Tier 1 positions (RB, WR, TE) | not started |
| 4 | Minimal Next.js app: team list → team page → player page | scaffolded |
| 5 | Tier 2 positions (CB, S, EDGE) with data-quality badges | not started |
| 6 | Historical seasons 2016–2023 | not started |
| 7 | Team-level opponent adjustment for Tier 1 | not started |
| 8 | Career grades (Kalman-style smoothing) | not started |
| 9 | Tier 3 positions (OL, iDL, off-ball LB, ST) with proxy stats | not started |
| 10 | Polish: depth chart viz, methodology page, comparisons | not started |

Keep this table in sync with `AGENTS.md`'s status table.

## CLI reference

```bash
nflgrades migrate [--seeds] [--dry-run]    # apply pending DB migrations
nflgrades gen-types [--check]              # write web/src/types/db.generated.ts
nflgrades ingest --season 2024             # pull data from nfl_data_py
nflgrades grade --season 2024 [--position QB]
nflgrades career                           # smooth season grades into career grades
nflgrades validate --season 2024           # face validity / YoY / benchmarks
nflgrades rebuild --season 2024            # ingest + grade + validate
```

## License

TBD.
