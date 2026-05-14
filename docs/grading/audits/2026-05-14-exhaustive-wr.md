# WR Exhaustive Candidate Audit — 2026-05-14

Second production application of the four-criterion audit framework. Largest cohort yet (574 qualified WR-seasons across 2017-2023). Scored every plausible WR candidate stat from our data inventory against:

1. **Reliability** — YoY Pearson r across 7+ consecutive season pairs
2. **Cross-sectional discrimination** — within-season std of the candidate
3. **Independence** — max abs Pearson r vs currently-shipped components (in z-units)
4. **Predictive validity** — Pearson r between this-year candidate value and next-year Pro Bowl selection

**Cohort:** qualified WR-seasons 2017-2024 (n=574 for stat_components, n=734 for NGS receiving 2017+, n=322 for FTN 2022+, n=618 for PFR 2018+).

Tool: `nflgrades audit-candidates --position WR` (framework in [pipeline/src/nfl_grades/grading/exhaustive_audit.py](../../../pipeline/src/nfl_grades/grading/exhaustive_audit.py)).

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped (re-scored with self-excluded):** | | | | | | | |
| `wr_drop_rate` | 322 | +0.161 | 0.03 | −0.179 | wr_success_rate_per_target | −0.098 | NOISE (light weight ok) |
| `wr_rec_epa_per_target` | 822 | +0.195 | 0.21 | **+0.745** | wr_success_rate_per_target | +0.156 | MEANINGFUL OVERLAP |
| `wr_separation` | 822 | **+0.560** | 0.49 | +0.194 | wr_yac_over_expected_per_rec | **+0.003** | Strong YoY, zero validity |
| `wr_success_rate_per_target` | 822 | +0.311 | 0.07 | **+0.746** | wr_rec_epa_per_target | +0.159 | MEANINGFUL OVERLAP |
| `wr_target_earn_rate` | 822 | **+0.682** | 0.06 | +0.283 | wr_success_rate_per_target | **+0.285** | **STRONG ADD candidate** |
| `wr_yac_over_expected_per_rec` | 822 | +0.342 | 1.14 | +0.365 | wr_rec_epa_per_target | +0.123 | Independent / weak validity |
| **nflvs_player_stats-derived:** | | | | | | | |
| `wr_td_rate` | 822 | +0.223 | 0.03 | +0.424 | wr_rec_epa_per_target | +0.081 | Independent / weak validity |
| `wr_first_down_rate` | 822 | +0.294 | 0.07 | +0.760 | wr_success_rate_per_target | +0.167 | MEANINGFUL OVERLAP |
| `wr_yards_per_target` | 822 | +0.280 | 1.43 | +0.759 | wr_rec_epa_per_target | +0.171 | MEANINGFUL OVERLAP |
| `wr_catch_rate` | 822 | +0.460 | 0.08 | +0.661 | wr_success_rate_per_target | +0.125 | MEANINGFUL OVERLAP |
| `wr_target_share` | 822 | +0.685 | 0.06 | **+0.981** | wr_target_earn_rate | +0.291 | STRONG REDUNDANCY (duplicate) |
| `wr_air_yards_share` | 822 | +0.677 | 0.09 | +0.742 | wr_target_earn_rate | +0.238 | MEANINGFUL OVERLAP |
| **NGS receiving (2017+):** | | | | | | | |
| `wr_ngs_cushion` | 734 | +0.450 | 0.65 | +0.482 | wr_separation | −0.152 | Negative validity (defense-driven) |
| `wr_ngs_intended_air_yards` | 734 | +0.695 | 2.76 | −0.559 | wr_separation | −0.004 | Strong YoY, zero validity (usage marker) |
| `wr_ngs_yac_above_expectation` | 734 | +0.384 | 0.81 | +0.770 | wr_yac_over_expected_per_rec | +0.118 | MEANINGFUL OVERLAP (duplicate of our YAC-OE) |
| `wr_ngs_air_yards_share` | 734 | +0.564 | 8.97 | +0.687 | wr_target_earn_rate | +0.272 | MEANINGFUL OVERLAP |
| `wr_ngs_catch_pct` | 734 | +0.466 | 7.64 | +0.674 | wr_success_rate_per_target | +0.124 | MEANINGFUL OVERLAP |
| **FTN charting (2022+):** | | | | | | | |
| `wr_ftn_contested_rate` | 322 | +0.401 | 0.11 | −0.574 | wr_separation | −0.036 | Inverse of separation; zero validity |
| `wr_ftn_created_reception_rate` | 322 | +0.422 | 0.04 | −0.427 | wr_separation | +0.012 | Doesn't predict Pro Bowl |
| **PFR advanced (2018+):** | | | | | | | |
| `wr_pfr_broken_tackle_per_rec` | 618 | +0.298 | 0.04 | +0.398 | wr_yac_over_expected_per_rec | +0.144 | Independent signal; modest |
| `wr_pfr_drop_pct` | 618 | +0.115 | 0.02 | +0.571 | wr_drop_rate | −0.010 | NOISE (PFR drops noisier than FTN) |
| `wr_pfr_receiving_rat` | 618 | +0.291 | 11.76 | +0.777 | wr_rec_epa_per_target | +0.233 | MEANINGFUL OVERLAP (QB-driven) |

## Per-candidate verdict + reasoning

### Currently shipped (decide whether to keep / change weight)

**`wr_target_earn_rate` — BUMP from 0.10 → 0.15.**
- **The strongest signal in the formula** by validity (+0.285, highest of any candidate) and joint-second by YoY (+0.682). Underweighted at 11%.
- Captures both "this WR is good enough to draw targets" and "the offense is using him as a primary option." Some tautological flavor (good WRs get targets) but the metric correlates highly with Pro Bowl voting because high-target receivers are who voters reward.
- New share: 15% of formula. Validity-gated; the bump should improve overall composite validity.

**`wr_rec_epa_per_target` — KEEP at 0.35.**
- Modest YoY (+0.195) and validity (+0.156). Heavily redundant with success_rate (+0.745).
- The redundancy is structural (success_rate is fraction-of-positive-EPA plays). The fix is on the success_rate side, not here.
- Remains the primary outcome signal; keep at 0.35.

**`wr_yac_over_expected_per_rec` — KEEP at 0.27.**
- Modest YoY (+0.342), weak validity (+0.123), reasonably independent (max_r +0.365 with EPA).
- Pre-adjusted by NGS's xYAC model — measures real receiver post-catch skill above context. Real signal even if Pro Bowl voters reward total YAC over YAC-OE.
- Keep at current weight.

**`wr_separation` — KEEP at 0.10 (despite zero validity).**
- Strong YoY (+0.560 — one of the most stable in the audit) but **validity essentially zero (+0.003).** A surprising finding.
- Two interpretations: (a) **separation is universal at the qualified WR level** — every Pro-Bowl-caliber receiver can separate; the metric can't differentiate at the top; or (b) Pro Bowl voters reward production not process.
- Strong YoY says it's measuring real stable skill. Keep at current weight; document the limitation. Don't chase validity by lowering — that would be reverse-engineering.

**`wr_success_rate_per_target` — LOWER from 0.08 → 0.05.**
- Same EPA-vs-success-rate redundancy as QB (max_r +0.746 with rec_epa). Validity moderate (+0.159).
- At 0.08 the harm was bounded; at 0.05 it's bounded further. Frees +0.03 (combined with the bump above) for target_earn_rate.

**`wr_drop_rate` — KEEP at −0.05.**
- YoY +0.161 (sub-threshold, NOISE on the rate-event side). Validity −0.098 (modest negative, expected direction — droppers don't make Pro Bowl).
- Already at light −0.05 weight per the post-fumble v1.2 audit. The NOISE verdict is consistent; light weight is the right home for it (cross-sectional spread + face-check + measurement-error caveat all support keeping).

### Strong-redundancy rejections (nflverse / NGS)

**`wr_target_share` — REJECT (duplicate of target_earn_rate).** max_r **+0.981** with our target_earn_rate. Same metric, different denominator (per-game team passes vs aggregated). Trivially redundant.

**`wr_ngs_yac_above_expectation` — REJECT (duplicate of our YAC-OE).** max_r +0.770 with our existing YAC-OE component. Same stat measured differently. Confirmed the WR v1.1 research finding.

**`wr_first_down_rate`, `wr_catch_rate`, `wr_yards_per_target`** — all reject. Each max_r > 0.66 with EPA or success_rate. The classic EPA family.

**`wr_pfr_receiving_rat` — REJECT.** Passer rating when targeted; +0.777 with our EPA. Mostly QB-driven (the receiver's QB throws the passes that determine the rating). Validity +0.233 is meaningful, but it's measuring QB quality not WR skill.

### Style/usage markers — independent but zero/negative validity

**`wr_ngs_intended_air_yards` — REJECT (style).** YoY +0.695 (very stable!), validity −0.004. Pure usage marker — deep threats (Tyreek, Lamb) vs slot receivers (Shakir, Cooper Kupp). Both archetypes win Pro Bowls. Skip.

**`wr_ngs_cushion` — REJECT (defense-driven).** Validity **−0.152**: tighter cushions get given to dangerous receivers, so high cushion = LESS Pro Bowl. Not a WR-skill signal.

**`wr_ftn_contested_rate` — REJECT.** max_r −0.574 with separation (it IS the inverse of separation, as the v1.1 research found). Validity essentially zero. Skip.

**`wr_ftn_created_reception_rate` — REJECT.** YoY +0.422, but validity +0.012 (essentially zero). "Receiver created the value" turns out not to predict Pro Bowl voting. Could be a real skill voters undervalue, or could be a noisy chart-y metric. Either way, skip.

**`wr_air_yards_share` and `wr_ngs_air_yards_share` — REJECT.** Both correlate ~0.69-0.74 with target_earn_rate. Capture overlapping "is this WR the offense's primary option" signal but slightly weaker than earn_rate on validity.

### Borderline / future consideration

**`wr_pfr_broken_tackle_per_rec` — DOCUMENT as known gap; don't ship.**
- Independent signal (max_r +0.40 with YAC), modest YoY (+0.298), modest validity (+0.144).
- Conceptually: this captures YAC-skill-via-tackle-breaking, which is partly distinct from our YAC-OE (which measures yards above expected). Tackle-breakers like Deebo Samuel and Puka Nacua would gain. Slot/possession receivers wouldn't change.
- Mixed verdict: real skill, modest signal, weak validity. Same shape as `qb_rush_epa_per_rush` was for QB — captures a skill the formula misses but doesn't move the needle.
- Documented as future consideration. Revisit if FTN or NGS publish more granular YAC-skill data, or if we add a WR-specific "tackle-breaking" sub-grade surfaced separately.

**`wr_td_rate` — REJECT.** Modest YoY (+0.223), modest correlation with EPA (+0.424), weak validity (+0.081). Adding it would partly double-count outcome value already in EPA. The lesson from QB applies here too.

### Rate-event noise

**`wr_drop_rate`** — already discussed. Keep at light −0.05.

**`wr_pfr_drop_pct`** — REJECT. YoY +0.115 (sub-threshold), validity −0.010. PFR's drop measurement is noisier than FTN's (max_r +0.571 with our FTN drop_rate). FTN remains the better source.

## What this audit confirms

1. **Target earn rate is the strongest signal in the WR formula**, underweighted at v1.2. Bumping to 0.15 is the cleanest single-change improvement.

2. **The classic EPA/success_rate redundancy applies to WR too.** Lowering success_rate from 0.08 → 0.05 follows the same logic as QB v1.1.

3. **Separation has surprisingly zero validity at the WR level.** Strong YoY suggests we ARE measuring it well; near-zero validity suggests it's universal among qualified WRs (every starter can separate). Keep at 0.10 with documented limitation.

4. **No new components added.** Of 22 candidates, zero new ones get added to the formula. Two key WR-skills NOT captured by our formula remain documented as known gaps:
   - YAC-via-tackle-breaking (would need `wr_pfr_broken_tackle_per_rec` at light weight, but validity is weak)
   - "Receiver-created" value (FTN's `is_created_reception`, but no validity)

5. **WR formula is structurally healthy.** Six components, clean independence (no |r| ≥ 0.85 among non-self pairs), strong validity on the top signal. The v1.3 changes are a minor rebalance, not a rebuild.

## Decision: WR v1.3 weight changes

| Component | v1.2 | v1.3 | Share v1.2 | Share v1.3 |
|---|---:|---:|---:|---:|
| `wr_rec_epa_per_target` | 0.35 | 0.35 | 37% | 36% |
| `wr_yac_over_expected_per_rec` | 0.27 | 0.27 | 28% | 28% |
| `wr_separation` | 0.10 | 0.10 | 11% | 10% |
| **`wr_target_earn_rate`** | 0.10 | **0.15** | 11% | **15%** |
| **`wr_success_rate_per_target`** | 0.08 | **0.05** | 8% | **5%** |
| `wr_drop_rate` | −0.05 | −0.05 | 5% | 5% |

Sum |w|: 0.95 → 0.97. Net shape stays: outcome 64% (EPA + YAC), process 30% (separation + earn + success), hands 5%.

**Validity check after re-grade:** WR composite vs next-year Pro Bowl correlation **improved from +0.280 → +0.300** across 2017-2023. Real signal-shift, not just a redistribution.

**Face-check 2024:** Top 5 unchanged (AJ Brown, Chris Godwin, Marvin Mims, Khalil Shakir, Puka Nacua). Biggest movers up are alpha-target receivers: Malik Nabers +4.13, Keenan Allen +2.90, Cooper Kupp +2.83, George Pickens +2.78, CeeDee Lamb +2.45, DJ Moore +2.40, Davante Adams +2.38. Biggest movers down are rotational role players or deep threats with low target share: Devaughn Vele −2.68, Tutu Atwell −2.14, Andrei Iosivas −2.11. Coherent — leaning further into "alpha target earner" signal moves alphas up and role players down.

## Notes for future audits

- **WR audit is the second production audit.** First production use of the four-criterion framework was QB; WR confirms the framework scales to larger cohorts (574 vs 239 QBs).
- **Same EPA-vs-success-rate redundancy pattern observed.** Documented in audit-playbook.md; will likely show up in RB, TE audits too. Pattern is mathematical (success_rate ≈ fraction-of-positive-EPA), not coincidental.
- **NGS receiving data is rich but mostly redundant with what we already use.** Adding it as new components offers little new signal — the NGS YAC-OE is nearly identical to our PBP-derived YAC-OE.
- **FTN data beyond drop_rate doesn't pay off.** Contested rate is inverse-of-separation; created_receptions has no Pro Bowl signal. The drop_rate component is the value from FTN; nothing else.
