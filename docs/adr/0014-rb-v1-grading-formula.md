# 0014 - RB v1 grading formula

- **Status**: Accepted (v1.2 revision — 2026-05-14)
- **Date**: 2026-04-24
- **Updated**: 2026-05-14 (v1.1 catch_pct removed, v1.2 rec_EPA weight lowered — see "Revision History")
- **Supersedes**: None
- **Companion to**: ADR-0013 (QB v1). Same pipeline shape, different
  components and per-skill sample sizes.

## Context

Second concrete grading formula. QB v1 shipped (ADR-0013); we're
extending the same architecture (extract → shrink → z → composite →
sigmoid) to RB. Two things make RB harder than QB:

1. **Role variation is huge.** Derrick Henry (280 carries / 20
   targets) and Christian McCaffrey (220 / 100) are both elite by
   very different profiles. A naive single-composite formula would
   wrongly penalize a thumper's "bad" receiving or reward a pass-
   catching back's "easy" rushing.
2. **Raw RB stats reflect a lot of non-RB stuff** (OL quality, box
   counts, play-action, scheme). NGS RYOE and YAC-over-expected
   already try to strip this out, so they deserve meaningful weight.

We choose to handle (1) with **usage-aware empirical Bayes
shrinkage** — a pure thumper's receiving components shrink hard
toward the league mean (because their `n_targets` is small relative
to the shrinkage `k`) and contribute close to zero to the composite.
No explicit role detection is needed.

## Decision

### Composite

```
grade = sigmoid(composite_z)

composite_z = 0.28 * z(shrunk_ryoe_per_attempt)
            + 0.18 * z(shrunk_rush_epa_per_attempt)
            + 0.14 * z(shrunk_rush_success_rate)
            + 0.18 * z(shrunk_rec_epa_per_target)
            + 0.12 * z(shrunk_yac_over_expected_per_rec)
            + 0.05 * z(shrunk_catch_pct)
            - 0.05 * z(shrunk_fumble_rate)
```

Rush 60% / Rec 35% / Security 5%. Fumble rate enters with a negative
sign (fumbles are bad).

- `z()` = within-position, within-season standardization (same
  helper as QB; mean/SD computed from **qualified** RBs only).
- `sigmoid()` = existing `grading/sigmoid.py` tuned so
  `z = 0 → 50`, `z = +2 → ~90`.

### Per-component definitions (before shrinkage)

| Component | Raw value | Sample (n) | Source |
|---|---|---|---|
| `rb_ryoe_per_attempt` | NGS `rush_yards_over_expected_per_att` | carries | `ngs_rushing` (week=0) |
| `rb_rush_epa_per_attempt` | mean of `plays.epa` on rushes | carries | `plays` |
| `rb_rush_success_rate` | mean of `plays.success` on rushes | carries | `plays` |
| `rb_rec_epa_per_target` | mean of `plays.epa` on targets | targets | `plays` |
| `rb_yac_over_expected_per_rec` | mean of `plays.yards_after_catch - plays.xyac_mean_yardage` on completions | receptions scored by xYAC model (`n_rec_with_xyac`) | `plays` (nflfastR xYAC) |
| `rb_catch_pct` | `n_receptions / n_targets` (from `plays`, filter-matched) | targets | `plays` |
| `rb_fumble_rate` | `fumble` rate per touch (any fumble by ball carrier) | total touches | `plays` |

**Pre-adjusted flag**: `rb_ryoe_per_attempt` and
`rb_yac_over_expected_per_rec` are already context-adjusted by their
upstream models (NGS's RYOE model and nflfastR's xYAC model
respectively). When opponent adjustment lands in v2, these two
components must be flagged so we don't double-adjust.

**Catch-% source**: NGS's `load_nextgen_stats("receiving")` only
publishes rows for WR/TE — RBs are never included regardless of
target volume. For v1 we derive catch % directly from `plays`:
`n_receptions / n_targets`, with the same garbage-time / 2-pt
filter as the rest of the receiving components. No expected-catch
baseline is applied (none is available); we accept the limitation
because RB target diet is relatively uniform (mostly short routes)
and the component's weight is only 5%.

**YAC-over-expected source**: same NGS-receiving RB gap — we
instead use nflfastR's `xyac_mean_yardage` column published on
every completion in `plays`. For each RB reception with a non-null
`xyac_mean_yardage`, the residual `yards_after_catch -
xyac_mean_yardage` is the RB's YAC over expected on that play. We
average across the RB's receptions (filter matches the rest of the
receiving components). Coverage on RB completions in the modern
era is >99% (≈0.9% null in 2024), so sample size effectively equals
`n_receptions`. See v1.1 refinement section below.

**Fumble rate**: computed from `plays.fumble` (any fumble by the
ball carrier, not just ones recovered by the defense). Counted on
both rushing and receiving plays within the same per-skill filters
as the production metrics. See v1.1 refinement section below.

### Filter

A rushing play counts toward the rushing components iff ALL:

```
plays.season_type = 'REG'
plays.rush_attempt = TRUE
plays.rusher_player_id IS NOT NULL
plays.qb_kneel  IS NULL OR plays.qb_kneel  = FALSE
plays.qb_scramble IS NULL OR plays.qb_scramble = FALSE   -- scrambles aren't RB production
plays.two_point_attempt IS NULL OR plays.two_point_attempt = FALSE
NOT garbage_time
```

A receiving play counts toward the receiving components iff ALL:

```
plays.season_type = 'REG'
plays.pass_attempt = TRUE
plays.receiver_player_id IS NOT NULL
plays.two_point_attempt IS NULL OR plays.two_point_attempt = FALSE
NOT garbage_time
```

Garbage-time rule is identical to ADR-0013:

```
garbage_time =
    (qtr >= 4 AND ABS(score_differential) > 21)
 OR (qtr  = 4 AND game_seconds_remaining < 300
                 AND ABS(score_differential) > 14)
```

### Position assignment

A player grades as RB iff `players.position = 'RB'`. We grade from
the master players table (not `player_seasons.position_played`) so
that a rookie who changed teams mid-season still gets one grade per
player, not one per team stint.

Non-RBs with rushes (scrambling QBs, WR jet-sweepers, gadget TEs)
don't get an RB grade — the feature query joins on
`players.position = 'RB'`.

### Empirical Bayes shrinkage

Per component, before z-scoring:

```
shrunk = (n * raw + k * mu_league) / (n + k)
```

where `mu_league` is the volume-weighted RB league mean (summed over
qualified *and* unqualified RBs, same convention as QB v1).

`k` per component (picked so `n == k` means "half-shrunk toward
league mean"):

| Component | `n` column | `k` |
|---|---|---|
| `rb_ryoe_per_attempt` | carries | 100 |
| `rb_rush_epa_per_attempt` | carries | 100 |
| `rb_rush_success_rate` | carries | 100 |
| `rb_rec_epa_per_target` | targets | 40 |
| `rb_yac_over_expected_per_rec` | receptions scored by xYAC (`n_rec_with_xyac`) | 30 |
| `rb_catch_pct` | targets | 40 |
| `rb_fumble_rate` | total touches | 200 |

The large `k` on fumble rate is deliberate — fumble rate (even with
the recovery coin-flip removed by switching from `fumble_lost` to
`fumble`) still has weak year-over-year reliability (~r=0.1-0.2),
so we shrink hard.

### Handling missing data

Some RBs are below NGS's volume thresholds and won't have
`ngs_rushing` season-summary rows. Our joins are LEFT JOINs and the
missing metrics come through as NaN with `n = 0`. Similarly, an RB
with no receptions has NaN receiving metrics.

**Policy**: before combining into the composite, *any* NaN
component z-score is replaced with 0 (neutral). This covers three
distinct "no data" cases under a single rule:

1. A pure thumper with `n_targets = 0` has NaN receiving z-scores.
2. A pass-game specialist with 15 carries (under NGS's rushing
   volume threshold for RYOE) has a NaN z for RYOE even though
   their `n_carries > 0`.
3. Some RBs may be missing NGS rushing rows for the season entirely
   (e.g. rookies whose first week was postseason).

All three collapse to "no evidence on this skill = assume league
average on this skill". The alternative — renormalizing composite
weights per-player to drop missing components — would re-introduce
role-aware weighting, which we explicitly wanted to avoid.

The `stat_components.z_score` column keeps the true NaN for these
rows so the UI can render "—" rather than "0.0" and be honest about
what we don't know. Only the composite calculation substitutes 0.

### Qualified thresholds

Three separate qualification concepts, because RBs have two skills:

| Threshold | Rule | Purpose |
|---|---|---|
| Grade at all | `touches >= 30` | Excludes fringe players we can't say anything meaningful about |
| Composite qualified | `touches >= 120` | "Real contributor" — appears in main leaderboard |
| Rushing sub-grade qualified | `carries >= 80` | Rushing sub-grade displays; else "—" |
| Receiving sub-grade qualified | `targets >= 40` | Receiving sub-grade displays; else "—" |

`120 touches` is roughly 7-8 touches/game over a full season — half
a full-season bell cow's workload, or all of a receiving specialist
like Ekeler. Tunable if the face-check shows too many marginal
committee backs at the top.

All backs with `touches >= 30` get a `season_grades` row; the
`qualified` column distinguishes them.

### Sub-grades

The `season_grades` row holds the **composite grade** only. Sub-
grades (rushing / receiving) are computed **at read time** in the
web app by combining the already-z-scored component rows in
`stat_components`. No schema change.

Rushing sub-grade z =
`(0.28*z_ryoe + 0.18*z_rush_epa + 0.14*z_rush_success) /
 (0.28 + 0.18 + 0.14)` then sigmoid to 0-100.

Receiving sub-grade z =
`(0.18*z_rec_epa + 0.12*z_yac_over_exp + 0.05*z_catch) /
 (0.18 + 0.12 + 0.05)` then sigmoid to 0-100.

A sub-grade renders as "—" when the sample-size threshold for that
skill isn't met. This is purely a UI convention — the composite
grade in `season_grades` is unaffected.

### Confidence

`season_grades.confidence = min(1, touches / 250)`. 250 touches is
roughly a full-season starter's workload; anyone at/above that gets
`confidence = 1`.

### Data tier

Per ADR-0003:

- 2016+: tier 1 (PBP + NGS available; full formula computes).
- Pre-2016: **out of scope for v1**. The formula depends on NGS
  components (RYOE, YAC-over-expected, catch %) for 45% of weight.
  Backfilling a pre-NGS fallback is deferred.

## Consequences

**Testability**: each stage is a pure function (same as QB);
unit tests verify the "n=0 → z=0" neutralization, the sub-grade
threshold gating, and that dual-threat backs outrank specialists.

**Web app**: the existing leaderboard + player detail pages render
RBs as soon as `season_grades` has rows. A position switcher on the
home page is a one-component follow-up (bundle with WR/TE).

**Iteration**: weight and `k` changes are single-coefficient edits
in `weights.py`. Adding broken-tackle-rate from PFR is a new
component row, no schema change.

## v1.1 refinement (2026-04-22)

Two caveats from the original v1 were resolved by adding two
columns to `plays` (migration `0005_add_fumble_and_xyac_to_plays`)
and switching the RB grader's data sources:

1. **Fumble rate now uses `plays.fumble`** rather than
   `plays.fumble_lost`. Fumble-lost depends on who recovers (a
   near-coin-flip), making it strictly noisier than true fumble
   rate. The change is source-only — the weight (-0.05), the large
   shrinkage `k` (200), and the ball-carrier attribution rules are
   unchanged.

2. **YAC-over-expected now sourced from `plays.xyac_mean_yardage`**
   (nflfastR's xYAC model output on each completion) rather than
   `ngs_receiving.avg_yac_above_expectation`. Root cause: NGS's
   receiving product publishes zero RB rows regardless of target
   volume, so the NGS-based component collapsed to a NaN-then-
   neutralized 0 for effectively every RB, silently wasting its 12%
   composite weight. The xYAC column covers >99% of modern-era RB
   completions, so the component is now active signal.

Both changes preserve the existing composite weights, shrinkage
constants, qualification thresholds, and `pre_adjusted` flags — the
data sources change, the formula does not. Pre-adjusted remains
`True` for the YAC component (xYAC is still a per-play, context-
aware model — opponent adjustment in v2 must still skip this
component).

The `stat_components.component_name` strings remain the same
(`rb_fumble_rate`, `rb_yac_over_expected_per_rec`), preserving the
public contract with the web app.

## Deferred

- **Opponent adjustment**: same deferral as QB v1. When added, the
  RYOE and YAC-over-expected components must be flagged as
  `pre_adjusted: True` to avoid double-adjustment.
- **Broken-tackle rate** from PFR — valuable skill signal, but
  reliability needs cross-year validation before we weight it.
- **Red-zone / goal-line efficiency** — small sample, mostly usage-
  driven, skipped.
- **Two-point conversion efficiency** — same reasoning.
- **20+ yard breakaway rate** — potentially distinct signal from
  EPA, but correlation is high enough that we're dropping it for
  v1. Revisit if breakaway-archetype backs grade unfairly low.
- **Route participation / target share as a graded input** — no
  routes-run data ingested yet.
- **Forced-fumble attribution, recoveries-in-pileups** — deferred
  to a defensive-grading pass.
- **Usage labels** ("Feature / Committee / Specialist") derived
  from snap share. Nice UI add, not a grading change. v1.5.

## References

- ADR-0013 — QB v1 grading formula (same architecture)
- ADR-0003 — data tiering
- ADR-0011 — thin plays table (updated by migration 0005 to include
  `fumble` and `xyac_mean_yardage`)
- ADR-0012 — NGS three-table layout (rushing used; receiving
  intentionally not joined for RB grading)

## Revision History

### v1.1 (2026-05-14) — `rb_catch_pct` removed as noise

**Removed `rb_catch_pct` (+0.05). Bumped `rb_yac_over_expected_per_rec` from +0.12 to +0.15** to absorb the receiving-side weight slot. Sum |weights| now 0.98 (vs 1.00).

**Why catch_pct out:**
- YoY r across 2020-2024 oscillated around zero: −0.015, +0.035, +0.120, −0.322 (mean ≈ −0.05). Same shape as WR fumble rate that was removed in the parallel WR v1.1 audit.
- Catch_pct correlates 0.61 with `rb_rush_success_rate` — partial redundancy when it has signal at all. Backs who run consistently also catch checkdowns consistently; the metric was mostly stylistic, not a stable skill.
- Range 0.45-1.00 with std 0.099 in 2024 — variation exists but doesn't persist year-over-year, so it's measuring noise not skill.

**Why YAC-OE bumped (not redistributed elsewhere):**
- Receiving share would have dropped from 35% to 30% with a pure removal. Bumping YAC-OE by 0.03 keeps the receiving / rushing balance approximately intact (~33% receiving).
- YAC-OE has stronger YoY stability and lower overlap with other components than catch_pct did, so the weight is going to a higher-quality signal.

**What we audited and rejected:**
- **NGS rushing additions** (`efficiency`, `rush_pct_over_expected`, `avg_time_to_los`, `percent_attempts_gte_eight_defenders`): all either redundant with RYOE (\|r\|>0.74 in two cases) or non-skill usage markers. None added independent signal.
- **MTF / Missed Tackles Forced** (proposed by external grading discussion): not available in nflverse — FTN charting only has passing-play flags (`is_drop`, `is_catchable_ball`, etc.), not rushing-play forced-tackles. PFF-only stat.
- **Stacked-box adjustment as a coefficient**: rejected because NGS's RYOE expected-yards model already accounts for defender count in the box; layering an explicit box-count adjustment would double-correct.
- **Removing `rb_fumble_rate`**: considered (YoY r ≈ +0.07, weak) but kept — RB fumble distribution is genuinely discriminating (median 2, max 7, 54% have 2+) and within-season correlation with composite is meaningful (−0.27). Different from WR fumbles which were pure noise.

**Face-check after revision:** 2024 top 10 essentially unchanged at the top (Henry, Saquon, Gibbs). Josh Jacobs moved into the top 10 (previously sat just outside). 2023 top 10 with Christian McCaffrey #1 — unchanged.

**Audit methodology:** Skill-tree mapping → correlation analysis on 2024 qualified RBs (n=41) → YoY noise check across 2020-2024 → face-check. Same playbook as WR v1.1. See memory: `project_rb_v1_1_research.md` and `reference_grading_methodology.md` for the full process.

### v1.2 (2026-05-14) — `rb_rec_epa_per_target` lowered (noise), `rb_yac_over_expected_per_rec` bumped

**Lowered `rb_rec_epa_per_target` from +0.18 → +0.05; bumped `rb_yac_over_expected_per_rec` from +0.15 → +0.28.** Sum |weights| unchanged at 0.98. Receiving share of the formula stays at 33% — just rebalanced within receiving.

**Why rec_EPA weight slashed (not removed):** The cross-position YoY audit run after WR v1.2 / TE v1.1 found `rb_rec_epa_per_target` had mean YoY r = **+0.027 across 2016-2025** — the lowest of any component in the entire system. RB per-target EPA is largely a function of QB choice + game state (RBs are checkdown receivers) rather than RB skill. At +0.18 weight, this was the worst noise-to-weight ratio in any shipped grader.

Kept at +0.05 (not removed entirely) because (a) it still captures *some* outcome signal on the rare deep-target RB plays, (b) removing entirely would require schema changes to stat_components which are out of scope for a weight-only revision, and (c) at +0.05 the noise contribution to the composite is bounded.

**Why YAC-OE absorbs the freed weight (not RYOE):** YAC-OE has YoY r = 0.205 — modest but real signal, ~7× the rec_EPA signal. Moving the weight here preserves the formula's 60/33/5 rush/receive/security shape; the alternative (moving to RYOE) would have shifted the formula to rushing-heavy and disadvantaged pass-catching backs (McCaffrey-archetype). Within-receiving rebalance is the more conservative choice.

**Face-check:** 2024 top 5 essentially unchanged (Henry/Gibbs/Saquon/Bucky/Bijan). Biggest movers down: De'Von Achane (−5.5), Chase Brown (−5.4), James Cook (−4.3) — all receiving-EPA-heavy backs. Biggest movers up: Jonathan Taylor (+7.2), Josh Jacobs (+5.1), Joe Mixon (+3.9), James Conner (+3.2) — all YAC-OE-strong workhorses. Story is coherent: weight shifted from noise to signal, and players sort accordingly.

**Audit methodology + tooling note:** This was the first revision shipped via the new `preview` + `regrade` workflow. End-to-end shipping time (preview → weights.py edit → web sync → regrade 10 seasons → face-check) was ~30 seconds. See `memory/reference_formula_iteration_workflow.md`. Audit data in `memory/project_cross_position_yoy_audit.md`.
