# 0015 - WR v1 grading formula

- **Status**: Accepted (v1.2 revision — 2026-05-14)
- **Date**: 2026-04-22
- **Supersedes**: None
- **Companion to**: ADR-0013 (QB v1), ADR-0014 (RB v1). Same pipeline
  shape (extract -> shrink -> z -> composite -> sigmoid), different
  components, filters, and qualification thresholds.

## Context

Third concrete grading formula. QB v1 and RB v1 shipped; we're
extending the same architecture to WR. Three things distinguish WR
grading from the prior two:

1. **WRs have one skill**, not two. There's no RB-style dual-skill
   split (rushing + receiving), so there's one composite and no
   sub-grades in v1. "Route runner vs YAC monster" is interesting UI
   data viz but not a separate qualification bucket.
2. **NGS receiving publishes WRs cleanly** (unlike RBs, which NGS
   excludes). We get `avg_separation` and `avg_yac_above_expectation`
   on essentially all qualified WRs from 2016+.
3. **Target earn rate is a real signal for WRs** (unlike for RBs,
   where carries are decreed by scheme). WRs partly earn their
   targets by winning routes and forcing the QB's eye. This is a
   new component with no RB analog.

The grade is meant to answer "how well did this WR play the
receiving role this season?" — separated from usage-driven
accumulators (total yards, touchdowns, target share as a volume
stat).

## Decision

### Composite

```
grade = sigmoid(composite_z)

composite_z = 0.35 * z(shrunk_rec_epa_per_target)
            + 0.27 * z(shrunk_yac_over_expected_per_rec)
            + 0.10 * z(shrunk_separation)
            + 0.10 * z(shrunk_target_earn_rate)
            + 0.08 * z(shrunk_success_rate_per_target)
            - 0.05 * z(shrunk_fumble_rate)
```

Sum of magnitudes = 0.95. The composite combiner normalizes by
**sum of magnitudes** (not signed sum); fumble contributes at its
designed 5.3% share (0.05 / 0.95). This invariant is locked by
`test_signed_weights_normalize_by_magnitude` in
`pipeline/tests/grading/test_composite.py` and further reinforced
by `test_wr_v1_weights_example` which uses the exact
`WR_V1_WEIGHTS` dict.

Rough shape:

- **62% outcome-based**: EPA/target 35% + YAC-over-expected 27%
- **28% process + usage**: separation 10% + target earn rate 10% + success rate 8%
- **5% ball security**: fumble rate (negative)

- `z()` = within-position, within-season standardization against
  **qualified** WRs only (same helper as QB and RB).
- `sigmoid()` = `grading/sigmoid.py`, z=0 -> 50, z=+2 -> ~90.

### Why these weights

- **EPA at 35%, not 40%**. A single metric at 40% gives any
  systematic bias (QB quality, scripted touches, YAC-heavy offense)
  too much leverage. 35% keeps EPA the biggest contributor without
  dominating the composite.
- **YAC at 27%**. Highest-reliability WR signal after EPA. xYAC
  pre-adjusts for coverage state at the catch, so this is close to
  pure WR skill.
- **Target earn rate at 10%, not 22%**. Target share is
  structurally correlated with team environment (top QB, pass-heavy
  scheme, weak WR2 competition, weak TE/RB pass game). These
  confounds don't wash out across a season; they persist for
  players in stable situations. 10% captures the "QB looks at you"
  signal without letting offensive environment drive a fifth of
  the grade.
- **Separation at 10%, not 15%**. Process metric, not outcome;
  inflated by easy targets (screens, hitches); NGS measures
  at-catch rather than at-throw. Keep it modest.
- **Success rate at 8%**. Diversifies efficiency measurement away
  from pure EPA, but it's partly role-contaminated (slot checkdowns
  on 3rd-and-medium have a different success-rate baseline than
  outside verticals on 1st-and-10). 8% is a compromise — not 5%
  (which underweights a second efficiency lens), not 10% (which
  overweights a role-biased metric). Flagged as a face-check watch
  item: if slot specialists systematically outgrade deep threats,
  dial this back first.
- **Catch-rate-over-expected dropped entirely**. Every version of
  this from public data is either QB-contaminated (aggregated
  `plays.cpoe` per receiver rewards pairing with accurate QBs) or
  role-contaminated (raw NGS catch % punishes deep threats and
  rewards screen/flat receivers). Omitting a component is an
  honesty signal — PFF has proprietary charting for catchable
  targets; we don't. Surface raw catch % on the player page as
  context, keep it out of the composite.
- **Fumble rate at -5%**. Same rationale as RB v1.1: rare event,
  low YoY reliability, shrink hard.

### Per-component definitions (before shrinkage)

| Component | Raw value | Sample (n) | Source | Pre-adjusted |
|---|---|---|---|---|
| `wr_rec_epa_per_target` | mean of `plays.epa` on targets | targets | `plays` | No |
| `wr_yac_over_expected_per_rec` | mean of `plays.yards_after_catch - plays.xyac_mean_yardage` on completions with non-null xYAC | `n_rec_with_xyac` | `plays` (nflfastR xYAC) | Yes |
| `wr_separation` | `avg_separation` | targets | `ngs_receiving` (week=0) | Yes |
| `wr_target_earn_rate` | `n_targets / n_team_pass_att_active` | team pass attempts while active | `plays` | No |
| `wr_success_rate_per_target` | mean of `plays.success` on targets | targets | `plays` | No |
| `wr_fumble_rate` | rate of `plays.fumble` per reception | receptions | `plays` | No |

**Target earn rate denominator**: `n_team_pass_att_active` is the
sum of `posteam`'s regular-season pass attempts across the set of
`(posteam, game_id)` pairs that appear in the WR's own target
plays. This handles mid-season trades cleanly — each game's
denominator is its correct team's pass volume. The "had >=1 target"
proxy for active may slightly under-count games where the WR
played but wasn't targeted; for qualified WRs this is rare.

**Fumble denominator = receptions** (not targets): WRs only touch
the ball on completions. Keeps fumble rate comparable across
possession WRs and deep threats.

**Pre-adjusted flag**: `wr_yac_over_expected_per_rec` and
`wr_separation` are already context-adjusted by their upstream
models. When opponent adjustment lands in v2, these components
must be flagged so we don't double-adjust.

### Filter

A receiving play counts toward WR components iff ALL:

```
plays.season_type = 'REG'
plays.pass_attempt = TRUE
plays.receiver_player_id IS NOT NULL
plays.two_point_attempt IS NULL OR plays.two_point_attempt = FALSE
NOT garbage_time
```

Identical to the RB v1 receiving filter — reused verbatim from
`grading/filters.py::RB_REC_FILTER_SQL`. Garbage-time rule is the
one defined in ADR-0013.

The team-pass-attempts aggregate for the earn-rate denominator
uses the same filter so numerator and denominator are consistent
(both count REG-season, non-garbage, non-2pt pass attempts).

### Position assignment

A WR grade is issued iff `players.position = 'WR'`. A WR running a
jet sweep doesn't get rushing credit — this is a receiving grade
only. A TE/RB running routes out of the backfield doesn't get a WR
grade; they belong in their own position's pipeline.

### Empirical Bayes shrinkage

Per component, before z-scoring:

```
shrunk = (n * raw + k * mu_league) / (n + k)
```

where `mu_league` is the volume-weighted WR league mean (summed
over qualified and unqualified WRs, same convention as QB/RB v1).

`k` per component:

| Component | n units | k |
|---|---|---|
| EPA per target | targets | 50 |
| YAC over expected per rec | receptions scored by xYAC | 30 |
| Separation | targets | 40 |
| Target earn rate | team pass attempts while active | 200 |
| Success rate per target | targets | 50 |
| Fumble rate | receptions | 100 |

Separation's k (40) is slightly below the other per-target
components (50) because NGS separation has higher year-over-year
reliability than raw per-play efficiency metrics. Target earn rate
uses its natural denominator (team pass attempts) rather than
games — the EB formulation shrinks toward league-mean target share
weighted by the number of observations, which is the correct
statistical framing. k=200 team pass attempts is roughly 35% of a
team's regular-season pass volume.

### Handling missing data

Same policy as RB v1 (see ADR-0014 "Handling missing data"): any
NaN component z-score is replaced with 0 (neutral) before entering
the composite. `stat_components.z_score` keeps the true NaN so the
UI can render "-" rather than "0.0".

Practically, this matters most for:

1. WRs under NGS's separation volume threshold (rookies with
   partial seasons, or below the volume NGS publishes). Separation
   is NaN; z is NaN; composite substitutes 0.
2. A WR with 0 completions (only happens at the extreme
   low-volume end) has NaN YAC and NaN fumble rate.

The alternative — renormalizing composite weights per-player to
drop missing components — would re-introduce role-aware weighting,
which we explicitly want to avoid.

### Weight normalization invariant

The composite combiner normalizes by **sum of magnitudes**
(`sum(abs(w))`), not signed sum. A player at z=+1 on every
component (including fumble rate — where z=+1 means "fumbles a
lot") gets composite_z = (0.35 + 0.27 + 0.10 + 0.10 + 0.08 -
0.05) / 0.95 ≈ 0.894, and fumble penalizes at exactly its
designed 5.3% share rather than being amplified by a smaller
signed-sum denominator.

This is locked by `test_signed_weights_normalize_by_magnitude`
(added during RB v1.1) and by the new
`test_wr_v1_weights_example` which exercises the actual
`WR_V1_WEIGHTS` dict.

### Qualification thresholds

Two qualification concepts:

| Threshold | Rule | Purpose |
|---|---|---|
| Grade at all | `targets >= 20` | Excludes fringe WRs we can't say anything meaningful about |
| Composite qualified | `targets >= 50` | Rotational WR3 or better; appears in main leaderboard; defines z-score population |

~3/game over a full season is roughly the floor for "this player
got real route time." Tunable if face-check shows too many
marginal WR3s at the top or too many clear WR1s falling below.

All WRs with `targets >= 20` get a `season_grades` row; the
`qualified` column distinguishes them.

### Confidence

`season_grades.confidence = min(1, targets / 100)`. 100 targets is
~6/game — "real starter usage" rather than WR1 workload
(which would be ~120-140+). Pegging full confidence here gives
most healthy starters `confidence = 1` and reserves the fractional
band for genuine part-season / rotational players.

### Data tier

Per ADR-0003:

- **2016+**: tier 1 (PBP + NGS available; full formula computes).
- **Pre-2016**: out of scope for v1. The formula depends on NGS
  components (separation, xYAC availability) for 37% of weight.
  A pre-NGS fallback is deferred; call it a v2 concern.

## Validation expectations

Expect WR composite year-over-year Pearson `r` on 2+-season
samples in the band **0.45 - 0.60**.

Interpretation triggers:

- **Below 0.45** — methodology problem. Most likely a process
  component (separation or success rate) dominating noise over
  EPA/YAC. Investigate weight distribution and per-component
  reliability.
- **0.45 - 0.60** — the expected band. WR production is genuinely
  more defense-dependent than QB production, and we don't have
  CB matchup adjustment in v1.
- **Above 0.65** — suspicious. Likely means we're accidentally
  measuring *usage* (target volume, team context) rather than
  *skill*. Investigate whether target earn rate is pulling the
  stability or whether separation's metric-stability is doing
  more work than intended.

QB v1 for comparison was in the 0.60 - 0.70 band; WR's lower
ceiling is a data limit (no CB matchup data), not a grading
failure. Don't chase the QB number by tuning weights.

## Consequences

**Testability**: each stage is a pure function, same as prior
positions. Unit tests verify NaN neutralization, that a pure
separator outranks a non-separator with the same efficiency,
that the fumble penalty actually subtracts, and that the
composite normalization constant matches the hand-computed value
from `WR_V1_WEIGHTS`.

**Web app**: the existing leaderboard + player detail pages
render WRs as soon as `season_grades` has rows. A position
switcher on the home page is a separate follow-up (currently
hardcoded to QB; RB and WR both pending surfacing).

**Iteration**: weight and `k` changes are single-coefficient
edits in `weights.py`. Adding a new component (say, separation
at-throw once it becomes publicly available) is a new SQL CTE
and a new row in the weights dicts; no schema change.

## Deferred (v1.1+)

- **Target-per-route-run** — the clean v1.5 upgrade to target
  earn rate, replaces the "team pass attempts while active"
  proxy with a true "routes run" denominator. Requires
  routes-run data (PFF/FTN); not ingested.
- **Team-context-adjusted target earn rate** — regress target
  share on team pass volume + QB EPA, grade on the residual.
  ~30 lines of code, a v1.1 candidate if face-check shows earn
  rate rewarding bad-team-WR1s too generously.
- **Drop rate** — `plays` can't cleanly isolate drops from
  defended passes. Requires explicit drop charting.
- **Slot vs outside split** — no alignment data ingested. Face-
  check will tell us if the one-scale approach systematically
  biases one archetype.
- **Contested catch rate** — not available in public tracking
  data.
- **Red-zone / goal-line efficiency** — small sample, mostly
  role-driven.
- **Opponent adjustment, team-level** — same deferral as QB/RB
  v1. `wr_yac_over_expected_per_rec` and `wr_separation` must be
  flagged `pre_adjusted=True` to avoid double-adjustment.
- **CB matchup adjustment** — the v2+ work that would push YoY
  `r` from the 0.45-0.60 band toward QB-level 0.60-0.70.
  Requires per-target defender charting.

## References

- ADR-0013 — QB v1 grading formula (same pipeline architecture)
- ADR-0014 — RB v1 grading formula (shares receiving machinery,
  same NaN neutralization policy, same xYAC source for YAC-over-
  expected)
- ADR-0012 — NGS three-table layout (receiving table used for
  `avg_separation`)
- ADR-0011 — thin `plays` table (with `fumble` and
  `xyac_mean_yardage` added by migration 0005)
- ADR-0003 — data tiering

## Revision History

### v1.1 (2026-05-14) — drop_rate in, fumble_rate out

**Replaced `wr_fumble_rate` (−0.05) with `wr_drop_rate` (−0.08).** Sum |weights| now 0.98.

**Why fumble out:** YoY r for WR fumble rate across 2020-2024 oscillated around zero (−0.26, +0.09, −0.40, +0.27, mean ≈ −0.07). 56% of qualified WRs had 0 fumbles in 2024, 90% had ≤1 — sample too small for meaningful grading. Confirmed noise. Fumbles still penalized implicitly via `rec_epa_per_target` (a fumble play has negative EPA).

**Why drops in:** Drop rate is the only WR-skill gap our v1 didn't measure (deferred at v1 release because "plays can't cleanly isolate drops from defended passes"). FTN charting (now ingested as `ftn_receiving_charting`, available 2022+) flags `is_drop` and `is_catchable_ball` per play, joined to PBP `receiver_player_id`. Correlation audit (2024 qualified WRs, n=89) showed `drop_rate` has max \|r\|=0.21 against every other component — fully independent signal. 2024 face-check matched consensus (best hands: McLaurin, Shakir, Kupp, Addison, Hopkins, ARSB; worst hands: George Pickens 6 drops, Allen Lazard 7, Xavier Legette 5).

**Weight sizing:** −0.08 chosen because drops have known data-quality caveats (FTN more conservative than PFF; some "0 drops on 40 catchable" entries are borderline). Bigger than the prior fumble weight because drops are ~10× more frequent and meaningfully discriminating; not so large that FTN's noise overwhelms the rest of the formula.

**Pre-2022 seasons:** No FTN data, so the `wr_drop_rate` component is NaN-neutralized to 0 contribution. 2016-2021 WR grades are effectively the v1 formula with fumble removed. This still works because z-scoring happens within-season and the player's grade is determined by the 5 remaining components.

**New schema:** Migration `0014_ftn_receiving_charting.sql` creates `ftn_receiving_charting` (player_id, season, catchable_balls, drops, contested_balls, created_receptions). Ingest module: `pipeline/src/nfl_grades/ingest/ftn_receiving.py`.

**Research notes:** Audit also considered WOPR (correlated 0.95 with target_share — redundant), RACR (target-depth artifact, not skill), NGS `avg_cushion` and `avg_intended_air_yards` (usage markers, not skills), and contested catch rate (correlated −0.71 with separation). None of these added meaningful independent signal. YPRR and CROE were considered but neither has source data in nflverse.

### v1.2 (2026-05-14) — lower drop_rate weight from −0.08 to −0.05

**Triggered by the TE v1.1 audit.** When auditing whether to add `te_drop_rate` for TE v1.1, we ran the YoY noise check on WR drop_rate after the fact — which v1.1 had skipped. Result across 2022-2025 qualified WRs (catchable_balls ≥ 50):

| Pair | n | r |
|---|---|---|
| 2022→2023 | 42 | +0.27 |
| 2023→2024 | 40 | −0.12 |
| 2024→2025 | 37 | +0.10 |

Mean YoY r = **+0.09** — statistically indistinguishable from the WR fumble rate we removed (mean −0.07). By the methodology's own rule (`reference_grading_methodology.md` Step 3: |r| < 0.20 → "weight tiny ≤ 0.05 or remove"), the v1.1 weight of −0.08 was over-weighted. The original v1.1 justification leaned on correlation independence + face-check, both of which still hold — but those only justify *inclusion at light weight*, not heavy weight.

**Why not remove entirely:** the metric still has real cross-sectional discrimination (std ~3%, max ~16%), captures a skill no other component covers, and face-checks correctly. At small per-player denominators (catchable median ~75), YoY r is mechanically depressed by measurement error even if the underlying skill is stable — so the face-check is stronger evidence than YoY r here. Light weight (−0.05) captures the real signal without overclaiming.

**Sum |weights| changes 0.98 → 0.95.** Other components unchanged. Re-graded WRs 2016-2025 on Neon. Expected impact: ≤1 grade-point shift per player for most WRs; no major rank shuffles. The biggest deltas land on extreme outliers (heavy droppers ranked slightly higher; clean-hands WRs ranked slightly lower).

**Symmetric with TE v1.1**, which also lands `te_drop_rate` at −0.05 for the same reason. See ADR-0016 and `memory/project_te_v1_1_research.md` for the full self-audit.

**Follow-up:** before any more positions ship, run the YoY noise check across every component in every shipped position. The WR drop_rate gap means other components added without YoY verification may also be over-weighted. Tracked in `memory/project_pending_audits.md`.
