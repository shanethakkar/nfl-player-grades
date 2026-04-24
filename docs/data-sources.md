# Data sources

All data flows through [`nflreadpy`](https://github.com/nflverse/nflreadpy),
the official nflverse-maintained Python client (Python port of `nflreadr`).
See [ADR 0010](./adr/0010-use-nflreadpy-not-nfl-data-py.md) for the rationale
on choosing it over `nfl_data_py`.

`nflreadpy` returns Polars DataFrames. The `cache_or_fetch` helper
(see ADR 0009) calls `.to_pandas()` at the boundary so the rest of the
pipeline stays pandas-native.

## What we pull

| Source              | `nflreadpy` function           | Used for                               |
|---------------------|--------------------------------|----------------------------------------|
| Play-by-play        | `load_pbp`                     | EPA, WP, garbage-time filter, QB/RB/WR components, team quality |
| Rosters (season)    | `load_rosters`                 | `players`, `player_seasons`            |
| Rosters (weekly)    | `load_rosters_weekly`          | Team-of-record for traded players      |
| Depth charts        | `load_depth_charts`            | `depth_charts`                         |
| NGS                 | `load_nextgen_stats(stat_type=...)` | QB / RB / WR/TE components        |
| Snap counts         | `load_snap_counts`             | `player_seasons.snaps_*`               |
| Participation / FTN | `load_ftn_charting`            | Personnel groupings, alignment (future)|
| Players (master)    | `load_players`                 | Stable IDs, draft info, biographical   |
| Schedules           | `load_schedules`               | Opponent + game context for adjustment |

`nflreadpy` is a superset of `nfl_data_py`'s coverage; if you need
something not listed above (contracts, injuries, draft picks, officials,
combine), check `import nflreadpy as nfl; help(nfl)` first.

### Function-name mapping (for anyone with `nfl_data_py` muscle memory)

| Old (`nfl_data_py`)        | New (`nflreadpy`)                     |
|----------------------------|---------------------------------------|
| `import_pbp_data`          | `load_pbp`                            |
| `import_seasonal_rosters`  | `load_rosters`                        |
| `import_weekly_rosters`    | `load_rosters_weekly`                 |
| `import_depth_charts`      | `load_depth_charts`                   |
| `import_ngs_data(stat)`    | `load_nextgen_stats(stat_type=stat)`  |
| `import_snap_counts`       | `load_snap_counts`                    |
| `import_seasonal_pfr`      | (no direct equivalent — PFR scrapes are out for now; use NGS+FTN) |
| `import_ftn_data`          | `load_ftn_charting`                   |

## Rate limiting / caching

`nflreadpy` hits GitHub releases on `nflverse-data`; no API key required but
be polite. We disable `nflreadpy`'s built-in cache (`NFLREADPY_CACHE=off`)
and run our own parquet cache + manifest under `PIPELINE_CACHE_DIR/raw/`
per ADR 0009. To force a refresh, use `nflgrades ingest <source> --refresh`
(or delete the parquet file).

## What we compute, not pull

- **Team-level efficiency** (DVOA-style offense/defense ratings) is computed
  from PBP inside the pipeline, not pulled. Keeps the methodology fully
  reproducible.
- **Opponent adjustments** applied to components are computed from the
  team-level ratings above.

## Reference data

- **Team IDs:** our internal `team_id` is a surrogate. Join to nflverse via
  `teams.abbr`. Historical relocations (OAK -> LV, SD -> LAC, STL -> LA) are
  mapped in ingestion to the current abbreviation via `team_aliases`
  (see ADR 0004).
- **Player IDs:** `players.gsis_id` is the canonical join key to nflverse
  data. We keep a surrogate `player_id` for our own FKs.
