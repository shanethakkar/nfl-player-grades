# Defensive Position Grading — v1 Lessons

EDGE (ADR-0020), iDL (ADR-0021), LB (ADR-0022) ship 2026-05-13/14.

## OLB misclassification (T.J. Watt problem)

nflverse classifies 3-4 OLB pass rushers as `LB`, not `EDGE`. Without a filter they dominate LB leaderboards via pass-rush production.

**Filter design that worked (LB v1):** target rate (`targets / snaps_defense >= 0.035`), not raw target count.

**Why a raw target threshold failed:** Andrew Van Ginkel 2024 had 22 targets (above a 20 threshold) but 922 snaps — 2.4% target rate. Pure off-ball LBs run 5-9% target rate. The rate-based filter cleanly separates them regardless of total snap count.

**OLB-gap closed 2026-05-14 (ADR-0020 v1.1):** EDGE grader now UNIONs `pfr_def_lb` rows where `position_played='LB'`, `pressures ≥ 25`, `target_rate < 3.5%`. Same skill formula, two source tables. Mutually exclusive with LB filter (no player graded twice). Parsons went from 2 graded seasons to 5; Watt now appears in EDGE leaderboards; ~15-30 more elite pass rushers per season are now graded.

**Discovery:** Found via player profile bug report — Parsons only showed 2 seasons because his nflverse `position_played` flipped between LB (2021/22/23/25) and EDGE (2024) year-to-year. Same pattern affects every 3-4 OLB.

## Per-snap rate inflation by role players

LB at the 400-snap qualified threshold (consistent with EDGE/iDL/S) had top-10 leaderboards dominated by 400-500-snap rotational specialists over 1000-snap every-down LBs. Their narrow usage (run-down only, or nickel-coverage only) produces per-snap rates that workhorses can't match.

**Fix for LB only:** raised QUALIFIED to 600 snaps (and FULL_CONFIDENCE to 900). EDGE/iDL/S keep 400/700 — those positions don't have the same role-player problem because their core stats (pressures, TFL) aren't as easily inflated by limited usage.

## "Stats vs reputation" disconnect for LBs

Fred Warner / Roquan Smith both graded mid-pack in 2024 by the formula. Both had statistically below-average years relative to their peaks; consensus elite reputation comes partly from snap-level film grading we can't replicate. Documented as a known limitation rather than a formula bug.

Expected LB YoY r band: 0.35-0.50 (much noisier than QB/WR). Below 0.35 → formula problem. Above 0.55 → measuring usage not skill.

## Ingest table separation

`pfr_def_pass_rush` (DL only — EDGE + iDL) vs `pfr_def_lb` (LB only). Separate tables because LB needs the full row (coverage + tackling + pass rush), while DL only needs pass rush + tackling. Both ingest from the same raw source (`pfr_advstats_def`), just filter on `position_played` differently.

## Mixed-case position codes (iDL)

The `iDL` code (not `IDL`) breaks two things by default:

1. `grading/run.py` does `position.upper()` — fixed to try exact match first.
2. `web/app/page.tsx` does `firstOf(positionParam)?.toUpperCase()` — fixed to case-insensitive `find()` against `POSITION_ORDER` returning canonical mixed-case form.

Both must match canonical casing or the position silently falls back to QB.

## Post-audit weight tweaks (2026-05-14)

After the cross-position YoY audit (see [../audits/2026-05-14-cross-position-yoy.md](../audits/2026-05-14-cross-position-yoy.md)):

- **iDL v1.1**: `idl_missed_tackle_rate` lowered −0.15 → −0.05. Mean YoY r was 0.080 (noise). Sum |w| 0.95 → 0.85; combiner renormalizes so signal-strong positives (TFL/pressure/sack) get more effective share. Top 3 unchanged 2024.
- **LB v1.1 (second revision)**: `lb_pbu_rate` lowered +0.08 → +0.05. Mean YoY r 0.085 (noise). INTs already captured inside `lb_passer_rating_allowed`. Top 4 unchanged 2024.

After the correlation audit ([../audits/2026-05-14-correlation.md](../audits/2026-05-14-correlation.md)):

- EDGE and iDL pressure/sack/TFL components correlate 0.57-0.78. **Partly designed overlap** (sack_rate as premium-event boost on pressure_rate per ADR-0020). Acknowledge in ADRs; don't undo.
