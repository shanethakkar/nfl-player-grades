# RB v1.1 → v1.4 — Audit + Implementation (2026-05-14)

> **v1.3 ship (2026-05-14, exhaustive audit Path A):** Lowered `rb_rush_success_rate` 0.14 → 0.05 — same EPA-vs-success-rate redundancy as QB and WR. Validity gate +0.243 → +0.247. Top 4 2024 unchanged.
>
> **v1.4 ship (2026-05-14, Path B schema change):** Added `rb_yards_after_contact_per_carry` at +0.10 weight. The exhaustive audit's headline finding — highest-validity candidate of any audit so far (+0.192 vs Pro Bowl, higher than any current RB component). Required a new PFR rush ingest module (`pipeline/.../ingest/pfr_rush.py`), new migration (`db/migrations/0015_pfr_rb_rush.sql`), grader update. Validity +0.247 → +0.259 (+0.012). Face-check 2024: Bucky Irving rose to #3 on elite YAC (2.69/carry); Saquon dropped to #4 because his YAC was below-average (1.97) for an OPOY candidate (his value was explosive pre-contact runs). First Path B ship from the exhaustive audit framework — proves it can surface real new components, not just redundancy diagnostics. Full audit at [`../audits/2026-05-14-exhaustive-rb.md`](../audits/2026-05-14-exhaustive-rb.md).

---



Status: **SHIPPED**. Pruning revision — removed one noise component, redistributed weight. Methodology applied: [../audit-playbook.md](../audit-playbook.md) (skill-tree + correlation + YoY noise check + face-check).

> **v1.2 follow-up (2026-05-14, same day):** Cross-position YoY audit (see [../audits/2026-05-14-cross-position-yoy.md](../audits/2026-05-14-cross-position-yoy.md)) found `rb_rec_epa_per_target` had mean YoY r = 0.027 across 2016-2025 — worst signal in the entire system. Lowered from +0.18 → +0.05; freed +0.13 to `rb_yac_over_expected_per_rec` (+0.15 → +0.28). Receiving share preserved at 33%. See ADR-0014 v1.2.

## v1.1 Conclusion

**Remove `rb_catch_pct` (+0.05). Bump `rb_yac_over_expected_per_rec` from +0.12 → +0.15 to absorb the slot. Keep everything else.**

| Component | v1 | v1.1 | v1.2 |
|---|---|---|---|
| `rb_ryoe_per_attempt` | +0.28 | +0.28 | +0.28 |
| `rb_rush_epa_per_attempt` | +0.18 | +0.18 | +0.18 |
| `rb_rush_success_rate` | +0.14 | +0.14 | +0.14 |
| `rb_rec_epa_per_target` | +0.18 | +0.18 | **+0.05** |
| `rb_yac_over_expected_per_rec` | +0.12 | **+0.15** | **+0.28** |
| ~~`rb_catch_pct`~~ | +0.05 | **REMOVED** | — |
| `rb_fumble_rate` | −0.05 | −0.05 | −0.05 |

Sum |abs| = 0.98 (vs v1's 1.00). 2024 leaderboard barely changes — Henry / Saquon / Gibbs at top either way.

## Audit findings

### 1. Other agent's proposal was weaker than our v1

Their formula: RYOE (35%) + Success Rate (25%) + Target Share (20%) + MTF (20%).

Problems:

- **Drops fumble rate** — for RBs this is real signal (median 2 fumbles, std 0.0068 on rate, 22%/24%/54% at 0/1/2+). Different from WR where fumble was pure noise.
- **Target Share over receiving efficiency** — target share is QB/scheme driven. Our `rb_rec_epa_per_target` measures actual contribution.
- **No rushing EPA** — RYOE is yards only; EPA factors down/distance. We have both.
- **MTF weighted 20% but isn't computable** — FTN doesn't have a `broken_tackles` or `missed_tackles_forced` flag (those are PFF metrics). Confirmed by inspecting FTN columns: only catchable / drop / contested / created flags for passing plays. The other agent didn't check whether their proposed stats existed in our data.
- **Stacked box % as "coefficient"** is wrong: box count is already baked into NGS's RYOE expected-yards model. Double-adjusting would be incorrect.

### 2. `rb_catch_pct` is noise + redundant

**YoY r:** −0.015, +0.035, +0.120, −0.322 (mean ≈ −0.05) across 2020-2024. Same shape as WR fumble rate that was removed.

**Correlation with `rb_rush_success_rate`:** 0.61. Partial redundancy — when catch_pct has any signal, it overlaps with rush success.

**Skill interpretation:** RB catch_pct is mostly checkdowns. Range 0.45-1.00 with std 0.099 (some variation) but the variation doesn't persist year-over-year, so it's not a stable skill measurement. Remove.

### 3. NGS rushing additions all rejected

Tested four NGS rushing columns we don't currently use, correlated with our composite_grade on 2024 qualified RBs (n=41):

| NGS column | r vs composite | r vs RYOE | Verdict |
|---|---|---|---|
| `efficiency` (lateral movement) | −0.57 | **−0.74** | Same stat sign-flipped (NGS efficiency = lateral dancing; better RBs hit holes straight) |
| `rush_pct_over_expected` | +0.62 | **+0.74** | Same stat as RYOE |
| `avg_time_to_los` | −0.15 | −0.04 | Weak signal; usage marker |
| `percent_attempts_gte_eight_defenders` | +0.12 | +0.12 | Already in RYOE's expected model; don't double-adjust |

**None added independent signal.** All four were either redundant with RYOE or non-skill (usage/scheme markers).

### 4. `rb_fumble_rate` keep — borderline but real signal

YoY r ≈ +0.07 (similar to WR fumble's −0.07 that was removed). But:

- **Cohort distribution is meaningfully different.** RB median 2 fumbles, std 0.0068, max 7. WR median 0 fumbles, max 3. RBs fumble enough that within-season ranking is real.
- **Within-season correlation with grade**: −0.27 (with composite) and −0.36 (with rush_epa). Meaningful negative signal.
- **Ball security is a coachable RB trait.** Keep at −0.05.

### 5. Face-check (2024 + 2023)

**2024 top 10:** Henry (90.4), Saquon (82.5), Gibbs (82.1), Bucky Irving, Bijan Robinson, James Cook, Allgeier, Montgomery, Mason, Conner — Pro Bowl / All-Pro names all present.

**2023 top 10:** CMC (85.8 — OPOY winner), Conner, Gus Edwards, Cook, Mostert, etc.

No miscalls. Formula is calibrated correctly.

## What this audit confirms about our methodology

1. **Correlation analysis prevents over-engineering.** Without checking, we'd have been tempted to add NGS efficiency or rush_pct_over_expected (both sound good in isolation). The correlation check showed they're the same stat as RYOE, just re-skinned.
2. **YoY noise check catches "dead weight" components.** rb_catch_pct looked plausible at +0.05 weight, but the YoY r told the story: it's not measuring a stable skill. Same lesson as WR fumble.
3. **Don't trust "industry standard" stats without verifying source data.** The other agent's 20% MTF weight was for a stat that doesn't exist in nflverse. Always check [../data-inventory.md](../data-inventory.md) first.
4. **Symmetric stats don't always behave symmetrically across positions.** Fumble rate is noise for WRs but signal for RBs. The cohort distribution and event frequency matter more than the metric name.
