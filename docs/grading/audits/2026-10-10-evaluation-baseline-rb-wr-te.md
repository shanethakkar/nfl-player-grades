# Evaluation baseline: RB, WR, TE — 2026-10-10

The current RB, WR and TE Formulas, scored by `nflgrades evaluate` (#13,
ADR-0029). This is the "before" for the Formula reworks (#15 shrinkage, #16
WR/TE, #17 RB). Read the [audit playbook](../audit-playbook.md) for what the
metrics mean and the ship rule.

Read-only against Neon, 2016–2025 completed seasons. Fit window 2016–2022;
hold-out 2023–2025.

```bash
nflgrades evaluate --position RB    # likewise WR, TE
python scripts/verify_evaluation_panels.py RB WR TE
```

## Reproduction

The harness's full-season split goes through each grader's own
`extract_features` and the same shrink → z → Composite path. Every Qualified
player-season's raw Component values match `stat_components.raw_value`
exactly: 3,164 RB rows, 4,932 WR rows and 1,992 TE rows. Composites match
`season_grades.composite_z` to ≤ 1e-15 in every season but three:

| Position-season | max \|Δ composite_z\| | Cause |
|---|---|---|
| RB 2025 | 2.4e-3 | Zavier Scott's `players.position` changed since the season was graded |
| TE 2022, TE 2023 | 5.6e-4, 5.5e-3 | Connor Heyward is now listed RB |

(QB 2023 has the same issue: Malik Cunningham is now listed WR.) In each case
the harness matches the grader re-run today to ≤ 7e-16. The stored grade is
stale. `players.position` is global, so the 2026 roster ingest changes which
players fall in an older season's shrinkage population. These seasons were not
regraded here.

## Formula baseline

Pearson r with Fisher-z 95% CIs (which run a little narrow; see the playbook).
QB is shown for reference.

### Hold-out 2023–2025

| Metric | QB | RB | WR | TE |
|---|---|---|---|---|
| Reliability (odd/even, S-B) | +0.69 [+0.55, +0.79] n=112 | +0.27 [−0.03, +0.48] n=133 | +0.56 [+0.43, +0.66] n=239 | +0.38 [+0.09, +0.58] n=107 |
| Portability (changers YoY) | +0.19 [−0.46, +0.71] n=11 | +0.36 [−0.22, +0.75] n=14 | −0.04 [−0.48, +0.41] n=20 | −0.21 [−0.92, +0.83] n=5 |
| YoY, all | +0.37 [+0.11, +0.58] n=54 | +0.24 [−0.01, +0.46] n=63 | +0.33 [+0.15, +0.48] n=113 | +0.49 [+0.25, +0.68] n=51 |
| YoY, stayers | +0.33 [+0.03, +0.57] n=43 | +0.23 [−0.06, +0.48] n=49 | +0.38 [+0.19, +0.54] n=93 | +0.55 [+0.30, +0.72] n=46 |
| Composite N → primary N+1 | +0.39 [+0.14, +0.60] n=54 | +0.17 [−0.08, +0.40] n=63 | +0.17 [−0.02, +0.34] n=113 | +0.45 [+0.21, +0.65] n=51 |
| Pro Bowl r (face validity) | +0.55 [+0.36, +0.69] n=75 | +0.50 [+0.33, +0.65] n=85 | +0.40 [+0.26, +0.52] n=163 | +0.38 [+0.15, +0.56] n=69 |

### Fit 2016–2022

| Metric | QB | RB | WR | TE |
|---|---|---|---|---|
| Reliability (odd/even, S-B) | +0.62 [+0.50, +0.70] n=241 | +0.38 [+0.23, +0.50] n=319 | +0.38 [+0.27, +0.48] n=583 | +0.43 [+0.26, +0.56] n=225 |
| Portability (changers YoY) | +0.00 [−0.40, +0.40] n=24 | +0.15 [−0.23, +0.48] n=30 | +0.15 [−0.12, +0.39] n=56 | +0.04 [−0.38, +0.44] n=23 |
| YoY, all | +0.40 [+0.26, +0.53] n=154 | +0.34 [+0.20, +0.47] n=168 | +0.31 [+0.21, +0.41] n=329 | +0.55 [+0.41, +0.67] n=112 |
| YoY, stayers | +0.43 [+0.27, +0.56] n=130 | +0.35 [+0.20, +0.49] n=138 | +0.34 [+0.23, +0.44] n=273 | +0.61 [+0.46, +0.73] n=89 |
| Composite N → primary N+1 | +0.39 [+0.25, +0.52] n=154 | +0.27 [+0.12, +0.40] n=168 | +0.14 [+0.03, +0.25] n=329 | +0.45 [+0.29, +0.59] n=112 |
| Pro Bowl r (face validity) | +0.57 [+0.46, +0.67] n=172 | +0.40 [+0.28, +0.50] n=231 | +0.40 [+0.31, +0.47] n=414 | +0.38 [+0.24, +0.51] n=158 |

Primary Components: `qb_epa_per_dropback`, `rb_rush_epa_per_attempt`,
`wr_rec_epa_per_target`, `te_rec_epa_per_target`. For RB, rushing EPA/attempt
is the outcome every back has in every season. NGS RYOE covers about 50 RBs a
season and none before 2018.

## Each Component alone

Each row scores a one-Component Formula (weight ±1, signed as in the current
Formula, so a good value always reads positive). A row covers only the
players who have that Component, so its n can be below the Formula's (RYOE:
NGS-qualified backs, 2018+; drop rate: 2022+). The `n` row is the Formula's.

### RB

| Hold-out | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.27 | +0.36 | +0.24 | +0.23 | +0.17 | +0.50 |
| `rb_ryoe_per_attempt` (+0.28) | +0.33 | +0.61 | +0.22 | +0.11 | +0.06 | +0.47 |
| `rb_rush_epa_per_attempt` (+0.18) | +0.33 | −0.05 | +0.04 | +0.07 | +0.05 | +0.50 |
| `rb_rush_success_rate` (+0.05) | +0.27 | −0.45 | +0.01 | +0.12 | −0.04 | +0.32 |
| `rb_rec_epa_per_target` (+0.05) | +0.15 | +0.33 | +0.14 | +0.08 | +0.09 | +0.14 |
| `rb_yac_over_expected_per_rec` (+0.28) | +0.14 | +0.48 | +0.26 | +0.21 | +0.18 | +0.21 |
| `rb_yards_after_contact_per_carry` (+0.10) | +0.17 | +0.48 | +0.14 | +0.04 | +0.11 | +0.22 |
| `rb_fumble_rate` (−0.05) | +0.02 | +0.48 | +0.16 | +0.08 | +0.18 | +0.04 |
| n | 133 | 14 | 63 | 49 | 63 | 85 |

| Fit | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.38 | +0.15 | +0.34 | +0.35 | +0.27 | +0.40 |
| `rb_ryoe_per_attempt` (+0.28) | +0.19 | −0.04 | +0.39 | +0.44 | +0.14 | +0.33 |
| `rb_rush_epa_per_attempt` (+0.18) | +0.33 | −0.07 | +0.19 | +0.24 | +0.16 | +0.30 |
| `rb_rush_success_rate` (+0.05) | +0.37 | −0.01 | +0.22 | +0.26 | +0.15 | +0.19 |
| `rb_rec_epa_per_target` (+0.05) | +0.09 | +0.05 | +0.08 | +0.07 | +0.13 | +0.16 |
| `rb_yac_over_expected_per_rec` (+0.28) | +0.19 | +0.32 | +0.18 | +0.15 | +0.19 | +0.25 |
| `rb_yards_after_contact_per_carry` (+0.10) | +0.42 | +0.31 | +0.42 | +0.42 | +0.21 | +0.30 |
| `rb_fumble_rate` (−0.05) | −0.00 | +0.23 | +0.16 | +0.14 | −0.13 | +0.04 |
| n | 319 | 30 | 168 | 138 | 168 | 231 |

### WR

| Hold-out | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.56 | −0.04 | +0.32 | +0.38 | +0.17 | +0.40 |
| `wr_rec_epa_per_target` (+0.35) | +0.28 | +0.11 | +0.24 | +0.24 | +0.24 | +0.35 |
| `wr_yac_over_expected_per_rec` (+0.27) | +0.51 | −0.10 | +0.28 | +0.39 | +0.03 | +0.21 |
| `wr_separation` (+0.10) | +0.70 | +0.10 | +0.58 | +0.64 | −0.14 | −0.02 |
| `wr_target_earn_rate` (+0.15) | +0.90 | +0.64 | +0.67 | +0.69 | +0.15 | +0.50 |
| `wr_success_rate_per_target` (+0.05) | +0.49 | −0.20 | +0.21 | +0.29 | +0.15 | +0.30 |
| `wr_drop_rate` (−0.05) | −0.08 | +0.22 | +0.13 | +0.12 | +0.09 | +0.02 |
| n | 239 | 20 | 113 | 93 | 113 | 163 |

| Fit | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.38 | +0.14 | +0.31 | +0.34 | +0.14 | +0.39 |
| `wr_rec_epa_per_target` (+0.35) | +0.18 | +0.05 | +0.18 | +0.21 | +0.17 | +0.29 |
| `wr_yac_over_expected_per_rec` (+0.27) | +0.37 | +0.24 | +0.37 | +0.40 | +0.04 | +0.17 |
| `wr_separation` (+0.10) | +0.65 | +0.54 | +0.58 | +0.59 | −0.01 | −0.02 |
| `wr_target_earn_rate` (+0.15) | +0.88 | +0.63 | +0.67 | +0.67 | +0.06 | +0.52 |
| `wr_success_rate_per_target` (+0.05) | +0.38 | +0.14 | +0.34 | +0.37 | +0.17 | +0.29 |
| `wr_drop_rate` (−0.05) | −0.04 | n/a | n/a | n/a | n/a | +0.14 |
| n | 583 | 56 | 329 | 273 | 329 | 414 |

### TE

| Hold-out | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.38 | −0.21 | +0.49 | +0.55 | +0.45 | +0.38 |
| `te_rec_epa_per_target` (+0.35) | +0.21 | −0.28 | +0.43 | +0.50 | +0.42 | +0.18 |
| `te_yac_over_expected_per_rec` (+0.27) | +0.42 | +0.06 | +0.46 | +0.50 | +0.37 | +0.25 |
| `te_separation` (+0.07) | +0.37 | +0.68 | +0.50 | +0.49 | +0.06 | −0.01 |
| `te_target_earn_rate` (+0.15) | +0.85 | −0.06 | +0.51 | +0.56 | −0.08 | +0.58 |
| `te_success_rate_per_target` (+0.05) | +0.52 | +0.22 | +0.45 | +0.47 | +0.43 | +0.20 |
| `te_drop_rate` (−0.05) | +0.22 | −0.82 | −0.01 | +0.03 | +0.23 | −0.11 |
| n | 107 | 5 | 51 | 46 | 51 | 69 |

| Fit | Rel | Port | YoY | YoY stay | → prim N+1 | Pro Bowl r |
|---|---:|---:|---:|---:|---:|---:|
| **Formula** | +0.43 | +0.04 | +0.55 | +0.61 | +0.45 | +0.38 |
| `te_rec_epa_per_target` (+0.35) | +0.30 | +0.03 | +0.42 | +0.50 | +0.41 | +0.26 |
| `te_yac_over_expected_per_rec` (+0.27) | +0.39 | +0.31 | +0.52 | +0.55 | +0.29 | +0.16 |
| `te_separation` (+0.07) | +0.42 | +0.54 | +0.38 | +0.34 | −0.04 | −0.07 |
| `te_target_earn_rate` (+0.15) | +0.89 | +0.46 | +0.62 | +0.62 | +0.19 | +0.59 |
| `te_success_rate_per_target` (+0.05) | +0.33 | +0.14 | +0.46 | +0.50 | +0.36 | +0.24 |
| `te_drop_rate` (−0.05) | +0.36 | n/a | n/a | n/a | n/a | +0.16 |
| n | 225 | 23 | 112 | 89 | 112 | 158 |

## What stands out

These are for #15–#17 to test under the ship rule, not conclusions:

- **WR and TE target earn rate** is the most reliable Component at either
  position (S-B ≈ 0.85–0.90). For WRs it is also the most portable
  (≈ 0.64 in both windows). It carries 15% of the weight.
- **Receiving EPA/target**, the heaviest-weighted WR/TE Component, is among
  the least reliable (0.18–0.30). Team changers barely carry it over. This
  is the QB effect #16 targets.
- **Separation** is reliable and portable. It predicts neither next-season
  EPA nor Pro Bowls: it is a stable trait that the outcome doesn't follow.
- **RB**: the Formula's hold-out Reliability (+0.27) is below that of its
  rushing Components scored alone (EPA +0.33, and RYOE +0.33 on its smaller
  cohort). The low-reliability receiving and fumble Components are the
  likely drag. Yards after contact was the
  most reliable RB Component in the fit window (+0.42) but not in the
  hold-out (+0.17).
- **Drop rate** has near-zero Reliability at WR and no usable YoY sample.

## Caveats

- **Portability rests on very few pairs.** TE hold-out has 5 team changers,
  so it cannot block or support a change. RB has 14 and WR 20. The ship
  rule's Portability guard only fails closed when a metric can't be
  estimated at all (fewer than 4 pairs), so at TE it is close to
  uninformative.
- **RB RYOE halves come from NGS weekly rows**, which NGS publishes only for
  games with 10+ carries (about 84% of attempts), and shrinks it by those
  rows' attempts. The full season uses the NGS season summary and every
  carry, as the grader does, so stored grades are unchanged. Half-season
  RYOE therefore leaves out a back's low-volume games.
- **NGS separation** uses weekly rows (5+ targets per game) for the full
  season and both halves, as the grader always has.
- **FTN drop rate starts in 2022**, so the fit window has one season of it
  and no YoY pairs. **PFR yards after contact starts in 2018.**
- **TE blocking Formula.** The harness scores every TE on `TE_V1_WEIGHTS`.
  No blocking TE has been Qualified in 2016–2025, and an unqualified
  player's Formula never reaches a metric. `panels.py` raises if a Qualified
  blocking TE ever appears.
- **Halves pro-rate the minimum-to-grade bar** to half a season, as a
  mid-season Provisional grade would. The scored cohort is the full-season
  Qualified cohort in every split.

## Data changes made for this

FTN charting and PFR rush stats were stored only as season totals. Migration
0028 adds `ftn_receiving_weekly` and `pfr_rb_rush_weekly` (one row per
player per REG week). The ingests now write those, and the WR, TE and RB
graders sum them, so odd and even weeks can be summed separately. On Neon,
the weekly tables summed to the season tables exactly for every player-season
(2018–2026 PFR, 2022–2026 FTN) before the graders were switched over. The
old season tables are no longer written. A later migration drops them once
this code is deployed.
