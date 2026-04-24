# Exploration — `load_snap_counts` and `load_depth_charts`

**Date:** 2026-04-23
**Author:** pipeline ingest work (D1, D2)
**nflreadpy version:** 0.1.5

Findings while wiring up the second- and third-stage ingest modules after
rosters. The two sources have very different shapes, and the depth_charts
schema **changed format** between 2024 and 2025 — document both here so
future agents don't rediscover it.

---

## `load_snap_counts(seasons=[s])`

### Shape

- ~26,600 rows per recent season
- ~2,200 distinct players per season (offensive + defensive + ST players
  who took at least one snap)
- Columns (16):

  | column | type | notes |
  |---|---|---|
  | `game_id` | str | `'2024_01_ARI_BUF'` |
  | `pfr_game_id` | str | `'202409080buf'` |
  | `season` | int | |
  | `game_type` | str | `REG` / `WC` / `DIV` / `CON` / `SB` |
  | `week` | int | 1..22 (SB = 22) |
  | `player` | str | display name |
  | `pfr_player_id` | str | **PFR id, not gsis_id** — see ID-join note below |
  | `position` | str | PFR-style: `QB`, `WR`, `CB`, `DE`, `DT`, `ILB`, `OLB`, `G`, `T`, `C`, `FS`, `SS`, `P`, `K`, `LS`, `FB`, `NT`, `MLB`, `DB`, `LB` |
  | `team`, `opponent` | str | abbrs |
  | `offense_snaps`, `offense_pct` | float | `snaps` is actually an integer count stored as float |
  | `defense_snaps`, `defense_pct` | float | |
  | `st_snaps`, `st_pct` | float | |

- Game-type distribution (2024): REG=25398, WC=564, DIV=372, CON=189, SB=92

### The ID-join problem

`snap_counts` keys on `pfr_player_id`, while **every other table** in our
schema keys on `gsis_id`. Several PFR-sourced data sets will hit the same
pattern, so rather than hand-roll name-based joining we:

1. Added a `pfr_id TEXT` column to `players` in migration `0002_add_pfr_id.sql`.
2. Populate `pfr_id` during rosters ingest from `load_players().pfr_id`
   (null rate ~9% in load_players; falls to ~10% overall post-rosters).
3. In `ingest/snap_counts.py`, build a `pfr_id -> player_id` dict once at
   the top of the run and use it for every aggregation row.

The ~7 skipped-no-pfr-match rows per season after backfill are all
practice-squad / active-only players who weren't in `load_players`.

### Aggregation choices (v1)

- **REG only** — playoff snap volume distorts per-game rates because team
  count varies.
- Group by `pfr_player_id` only (not by team). Traded players' snaps are
  summed; the total attaches to their end-of-season team's
  `player_seasons` row via the (player_id, season) join — matching
  rosters grain.
- `games` = count of rows per (player, season).
- `snaps_offense`, `snaps_defense`, `snaps_special` = sums.
- `games_started` **heuristic**: snap_counts exposes no "started" flag.
  We count a game as a start if the player took ≥50% of their primary
  phase snaps. Primary phase = phase with highest mean `*_pct` across
  the season. This matches PFR's own definition closely for starters
  but will undercount spot-starters. Documented as approximate in the
  module docstring; can be replaced later with a PFR-scraped source.

### Sanity results (see `scripts/verify_snap_counts.py`)

- **2024**: 3,215 player_seasons, 2,183 (67.9%) with any snaps. All 17
  games for Burrow, Goff, Baker Mayfield, Caleb Williams, Darnold,
  Lamar, Bo Nix, Aaron Rodgers, etc. Mahomes 16 (Week 18 rested).
  Purdy 15 (injury). Jalen Hurts 15 started 14 (injury).
- **2025**: 3,134 player_seasons, 2,179 (69.5%) with any snaps. All
  trades correctly attributed: Geno Smith SEA→LV, Sam Darnold MIN→SEA,
  Aaron Rodgers NYJ→PIT, Matthew Stafford stayed LA.

---

## `load_depth_charts(seasons=[s])` — **two schemas**

The nflverse changed the depth_charts format starting with 2025. Both are
handled by `_select_snapshot()` in `ingest/depth_charts.py`.

### Old format (2001–2024): week-keyed

- ~37,000 rows per season
- Columns (15): `season`, `club_code`, `week`, `game_type`, `depth_team`,
  `last_name`, `first_name`, `football_name`, `formation`, `gsis_id`,
  `jersey_number`, `position`, `elias_id`, `depth_position`, `full_name`
- `week` spans 1..22; `game_type` uses same codes as snap_counts
  (`REG`/`WC`/`DIV`/`CON`/`SBBYE`/`SB`). Small share (~0.6%) have null
  `week`.
- `formation` is `'Offense'` / `'Defense'` / `'Special Teams'`.
- `depth_team` is a **string** `'1'`/`'2'`/`'3'`/... = depth order.
- `position` is coarse (`G`, `T`, `C`, `CB`, `DE`, `DT`, `ILB`, `OLB`,
  etc.); `depth_position` is the specific slot (`RG`/`LG`, `LT`/`RT`,
  `LCB`/`RCB`, `MLB`/`SLB`/`WLB`, `FS`/`SS`, ...). We prefer
  `depth_position` because the depth-chart UI wants the specific slot.

### New format (2025+): timestamp-keyed

- ~554,000 rows per season (already!) — one row per team per position
  slot per **day** between Aug 3, 2025 and Mar 14, 2026 (~220 dates).
- Columns (12): `dt`, `team`, `player_name`, `espn_id`, `gsis_id`,
  `pos_grp_id`, `pos_grp`, `pos_id`, `pos_name`, `pos_abb`, `pos_slot`,
  `pos_rank`
- `dt` is an ISO timestamp (date+time).
- `pos_abb` is already specific (`LCB`, `LDT`, `RDE`, `SLB`, `WLB`,
  `MLB`, `FS`, `SS`, `PK`, `PR`, `KR`, `NB`, ...).
- `pos_rank` = depth order (1=starter, 2=backup, ...).
- `pos_slot` = 1..12; appears to be a position-group ordinal *within
  the formation* (not what we want for depth_order).
- **No `game_type` or `week`**; we pick the latest `dt` as our snapshot.

### Position taxonomy differs across formats

- 2024 snapshot: 54 distinct position labels
- 2025 snapshot: 31 distinct position labels

The 2025 format is more specific in some places (`PK` for kicker vs `K`,
`NB` nickel back explicit) and less specific in others. A future
enhancement could normalize to a common depth-chart taxonomy, but v1
simply stores whatever the source gives — the depth-chart UI will
display whatever label is present.

### Snapshot convention

- All depth-chart rows stored as `week = 99` per the comment in
  `db/migrations/0001_init.sql` ("99 for end-of-season snapshot").
  Future per-week ingestion can land at weeks 1..18 without colliding.

### Sanity results (see `scripts/verify_depth_charts.py`)

- **2024** (1,444 rows, 32 teams): all 32 starting QBs correct for the
  final regular-season week, including backup-driven endings (Cooper
  Rush at DAL, Mac Jones at JAX, Jimmy Garoppolo at LA, Joe Flacco at
  IND, Drew Lock at NYG). KC depth shows Mahomes/Wentz, Kelce/Gray
  TE1/TE2, Humphrey/Nourzad at C.
- **2025** (2,286 rows, 32 teams): reflects 2025 offseason shakeup —
  Shedeur Sanders CLE, Cam Ward TEN, Jaxson Dart NYG, Daniel Jones IND,
  Kyler Murray MIN, Aaron Rodgers PIT, Geno Smith LV→NYJ, Sam Darnold
  SEA. KC draft picks show up (Josh Simmons LT, Brashard Smith KR/RB,
  Kenneth Walker III RB1 after trade).

---

## Implications for grading

- **Inverse-noise weighting** (ADR-0007) needs per-player opportunity
  counts — `snaps_offense/defense/special` from this step feeds that
  directly.
- **Minimum-sample thresholds** (e.g. "QB grade requires ≥100 dropbacks")
  come from PBP, not snaps. Don't conflate.
- **Depth-chart UI** should query `WHERE week = 99` for "current
  roster view". Keep the snapshot-week convention stable.

## Open items

- 2024 `skipped_dup=377` on depth-chart ingest — same player appearing
  on multiple formations (e.g. a CB who's also PR on Special Teams).
  Current behavior keeps the first occurrence. If we later want the ST
  role visible too, we'd need a separate table or prefix the position
  with formation. Not needed for v1.
- `games_started` is a heuristic; replace with a PFR game-log scrape
  when/if we want reporter-grade accuracy.
- The 2025 timestamp-keyed format is ~15x larger per season than 2024;
  if we ever ingest per-week / per-day depth charts, partitioning or a
  separate `depth_chart_history` table becomes worthwhile.
