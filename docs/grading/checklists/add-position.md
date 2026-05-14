# Adding a New Graded Position — Full Checklist

Derived from CB (ADR-0018) and Safety (ADR-0019) implementations.
Position code below is a placeholder — substitute the real code (e.g. "LB", "EDGE").

---

## 1. DB Migration

Create `db/migrations/00NN_<position>_coverage.sql`:
- Table: `pfr_def_coverage_<pos>` (or similar; grain = player_id + season)
- Include an index on `season`
- Wrap in `BEGIN; ... COMMIT;`

Run against Neon:
```
$env:DATABASE_URL = "<neon url>"; nflgrades migrate
```

Neon URL lives in `web/.env.local` → `DATABASE_URL` (the pooled one).
**Always set DATABASE_URL before importing nfl_grades.db or the local Docker engine is used.**

---

## 2. Pipeline: weights.py

Add to `pipeline/src/nfl_grades/grading/weights.py`:
- Component name constants: `POS_COMPONENT_X: str = "pos_x"`
- `POS_V1_WEIGHTS: dict[str, float]` — sum of |abs| values is the normalization denominator; don't need to sum to 1.0
- `POS_V1_SHRINKAGE_K: dict[str, float]` — "equivalent pseudo-sample" for EB shrinkage
- `POS_V1_RAW_VALUE_COLS: dict[str, str]` — component → feature column name in DataFrame
- `POS_V1_SAMPLE_SIZE_COLS: dict[str, str]` — component → n-column in DataFrame
- Qualification thresholds: `POS_V1_MIN_X_TO_GRADE`, `POS_V1_QUALIFIED_MIN_X`, `POS_V1_CONFIDENCE_FULL_X`

---

## 3. Pipeline: ingest module

Create `pipeline/src/nfl_grades/ingest/pfr_<pos>.py` (or add to pfr.py if very similar to CB):
- `PFR_DEF_COVERAGE_<POS>_MIN_SEASON = 2018`
- `run(season, refresh=False) → RunResult` — idempotent DELETE+INSERT
- Position filter against `players.position` (canonical values: QB/RB/WR/TE/OL/iDL/EDGE/LB/CB/S/K/P/LS)
- Use `cache_or_fetch("pfr_advstats_def", season)` for PFR coverage data
- Use `cache_or_fetch("nflvs_player_stats", season)` for nflverse stats (PBU, tackles, etc.)
- Player linkage: `pfr_id → (player_id, position, gsis_id)` from players table
- For nflverse: aggregate by `gsis_id` (nflverse uses gsis as `player_id` column)
- **Delete pattern**: `DELETE FROM <table> WHERE season = :season` (whole-season replace)

No need to add a new `SourceName` to `_cache.py` — `pfr_advstats_def` and `nflvs_player_stats` already registered and cover both CB and Safety use cases.

---

## 4. Pipeline: grading module

Create `pipeline/src/nfl_grades/grading/<pos>.py`:
- `POSITION = "POS"` constant
- `run(season) → RunResult` — guards on MIN_SEASON, calls extract/compute/write
- `extract_features(conn, season) → pd.DataFrame` — SQL pulls from the ingest table + player_seasons for snaps_defense
  - Compute all rate columns in Python (not SQL)
  - Coerce int/float columns carefully (fillna(0) for count cols, Float64 for nullable floats)
- `compute_grades(features) → pd.DataFrame` — shrink → zscore → NaN neutralize (fillna(0.0)) → composite → sigmoid → percentile
- `write_results(conn, graded, season) → (n_components, n_grades)`
  - **DELETE pattern**: `component_name LIKE 'pos_%'` — NOT `= ANY(:components)`. Using a prefix LIKE prevents orphaned rows if the formula changes between runs.
  - `role = None` if no role classification for this position

---

## 5. Pipeline: run.py + cli.py

In `pipeline/src/nfl_grades/grading/run.py`:
- Import the new grading module
- Add `"POS": pos_module.run` to `POSITION_RUNNERS`
- Add `pos_module.RunResult` to the `PositionRunResult` union type

In `pipeline/src/nfl_grades/cli.py`:
- Add `@ingest.command(name="pfr-def-coverage-pos")` command
- Add to `ingest all` command (inside `if season >= 2018:` block if PFR-limited)
- Update `grade` command's `--position` help string to include new position
- Update `_TOTAL_ATTRS` and `_QUAL_ATTRS` tuples in grade command to include `n_<pos>s_total` / `n_<pos>s_qualified`

---

## 6. Web: types/index.ts

Add position-specific fields to `LeaderboardEntry`:
```ts
// --- POS columns ---
n_<metric>: number | null;
pos_component_1: number | null;
pos_component_2: number | null;
```

Update the JSDoc comment above `LeaderboardEntry` to list the new position.

---

## 7. Web: lib/grades.ts

- Add entries to `COMPONENT_FORMATS` for each `pos_*` component (label, suffix, formatValue, description, sampleNoun)
- Add entries to `COMPONENT_WEIGHTS` for each `pos_*` component
- Add role label helpers if the position has roles (e.g. `POS_ROLE_LABELS`, `posRoleLabel()`)

After adding the weights to weights.py, run `python pipeline/scripts/sync_weights_to_web.py` to push them into the AUTOGEN block of grades.ts.

---

## 8. Web: lib/queries.ts

Add `if (position === "POS")` branch in `_getLeaderboard()`:
- SELECT the headline stat columns (3-4 components + a sample-size column)
- For **offensive** positions: use `${teamLookupLateralForSgP}` LATERAL join (works via plays table passer/rusher/receiver IDs)
- For **defensive** positions: use `LEFT JOIN player_seasons ps ... LEFT JOIN teams t ON t.team_id = ps.team_id` (offensive players don't appear in plays as defenders)
- Add new fields to `coerceLeaderboardEntry()` at bottom of file

---

## 9. Web: components/LeaderboardTable.tsx

Add `const POS_COLUMNS: SortableColumn[]` array with 3-4 headline columns, then add `POS: POS_COLUMNS` to `COLUMN_SPECS`.

---

## 10. Web: app/page.tsx  ← EASY TO FORGET

**This is the most commonly missed step.** The homepage has hardcoded data structures that must all be updated:

```ts
const POSITION_ORDER: readonly string[] = ["QB", "RB", "WR", "TE", "CB", "S", ...];
```

Also update:
- `COMPOSITE_BLURB` — one-liner describing the formula
- `LOW_VOLUME_COPY` — heading + threshold text for the collapsed section
- `QUALIFIED_NOUN` — singular/plural noun (e.g. "qualified safety" / "qualified safeties")

Without updating `POSITION_ORDER`, the tab will never appear even if the data is in the DB.

---

## 11. Web: app/methodology/page.tsx

- Add to `POSITION_COMPONENTS` record: component entries with weights
- Add `sTop = getCurrentTopAtPosition("POS")` to `Promise.all()`
- Add entry to `positions` array with `availabilityNote`
- Add `"POS"` to `PositionCardData` union type

---

## 12. ADR

Create `docs/adr/00NN-pos-v1-grading-formula.md` covering:
- Data sources + why
- Component table (name / weight / direction / rationale)
- Qualification thresholds and why
- Shrinkage k rationale per component
- NaN handling (known null sources)
- Alternatives considered

---

## 13. Run the Pipeline

```powershell
$env:DATABASE_URL = "<neon url from web/.env.local>"
Set-Location pipeline

# Ingest
foreach ($s in 2018..2025) { nflgrades ingest pfr-def-coverage-pos --season $s }

# Grade
foreach ($s in 2018..2025) { nflgrades grade --season $s --position POS }

# Optional: backfill team context if offensive position
# nflgrades backfill-team-context --season $s
```

Sanity check: query top 10 qualified players for the most recent season and verify they are recognizable names at the right tier.

---

## Key Gotchas

- **`POSITION_ORDER` in `page.tsx`** — the tab will silently disappear if the position isn't in this array (the `filter()` call strips it)
- **Delete pattern (CRITICAL when removing components)**: graders MUST use `component_name LIKE 'pos_%'` in `_DELETE_STAT_COMPONENTS`, NOT `= ANY(:components)`. See [../checklists/removing-a-component.md](removing-a-component.md) for the full workflow.
- **DATABASE_URL must be set BEFORE any Python import of nfl_grades.db** — the engine is cached at import time; setting it after won't help. Use the CLI (sets env before Python starts) rather than inline `os.environ` scripts.
- **Neon URL**: pooled endpoint in `web/.env.local` → `DATABASE_URL`; direct (non-pooled) for migrations is same host with `-pooler` removed from hostname
- **Defensive team lookup**: don't use the `teamLookupLateralForSgP` LATERAL (it only finds players who appear as passer/rusher/receiver in plays). Use `player_seasons → teams` join instead.
- **nflverse position codes**: in `nflvs_player_stats`, safety positions may appear as "SS", "FS", "S", or "DB". Don't filter by position in the nflverse aggregate — rely on our players table join instead.
- **Missed tackle / PFR tackling columns**: `pfr_advstats_def` includes missed tackle counts (confirmed present 2018-2025). Try multiple column name variants and log gracefully if none found.
- **TypeScript after adding fields**: run `npx tsc --noEmit` before restarting the dev server to catch missing fields in types or coerce functions early.
- **Mixed-case position codes (iDL)**: position codes that aren't all-uppercase (like `iDL`) break two things by default. (1) `pipeline/grading/run.py` does `position.upper()` — fixed to try exact match first, then case-insensitive fallback. (2) `web/app/page.tsx` does `firstOf(positionParam)?.toUpperCase()` for URL params — also needs case-insensitive `find()` against `POSITION_ORDER` that returns the canonical mixed-case form. Both must match the canonical casing (e.g. `"iDL"`) or the tab silently falls back to QB.
