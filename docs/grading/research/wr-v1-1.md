# WR v1.1 → v1.3 — Research + Implementation (2026-05-14)

> **v1.3 ship (2026-05-14, exhaustive audit):** Bumped `wr_target_earn_rate` 0.10 → 0.15 (highest-validity signal in formula, was underweighted); lowered `wr_success_rate_per_target` 0.08 → 0.05 (EPA redundancy, same pattern as QB v1.1). Validity gate passed: +0.280 → +0.300. Top 5 2024 unchanged; alpha-target receivers (Nabers, Kupp, Pickens, Lamb, DJ Moore) rose. Full audit: [`../audits/2026-05-14-exhaustive-wr.md`](../audits/2026-05-14-exhaustive-wr.md). 22 candidates scored, no new components added; `wr_pfr_broken_tackle_per_rec` documented as known YAC-skill gap.

---



Status: **SHIPPED**. Migration 0014 applied to Neon + local. FTN ingest module live. All 2016-2025 WR seasons re-graded with v1.1 weights. Pre-2022 seasons NaN-neutralize the drop component.

> **2026-05-14 follow-up (TE v1.1 audit revealed inconsistency):** the v1.1 process applied the YoY noise check rigorously to `wr_fumble_rate` (removed it) but **did not run YoY on `wr_drop_rate` before adding it at −0.08**. When run after the fact, `wr_drop_rate` YoY mean r = +0.09 — statistically indistinguishable from the fumble rate we removed. By the methodology's own threshold (|r| < 0.20 → "weight tiny ≤0.05 or remove"), the −0.08 weight was over-weighted.
>
> **Correction shipped (v1.2):** lowered `wr_drop_rate` to −0.05, matching the TE v1.1 weight, to apply the methodology consistently across positions. See [te-v1-1.md](te-v1-1.md) for the full self-audit.

## Conclusion

Add `wr_drop_rate` at weight −0.08 (lowered to −0.05 in v1.2). Remove `wr_fumble_rate` (noise). Don't add WOPR/RACR/cushion/intended_air_yards (redundant or non-skill signals). Don't add YPRR/CROE (no data).

v1.1 weights (sum |abs| = 0.98 → 0.95 after v1.2):

| Component | v1.1 | v1.2 |
|---|---|---|
| `wr_rec_epa_per_target` | +0.35 | +0.35 |
| `wr_yac_over_expected_per_rec` | +0.27 | +0.27 |
| `wr_separation` | +0.10 | +0.10 |
| `wr_target_earn_rate` | +0.10 | +0.10 |
| `wr_success_rate_per_target` | +0.08 | +0.08 |
| `wr_drop_rate` (new) | −0.08 | **−0.05** |
| ~~`wr_fumble_rate`~~ | REMOVED | — |

## Implementation cost

1. New ingest module `pipeline/src/nfl_grades/ingest/ftn_receiving.py` — joins FTN flags to PBP, aggregates by receiver per season. Outputs catchable + drops + contested + created. ~150 LOC.
2. New migration creating `ftn_receiving_charting` table (player_id, season, catchable_balls, drops, contested_balls, created_receptions, PRIMARY KEY(player_id, season)).
3. Update `weights.py` WR section: replace `wr_fumble_rate` with `wr_drop_rate`.
4. Update `grading/wr.py` to pull drop_rate from new table.
5. Web layer + ADR-0015 revision history + re-grade 2022-2025 (FTN data starts 2022).

**Critical caveat:** FTN data starts 2022. WR grades for 2016-2021 will have the v1 formula (no drop component) while 2022+ uses v1.1. Document this in the methodology page.

## Correlation matrix findings (2024 qualified WRs, n=89)

Key pairs (Pearson r):

| Pair | r | Verdict |
|---|---|---|
| target_share ↔ wopr | **0.95** | WOPR ≈ target_share, redundant |
| racr ↔ avg_intended_air_yards | **−0.78** | RACR is a target-depth artifact |
| racr ↔ yac_per_rec | 0.65 | RACR overlaps with existing YAC |
| contested_rate ↔ avg_separation | **−0.71** | Contested rate ≈ inverse of separation |
| avg_yac_above_expectation ↔ yac_per_rec | 0.71 | NGS YAC ≈ our existing component |
| drop_rate ↔ everything | max \|r\|=0.21 | **Independent signal**, strong add |
| epa_per_tgt ↔ wopr | 0.15 | WOPR is volume, not efficiency |

Bottom line: drop_rate was the only candidate with low correlation against every existing component. The other agent's proposed adds (WOPR, RACR) were redundant; CROE/YPRR weren't computable.

## YoY noise check on fumble rate

WR fumble rate YoY correlations (qualified WRs, ≥50 catches in both seasons):

| Pair | r | n |
|---|---|---|
| 2020→2021 | −0.256 | 34 |
| 2021→2022 | +0.087 | 34 |
| 2022→2023 | −0.396 | 37 |
| 2023→2024 | +0.271 | 35 |

Mean r ≈ −0.07. Pure noise — oscillates around zero.

Cohort distribution for 2024 qualified WRs:
- 56% had 0 fumbles
- 90% had ≤1 fumble
- Max was 3 fumbles
- fumble_rate std = 0.0108

Conclusion: at WR sample sizes, fumble rate is essentially random year-to-year. Remove from formula. (Different from RB fumble rate, which has YoY r ~0.25-0.35 because RBs have 200+ touches.)

## Drop rate 2024 face-check

**Best hands (lowest drop rate, ≥40 catchable):**
- Terry McLaurin 0/87
- Khalil Shakir 0/77
- Cooper Kupp 1/70
- Jordan Addison 1/68
- DeAndre Hopkins 1/60
- Amon-Ra St. Brown 2/117
- Jaxon Smith-Njigba 2/108

**Worst hands:**
- George Pickens 6/69 (notoriously dropsy in 2024)
- Xavier Legette 5/59 (rookie struggles)
- Keon Coleman 5/39
- Allen Lazard 7/46

Face-check passes. FTN drop tracking aligns with consensus reputation.

**Caveat on data quality:** FTN is more conservative than PFF — only flags clear drops, not "should-have-caught" plays. A handful of WRs at 0/N are suspicious (McLaurin at 0/87 is plausible but borderline). The metric is real signal but noisier than ideal at the top of the distribution.

Cohort: median drop rate 4.5%, std 2.9%, range 0–16.3%. Reasonable distribution.

## What we considered but rejected

**WOPR (Weighted Opportunity Rating):** correlates 0.95 with target_share. We already have `wr_target_earn_rate` which captures the same signal. WOPR adds the air-yards-share component, but air yards share is partly scheme/QB-driven (it tells you what role the WR plays, not how good they are). Adding WOPR would basically double-count target volume.

**RACR (Receiver Air Conversion Ratio):** total yards / air yards. Correlates −0.78 with avg_intended_air_yards: WRs who run short routes have high RACR by construction (low denominator). Puka Nacua led 2024 RACR at 2.78 not because he's elite at converting air yards but because his target depth is short. This is a target-depth artifact, not a skill measure.

**Contested catch rate:** correlates −0.71 with separation. It's essentially "inverse of separation" — WRs who don't separate get more contested balls. We already weight separation; adding contested rate double-counts.

**NGS avg_cushion:** describes how defenses *play* the WR (deep vs press), not WR skill. Pro Bowl WRs and average WRs both can get press coverage depending on scheme. Skip.

**NGS avg_intended_air_yards:** usage marker (deep threat vs slot vs possession). Not a skill measure. Skip.

**NGS avg_yac_above_expectation:** correlates 0.71 with our existing `wr_yac_over_expected_per_rec`. Same stat from a different source. Skip.

**YPRR (Yards Per Route Run):** the other agent's centerpiece. Requires `routes_run` column which **does not exist in any nflverse source**. PFF-only. Not computable.

**CROE (Catch Rate Over Expected):** requires per-play expected catch %. Not in pbp/ngs/ftn at the receiver level. Not computable.

## Skill-tree coverage after v1.1

| WR skill | v1.1 coverage |
|---|---|
| Separation / route running | `wr_separation` (10%) |
| Hands / drops | `wr_drop_rate` (−5%) [NEW] |
| YAC ability | `wr_yac_over_expected_per_rec` (27%) |
| Earning targets | `wr_target_earn_rate` (10%) |
| Production value | `wr_rec_epa_per_target` (35%) |
| Consistency | `wr_success_rate_per_target` (8%) |
| Big plays | implicit in EPA |
| Red zone | implicit in EPA |
| Contested catches | implicit in separation + EPA |

Only `wr_fumble_rate` was removed — confirmed noise, not a real signal at WR sample sizes.
