# Cross-position YoY Audit — 2026-05-14

Run after TE v1.1 + WR v1.2 shipped. Output: every (position, component) pair with mean YoY r across 2018-2025 (or 2016-2025 for offensive positions). Threshold: weight > 0.05 + mean r < 0.20 → flag.

## Key insight from the audit

The 0.20 threshold catches **two different failure modes** that need different responses:

1. **Pure noise** — both YoY r AND cross-sectional discrimination weak. Remove or weight-tiny. Example: WR fumble_rate (mean r −0.07, 90% of qualified WRs had 0-1 fumbles).
2. **Team-context-dependent skill** — wide cross-sectional discrimination, but YoY-unstable because team context varies year-to-year. Real in-season measurement, weak across-season stability. Example: WR rec_epa_per_target (mean r 0.171; high cross-sectional spread; depends on QB).

The methodology playbook ([../audit-playbook.md](../audit-playbook.md)) was updated to distinguish these. Don't apply the same 0.20 rule uniformly.

## Three noise components flagged for weight reduction

| Position | Component | Old | Mean YoY r | New |
|---|---|---:|---:|---:|
| RB | `rb_rec_epa_per_target` | **+0.18** | **0.027** | +0.05 (v1.2) |
| iDL | `idl_missed_tackle_rate` | **−0.15** | **0.080** | −0.05 (v1.1) |
| LB | `lb_pbu_rate` | **+0.08** | **0.085** | +0.05 (v1.1) |

**`rb_rec_epa_per_target` was the worst offender — mean YoY r = 0.027 on a +0.18 weight.** RBs as checkdown receivers have per-target EPA driven mostly by QB choice and game state. Cross-section also weak — RBs cluster on this metric. Lowered to +0.05; freed +0.13 reallocated to `rb_yac_over_expected_per_rec` (mean r 0.205) to preserve the receiving share at 33%.

`idl_missed_tackle_rate` mean r 0.080 — even weaker than fumble/drop rate. Lowered to −0.05.

`lb_pbu_rate` mean r 0.085 — same pattern. Lowered to +0.05. (INTs already captured inside lb_passer_rating_allowed, so this was a narrow "broke up catch" signal even before the weight cut.)

## Team-context-dependent components (kept, with documentation)

These all have weight > 0.05 and mean YoY r in 0.10-0.20 range. **Cross-sectional discrimination is wide** (the metric meaningfully separates good from bad in a given season), but YoY r is low because team context changes (QB changes for WRs, opposing WRs change for CBs, etc.). Keep at current weights; document the limitation in each ADR.

| Position | Component | Weight | Mean YoY r |
|---|---|---:|---:|
| WR | rec_epa_per_target | +0.35 | 0.171 |
| CB | passer_rating_allowed | −0.35 | 0.126 |
| S | passer_rating_allowed | −0.30 | 0.143 |
| LB | passer_rating_allowed | −0.27 | 0.146 |
| CB | yac_per_rec_allowed | −0.15 | 0.174 |
| RB | rush_epa_per_attempt | +0.18 | 0.145 |
| RB | rush_success_rate | +0.14 | 0.141 |
| CB | pbu_rate | +0.12 | 0.189 |

These are mostly **EPA-based or passer-rating-allowed metrics**, all of which structurally absorb team-context signal. The pre-existing WR validation expectation (composite YoY r 0.45-0.60 with no CB matchup adjustment) already accounts for exactly this kind of structural noise. Lowering these weights would gut the formula's primary in-season measurement.

## Components that pass cleanly (mean r ≥ 0.20)

QB all three. WR yac/sep/earn/success (sep at 0.57, earn at 0.68, beautiful). TE everything (0.39-0.60 range — TE formula is the cleanest by this measure). S target_rate (0.43), tackles/snap (0.50), backfield_disruption (0.42). EDGE pressure_rate (0.64), sack_rate (0.41), tfl_rate (0.36). iDL pressure_rate (0.69!), tfl_rate (0.37), sack_rate (0.45). LB tfl_rate (0.31), tackle_rate (0.48), pressure_rate (0.41).

## Borderline (within ±0.02 of threshold) — leave alone

- `edge_missed_tackle_rate` (0.195)
- `s_pbu_rate` (0.200)
- `wr_drop_rate` (0.161) — already at light −0.05
- `te_drop_rate` (0.128) — already at light −0.05
- `rb_fumble_rate` (0.138) — already at light −0.05

## Actions shipped 2026-05-14

1. ~~**RB v1.2**~~ **SHIPPED**: `rb_rec_epa_per_target` lowered +0.18 → +0.05; freed weight to `rb_yac_over_expected_per_rec` (+0.15 → +0.28). Receiving share preserved at 33%. Re-graded 2016-2025 on Neon. First production use of the new preview/regrade workflow. See ADR-0014 v1.2.
2. ~~**iDL v1.1**~~ **SHIPPED**: `idl_missed_tackle_rate` lowered −0.15 → −0.05. Sum |w| 0.95 → 0.85 (combiner renormalizes; signal-strong positives get more effective share). Face-check: top 3 unchanged, Quinnen Williams rises 16→9. See ADR-0021 v1.1.
3. ~~**LB v1.1**~~ **SHIPPED**: `lb_pbu_rate` lowered +0.08 → +0.05. Sum |w| 0.90 → 0.87. Face-check: top 4 unchanged. See ADR-0022 v1.1 (second revision).
4. ~~**Build preview + codegen + skip-extract tooling**~~ **SHIPPED**. See [../iteration-workflow.md](../iteration-workflow.md).
5. ~~**Methodology playbook update**~~ **SHIPPED**. See [../audit-playbook.md](../audit-playbook.md).

## What worked, what didn't in the methodology

The 0.20 threshold caught real noise (the 3 flagged components above). But it also flagged 8 components that aren't noise per se — they're team-context-dependent skill measurements. **A strict threshold without nuance would gut the formula.**

The right framing seems to be:

- **Rate-event metrics** (fumble, drop, missed tackle, PBU, sack, INT): apply 0.20 threshold strictly. Below = noise. Both YoY r AND cross-sectional spread tend to be weak together when these are noise.
- **Production efficiency metrics** (EPA, passer rating allowed, success rate): expect 0.10-0.30 range. The low YoY reflects structural team-context dependence. Cross-sectional spread is wide — the metric still meaningfully separates good from bad in-season. Keep at chosen weight; document limitation.

Need to add a "cross-sectional discrimination check" alongside the YoY check: a metric is **noise** only if BOTH YoY r is low AND cross-sectional spread is narrow. If cross-sectional spread is wide but YoY r is low, it's a context-dependent measurement, not noise.

## Reference: full audit table

(Run on Neon 2026-05-14 — qualified player-seasons only.)

| Pos | Component | Weight | n | Mean YoY r |
|---|---|---:|---:|---:|
| QB | epa_per_dropback | +0.50 | 344 | 0.412 |
| QB | cpoe | +0.25 | 344 | 0.395 |
| QB | success_rate | +0.25 | 344 | 0.454 |
| RB | ryoe_per_attempt | +0.28 | 353 | 0.246 |
| RB | rush_epa_per_attempt | +0.18 | 452 | 0.145 |
| RB | rush_success_rate | +0.14 | 452 | 0.141 |
| RB | rec_epa_per_target | +0.18 | 452 | **0.027** |
| RB | yac_over_expected_per_rec | +0.15 | 452 | 0.205 |
| RB | fumble_rate | −0.05 | 452 | 0.138 |
| WR | rec_epa_per_target | +0.35 | 822 | 0.171 |
| WR | yac_over_expected_per_rec | +0.27 | 822 | 0.326 |
| WR | separation | +0.10 | 822 | 0.565 |
| WR | target_earn_rate | +0.10 | 822 | 0.676 |
| WR | success_rate_per_target | +0.08 | 822 | 0.291 |
| WR | drop_rate | −0.05 | 322 | 0.161 |
| TE | rec_epa_per_target | +0.35 | 332 | 0.390 |
| TE | yac_over_expected_per_rec | +0.27 | 332 | 0.481 |
| TE | separation | +0.07 | 332 | 0.404 |
| TE | target_earn_rate | +0.10 | 332 | 0.598 |
| TE | success_rate_per_target | +0.08 | 332 | 0.406 |
| TE | drop_rate | −0.05 | 138 | 0.128 |
| CB | passer_rating_allowed | −0.35 | 946 | 0.126 |
| CB | yac_per_rec_allowed | −0.15 | 946 | 0.174 |
| CB | target_rate | −0.08 | 946 | 0.282 |
| CB | pbu_rate | +0.12 | 946 | 0.189 |
| S | passer_rating_allowed | −0.30 | 625 | 0.143 |
| S | pbu_rate | +0.12 | 625 | 0.200 |
| S | target_rate | −0.08 | 625 | 0.425 |
| S | tackles_per_snap | +0.07 | 625 | 0.497 |
| S | missed_tackle_rate | −0.09 | 625 | 0.247 |
| S | backfield_disruption | +0.09 | 625 | 0.420 |
| EDGE | pressure_rate | +0.35 | 633 | 0.644 |
| EDGE | sack_rate | +0.30 | 633 | 0.414 |
| EDGE | tfl_rate | +0.15 | 633 | 0.362 |
| EDGE | missed_tackle_rate | −0.10 | 633 | 0.195 |
| iDL | tfl_rate | +0.35 | 563 | 0.371 |
| iDL | pressure_rate | +0.30 | 563 | 0.689 |
| iDL | sack_rate | +0.15 | 563 | 0.450 |
| iDL | missed_tackle_rate | −0.15 | 563 | **0.080** |
| LB | tfl_rate | +0.20 | 430 | 0.314 |
| LB | passer_rating_allowed | −0.27 | 430 | 0.146 |
| LB | missed_tackle_rate | −0.15 | 430 | 0.232 |
| LB | pbu_rate | +0.08 | 430 | **0.085** |
| LB | tackle_rate | +0.13 | 430 | 0.475 |
| LB | pressure_rate | +0.07 | 430 | 0.407 |
