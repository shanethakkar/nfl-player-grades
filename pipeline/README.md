# Pipeline

Python package responsible for:

1. **Ingesting** raw data (PBP, rosters, NGS, depth charts, snaps, FTN charting) from `nflreadpy` into parquet cache, then into Postgres typed tables. See ADRs 0009 (caching) and 0010 (data client).
2. **Computing stat components** per position from raw data.
3. **Adjusting** for opponent quality (Tier 1 positions).
4. **Grading**: empirical Bayes shrinkage → z-scores → inverse-noise-weighted composite → sigmoid → 0–100.
5. **Career smoothing**: Kalman-style recency-weighted grade with uncertainty.
6. **Validating**: face validity, year-over-year reliability, predictive validity, external benchmarks.

## Setup

```bash
cd pipeline
python -m venv .venv
.venv/Scripts/activate          # Windows (PowerShell: .venv\Scripts\Activate.ps1)
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
```

## Layout

```
pipeline/
├── src/nfl_grades/
│   ├── config.py         # env-driven settings (Pydantic)
│   ├── db.py             # SQLAlchemy engine + session helpers
│   ├── ingest/           # nflreadpy → parquet cache → Postgres
│   ├── components/       # raw stats → per-position component values
│   ├── adjust/           # team-level opponent adjustment
│   ├── grading/          # empirical Bayes, z-scores, composite, sigmoid
│   ├── career/           # Kalman-style smoothing
│   ├── validation/       # face validity, YoY reliability, benchmarks
│   └── cli.py            # `nflgrades` command
├── scripts/              # orchestration entry points (ingest, grade, rebuild)
├── notebooks/            # EDA and tuning (gitignored .ipynb_checkpoints)
└── tests/                # pytest
```

## Common commands

```bash
# Run everything for a single season (useful during MVP dev)
nflgrades rebuild --season 2024

# Just ingest
nflgrades ingest --season 2024

# Just re-grade (assumes ingestion is up to date)
nflgrades grade --season 2024 --position QB

# Career grades (after season grades exist)
nflgrades career

# Validation suite
nflgrades validate --season 2024
```

## Testing

```bash
pytest
ruff check src tests
mypy src
```

## Conventions

- **Pure functions where possible.** Grading math should be testable without a DB.
- **DB I/O lives in `db.py` and the `ingest/` package.** Component and grading modules take DataFrames, return DataFrames.
- **Every pipeline stage writes a row to `pipeline_runs`** so we can see freshness and debug rebuilds.
- **Raw downloads cached under `PIPELINE_CACHE_DIR`** (gitignored) to avoid hammering nflverse.
