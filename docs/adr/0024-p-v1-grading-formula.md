# ADR-0024 — P v1 Grading Formula

**Status:** Accepted (v1 audit-first release — 2026-05-14)
**Date:** 2026-05-14

---

## Context

Punters are the eleventh and final graded position in the foundation set. Designed audit-first per the locked methodology. The K v1.1 lesson (FGOE over raw rates) informed the candidate set — over-expected metrics were tested from the start.

**Audit finding (critical):** Unlike K, where FGOE per attempt cleanly dominated all alternatives, the analogous over-expected metric for P (EPA per punt) did **not** dominate raw rate metrics. `p_net_avg` beat `p_epa_per_punt` on both YoY reliability (+0.355 vs +0.269) and Pro Bowl validity (+0.166 vs +0.163). The K story does not generalize for punters because punt EPA mixes punter skill with opponent quality (returner, coverage), field position, and game state.

We therefore went with **Option B: multi-component formula composing the two strongest individual signals** (net average + inside-20 placement rate) plus a small block-rate penalty. Option A (single-component EPA per punt) was considered and rejected for lack of audit dominance.

**v1 scope:** all punting outcomes captured in nflverse pbp. No hangtime data (not available in nflverse).

---

## Data Sources

| Source | Columns | Coverage |
|---|---|---|
| `pbp` → `punter_stats` | punts, gross_yards, return_yards, net_yards, inside_20, touchbacks, blocked, fair_catches, out_of_bounds, downed, epa_total, long_punt | 2016+ |

Grain: one row per (player_id, season). Aggregated from pbp rows where `punt_attempt=1`, grouped by `punter_player_id`, REG-season only.

---

## Components (v1, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `p_net_avg` | net_yards / punts | **+0.55** | higher = better |
| `p_inside_20_rate` | inside_20 / punts | **+0.30** | higher = better |
| `p_blocked_rate` | blocked / punts | **−0.05** | lower = better |

Sum |weights| = 0.90. Normalized dynamically by `composite.combine`.

**Relative shares:** net average 61%, inside-20 placement 33%, block penalty 6%.

---

## Qualification (punt-count based)

| Threshold | Punts |
|---|---|
| MIN to grade | 25 |
| QUALIFIED (main leaderboard) | 40 |
| Full confidence | 60 |

Most starting punters have 50-80 punts per season. 40-punt threshold filters mid-season callups and committee splits without being overly restrictive.

---

## Shrinkage k Values

| Component | k | Rationale |
|---|---|---|
| `p_net_avg` | 10 punts | Light — starters have 50-80 punts |
| `p_inside_20_rate` | 15 punts | Moderate — bucketed event, ~30% league-wide |
| `p_blocked_rate` | 30 punts | Heavy — blocks very rare (1-2/season per punter); shrink toward league mean |

---

## Design Rationale

**Net average dominant (+0.55):** Net yards per punt captures the actual field-position outcome — both punter leg strength (gross distance) and coverage-team / placement performance (return prevention). The audit found this is the most YoY-stable signal in the punter feature set (+0.355) AND the second-highest validity (+0.166). Net is also already implicitly risk-asymmetric: touchbacks cap the net (ball gets placed at the 20 regardless of how far the punt traveled), so a punter who blasts everything past the goal line gets credit only up to the touchback line.

**Inside-20 rate (+0.30):** Captures placement skill — the ability to angle a punt so it pins opponents deep without bouncing into the endzone. This is **orthogonal to net avg**: a 40-yard punt downed at the 5 looks identical to a 40-yard punt downed at the 35 by net average. The audit gave this the highest validity (+0.188) of any candidate. Lower YoY (+0.168) reflects that inside-20 attempts are partly opportunity-driven (you only get them when punting from the right field position).

**Block-rate penalty (−0.05):** Small. Blocks are mostly snap/protection failures rather than punter skill (audit YoY r = −0.05, near-zero), so weighting them heavily would punish punters for their teammates' mistakes. But a blocked punt is catastrophic (often a TD for the opponent), and the punter is the player most associated with the play. The small penalty acknowledges ownership without overweighting.

**iDL vs EDGE-style decision rejected (Option A):** A single-component `p_epa_per_punt` formula was considered — analogous to K v1.1's FGOE/att. EPA per punt comprehensively captures distance, placement, return prevention, and blocks. But the audit showed it does NOT dominate net average:

| Metric | YoY r | Validity r |
|---|---:|---:|
| `p_net_avg` | **+0.355** | **+0.166** |
| `p_epa_per_punt` | +0.269 | +0.163 |

Why the K analogy doesn't carry: FG kicks have well-defined distance baselines (every 40-yard FG faces a similar challenge). Punt EPA depends on the returner, the coverage team, the wind, the field surface — mixing in non-punter-skill variance that dilutes the signal. We documented Option A as an alternative considered and chose B.

---

## Rejected Candidates (audit log)

- **`p_gross_avg`** — YoY +0.334, validity +0.113. Subsumed by net avg (which uses the same gross yards but accounts for return).
- **`p_touchback_rate`** — validity −0.030 (near-zero). Touchback avoidance is implicitly handled by net average (touchbacks cap net), so a separate weighted component would double-count.
- **`p_return_yards_per_punt`** — validity −0.083 (sign correct, lower = better). Same subsumption logic as touchback: net avg already credits return prevention.
- **`p_fair_catch_rate`** — validity +0.013, near-zero. Fair catches are a returner decision driven by hangtime and coverage, not strictly a punter skill we can isolate.
- **`p_i20_minus_tb_per_punt`** — validity +0.189, basically ties inside_20_rate. Considered as an alternative to inside_20 but YoY r is identical (+0.163 vs +0.168) and the simpler "inside 20%" framing is more reader-recognizable.
- **`p_long_punt`** — YoY +0.077, validity +0.076. Weak both ways. Power signal exists but is dominated by net avg's continuous treatment.
- **`p_epa_per_punt`** — YoY +0.269, validity +0.163. The comprehensive over-expected metric. Did not dominate alternatives; would be a viable Option A formula but Option B (multi-component) won on individual-signal strength.

---

## NaN Handling

Standard NaN-neutralization: if a component's z-score is NaN, it's replaced with 0.0 before entering the composite.

Known NaN sources:
- `p_blocked_rate`: NaN if `punts = 0` (filtered out by MIN_PUNTS_TO_GRADE).

---

## Alternatives Considered

**Option A — single-component EPA per punt:** See "Design Rationale" above. The over-expected approach didn't dominate, so we chose multi-component.

**Including `p_gross_avg`:** Tempting because it's the conventional punter headline. Rejected because it's strictly subsumed by net average (which uses the same gross yards but is more informative).

**Hangtime data:** Would be the ideal placement-skill metric. Not in nflverse. PFF charts hangtime but is paid. Deferred until a free source emerges.

**Negative weight on returns/touchbacks:** Both are implicitly in net average. Adding them as separate components would double-count.

**Using `i20_minus_tb_per_punt` instead of `inside_20_rate`:** Functionally equivalent in this audit (validity +0.189 vs +0.188). The simpler "inside 20%" rate is more reader-recognizable.

---

## Known Limitations

**Lowest validity baseline of any graded position (+0.122).** Even lower than K (+0.153). Reasons:
- Only 2 P Pro Bowls per year out of ~30 qualified (5% rate)
- Punter Pro Bowl voting is heavily reputation-weighted
- Net average and inside-20 are noisier YoY than offensive position primary metrics

**No hangtime adjustment.** A high hang time / short punt that's downed at the 5 is great punting; net avg sees it as a mediocre 35-yard kick. Inside-20 rate partially captures this. PFF-style hang time data would fix the gap but requires paid data.

**Block rate is mostly snap/protection failure.** Documented above. The −0.05 weight is conservative for this reason.

**Coverage starts 2016.** Earlier punter data exists in pbp but we cap at 2016 to match other position coverage windows.

---

## Consequences

- P grades available from 2016 onward.
- Pipeline requires: `punter_stats` table (migration 0017), `pbp` ingest (already running).
- To regenerate grades: `nflgrades grade --season <year> --position P` for each season 2016-2025.
- Leaderboard uses the two-tier FORMULA / CONTEXT header pattern introduced for K — Net avg / Inside 20% / Block% sit under FORMULA; Gross avg / Long / TB% sit under CONTEXT.

---

## Future Work

**v2 candidates:**
- Hangtime once accessible.
- EPA per punt as an additional small-weight component if v2 validity testing supports it.
- Field-position-adjusted net average (different baseline by LOS).
- Net-over-expected (NEPA) model — would be the cleanest "over-expected" version if we can build a stable model.

Any v2 add will go through the same four-criterion audit before shipping.
