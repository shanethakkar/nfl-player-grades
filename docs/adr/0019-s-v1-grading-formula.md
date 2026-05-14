# ADR-0019: Safety v1 Grading Formula

**Status:** Accepted (v1.1 passer-rating revision — 2026-05-14)
**Date:** 2026-05-13

## Context

Safety is the second defensive position graded by the system. The core challenge
is that safeties play two distinct roles — deep coverage and run support — and
no single metric captures both. PBP data records which defender made a tackle or
PBU but does not reliably identify the covering defender on completions (the same
problem as CB, resolved the same way: use PFR's per-player coverage stats).

**Data sources:**
- **Coverage stats** (targets, completions, yards, INTs): PFR Advanced Defensive
  Stats via `nflreadpy.load_pfr_advstats(stat_type="def")`, same source as CB.
- **Pass breakups (PBU):** nflverse weekly player stats via
  `nflreadpy.load_player_stats()`, column `def_pass_defended`.
- **Tackle stats** (combined, TFL, sacks): nflverse player_stats —
  `def_tackles_solo + def_tackle_assists`, `def_tackles_loss`, `def_sacks`.
- **Missed tackle count:** attempted from `pfr_advstats_def` (multiple column
  name variants). Stored as NULL if not found; the component is NaN-neutralized.
- **Defensive snap counts:** `player_seasons.snaps_defense` (snap-counts ingest).

**Coverage:** 2018+ only. PFR per-defender coverage data begins in 2018.

## Decision

### Metric Set (v1.1 passer-rating revision, 2026-05-14)

| Component | Weight | Direction | Rationale |
|---|---|---|---|
| `s_passer_rating_allowed` | **−0.30** | Lower = better | NFL passer rating allowed when targeted. Industry-standard coverage damage metric combining comp%, yards per attempt, TDs allowed, and INTs into one number. Replaces separate `s_comp_pct_allowed`, `s_yards_per_target_allowed`, and `s_int_rate` components. 2024 face-check confirmed Kerby Joseph (9 INTs, All-Pro) #1, McKinney #2, Derwin James #3, Brian Branch #5 — consensus elites all in top 5. |
| `s_pbu_rate` | +0.12 | Higher = better | Pass breakups per target. Active play that breaks up the catch. INTs now captured inside passer rating allowed; this is PBU-only (down from v1 PBU+INT bundle at 0.15). |
| `s_target_rate` | −0.08 | Lower = better | Targets per defensive snap. QB avoidance signal. Denominator is snaps_defense (not coverage snaps, unavailable in public data), so it conflates avoidance with scheme role. Modest weight reflects this limitation. |
| `s_tackles_per_snap` | +0.07 | Higher = better | Combined tackles per snap. Run support and box coverage both require reliable tackling. |
| `s_missed_tackle_rate` | −0.09 | Lower = better | Missed tackles / tackle attempts. Open-field technique matters most for safeties: a miss in space typically becomes a big gain. |
| `s_backfield_disruption_per_snap` | +0.09 | Higher = better | (TFL + sacks) / snaps_defense. Measures pass-rush versatility from depth. Combined into one metric because TFL and sacks measure the same skill; combining doubles the event count and improves stability. |

**Weight breakdown:**
Coverage (67%): `|−0.30| + |0.12| + |−0.08|` = 0.50
Tackling (33%): `|0.07| + |−0.09| + |0.09|` = 0.25
Sum |abs| = 0.75

### Why yards/target instead of YAC/rec?

For CBs, the YAC decomposition (separate from comp%) captures a distinct skill
(cushion at the catch point + tackling quality). For safeties, who typically
defend deeper routes and assist in run support, the cleaner split is less
meaningful: a safety targeted on a post catches the ball in stride. YAC on those
routes reflects route design as much as coverage. `yards_per_target` collapses
the two signals into one, keeping the formula simpler without meaningful
information loss.

### Why combined TFL + sacks?

TFLs and sacks measure the same underlying outcome: stopping the play behind
the line of scrimmage. Separating them at low sample sizes (1–3 sacks/season
for most safeties) would produce two noisy, near-zero components. Combining them
creates a more stable metric with k=300 snaps of shrinkage.

### Qualification

Snap-based, not target-based (unlike CB). Safeties can appear in 400+ snaps
with very few coverage targets depending on scheme.

| Threshold | Value |
|---|---|
| Minimum snaps to appear | 200 |
| Qualified (percentile pool) | 400 |
| Full confidence | 700 |

### Shrinkage k rationale

| Component | k | Denominator | Rationale |
|---|---|---|---|
| `comp_pct_allowed`, `yards_per_target` | 50 targets | targets | Moderate shrinkage; after ~50 targets reliability is sufficient. |
| `pbu_rate`, `int_rate` | 80 targets | targets | Heavy shrinkage; rare events (r<0.25 YoY). |
| `target_rate` | 150 snaps | snaps | Scheme-driven; less volatile than event rates. |
| `tackles_per_snap` | 200 snaps | snaps | Stable over time; role is consistent across weeks. |
| `missed_tackle_rate` | 100 tackle attempts | tackle_attempts | Technique is a real skill but angle/bounce introduces noise. |
| `backfield_disruption` | 300 snaps | snaps | TFL+sacks rare; heavy shrinkage prevents overweighting hot starts. |

### NaN Handling

Standard NaN-neutralization (ADR-0015): if a component's z-score is NaN (missing
source data), it is replaced with 0.0 before entering the composite. The raw NULL
is preserved in `stat_components.z_score` so the UI renders "—".

Known NaN sources:
- `s_missed_tackle_rate`: if `pfr_advstats_def` does not include a missed-tackle
  column for a given release (column names vary). All players in that season will
  have NULL missed_tackles; the entire component is NaN-neutralized.
- `s_pbu_rate`: NULL when a safety is absent from nflverse player_stats (edge
  cases — players without a registered gsis_id in our DB).
- `s_target_rate`, `s_tackles_per_snap`, `s_backfield_disruption_per_snap`: NULL
  if snap-counts ingest has not been run for the season.

## Alternatives Considered

**Target-based qualification (like CB):** Rejected. Safeties in zone coverage can
play 600+ snaps with very few direct targets. A target-based minimum (e.g. 25)
would exclude most split-safety schemes and heavily penalize traditional free
safeties. Snap-based qualification is position-appropriate.

**Role-bucketed z-scoring (FS vs. SS):** Correct in principle. Rejected for v1
for the same reason as CB role-bucketing: with ~30–50 qualified safeties per
season, splitting further produces unstable z-scores. Role labels (if added in v2)
would use `pfr_advstats_def`'s alignment data.

**Separate TFL and sacks components:** Rejected due to sample-size instability.
Most safeties record 0–1 sacks per season. At k=300 snaps, both a 0.0 and a 0.5
rate shrink heavily toward the mean — the combined metric is more stable with no
meaningful information cost.

**Coverage-only formula:** Rejected. Tackling is a core job requirement for
safeties in a way it is not for CBs. A safety who excels in coverage but misses
tackles in space is not an elite player. The 30% tackling weight reflects real
positional value.

**Angles/context for missed tackles:** PFR does not publish angle or distance
data for missed tackles. The raw rate is accepted as-is.

## Consequences

- Safety grades available from 2018–present.
- Pipeline requires: `pfr_advstats_def`, `nflvs_player_stats`, and
  `player_seasons.snaps_defense`.
- Missed tackle data availability depends on the pfr_advstats_def column
  release; the component may be NaN-neutralized for some seasons. This will
  be revisited in v1.1 once data availability is confirmed for all seasons.
- Seasons 2016–2017 return no Safety grades (same PFR limitation as CB).
- To regenerate grades: `nflgrades grade --position S --season <year>` for
  all seasons 2018–2025.

## Revision History

**2026-05-14 (passer-rating revision):** Replaced three components — `s_comp_pct_allowed` (−0.13), `s_yards_per_target_allowed` (−0.08), and `s_int_rate` (+0.13) — with a single `s_passer_rating_allowed` component at weight −0.30. Reduced `s_pbu_rate` from +0.15 (PBU+INT bundle) to +0.12 (PBU-only) since INTs are now inside passer rating allowed. Tackling components unchanged. Required schema migration `0013_safety_tds_allowed.sql` to add `tds_allowed` to `pfr_def_coverage_s` (CB table already had it).

**Why:** Passer rating allowed is the industry-standard NFL coverage metric and is the single cleanest safety skill signal we have. It penalizes TDs allowed (v1 didn't capture this at all) while still rewarding INTs and forced incompletions. 2024 face-check confirmed Kerby Joseph (9 INTs, First-Team All-Pro) #1, Xavier McKinney (8 INTs, Pro Bowl) #2, Derwin James #3, Brian Branch #5.

**Known limitation:** Kyle Hamilton (universally regarded top-3 safety) grades #13 in 2024 because his disguised-coverage style produces fewer direct target events. This is the same "stats vs film" gap noted for LB v1.1.

**Weight totals:** v1 sum |abs| = 0.82 → v1.1 sum |abs| = 0.75. Same coverage/tackling proportion (~67/33).
