# CB Exhaustive Candidate Audit — 2026-05-14

Fifth production application of the four-criterion framework. **First defensive position** audited — different data sources (no NGS, primary source is `pfr_advstats_def` 2018+).

**Cohort:** qualified CB-seasons 2018-2024 (n=946 for stat_components, n=878 for PFR-derived candidates, n=861 for missed-tackle candidates).

11 candidates scored: 4 current components + 7 new PFR-derived candidates.

Tool: `nflgrades audit-candidates --position CB`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped (re-scored with self-excluded):** | | | | | | | |
| `cb_passer_rating_allowed` | 946 | +0.126 | 18.59 | −0.463 | cb_pbu_rate | **−0.161** | Modest signal (correct direction) |
| `cb_pbu_rate` | 946 | +0.189 | 0.05 | −0.461 | cb_passer_rating_allowed | +0.123 | Modest |
| `cb_target_rate` | 946 | +0.282 | 0.02 | −0.118 | cb_pbu_rate | **+0.013** | NEAR-ZERO validity, weight is over-stated |
| `cb_yac_per_rec_allowed` | 946 | +0.174 | 1.22 | +0.132 | cb_passer_rating_allowed | −0.047 | Weak but kept (skill-tree distinct) |
| **PFR-derived candidates:** | | | | | | | |
| `cb_comp_pct_allowed` | 878 | +0.243 | 0.08 | +0.645 | cb_passer_rating_allowed | −0.149 | MEANINGFUL OVERLAP with PR_allowed (which subsumes comp%) |
| `cb_yards_per_target_allowed` | 878 | +0.042 | 1.40 | +0.649 | cb_passer_rating_allowed | −0.082 | NOISE |
| `cb_int_rate` | 878 | +0.208 | 0.02 | −0.540 | cb_passer_rating_allowed | +0.165 | "STRONG ADD" flag — but mathematically inside PR_allowed (double-count if added) |
| `cb_td_rate_allowed` | 878 | +0.073 | 0.03 | +0.620 | cb_passer_rating_allowed | −0.036 | NOISE |
| `cb_missed_tackle_rate` | 861 | +0.272 | 0.05 | +0.224 | cb_yac_per_rec_allowed | −0.021 | Independent / zero validity |
| `cb_tackles_per_snap` | 878 | +0.490 | 0.02 | +0.316 | cb_target_rate | −0.107 | Style metric (zone-heavy CBs tackle more) |
| `cb_adot_allowed` | 878 | +0.338 | 2.51 | +0.315 | cb_pbu_rate | +0.066 | Scheme/style marker |

## Verdict notes

**`cb_passer_rating_allowed` — KEEP at −0.35.**
- Weak YoY (+0.126) but **the validity SIGN matches the weight direction**: validity −0.161 means high PR allowed → less likely to make Pro Bowl. The metric is doing real work; CB Pro Bowl voting is just noisy.
- Primary coverage damage signal. v1.1's consolidation of comp%+yds/tgt+TDs+INTs into PR_allowed is validated — the individual sub-components either correlate strongly with PR_allowed (comp_pct +0.645, td_rate +0.620) or are noise (yards_per_target +0.042 YoY, td_rate +0.073 YoY).

**`cb_pbu_rate` — KEEP at +0.12.**
- YoY +0.189 (just under threshold), validity +0.123 (matches weight direction). Solid signal.
- Negative correlation with PR_allowed (−0.461) is **mechanism**, not redundancy — PBUs definitionally reduce PR allowed. Both belong.

**`cb_target_rate` — LOWER from −0.08 → −0.05.** ← v1.2 SHIPPED
- YoY +0.282 (modest), validity **+0.013** (essentially zero).
- The validity SIGN is positive but design weight is negative. We model "elite CBs get avoided" but at the qualified-CB level, all top corners face similar volume because they're matched up with WR1s. The "avoidance effect" exists at the league-wide level but doesn't differentiate at the top of our cohort.
- Lowered to −0.05. Same logic as the cross-position YoY methodology — when validity is near zero, weight should be ≤0.05.

**`cb_yac_per_rec_allowed` — KEEP at −0.15.**
- YoY +0.174, validity −0.047 (small magnitude, correct direction).
- Captures distinct coverage skill (cushion + tackling at catch point — different from PR_allowed which is yards-per-attempt). Skill-tree placement justifies the weight despite weak validity.

## Rejected new candidates

**`cb_int_rate` — REJECT (despite STRONG ADD flag).**
- Highest validity of any non-shipped candidate (+0.165). Independent of PR_allowed at the modest end (max_r −0.540).
- BUT: INTs are mathematically inside the passer rating formula already. PR allowed = function of comp%, yards/att, TDs/att, **INTs/att**. Adding `cb_int_rate` as a separate component would partially double-count the INT signal.
- The flag is a false positive from the auto-verdict logic (doesn't know about mathematical containment). Documented for transparency.

**`cb_comp_pct_allowed` — REJECT (subsumed by PR_allowed).**
- +0.645 with PR_allowed; PR_allowed already incorporates comp%.

**`cb_td_rate_allowed`, `cb_yards_per_target_allowed`** — REJECT (NOISE, also subsumed by PR_allowed).

**`cb_missed_tackle_rate` — REJECT.**
- YoY +0.272 (modest), but validity essentially zero (−0.021). Pro Bowl CB voters don't differentiate on tackling ability. Real skill but no consensus alignment.
- Worth noting: Safety formula uses missed_tackle_rate at −0.09 and it has +0.247 YoY r there. For CB the YoY is weaker and validity is zero. Position-specific.

**`cb_tackles_per_snap` — REJECT.**
- Strongest YoY in the audit (+0.490) but validity −0.107 (negative — more tackles, LESS likely to make Pro Bowl).
- Style indicator: zone-heavy CBs make more tackles because they let catches happen in front of them. Man-heavy press CBs (Pro Bowl archetype) tackle less.

**`cb_adot_allowed` — REJECT.**
- YoY +0.338 (modest), validity +0.066 (weak). Average depth of target = scheme indicator (zone vs press). Not a CB skill measure.

## What this audit confirms

1. **The v1.1 passer-rating-allowed consolidation was correct.** All four sub-components (comp%, yards/att, TDs, INTs) either fail standalone or strongly overlap with PR_allowed.

2. **CB has structurally weak validity** — best component is PR_allowed at |validity| = 0.161. Other coverage positions:
   - S: best component validity ~0.21 (passer_rating_allowed)
   - LB: known weakest at +0.179
   
   This isn't a formula problem — it's a Pro Bowl voting problem. CB voting rewards interceptions and "shutdown" reputation more than per-target rate. Documented.

3. **No new components added.** The CB formula's 4-component shape is structurally right. The only tweak is shrinking target_rate (validity near zero).

## Decision: CB v1.2 weight change

| Component | v1.1 | v1.2 | Share v1.1 | Share v1.2 |
|---|---:|---:|---:|---:|
| `cb_passer_rating_allowed` | −0.35 | −0.35 | 50% | 52% |
| `cb_yac_per_rec_allowed` | −0.15 | −0.15 | 21% | 22% |
| **`cb_target_rate`** | −0.08 | **−0.05** | 11% | **7%** |
| `cb_pbu_rate` | +0.12 | +0.12 | 17% | 18% |

Sum |w|: 0.70 → 0.67.

**Validity:** CB composite vs next-year Pro Bowl correlation **+0.219 → +0.220** (essentially unchanged). Expected — target_rate was barely contributing because its validity was near zero. The change is a methodology cleanup (don't over-weight a near-zero-validity signal), not a validity gain.

**Face-check 2024:** Top 4 unchanged (Stingley, Surtain, Wiggins, Humphrey). Top 10 essentially the same; minor reshuffles at #5-10.

## Honest take on CB validity ceiling

The validity baseline for CB is +0.219, second-weakest after LB (+0.179). Pro Bowl CB voting is famously noisy:
- Voters reward narrative + interceptions + "shutdown" reputation more than per-target efficiency
- Zone vs man assignment is mostly scheme, but voters credit man specialists more
- Slot/outside is a real skill distinction but Pro Bowl voting doesn't separate

**This is a known position limitation, not a formula bug.** No realistic weight tweak will move CB validity from 0.22 to 0.40 — the ceiling is set by voter behavior, not by the metrics available.

A future v1.3 could investigate adding more PFR data (separated press vs off snaps if available, contested ball stats specifically for DBs) but the marginal validity gain would be small.
