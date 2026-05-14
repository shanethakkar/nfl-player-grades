# nflverse Data Inventory — Where Each Column Lives

Validated 2026-05-14 against `nflreadpy` cached parquets. Use this as the first check when scoping a new component — if the column doesn't exist in any source listed here, the metric isn't computable for v1.

Sources registered in `pipeline/src/nfl_grades/ingest/_cache.py`:

- `pbp` — play-by-play
- `nflvs_player_stats` — pre-aggregated player-game stats (nflverse box score)
- `ngs_passing` / `ngs_receiving` / `ngs_rushing` — NFL Next Gen Stats
- `pfr_advstats_def` — Pro Football Reference advanced defensive
- `ftn` — FTN charting (subjective per-play flags, 2022+)
- `rosters` / `rosters_weekly` / `players` / `depth_charts` / `snap_counts`

## Offensive receiver/passer columns

### nflvs_player_stats (per player-game, pre-aggregated)

Key WR/TE-relevant fields:
- `targets`, `receptions`, `receiving_yards`, `receiving_tds`
- `receiving_air_yards`, `receiving_yards_after_catch`, `receiving_first_downs`
- `receiving_epa`
- `receiving_fumbles`, `receiving_fumbles_lost`
- **`racr`** (Receiver Air Conversion Ratio = total yards / air yards) — pre-computed
- **`target_share`** (player targets / team pass attempts) — pre-computed
- **`air_yards_share`** (player air yards / team air yards) — pre-computed
- **`wopr`** (1.5×target_share + 0.7×air_yards_share) — pre-computed

Per-game so sum receptions/yards/etc., but recompute season rates (target_share, racr, wopr) from totals — averaging per-game gives wrong results.

### ngs_receiving (week=0 row is season aggregate)

- `avg_cushion` — pre-snap CB depth (yards)
- `avg_separation` — yards from nearest defender at catch point
- `avg_intended_air_yards` — depth of target (deep vs short)
- `percent_share_of_intended_air_yards` — air yards share, NGS version
- `avg_yac`, `avg_expected_yac`, `avg_yac_above_expectation` — YAC + expected YAC
- `catch_percentage`, `receptions`, `targets`, `yards`, `rec_touchdowns`

Caveat: NGS coverage is selective — only WRs above a snap/target threshold. ~120-150 WRs per season have NGS data.

### pbp (play-by-play, all plays)

- `receiver_player_id`, `receiver_player_name`
- `air_yards`, `yards_after_catch`
- `epa`, `wpa`, `air_epa`, `yac_epa`, `comp_air_epa`, `comp_yac_epa`
- `cpoe` (Completion % Over Expected — on QB side)
- `xyac_epa`, `xyac_mean_yardage`, `xyac_median_yardage`, `xyac_success` — expected YAC
- `complete_pass`, `incomplete_pass`

Useful for: ground-truth aggregations not in nflvs (e.g., team-level totals for target_share denominator, success_rate, EPA splits by situation).

### ftn (per-play subjective flags, 2022+)

- `is_catchable_ball` — was the throw catchable
- `is_drop` — drop on a catchable ball
- `is_contested_ball` — contested-catch situation
- `is_created_reception` — receiver created the play vs. easy catch
- `is_play_action`, `is_screen_pass`, `is_rpo`, `is_motion`, `is_no_huddle`
- `n_offense_backfield`, `n_defense_box`, `n_blitzers`, `n_pass_rushers`
- `qb_location`, `read_thrown`, `is_qb_out_of_pocket`, `is_throw_away`
- `is_interception_worthy`, `is_qb_fault_sack`

**Join key:** `ftn.nflverse_play_id ↔ pbp.play_id` AND `ftn.nflverse_game_id ↔ pbp.game_id` (both required — play_id alone is not unique). For receiver-level aggregation, join to PBP and group by `pbp.receiver_player_id`.

FTN is more conservative on drops than PFF — only flags clear drops, not "should-have-caught" plays. Expect lower drop totals.

## Defensive columns

### pfr_advstats_def (per player-game)

- `def_targets`, `def_completions_allowed`, `def_yards_allowed`
- `def_receiving_td_allowed` — TDs allowed in coverage (used in passer rating allowed)
- `def_ints`
- `def_passer_rating_allowed` — PFR pre-computed per-game, but **recompute from season totals** because averaging per-game ratings is wrong (rating is non-linear)
- `def_yards_allowed_per_cmp`, `def_yards_allowed_per_tgt`, `def_adot`, `def_air_yards_completed`, `def_yards_after_catch` — coverage detail
- `def_pressures`, `def_sacks`, `def_times_hitqb`, `def_times_hurried`, `def_times_blitzed`
- `def_tackles_combined`, `def_missed_tackles`, `def_missed_tackle_pct`

### nflvs_player_stats (defensive aggregations)

- `def_tackles_solo`, `def_tackles_with_assist`, `def_tackle_assists`
- `def_tackles_for_loss`, `def_tackles_for_loss_yards`
- `def_fumbles_forced`, `def_sacks`, `def_sack_yards`, `def_qb_hits`
- `def_interceptions`, `def_pass_defended` (PBUs)

## What's NOT available in nflverse

Common external metrics that **cannot** be computed from our sources (would need PFF, Sumer Sports, or other paid sources):

- **Routes run** → blocks YPRR, route participation rate
- **Coverage snaps** → blocks "targets per coverage snap" (we use targets per defensive snap instead)
- **Per-play expected catch %** → blocks CROE (Catch Rate Over Expected) at receiver level
- **PFF coverage grades** → blocks ground-truth comparison
- **Pass-rush snaps split** → blocks "pressure rate per pass-rush snap" (we use total defensive snaps)
- **Block efficiency** → blocks OL grading entirely (deferred from v1 system)

## When proposing a new component

Quick checklist:

1. Find which source has the underlying column. If none → not computable, drop.
2. If it's in `nflvs_player_stats` as pre-computed (wopr/racr/target_share): re-derive from season totals, don't average per-game.
3. If it's in `ftn`: confirm 2022+ coverage acceptable; join via `nflverse_play_id`+`nflverse_game_id` to PBP.
4. If it's in NGS: confirm the qualified pool is large enough (typically 100-150 players per season vs ~250-400 in PBP).
5. If it's a defender-attribution stat (passer rating allowed, comp% allowed): aggregate from raw counts, never from per-game pre-computed rates.
