# Team Position Weights — Empirical Audit (2026-05-25)

**Purpose:** derive position weights for team v1 grading ([ADR-0026](../adr/0026-team-v1-grading-formula.md)) from data rather than gut feel.

**Method:** two empirical anchors compared against the original ADR-0026 prior weights.

1. **Ridge regression** of team success vs. snap-weighted per-position team grades.
   - Targets: season-total point differential AND average closing spread (favoring the team).
   - Per-phase ridge (alpha=1.0) so within-phase multicollinearity is contained.
   - Coefficients normalized by absolute value and rescaled to sum to 1 within phase = "empirical weights."
2. **Salary cap allocation** — league-average % of cap spent at each position (Spotrac / OTC, 2022-2024 cap years smoothed).

**Data:** 2018-2024 regular seasons. 222 (team, season) rows, 11 player positions + OL (team-level grade from ADR-0025).

Raw script output: [2026-05-25-team-weights-raw.txt](2026-05-25-team-weights-raw.txt). Script: [pipeline/scripts/audit_team_weights.py](../../../pipeline/scripts/audit_team_weights.py).

---

## Results

### Offense (R² = 0.60 vs point diff, 0.56 vs spread — strong fit)

| Position | Prior | Cap   | Reg(PD) | Reg(spread) | Univariate r(PD) |
|----------|------:|------:|--------:|------------:|-----------------:|
| **QB**   | 0.40  | 0.28  | **0.61**| **0.57**    | **0.74**         |
| OL       | 0.25  | 0.43  | 0.21    | 0.25        | 0.51             |
| WR       | 0.15  | 0.18  | **0.01**| 0.07        | 0.52             |
| TE       | 0.10  | 0.06  | 0.08    | 0.01        | 0.49             |
| RB       | 0.10  | 0.05  | 0.09    | 0.11        | 0.42             |

### Defense (R² = 0.35 vs point diff, 0.25 vs spread — moderate)

| Position | Prior | Cap  | Reg(PD)  | Reg(spread) | Univariate r(PD) |
|----------|------:|-----:|---------:|------------:|-----------------:|
| EDGE     | 0.25  | 0.27 | 0.23     | 0.27        | 0.32             |
| CB       | 0.25  | 0.24 | 0.26     | 0.24        | **0.39**         |
| LB       | 0.20  | 0.16 | 0.25     | 0.24        | 0.30             |
| S        | 0.15  | 0.14 | **0.25** | 0.20        | 0.31             |
| **iDL**  | 0.15  | 0.19 | **0.01** | 0.05        | **0.12**         |

### Special teams (R² = 0.04 — essentially flat)

| Position | Prior | Cap  | Reg(PD) | Reg(spread) | Univariate r(PD) |
|----------|------:|-----:|--------:|------------:|-----------------:|
| K        | 0.55  | 0.52 | 0.51    | 0.51        | 0.15             |
| P        | 0.45  | 0.48 | 0.49    | 0.50        | 0.15             |

---

## Key findings

### 1. QB is much heavier than the prior or the cap

Regression: **0.60**. Prior: 0.40. Cap: 0.28. Univariate r = 0.74 (highest of any position by a wide margin). QB is *the* dominant position in predicting team success — even more than the consensus suggests, and considerably more than what cap allocation reveals.

The cap–regression gap is the expected scarcity artifact: QBs aren't paid 60% of the offense's cap because the supply of starting-caliber QBs is so small that the cap can't allocate that much to one position. The cap reflects price; regression reflects marginal contribution to wins. **Trust the regression.**

### 2. WR drops to ~0 in multivariate but is genuinely important univariately (multicollinearity)

WR's multivariate weight (0.01 vs point diff) is a textbook **multicollinearity collapse**. The univariate r is 0.52 — substantial. But conditional on QB grade being in the model, WR adds little marginal info. Good QBs make their receivers look better, so the WR composite is partly a measure of QB play already.

Setting WR weight at 0.01 would be wrong philosophically: WR's contribution isn't actually zero, it's *redundant given QB*. The regression can't separate them. We should weight WR meaningfully (0.10-0.15) — accepting some double-counting with QB — rather than pretending WR doesn't matter.

### 3. iDL is genuinely the lightest position group

Regression: 0.01. Univariate: 0.12 (lowest of any position). Even alone, iDL grade barely correlates with team success. This is the cleanest "this position matters less than analytics fans assume" finding.

Two explanations:
- **The iDL grade formula doesn't capture the value** — interior pressure is real, but the iDL grading methodology (ADR-0021) may miss what makes elite interior DLs valuable.
- **iDL actually matters less than people think** — a great iDL is a luxury, not a foundation. Defensive success comes more from EDGE + coverage.

Either way, iDL weight should be reduced from prior 0.15 → 0.10 or 0.12.

### 4. OL is around the prior, not the cap

Regression: 0.21–0.25. Cap: 0.43. Prior: 0.25.

The cap allocates ~43% of offense because OL is 5 players. But on a per-quality-of-play basis, OL contributes ~20-25% to team success. Cap-as-prior would have us overweight OL; regression backs the original 0.25.

### 5. Defense is more balanced than the prior suggested

Prior put EDGE & CB at 0.25 each and S at 0.15. Regression evens this out: all four (EDGE, CB, LB, S) sit at 0.23–0.26, with iDL the clear odd one out at 0.01.

Slight bump up for S (0.15 → 0.20), slight bump down for iDL (0.15 → 0.10–0.12).

### 6. Special teams is nearly 50/50 K vs P (regression and cap agree)

The ST regression R² is 0.04 — ST barely moves team outcomes at the team-season level. K and P are roughly equal. 0.50/0.50 or 0.55/0.45 — both defensible; either way it's a 10% slice of the total grade.

### 7. Offense regresses better than defense

Offense R² = 0.60. Defense R² = 0.35. This isn't itself a phase-weight signal, but it suggests **offense grades carry more team-success signal than defense grades** in this dataset. Two readings:
- Offense matters more in modern NFL (true to varying degrees in public research)
- Defensive position grades are noisier (defensive performance is more system-dependent)

Worth considering: bumping Offense phase weight slightly (0.45 → 0.50) and trimming Defense (0.45 → 0.40). Or staying at 0.45/0.45/0.10 to match the consensus framing. **Recommend staying 0.45/0.45/0.10** until v1.1 audit — phase-weight changes affect every team grade and should be made carefully.

---

## Reconciled weights (recommended for v1.0 ship)

Synthesizing the regression result, the cap anchor, and the known limitations (multicollinearity, sample size, iDL formula caveat):

### Offense (sums to 1.00)

| Position | Prior | Cap   | Regression | **v1.0**  |
|----------|------:|------:|-----------:|----------:|
| **QB**   | 0.40  | 0.28  | 0.61       | **0.45**  |
| OL       | 0.25  | 0.43  | 0.23       | **0.25**  |
| WR       | 0.15  | 0.18  | 0.04       | **0.13**  |
| RB       | 0.10  | 0.05  | 0.10       | **0.09**  |
| TE       | 0.10  | 0.06  | 0.04       | **0.08**  |

- **QB +0.05** over prior (was the strongest empirical finding; full move to 0.60 felt aggressive)
- **OL unchanged** — regression backs the original number
- **WR -0.02** — accept small reduction since multicollinearity warns against keeping it high, but don't drop to 0
- **RB -0.01**, **TE -0.02** — tiny trims to balance the QB bump

### Defense (sums to 1.00)

| Position | Prior | Cap  | Regression | **v1.0** |
|----------|------:|-----:|-----------:|---------:|
| EDGE     | 0.25  | 0.27 | 0.25       | **0.24** |
| CB       | 0.25  | 0.24 | 0.25       | **0.24** |
| LB       | 0.20  | 0.16 | 0.25       | **0.22** |
| **S**    | 0.15  | 0.14 | 0.23       | **0.20** |
| **iDL**  | 0.15  | 0.19 | 0.03       | **0.10** |

- **S +0.05** — regression supports a real bump
- **iDL -0.05** — regression strongly supports a reduction; cap-anchored to keep some weight
- LB +0.02, EDGE and CB -0.01 each — round out to sum to 1.00

### Special teams (sums to 1.00)

| Position | Prior | Cap  | Regression | **v1.0** |
|----------|------:|-----:|-----------:|---------:|
| K        | 0.55  | 0.52 | 0.51       | **0.52** |
| P        | 0.45  | 0.48 | 0.49       | **0.48** |

Move to near-even split. Both anchors agree.

### Phase weights (v1.1 audit — added 2026-05-25 same-day)

A second-stage regression: compute each team-season's `offense_grade`,
`defense_grade`, and `st_grade` using the v1.0 reconciled position
weights above, then regress team success on those three phase grades.
Combined R² = **0.79 vs point diff, 0.69 vs spread** — much stronger
fit than any single phase regressed alone.

| Phase | Prior | Cap   | Reg(PD)  | Reg(spread) | **v1.0** |
|-------|------:|------:|---------:|------------:|---------:|
| **Offense** | 0.45 | 0.49 | **0.58** | **0.64** | **0.55** |
| **Defense** | 0.45 | 0.49 | 0.36     | 0.34        | **0.40** |
| **ST**      | 0.10 | 0.02 | 0.06     | 0.02        | **0.05** |

Key findings:
- **Offense matters more than defense in modern NFL** — regression puts
  it at 0.58–0.64, well above the prior 0.45/0.45 balance. Aligns with
  the broader analytics consensus.
- **ST is lighter than the prior** — both anchors say 2-6%. The 0.10
  prior overweighted special teams.
- **Cap allocation says ~50/50 Off/Def** — but cap is forced to
  allocate by roster size (which biases toward defense via more
  rostered defensive players). The regression is the cleaner signal
  for "what moves team success."

Reconciled to **0.55 / 0.40 / 0.05**:
- Substantial move toward regression without going all the way to
  raw 0.60/0.35/0.05 (small sample = humility warranted)
- Defense at 0.40 keeps it meaningful — playoff narratives reward
  defense more than the regular-season regression captures
- ST at 0.05 not 0.02 — a peak-Tucker-grade kicker should still
  visibly move a team grade

---

## Caveats

- **Sample size:** 222 team-seasons / 5 features per phase. Ridge regression is appropriate but coefficients are noisy. The QB and iDL findings are large enough to survive this; smaller moves (e.g. WR -0.02) are within noise.
- **Multicollinearity:** explicitly limits how much trust to put in any single regression coefficient. The univariate diagnostics in the raw report help triangulate.
- **OL is graded by a separate methodology** (ADR-0025) using only 2 components. Its grade may be smoother / less differentiating than the player-position composites. This could under-weight OL in the regression.
- **iDL findings are partly methodology-conditional** — if the iDL grade formula is itself under-capturing iDL value, the regression confirms the grade is weak, not necessarily that the position is unimportant.
- **Closing spread coverage is incomplete** for early 2018 seasons (some games missing `spread_line`). Point-diff is fully populated and is the primary signal here.

---

## What changes in ADR-0026

Update the v1 weights table to the reconciled values above, with a short reference to this audit doc as the empirical basis. Phase weights stay 0.45/0.45/0.10.

A future v1.1 could:
- Re-audit with closing spreads from a cleaner historical source (e.g. an odds API rather than nflverse schedules)
- Investigate the iDL formula caveat directly (does QB pressures-allowed correlate better than the current iDL composite?)
- Run the audit at the position-component level (do certain *components* drive team success more than others?)
