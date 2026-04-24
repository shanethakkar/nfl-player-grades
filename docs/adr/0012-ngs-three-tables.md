# 0012 - Store NGS as three tables, not one unified fact table

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

Next Gen Stats (NGS) arrives via `nflreadpy.load_nextgen_stats(stat_type=...)`
in three flavors:

- **passing** (29 cols): `avg_time_to_throw`, `aggressiveness`,
  `completion_percentage_above_expectation` (NGS's CPOE),
  `avg_air_yards_to_sticks`, plus derived efficiency numbers.
- **rushing** (22 cols): `rush_yards_over_expected_per_att`,
  `efficiency`, `percent_attempts_gte_eight_defenders`,
  `avg_time_to_los`.
- **receiving** (23 cols): `avg_separation`, `avg_cushion`,
  `avg_yac_above_expectation`, `percent_share_of_intended_air_yards`.

Column overlap across the three: only the keys
(`player_gsis_id`, `season`, `season_type`, `week`, `team_abbr`) and the
"display" fields we drop. **Zero substantive stat overlap.**

NGS coverage: **2016 → present**. Earlier seasons have no NGS data at
all.

Options:

1. **Three tables**: `ngs_passing`, `ngs_rushing`, `ngs_receiving`,
   each with its native columns.
2. **One unified `ngs_stats(player_id, season, week, component_name, value)`
   EAV table**: normalizes across stat types.
3. **One wide table** with all 29+22+23 columns, most nullable.

## Decision

**Option 1.** Three tables, each holding its source columns verbatim
(minus display dupes like `player_first_name`). Feature extraction joins
whichever table the position needs.

## Rationale

- **Column overlap is zero.** An EAV table would force every query to
  filter by `component_name`, losing type safety and pushing schema into
  strings. No analytic win.
- **Query shape matches the storage shape.** QB grading reads one row
  per passer from `ngs_passing`. RB reads one row from `ngs_rushing`.
  Not joining across stat types — no benefit to unifying them.
- **Size is trivial.** ~600 QB-season-weeks + ~600 RB-season-weeks +
  ~1400 WR/TE-season-weeks × 10 seasons × ~74 columns total = well
  under 100 MB. Three tables don't hurt.
- **Rejected Option 3 (wide table)**: half the row would be nulls for
  any given position. Ugly, misleading query surface, same storage win
  as Option 1 once you exclude nulls.

## Grain and keys

Each table: one row per **(player, season, season_type, week, team)**.

- `week = 0` is the **season summary** row (nflverse convention). The
  grading pipeline reads `WHERE week = 0` for per-season metrics.
- `week > 0` preserved for future weekly UI / trend charts.
- `season_type` is kept because NGS includes postseason rows
  (weeks 19, 20, 21, 23 on the nflverse week axis).
- `team_id` is part of the PK because a player traded mid-season
  gets separate NGS rows per team (the season-summary row too — each
  team segment gets its own summary).

## Team normalization

`team_abbr` in the source is the **contemporary** abbreviation (`LAR`,
`LAC`, `LV`, etc.). We resolve via `team_aliases` at ingest time to
get `team_id`, same as every other ingest. See ADR-0004.

## Player mapping

`player_gsis_id` in NGS is the nflverse gsis id, which we already use
as the canonical identifier on `players.gsis_id`. No name matching
required.

## Minimum season

`season >= 2016` is enforced in ingest. Earlier seasons have no NGS;
the grading pipeline handles their absence via `data_tier` (ADR-0003).

## What we store

Every NGS-specific column, verbatim. No pruning — NGS is small and
future formula variants may want `max_air_distance` or
`percent_attempts_gte_eight_defenders` even if v1 doesn't.

We drop: `player_first_name`, `player_last_name`, `player_display_name`,
`player_short_name`, `player_position`, `player_jersey_number`. All
already available on `players` / `player_seasons` / depth charts.

## Consequences

**Good:**
- Natural query shape: `SELECT * FROM ngs_passing WHERE week=0 AND season=2024`.
- Adding new NGS columns (if nflverse exposes them) is a single
  `ALTER TABLE` per affected stat type — no EAV-row-count explosion.
- Type-safe columns in generated TypeScript.

**Trade-offs:**
- Three ingest code paths (shared via a dispatcher — see `ingest/ngs.py`).
- Adding a new stat type (hypothetical `ngs_defense`) is a new migration
  rather than "just insert rows".

## References

- ADR-0003 — `data_tier` for missing historical coverage
- ADR-0004 — team abbr normalization
- `docs/exploration/2026-04-23-ngs.md` (when populated) — schema probe
