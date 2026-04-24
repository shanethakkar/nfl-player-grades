# 2026-04-24 — YPRR feasibility probe (v1.5 receiver component)

Follow-up from the ADR-0017 discussion. User asked whether
`percent_share_of_intended_air_yards` should be added to the WR/TE
composite at 5-8%; I argued against (it amplifies the ADR-0017
contamination; it penalizes legitimate archetypes); user redirected to
**YPRR** (yards per route run) as the preferred v1.5 direction.

This note answers whether YPRR is buildable on the data we ingest today,
and — since it isn't — evaluates the best-available alternatives.

## Verdict

1. **YPRR is infeasible on public data** accessible via `nflreadpy`.
   Routes-run is a PFF paywall metric. Public FTN charting has no
   routes-run column and no per-receiver participation signal that would
   let us reconstruct it.

2. **RACR is available today but not a clean v1.5 upgrade.** Spearman
   rank correlation with the current composite is ~0.35 for both WR and
   TE; it moves rankings meaningfully but introduces a new archetype bias
   (rewards slot / short-route specialists, penalizes deep threats) that
   *breaks* one of ADR-0017's working counter-examples (Brian Thomas Jr.).

3. **The real v1.5 opening is FTN charting as a whole**, not YPRR.
   FTN publishes clean per-target receiver-skill signals — `is_drop`,
   `is_contested_ball`, `is_created_reception`, `is_screen_pass` — that
   ADR-0015 explicitly declared unavailable on public data. Coverage is
   2022-2025 only, so a v1.5 built on FTN is necessarily a data-tier-2
   upgrade for 2022+ with fallback for 2016-2021.

**Recommendation**: close YPRR as a v1.5 candidate. Open a separate
plan for FTN ingest + v1.5 composite additions (drop rate, contested
catch rate, created-reception rate, screen-excluded EPA/target) targeting
2022+ seasons.

## 1. What `load_ftn_charting` actually publishes

29 columns, all of them either pre-snap context or per-play event flags.
Grain is `(nflverse_game_id, nflverse_play_id)` — one row per play, the
receiver is not identified on the FTN row (join through `plays` on the
same keys).

| Category | Columns |
|---|---|
| Identifiers | `ftn_game_id`, `nflverse_game_id`, `season`, `week`, `ftn_play_id`, `nflverse_play_id`, `date_pulled` |
| Pre-snap | `starting_hash`, `qb_location`, `n_offense_backfield`, `n_defense_box`, `is_no_huddle`, `is_motion`, `is_play_action`, `is_screen_pass`, `is_rpo`, `is_trick_play` |
| QB/pass event | `is_qb_out_of_pocket`, `is_interception_worthy`, `is_throw_away`, `is_qb_fault_sack`, `read_thrown` |
| Receiver skill | `is_catchable_ball`, `is_contested_ball`, `is_created_reception`, `is_drop` |
| Pressure/rush | `is_qb_sneak`, `n_blitzers`, `n_pass_rushers` |

**Nothing route-related**. A scan for any column name containing
`route`, `receiver`, `target`, `wr`, `te`, or `eligible` returns empty.

## 2. Coverage

```
2016-2021: ValueError ("Season must be between 2022 and 2025")
2022:      41,643 rows
2023:      48,225 rows
2024:      48,031 rows
2025:      47,316 rows
```

FTN's public window is 2022+. The v1 grading window is 2016+. Any
v1.5 component built on FTN needs an explicit data-tier fallback for
2016-2021.

## 3. Join to `plays`

100% join rate on `(game_id, play_id) == (nflverse_game_id,
nflverse_play_id)`. For all 14,004 WR+TE REG-season target plays in
2024, FTN has a matching row. Zero orphans. Column `plays.play_id`
is already the integer `nflverse_play_id` — no translation needed.

## 4. Best-available alternative: RACR

RACR = `sum(receiving_yards_on_targets) / sum(intended_air_yards_on_targets)`,
computed per receiver, target-level (includes incompletions where
`yards_gained=0` but `air_yards` is known from the throw).

### WR 2024, top-20 by RACR (min 50 targets)

| # | WR | Tgt | RACR | v1 grade | v1 pct |
|---:|---|---:|---:|---:|---:|
| 1 | Greg Dortch | 50 | 1.652 | 52.1 | 56 |
| 2 | Chris Godwin Jr. | 62 | 1.643 | 81.0 | 98 |
| 3 | Khalil Shakir | 100 | 1.498 | 79.5 | 94 |
| 4 | Marvin Mims Jr. | 52 | 1.305 | 80.9 | 96 |
| 5 | Jayden Reed | 75 | 1.260 | 68.4 | 82 |
| 6 | Amon-Ra St. Brown | 141 | 1.253 | 76.8 | 93 |
| 7 | Olamide Zaccheaus | 64 | 1.246 | 68.4 | 81 |
| 8 | Deebo Samuel Sr. | 81 | 1.216 | 57.7 | 69 |
| 9 | Puka Nacua | 106 | 1.180 | 80.2 | 95 |
| 11 | Ja'Marr Chase | 175 | 1.119 | 81.4 | 99 |
| 13 | Wan'Dale Robinson | 140 | 1.066 | 22.5 | 6 |
| 14 | Ladd McConkey | 112 | 1.037 | 73.8 | 88 |
| 17 | CeeDee Lamb | 152 | 1.003 | 51.1 | 56 |

Spearman rank correlation RACR vs v1 composite: **0.344** (n=20).

### TE 2024, top-15 by RACR (min 40 targets)

| # | TE | Tgt | RACR | v1 grade | v1 pct |
|---:|---|---:|---:|---:|---:|
| 1 | Tucker Kraft | 70 | 1.890 | 86.3 | 97 |
| 2 | Jonnu Smith | 111 | 1.631 | 71.4 | 91 |
| 3 | Will Dissly | 64 | 1.631 | 49.0 | 59 |
| 7 | George Kittle | 94 | 1.383 | 89.7 | 100 |
| 9 | Brock Bowers | 153 | 1.294 | 50.4 | 62 |
| 14 | Tyler Conklin | 72 | 1.254 | 36.0 | 21 |
| 15 | Sam LaPorta | 83 | 1.252 | 62.4 | 82 |

Spearman rank correlation RACR vs v1 composite: **0.354** (n=15).

### RACR's failure mode

RACR's denominator punishes deep-route specialists. The metric rewards
"yards earned per unit of depth attempted," which is inverted from
what a well-specified WR/TE grade should measure:

- **Slot/short-route archetypes inflate** — Greg Dortch (50 tgt, mostly
  screens and flats) is #1 WR by RACR. Khalil Shakir and Olamide
  Zaccheaus are in the top 10 for the same reason. The v1 grader
  correctly ranks Dortch mid-pack; RACR promotes him above Ja'Marr Chase.
- **Primary deep-threat WR1s get depressed** — Chase is #11 despite
  the triple crown. Brian Thomas Jr. (ADR-0017 counter-example) drops
  to RACR 0.831, which would lower his v1 grade of 73.9. The metric
  systematically disagrees with v1's *correct* call on him.
- **Wan'Dale Robinson RACR 1.066** puts him ahead of DeVonta Smith and
  CeeDee Lamb despite grading in the 6th percentile. RACR credits
  high-volume short-yardage catches as efficient.

This is the mirror image of the `percent_share_of_intended_air_yards`
problem: instead of over-rewarding deep usage, RACR over-rewards short
usage. Neither is a clean signal of receiver quality.

### RACR on the ADR-0017 cluster

| Player | Pos | Tgt | RACR | v1 grade | Interpretation |
|---|---|---:|---:|---:|---|
| Jonnu Smith | TE | 111 | 1.631 | 71.4 | v1 right, RACR agrees |
| Brock Bowers | TE | 153 | 1.294 | 50.4 | RACR would lift modestly |
| David Njoku | TE | 97 | 0.990 | 21.2 | RACR doesn't rescue |
| Dalton Schultz | TE | 85 | 0.778 | 30.0 | RACR doesn't rescue |
| Zach Ertz | TE | 91 | 0.953 | 41.7 | v1 right, RACR agrees |
| Brian Thomas Jr. | WR | 133 | 0.831 | 73.9 | **RACR contradicts v1** |
| Garrett Wilson | WR | 153 | 0.801 | 43.3 | RACR doesn't rescue |
| Jerry Jeudy | WR | 145 | 0.763 | 55.1 | RACR doesn't rescue |
| Malik Nabers | WR | 170 | 0.748 | 55.2 | RACR doesn't rescue |

RACR does not solve the ADR-0017 QB-contamination problem. Wilson,
Jeudy, and Nabers all have low RACR for the *same reason* their v1
grades are low — their per-attempt yards are depressed by QB play.
Swapping metric shapes doesn't fix the underlying cause.

Worse: RACR pushes against v1 on Brian Thomas Jr., one of the
counter-examples ADR-0017 held up as evidence the grader distinguishes
efficient-in-bad-context players from forced-volume players. Adding
RACR at 5-10% weight would erode that correctly-graded case.

**Conclusion**: RACR doesn't clear the bar for a v1.5 composite addition.

## 5. The real v1.5 opening: FTN charting

Even though FTN doesn't carry YPRR's denominator, the flags it does
publish directly address several of the "not available on public data"
caveats in ADR-0015:

- `is_drop` — the PBP-can't-distinguish-drops-from-defended-passes
  problem ADR-0015 cited when dropping catch-rate-over-expected.
- `is_contested_ball` — the "not available in public tracking data"
  gap ADR-0015 listed under Deferred.
- `is_created_reception` — a receiver-skill signal with no direct
  analog in v1; separates WR1s who win difficult throws.
- `is_screen_pass` — lets us screen-exclude an EPA/target variant so
  the per-target efficiency component isn't structurally inflated for
  schemed-YAC offenses.

### Face-validity of the FTN signals (2024, WR+TE min 50 tgts)

ADR-0017 cluster:

| Player | Pos | Tgt | Drop% | Contested% | Created% | Screen% |
|---|---|---:|---:|---:|---:|---:|
| Jonnu Smith | TE | 111 | 3.6 | 11.7 | 4.5 | 18.0 |
| David Njoku | TE | 97 | 7.2 | 21.6 | 7.2 | 7.2 |
| Dalton Schultz | TE | 85 | 5.9 | 15.3 | 0.0 | 0.0 |
| Brock Bowers | TE | 153 | 3.9 | 16.3 | 2.6 | 8.5 |
| Brian Thomas Jr. | WR | 133 | 3.8 | 11.3 | 4.5 | 11.3 |
| Garrett Wilson | WR | 153 | 2.6 | 21.6 | 5.2 | 11.8 |
| Jerry Jeudy | WR | 145 | 5.5 | 15.2 | 4.1 | 2.1 |
| Malik Nabers | WR | 170 | 5.9 | 20.6 | 5.9 | 10.0 |

Wilson's 21.6% contested rate on NYJ with Rodgers is notably high —
he was catching difficult balls at starter volume, which the v1 composite
doesn't directly reward. This is exactly the kind of receiver-skill-
separable-from-QB-context signal that would move his grade toward a more
defensible spot without layering team-EPA residualization on top.

Top-10 drop rate (worst hands, min 50 targets):

| Player | Pos | Tgt | Drop% |
|---|---|---:|---:|
| Allen Lazard | WR | 61 | 11.5 |
| Keon Coleman | WR | 57 | 8.8 |
| Cade Otton | TE | 87 | 8.0 |
| David Njoku | TE | 97 | 7.2 |
| Calvin Austin III | WR | 58 | 6.9 |
| Jayden Reed | WR | 75 | 6.7 |
| Dontayvion Wicks | WR | 76 | 6.6 |

Top-10 created reception rate (best hands-in-traffic, min 50 targets):

| Player | Pos | Tgt | Created% |
|---|---|---:|---:|
| Amari Cooper | WR | 85 | 11.8 |
| Andrei Iosivas | WR | 61 | 9.8 |
| Romeo Doubs | WR | 72 | 9.7 |
| George Pickens | WR | 103 | 9.7 |
| Christian Watson | WR | 53 | 9.4 |
| Mark Andrews | TE | 69 | 8.7 |
| Terry McLaurin | WR | 117 | 8.5 |
| Courtland Sutton | WR | 135 | 8.1 |
| Nico Collins | WR | 99 | 8.1 |
| Marvin Harrison Jr. | WR | 116 | 7.8 |

These lists match tape-watch consensus (Lazard / Otton / Njoku as
butter-hands, Cooper / Pickens / McLaurin / Sutton as veteran
separators). The signal is real.

## 6. Recommendation

**Close YPRR as a v1.5 candidate.** It's gated on PFF data we don't
have and have no clean path to acquiring.

**Close RACR as a v1.5 candidate.** It's available today but introduces
a new archetype bias without resolving the ADR-0017 confound. Net
neutral to slightly negative on face-validity.

**Open a v1.5 plan around FTN ingest.** Concretely:

1. New migration: `ftn_plays` table (or denormalized columns on `plays`
   — decide in the plan; FTN is 2022+-only, mirroring the per-play
   grain of `plays`, so a side table is probably cleaner).
2. New ingest module: `pipeline/src/nfl_grades/ingest/ftn.py` mirroring
   the pattern of `pbp.py` / `ngs.py`, fetching 2022-2025 via
   `cache_or_fetch("ftn", season)`.
3. New components for v1.5 receiver composites:
   - `wr_drop_rate` / `te_drop_rate` (negative weight, ~4%)
   - `wr_contested_catch_rate` / `te_contested_catch_rate` (positive, ~5%)
   - `wr_created_reception_rate` / `te_created_reception_rate`
     (positive, ~4%)
   - Optionally: a screen-excluded variant of `*_rec_epa_per_target`
     replacing the current component for 2022+ to reduce scheme-YAC
     contamination of the EPA signal.
4. Weight rebalance: the new components come from shrinking
   `target_earn_rate` (currently 10%) and `success_rate_per_target`
   (currently 8%) — the two components ADR-0015 flagged as watch items
   for role contamination. Net weight-budget neutral.
5. Data tiering: 2022+ uses full v1.5 composite (tier 1); 2016-2021
   continues on v1 composite (tier 2). `data_tier_reason` column gets
   a new value, `pre_ftn_coverage`, for seasons falling back.
6. ADR-0018 documenting the above before touching `weights.py`.

**Short-term (before v1.5 plan opens)**: nothing urgent. RACR could
optionally be surfaced as a descriptive column on the player page
(it's fully computable from `plays` today, no new ingest), with a
tooltip noting it's context-for-interpretation rather than part of the
grade. That's a UI-only change and doesn't require a weight ADR.

## 7. What doesn't change from this round

- No edits to `pipeline/src/nfl_grades/grading/weights.py`.
- No new ADR. ADR-0018 (FTN-based v1.5) is the follow-up, not this memo.
- No ingest module for FTN yet (would trigger a migration + tests;
  belongs in the v1.5 plan).
- `percent_share_of_intended_air_yards` stays out of the composite, as
  already decided.

## References

- ADR-0015 §"Catch-rate-over-expected dropped entirely" and
  §Deferred "Contested catch rate" / "Drop rate" — the gaps this memo
  shows are closable on public data.
- ADR-0017 §"The specific confound" — the RACR analysis above shows
  simple per-target-yards alternatives don't dissolve this.
- Probe script: throwaway `pipeline/scripts/_probe_ftn.py`, deleted
  after this memo was written. Raw output preserved in the agent
  transcript if needed for replay.
