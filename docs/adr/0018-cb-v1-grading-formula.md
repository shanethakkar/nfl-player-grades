# ADR-0018: CB v1 Grading Formula

**Status:** Accepted  
**Date:** 2026-05-12

## Context

CB grading is the first defensive position in the system. The core challenge is
data: nflverse play-by-play records which defender broke up or intercepted a pass
(`pass_defense_1_player_id`, `interception_player_id`), but it does **not** record
which CB was in coverage on completions. This makes PBP-only CB metrics severely
biased — we can count PBUs and INTs, but not completions allowed or yards surrendered.

**Data sources:**
- **Coverage stats** (targets, completions, yards, YAC, TDs, INTs): PFR Advanced
  Defensive Stats via `nflreadpy.load_pfr_advstats(stat_type="def")`. The only
  free, publicly available source with full coverage-side metrics per CB per season.
- **Pass breakups (PBU):** nflverse weekly player stats via `nflreadpy.load_player_stats()`,
  column `def_pass_defended`. PFR's advstats feed in nflreadpy does not expose PBUs;
  nflverse box-score stats do, with ~78% of CBs recording non-zero values in a typical
  season. CBs absent from that source get NULL `pass_breakups` (NaN-neutralized in
  the composite).

**Coverage:** 2018+ only. PFR began publishing per-CB target/completion data in 2018.
Seasons 2016–2017 have no CB grades. (Historical backfill may be possible from
PFR's web archive in a future version.)

## Decision

### Metric Set

| Component | Weight | k (shrinkage) | Direction | Rationale |
|---|---|---|---|---|
| `cb_comp_pct_allowed` | −0.22 | 50 | Lower is better | Primary coverage quality signal. Completion % allowed is the most direct measure of how often a CB wins his rep. k=50 ≈ half-season targets. |
| `cb_yac_per_rec_allowed` | −0.18 | 50 | Lower is better | Post-catch run-after-catch reflects both cushion allowed and tackling ability near the catch point. YAC is available from PFR for most seasons; if absent for a season, the component is NaN-neutralized. |
| `cb_td_rate` | −0.07 | 80 | Lower is better | TD prevention matters but event frequency is very low (r<0.15 YoY). High k=80 shrinks heavily toward mean. Small weight avoids penalizing a CB whose one TD allowed came on a scramble drill. |
| `cb_int_rate` | +0.10 | 80 | Higher is better | INTs are good but highly variable — luck (drops, tipped balls) dominates at low sample sizes. k=80 same as TD rate. Slightly reduced vs original plan to balance alongside PBU. |
| `cb_pbu_rate` | +0.09 | 80 | Higher is better | Pass breakups per target. Active defense that stops the play without a turnover. Sourced from nflverse `def_pass_defended`. High k=80 (noisy event). Weighted slightly below INT since PBU is ~3× more frequent but lower value per play. |

**Weight magnitudes:** comp% 33% + YAC 27% + INT 15% + PBU 14% + TD 11% = 100%
(the combiner normalizes by sum of |weights| = 0.66).

**Why no yards/target component?**
Yards per target combines comp% and YAC into one number and was considered as a simpler
alternative. We chose the decomposed version (comp% + YAC separately) because:
1. They measure different things: comp% = CB's ability to prevent the catch; YAC = cushion/tackling after.
2. They have different YoY reliability and warrant different k values.
3. The decomposed form gives the player profile page more granular insight.

### Qualification

- **Minimum targets to appear:** 25 (appears in the system with "low volume" badge).
- **Qualified threshold:** 30 targets (included in the percentile pool; typical for a
  starter who missed a few games or played in a zone-heavy scheme).
- **Confidence full at:** 60 targets (~4 targets per game for a full season starter).

### Role Classification

CBs are classified based on `slot_pct` from PFR:

| Role | Condition |
|---|---|
| `outside_cb` | slot_pct < 35% |
| `hybrid_cb` | 35% ≤ slot_pct ≤ 65% |
| `slot_cb` | slot_pct > 65% |

Role is **label-only** — z-scores are computed against the full CB pool, not within
role cohorts. With ~30–60 qualified CBs per season, splitting further would make
z-scores unstable. The role label lets fans understand why a Patrick Surtain grade
looks different from a Darius Slay grade.

If `slot_pct` is missing from the PFR data for a season, role is stored as NULL.

### Data Tier

CB grades inherit the standard era tier from `_era_tier_for_season`:
- 2018+: Tier 1 (full PBP+NGS era, per ADR-0003). CB data is PFR-sourced, not
  NGS, but PFR coverage data for this era is considered high quality.

### Empirical Bayes Shrinkage

Standard pipeline implementation (`empirical_bayes.shrink_series`). The "sample
size" denominator for all CB components is **targets**, for consistency across
the five metrics. (YAC's rate denominator is completions, but its EB denominator
is targets — this ensures YAC shrinks at the same rate as comp% for a given
number of targets, which is the right behavior since YAC is confounded by comp%.)

### NaN Handling

The same NaN-neutralization policy (ADR-0015) applies to all five components:
if a component's z-score is NaN (due to missing source data), it is replaced with
0.0 before entering the composite. The raw NULL is preserved in
`stat_components.z_score` so the UI renders "—" for that metric.

Known NaN sources:
- `cb_yac_per_rec_allowed`: NULL in `pfr_def_coverage.yac` for some seasons.
- `cb_pbu_rate`: NULL in `pfr_def_coverage.pass_breakups` for CBs absent from
  nflverse player_stats (edge cases: practice-squad call-ups, late-season additions).

## Alternatives Considered

**PBP `pass_defense_1_player_id` for PBU:** The play-by-play records a defender ID
on incomplete passes, but only for ~31% of incompletions (drops, overthrows, and
throwaway incompletions get no credit). Too noisy and systematically biased against
CBs who contest uncreditied balls. Rejected in favor of nflverse box-score stats.

**NGS defensive data:** NGS does not publish per-CB coverage stats in nflreadpy.
Considered but not available.

**ESPN Analytics coverage metrics:** Not publicly available via any free API.

**Yards per target instead of comp% + YAC:** Simpler, but merges two different
skills into one opaque number. See metric set rationale above.

## Consequences

- CB grades available from 2018–present.
- Pipeline requires two nflreadpy sources: `load_pfr_advstats(stat_type="def")`
  for coverage stats and `load_player_stats()` for PBU (`def_pass_defended`).
- Historical seasons 2016–2017 return no CB grades. If they become available later,
  re-running the ingest + grader for those seasons is sufficient (fully idempotent).
- YAC component may be absent in some early seasons (2018–2019). PBU component may
  be absent for edge-case CBs not in the nflverse player_stats source. Both are
  NaN-neutralized gracefully.
