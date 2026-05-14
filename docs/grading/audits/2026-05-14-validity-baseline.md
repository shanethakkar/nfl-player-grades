# Validity Baseline — 2026-05-14

First production run of the downstream predictive validity check. For each shipped position, computes the Pearson correlation between this-year composite grade and next-year Pro Bowl selection (0/1) across qualified player-seasons.

**Pro Bowl data:** [pipeline/data/pro_bowl_selections.csv](../../../pipeline/data/pro_bowl_selections.csv) — curated from Wikipedia "Pro Bowl Games" pages, 7 seasons (2018-2024 regular seasons).

**Name match rate:** 69% of Pro Bowl players are matched to a player_id in our `players` table. The 31% unmatched are predominantly **non-graded positions** (OL, FB, K, P, LS, KR, ST) — verified by inspection. Match rate among graded positions is ~95%+, so the validity numbers below are not meaningfully suppressed by name-join misses.

## Baseline per position

| Position | n qualified seasons | Pro Bowls next yr | Base rate | Pearson r | Verdict |
|---|---:|---:|---:|---:|---|
| **iDL** | 415 | 45 | 10.8% | **+0.457** | Strong — formula well-calibrated |
| **EDGE** | 487 | 64 | 13.1% | **+0.420** | Strong |
| **TE** | 224 | 32 | 14.3% | **+0.384** | Strong |
| **WR** | 574 | 70 | 12.2% | +0.280 | Moderate |
| **S** | 459 | 35 | 7.6% | +0.253 | Moderate |
| **RB** | 322 | 45 | 14.0% | +0.243 | Moderate |
| **QB** | 239 | 53 | 22.2% | +0.237 | Moderate |
| **CB** | 731 | 49 | 6.7% | +0.219 | Moderate |
| **LB** | 325 | 27 | 8.3% | **+0.179** | Weakest |

Seasons covered: 2017-2023 for offensive positions (QB/RB/WR/TE), 2018-2023 for defensive positions (CB/S/EDGE/iDL/LB). The "+1" lookup is for the next-year Pro Bowl honor; the latest Pro Bowl data we have is the 2024 regular-season honors (Pro Bowl Games 2025).

## Interpretation

**Expected range for a healthy composite:** Pro Bowl correlation between **+0.20 and +0.50**. Pro Bowl voting carries narrative/visibility bias, so perfect grading wouldn't reach r=1.0 even theoretically. The realistic ceiling is ~0.50, achieved by positions where consensus mostly tracks per-snap efficiency (DL).

**Strong (≥0.35):** iDL, EDGE, TE. These three formulas track external consensus closely. iDL and EDGE benefit from the audit-driven v1.1 weight cleanup. TE has the cleanest internal structure of any position (per the correlation audit) and that translates to validity.

**Moderate (0.20-0.30):** QB, RB, WR, S, CB. Standard range for good-but-not-great validity. Each is doing real work; gap to "strong" likely reflects positional voting noise (CBs notoriously, S also rough) and per-snap-vs-volume philosophy choices.

**Weakest (<0.20):** LB at +0.179. **Confirms the known "stats vs reputation" disconnect** documented in [../research/defensive-grading.md](../research/defensive-grading.md) — Fred Warner / Roquan Smith consistently get Pro Bowl votes despite below-peak statistical seasons, and the LB grade can't see that. **This is a known limitation, not a fixable formula bug** — the snap-level film grading we can't replicate is what voters reward.

## What this baseline does for the project

Two uses going forward:

1. **Decision criterion for weight changes.** Any new weight tweak (starting with QB v1.1) must be evaluated on whether it improves or degrades the Pro Bowl correlation. Lower validity = back out the change.

2. **Candidate scoring in the exhaustive audit.** Every candidate stat we consider in `nflgrades audit-candidates` gets a `validity_r` score — its individual correlation with next-year Pro Bowl. Strong YoY r + independence + positive validity = strong ADD candidate.

## Reproducibility

```
DATABASE_URL=<neon url> nflgrades validity
DATABASE_URL=<neon url> nflgrades validity --diagnose  # includes name-match audit
```

The Pro Bowl CSV is checked in at [pipeline/data/pro_bowl_selections.csv](../../../pipeline/data/pro_bowl_selections.csv) so the methodology is fully reproducible. Updating each year requires fetching one more Wikipedia Pro Bowl page and appending rows.

## Caveats

- **Pro Bowl honors carry voter bias** (recency, narrative, big-market). A composite that under-correlates may be measuring real skill that voters miss; a composite that over-correlates may be measuring consensus rather than skill. r=0.45 is the sweet spot — agrees with consensus but isn't slavishly chasing it.
- **AP All-Pro would be a sharper signal** (smaller cohort, more rigorous voting) but is sourced from the same Wikipedia-scraping problem and would give us roughly half the positive examples. Pro Bowl chosen for cohort size.
- **The Pro Bowl correlation has a small ceiling** because the base rate is 7-22% across positions — point-biserial correlations are mechanically bounded under unbalanced binary targets.
