# Database schema

Source of truth: `db/migrations/0001_init.sql` and **forward** migrations
(e.g. `0006_*.sql` for `role`, `data_tier_reason`, `used_in_composite`). This
doc summarizes the shape and relationships; read the SQL for exact types and indexes.

- **`season_grades`**: `role` (TEXT, app convention — TE uses `receiving_te` /
  `balanced_te` / `blocking_te`; `NULL` for other positions);
  `data_tier_reason` (TEXT, nullable — e.g. `era_pre_ngs`, `role_blocking_te`,
  `era_and_role`); `through_week` (SMALLINT, nullable, migration 0026) — the
  last regular-season week a Provisional grade covers; `NULL` for a completed
  season (ADR-0031).
- **`team_grades`**, **`team_ol_grades`**: `through_week` (SMALLINT, nullable,
  migration 0027), as on `season_grades`. `team_grades.st_grade` / `st_z` are
  nullable: early in a season no kicker or punter has qualified, and Overall
  renormalizes over Offense and Defense (ADR-0031).
- **`stat_components`**: `used_in_composite` (boolean, default true) — false when
  a component was stored for audit/debug but omitted from the headline composite
  (e.g. TE `te_target_earn_rate` for `blocking_te` rows; ADR-0016).

## Entities

```
teams (32 rows, seeded)
  |
  +-- players (current_team_id FK)
        |
        +-- player_seasons (one per player/season/team)
        +-- depth_charts (positional depth per team/season/week)
        +-- stat_components (per component per season)
        +-- season_grades (final per-position per-season grade)
        +-- career_grades (Kalman-smoothed, one per player per as_of_date)
```

## Write paths

| Table            | Writer                                 | Cadence                |
|------------------|----------------------------------------|------------------------|
| `teams`          | `db/seeds/teams.sql`                   | once                   |
| `players`        | `pipeline/ingest/rosters.py`           | per season             |
| `player_seasons` | `pipeline/ingest/rosters.py`           | per season             |
| `depth_charts`   | `pipeline/ingest/depth_charts.py`      | per season             |
| `stat_components`| `pipeline/components/<position>.py`    | per season per position|
| `season_grades`  | `pipeline/grading/`                    | per season per position|
| `career_grades`  | `pipeline/career/kalman.py`            | after season_grades    |
| `pipeline_runs`  | all pipeline stages                    | on every run           |

## Read paths (web)

- `GET /api/teams` -> `teams`
- `GET /api/teams/:abbr` -> `teams` + `player_seasons` (current season roster)
- `GET /api/teams/:abbr/depth-chart` -> `depth_charts` + `players` + latest `season_grades`
- `GET /api/players/:id` -> `players` + all `season_grades` + latest `career_grades`

## Migration conventions

See `db/README.md`. Forward-only, zero-padded sequence, idempotent where
practical.
