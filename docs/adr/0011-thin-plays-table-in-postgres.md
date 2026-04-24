# 0011 - Store a thin `plays` table in Postgres, not the full PBP fat table

- **Status**: Accepted
- **Date**: 2026-04-23

## Context

The nflverse PBP feed (`nflreadpy.load_pbp`) returns ~49,500 rows × **372
columns** per season. It's the input to every grading formula. ADR-0009
already decided that raw source data lives as Parquet on disk, with only
typed queryable tables in Postgres. The question now is what shape the
Postgres-side plays table takes.

Three options:

1. **No plays in Postgres.** Grading reads Parquet each run. Web app
   can never drill into individual plays.
2. **Thin plays table** — ~40 columns we actually use: identifiers,
   situation, classification, player attribution, outcomes.
3. **Fat plays table** — store all 372 columns.

## Decision

**Option 2.** Create a `plays` table with ~40 curated columns, documented
below. The full 372-column Parquet remains the source of truth on disk
(`pipeline/.cache/raw/pbp/<season>.parquet`), and any analysis that needs
columns not in the table can re-read the Parquet directly.

## Column selection

Columns chosen for one of four reasons:

1. **Required by the v1 grading formula** (QB composite: EPA/db, CPOE,
   success rate + garbage-time filter).
2. **Required by likely v1.x grading expansions** (RB RYOE context, WR
   separation context, defensive attribution).
3. **Required by UI drill-down** ("top 10 EPA plays for player X").
4. **Cheap to keep** and likely needed soon (penalty, air_yards, yac).

Everything else — Elias IDs, no_huddle flags, yardline strings, 200+
tracking-derived columns — stays in Parquet only.

## Columns

See `db/migrations/0003_create_plays.sql` for the authoritative schema.
Summary:

| group | columns |
|---|---|
| identifiers (PK) | `game_id`, `play_id` |
| game context | `season`, `season_type`, `week`, `game_date` |
| teams (text abbrs, not FK) | `posteam`, `defteam`, `home_team`, `away_team` |
| situational | `qtr`, `down`, `ydstogo`, `yardline_100`, `score_differential`, `game_seconds_remaining`, `half_seconds_remaining`, `wp` |
| classification | `play_type`, `qb_dropback`, `pass_attempt`, `rush_attempt`, `sack`, `qb_scramble`, `qb_spike`, `qb_kneel`, `aborted_play`, `two_point_attempt`, `penalty` |
| player attribution (gsis_id text) | `passer_player_id`, `rusher_player_id`, `receiver_player_id`, `sack_player_id`, `interception_player_id` |
| outcomes | `yards_gained`, `epa`, `wpa`, `cpoe`, `success`, `air_yards`, `yards_after_catch`, `complete_pass`, `incomplete_pass`, `interception`, `fumble_lost`, `pass_touchdown`, `rush_touchdown`, `touchdown` |
| debugging | `play_desc` (renamed from nflverse `desc` to avoid SQL reserved-word friction) |

Total: ~42 columns.

## Team and player references: strings, not FKs

- `posteam` / `defteam` stay as `TEXT` (not FK to `teams`). Historical
  team abbreviations (`STL`, `OAK`, `SD`, `LA` pre-rebrand) already have
  normalization coverage via `team_aliases`; pushing FK semantics into
  the plays table would force rewriting team abbrs during ingest and
  fight against the source.
- `*_player_id` columns store the raw `gsis_id` as `TEXT`. Joining to
  `players.gsis_id` is one-line SQL. Deferred advantages: we can ingest
  plays before rosters for that season (hasn't happened yet, but is a
  real recovery story if rosters breaks), and we don't have to manage
  FK cascades when a player is deleted.

## Indexes

- `(season, season_type)` — partitions most grading queries.
- `(passer_player_id, season)`, `(rusher_player_id, season)`,
  `(receiver_player_id, season)` — for the "feature extraction" queries
  that pull one player-season's plays at a time.

## Size and storage

- ~50k rows/season. 10 seasons of history = ~500k rows.
- ~40 columns, mostly nullable small numerics + a few text keys.
- Estimated ~80 MB for 10 seasons in Postgres (10x smaller than the
  Parquet cache, since we're dropping 330 columns).
- Well inside "don't bother partitioning" territory.

## Consequences

**Easier:**
- Grading reads `SELECT ... FROM plays WHERE season=? AND passer_player_id=?`
  with no pandas overhead.
- UI player pages can show "top 10 EPA plays" with a cheap indexed
  query.
- New stat components for existing positions are small SQL additions —
  no new ingest needed.

**Harder:**
- Adding a new column we later need means a new migration + a full
  re-ingest of affected seasons. We accept this: the column list above
  is conservative and covers the build plan through career grading.
- Two sources of truth for raw PBP (Parquet + Postgres). The Parquet
  file is canonical; if the Postgres table disagrees we re-ingest.

**Explicitly given up:**
- Per-play tracking fields (time-to-throw per play, pressure tags) —
  those live in NGS / FTN, not PBP, and are ingested separately.
- The 300 "everything else" PBP columns — fumble recovery IDs, drive
  numbers, kicker yards etc. Available via the Parquet cache if needed
  for ad-hoc analysis.

## References

- ADR-0009: Raw data cached as Parquet, typed tables in Postgres.
- `docs/exploration/2026-04-23-pbp.md` (to follow this ADR) — probe
  output that anchored this column selection.
