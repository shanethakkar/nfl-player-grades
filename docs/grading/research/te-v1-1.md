# TE v1.1 → v1.2 + WR v1.2 — SHIPPED 2026-05-14

> **v1.2 ship (2026-05-14, exhaustive audit):** Bumped `te_target_earn_rate` 0.10 → 0.15 (highest-validity signal in formula, +0.301); lowered `te_success_rate_per_target` 0.08 → 0.05 (EPA redundancy +0.723, same pattern as QB/WR/RB). **Validity +0.384 → +0.407 (+0.023 — strongest Path A gain in any audit so far).** Top 5 hold; Brock Bowers rises 18 → 13. Full audit: [`../audits/2026-05-14-exhaustive-te.md`](../audits/2026-05-14-exhaustive-te.md). Also notable: te_separation has NEGATIVE validity (-0.053) at TE — voters reward tight-window over open routes — but kept at 0.07 (strong YoY says real skill, don't reverse-engineer).

---



Status: **SHIPPED**. Weights, graders, ADRs, web layer all updated. TE 2016-2025 + WR 2016-2025 re-graded on Neon. Cache TTL = 1 hour; users see new grades after hard refresh or expiry.

2024 face-check after re-grade:

- **WR top:** Godwin, AJ Brown, Mims, Shakir, Puka, Chase, ARSB, McConkey, Smith. Jefferson #14 (consensus higher; same per-snap vs volume limitation we accept across positions).
- **TE top:** Kittle, Kraft, Likely, Andrews, Jonnu, Moreau, Goedert, LaPorta, McBride. Brock Bowers #18 / 50th percentile — biggest face-check miss (consensus top-3 TE). Same per-snap-efficiency limitation as Jefferson WR / Hutchinson EDGE. Documented as known philosophy outcome, not a v1.1 regression.
- Cade Otton (7 drops on 59 catchable) correctly at 27th percentile; George Pickens (high drop rate) correctly at 17th percentile.

## Final recommendation

- **TE**: remove `te_fumble_rate`, add `te_drop_rate` at **−0.05**. Ship as v1.1.
- **WR (revisit)**: lower `wr_drop_rate` from −0.08 → −0.05. Re-ship as v1.2.
- **Audit task**: before more positions ship, run YoY r across every component in every shipped position (QB, RB, WR, TE, CB, S, EDGE, iDL, LB). Anything with weight > 0.05 and YoY r < 0.20 gets case-by-case review. See [../audit-playbook.md](../audit-playbook.md) for thresholds.

TE v1.1 weights (full tier):

| Component | v1 | v1.1 |
|---|---|---|
| `te_rec_epa_per_target` | 0.35 | 0.35 |
| `te_yac_over_expected_per_rec` | 0.27 | 0.27 |
| `te_separation` | 0.07 | 0.07 |
| `te_target_earn_rate` | 0.10 | 0.10 |
| `te_success_rate_per_target` | 0.08 | 0.08 |
| ~~`te_fumble_rate`~~ | −0.05 | REMOVED |
| `te_drop_rate` (NEW) | — | **−0.05** |

Sum |w| = 0.92 (unchanged from v1 — drop_rate replaces fumble_rate at equal weight). For `blocking_te` tier-2, target-earn redistribution unchanged (EPA→0.406, YAC→0.314).

## Why the recommendation changed from −0.10 → −0.05 (the self-audit)

First-pass analysis recommended TE drop_rate at −0.10 on three arguments:

1. Structural slot freed by lower TE separation weight (0.07 vs WR 0.10).
2. Position emphasis — TEs target seam/RZ, drops cost more.
3. YoY r slightly higher than WR (+0.13 vs +0.09).

On stepping back, I noticed an inconsistency in how the methodology had been applied:

- We removed `wr_fumble_rate` because YoY mean r = −0.07 (< 0.20 threshold).
- We added `wr_drop_rate` at −0.08 **without running the YoY noise check on it.**
- When I ran that check, WR drop_rate YoY mean r = +0.09 — statistically indistinguishable from the fumble rate we removed.

By the methodology's own rule ("YoY r < 0.20 → weight tiny ≤0.05 or remove"), WR drop_rate at −0.08 was over-weighted. Proposing TE at anything higher than WR replicates the inconsistency. Correct fix: apply the noise filter consistently, weight both at −0.05.

## YoY r evidence (run on Neon, 2026-05-14)

**TE fumble_rate** (qualified TEs, ≥40 targets) — the "remove" case:

| Pair | n | r |
|---|---|---|
| 2020→2021 | 21 | +0.01 |
| 2021→2022 | 22 | +0.20 |
| 2022→2023 | 22 | +0.07 |
| 2023→2024 | 25 | −0.25 |
| 2024→2025 | 26 | +0.36 |

Mean r = **+0.08**, oscillates. Pure noise. Remove.

**TE vs WR drop_rate** (FTN, catchable ≥25 for TE, ≥50 for WR):

| Pair | TE r | WR r |
|---|---|---|
| 2022→2023 | +0.33 | +0.27 |
| 2023→2024 | +0.02 | −0.12 |
| 2024→2025 | +0.04 | +0.10 |
| **Mean** | **+0.13** | **+0.09** |

Both in the "weak signal" band. TE slightly higher but the gap is within noise at n~30 pairs.

## Defenses of including drop_rate at low weight (despite weak YoY)

Three real arguments, but each only supports inclusion, not heavy weight:

1. **Independence from existing components.** Max |r| with other components = 0.40 (with success_rate); next highest 0.35 (separation). Below the 0.60 redundancy threshold — captures a distinct skill dimension EPA doesn't fully absorb.
2. **Face-check passes.** 2024 TEs: Hooper/Akins/Moreau/Likely at 0 drops; Otton 7/59, Njoku 7/74 — aligns with consensus reputation.
3. **Cross-sectional discrimination is real.** Drop_rate std ≈ 3%, max ≈ 12% (vs fumble_rate std ≈ 1%, max 3%). Spreads players meaningfully in a season.

**Caveat the other agent sharpened:** cross-sectional spread without YoY stability could be variance, not skill. The honest reading is "drop_rate has a small persistent skill component plus a large variance component." Small persistent component → light weight; variance component → not heavier.

**Additional caveat:** at small per-player denominators (TE median catchable ≈ 47), YoY r is **mechanically suppressed** by measurement error even if the true underlying skill is perfectly stable. So YoY r ≈ 0.13 isn't conclusive evidence of weak skill — it could be partly an artifact of small denominators. The face-check (Pickens/Njoku consistent across years) is actually stronger evidence of stable skill than YoY r when denominators are small. Net: light weight is right; weight ≤0.05 captures the signal without overclaiming.

## Cohort distribution

TE drop_rate 2022-2025:
- median ~3.3-5.1%, mean ~4-6%, std ~3-4%, max ~12-15%
- catchable median ~47, ~12-17% of qualified TEs have 0 drops

Realistic distribution, similar shape to WR cohort.

## 2024 face-check (TE, catchable ≥25)

**Best hands (0 drops):** Austin Hooper, Jordan Akins, Foster Moreau, Juwan Johnson, Grant Calcaterra, Isaiah Likely, Luke Schoonmaker.

**Single drop on 40-60+ catchable:** LaPorta 1/63, Mark Andrews 1/54, Tyler Conklin 1/53, Evan Engram 1/51, Hockenson 1/44.

**Worst:** Cade Otton 7/59 (11.9%), David Njoku 7/74 (9.5%), Theo Johnson 3/33, Mike Gesicki 5/73, Travis Kelce 6/107.

## Cross-references

- [wr-v1-1.md](wr-v1-1.md) — the v1.1 audit that introduced wr_drop_rate. Documented the correlation + face-check pillars but skipped the YoY noise check on drop_rate itself.
- [../audit-playbook.md](../audit-playbook.md) — the playbook. Step 3 (YoY noise check) was the unevenly-applied filter.
- [../checklists/removing-a-component.md](../checklists/removing-a-component.md) — DELETE-orphan workflow (TE grader already compliant).
