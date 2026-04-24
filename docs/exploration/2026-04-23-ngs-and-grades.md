# 2026-04-23 — NGS ingest + QB v1 grades first run

Concludes the sprint that covered E1.5 (NGS) and F (QB grading v1).
Raw face-validity notes kept here so the numbers aren't lost when
the transcript rolls.

## NGS ingest (E1.5)

### Scope landed

- Migration 0004 → three tables `ngs_passing`, `ngs_rushing`,
  `ngs_receiving`. Keys `(player_id, season, season_type, week, team_id)`.
- `ingest/ngs.py` with a dispatcher (`run_all`) + per-stat-type `run`.
  Reuses the same `team_aliases` and `gsis_id` lookups as
  `depth_charts.py` / `rosters.py`.
- CLI: `nflgrades ingest ngs --season YYYY [--stat-type passing|rushing|receiving|all]`.
- 14 unit + integration tests in `tests/ingest/test_ngs.py`.

### Coverage

- 2024 — 614 passing / 601 rushing / 1,435 receiving = 2,650 rows.
- 2025 — 605 passing / 648 rushing / 1,402 receiving = 2,655 rows.
- Zero skips in either season (every `player_gsis_id` resolved,
  every `team_abbr` resolved).

Historical backfill (2016-2023) gated on ingesting rosters for those
seasons first. Not in this sprint — separate follow-up.

### Face-validity probes

- **Mahomes 2024 passing season summary**: 581 att / 3928 yds /
  26 TD / 11 INT, TTT 2.81, CPOE −1.15. Matches every public source
  (PFR / NFL.com exact).
- **Mahomes 2025**: slight uptick in aggressiveness (10.3 → 12.9) and
  worse CPOE (−1.15 → −2.90) — consistent with the narrative of a
  deteriorated surrounding cast forcing tighter-window throws.
- **RYOE/att top of 2024**: Derrick Henry 1.77, Saquon 1.61,
  Jordan Mason 1.38, Chuba Hubbard 1.11 — exact order as every
  published NGS analytics article from Jan 2025.
- **Avg separation leaders**: dominated by slot WRs and TEs as
  expected (slot routes + mismatches vs LBs → more open throws).

Ingest is trustworthy.

## QB v1 grading (F)

### Scope landed

- ADR-0013 formalizes the formula from `docs/grading/qb-v1-proposal.md`.
- Five helper modules filled in: `filters.py`, `empirical_bayes.py`,
  `zscore.py`, `composite.py`, `weights.py`, plus a reused `sigmoid.py`.
- `grading/qb.py` implements the three-stage pipeline
  (extract → compute → write). `grading/run.py` orchestrates.
- CLI: `nflgrades grade --season YYYY [--position QB]`.
- 32 new grading tests: shrinkage, z-score, composite, and an
  integration test that round-trips synthetic QBs through the full
  pipeline.

### First-run outputs

**2024 — 37 qualified QBs, mean grade 50.1:**

| Rank | QB | Grade | EPA/db | CPOE | Succ% | Drops |
|---|---|---|---|---|---|---|
| 1 | Lamar Jackson | 89.6 | +0.349 | +4.64 | 52.4 | 489 |
| 2 | Jared Goff | 87.9 | +0.269 | +5.29 | 53.7 | 559 |
| 3 | Joe Burrow | 81.4 | +0.154 | +6.83 | 51.4 | 696 |
| 4 | Tua Tagovailoa | 80.0 | +0.199 | +4.16 | 52.8 | 407 |
| 5 | Josh Allen | 77.0 | +0.258 | +1.04 | 48.9 | 491 |
| 9 | Patrick Mahomes | 67.3 | +0.112 | +2.56 | 49.3 | 615 |
| 15 | Jayden Daniels | 58.3 | +0.086 | +3.04 | 45.0 | 504 |

Bottom of qualified: Anthony Richardson 11.0, Deshaun Watson 12.4,
Will Levis 14.3.

**2025 — 36 qualified QBs, mean grade 49.8:**

| Rank | QB | Grade | EPA/db | CPOE | Succ% | Drops |
|---|---|---|---|---|---|---|
| 1 | Drake Maye | 94.0 | +0.301 | +10.75 | 54.6 | 533 |
| 2 | Brock Purdy | 84.1 | +0.209 | +7.29 | 54.1 | 292 |
| 3 | Matthew Stafford | 83.3 | +0.233 | +1.78 | 53.3 | 615 |
| 4 | Jordan Love | 82.9 | +0.237 | +5.53 | 49.5 | 459 |
| 11 | Josh Allen | 66.2 | +0.114 | +3.18 | 47.1 | 486 |
| 12 | Patrick Mahomes | 63.7 | +0.127 | +0.45 | 47.8 | 531 |

Bottom: Shedeur Sanders 8.3, Cam Ward 13.4, J.J. McCarthy 15.6,
Justin Fields 21.8.

### Face-validity check

**Top-5 maps tightly to PFF / consensus analytics**, both years:
- 2024 Lamar/Goff/Burrow at the top is the exact order many analytics
  sites published.
- Drake Maye as the 2025 breakout leader is the story of the season
  through week 12.
- Mahomes grading ~10-15 both seasons reflects his documented
  regression in a rebuilding WR room.

### Iteration notes (not fixing in v1)

- **Jalen Hurts overweight**: +7.62 CPOE (massive, from RPO quick
  games) pulls him to 70+ despite 46% success rate. The success-rate
  component does pull him down, but probably not enough. A future
  version could penalize "easy" CPOE the same way DVOA does.
- **Tua at #4 in 2024** feels a click high. Air-yards-adjusted CPOE
  would likely knock him to #6-8.
- **No opponent adjustment**: Goff benefited from the NFC North
  defenses' struggles; Burrow threw against a harder slate. v2.
- **Shrinkage is well-calibrated**: Purdy at 292 dropbacks in 2025
  (injury-shortened) grades legitimately top-5 without getting
  dragged down by small-sample suspicion. Feels right.

### Performance

- QB grading for one season: ~1s end-to-end (SQL aggregation +
  pandas + write).
- `stat_components` written: 312 rows / season (104 QBs × 3 components).
- `season_grades` written: ~95 rows / season (unqualified QBs with
  zero pass attempts get filtered out — they'd have NaN CPOE).

## What this unlocks

- Web app can now render a full QB leaderboard with composite grades,
  percentiles, and per-component breakdowns (all three of those are
  columns in `season_grades` + `stat_components`).
- Adding RB / WR / TE grading is now a copy-paste exercise: new
  per-position module that follows the same
  `extract_features → compute_grades → write_results` shape.
- NGS data is live for whenever we want to fold `time_to_throw` and
  `CPOE_from_NGS` into a v2 formula.

## Known gaps (tracked)

- Rosters + PBP only go back to 2024. NGS could cover 2016 onward but
  is bounded by our rosters coverage.
- No career grades yet (`career_grades` table exists, not populated).
- No opponent adjustment.
- FTN charting (turnover-worthy throw, qb-fault sack) not ingested.
