# Pairwise Correlation Audit — 2026-05-14

Companion to [2026-05-14-cross-position-yoy.md](2026-05-14-cross-position-yoy.md). Where the YoY audit measures **reliability** (does the metric persist across seasons?), this audit measures **redundancy** (do multiple components within a position measure the same thing?).

Run on Neon. Data: `stat_components.z_score` for all qualified player-seasons (pooled across all available years per position). Pearson correlation between every component-pair within each position. Threshold convention:

- **|r| ≥ 0.85** — strong redundancy (essentially the same metric)
- **0.60 ≤ |r| < 0.85** — meaningful overlap (decide: keep both, drop one, or treat as one)
- **0.40 ≤ |r| < 0.60** — modest overlap (document, usually keep)
- **|r| < 0.40** — independent enough

Cross-position summary: **1 strong redundancy, 11 meaningful overlaps, 6 modest overlaps** across 9 positions.

## Position-by-position findings

### QB (n=344) — MOST REDUNDANT FORMULA

```
                  epa_per_dropback   cpoe   success_rate
epa_per_dropback              1.00   0.70           0.88
cpoe                          0.70   1.00           0.74
success_rate                  0.88   0.74           1.00
```

Every QB component pair correlates 0.70-0.88. **The formula has effectively one underlying signal weighted three ways.** Composite range is compressed (extreme players grade less extreme than they would with truly independent components), but rankings are preserved.

- `epa_per_dropback` ↔ `success_rate` at **r=0.883** (weights 0.50 + 0.25): Mathematically related — success rate ≈ "fraction of dropbacks with positive EPA"; EPA per dropback = mean. They're nearly the same metric.
- `cpoe` ↔ `success_rate` at r=0.738 (weights 0.25 + 0.25): Both lens "did the play work out."
- `epa_per_dropback` ↔ `cpoe` at r=0.697 (weights 0.50 + 0.25): Accuracy drives EPA, so correlated. Different mechanism (accuracy vs production), but high.

**Verdict: candidate for QB v1.1 weight tightening.** Options:

- Lower `success_rate` to 0.10 (it's the most redundant with EPA).
- Or merge success_rate into EPA (effective weights: 0.65 EPA, 0.35 CPOE).
- Both produce roughly the same ranking but a wider grade range and a cleaner methodology story.

### RB (n=452) — rushing components heavily correlated

```
                       ryoe   rush_epa   rush_success   rec_epa   yac_oe   fumble
ryoe                   1.00       0.61           0.39      0.07     0.17     0.06
rush_epa               0.61       1.00           0.75      0.15     0.17    -0.10
rush_success           0.39       0.75           1.00      0.14     0.15     0.12
rec_epa                0.07       0.15           0.14      1.00     0.64    -0.06
yac_over_exp           0.17       0.17           0.15      0.64     1.00     0.04
fumble_rate            0.06      -0.10           0.12     -0.06     0.04     1.00
```

- `ryoe_per_attempt` ↔ `rush_epa_per_attempt` at r=0.611 (0.28 + 0.18): Both rushing efficiency. RYOE strips OL/box; EPA captures scoring leverage. Distinct mechanism but overlapping.
- `rush_epa_per_attempt` ↔ `rush_success_rate` at **r=0.753** (0.18 + 0.14): Classic EPA-vs-success-rate redundancy.
- `rec_epa_per_target` ↔ `yac_over_expected_per_rec` at r=0.642 (0.05 + 0.28): We already lowered rec_EPA to 0.05 in v1.2, so this is no longer a weight concern.

**RB rushing has 0.60 of formula weight split across three correlated components (0.28 + 0.18 + 0.14).** The "true" independent rushing signal is probably worth ~0.40-0.45. Possible v1.3 simplification: drop rush_EPA (covered by RYOE + rush_success_rate), reallocate weight. Lower priority than QB since the rankings are likely fine.

### WR (n=822) — one meaningful pair, formula is mostly clean

```
                          rec_epa   yac_oe   sep   earn   succ   drop
rec_epa_per_target           1.00     0.36  0.04   0.22   0.76  -0.09
yac_over_expected_per_rec    0.36     1.00  0.20   0.09   0.23   0.07
separation                   0.04     0.20  1.00  -0.08   0.07  -0.01
target_earn_rate             0.22     0.09 -0.08   1.00   0.29  -0.17
success_rate_per_target      0.76     0.23  0.07   0.29   1.00  -0.19
drop_rate                   -0.09     0.07 -0.01  -0.17  -0.19   1.00
```

- `rec_epa_per_target` ↔ `success_rate_per_target` at **r=0.763** (0.35 + 0.08): Same EPA-vs-success pattern.

success_rate at +0.08 is small enough that even being mostly redundant doesn't cost much. Could remove for v1.3 cleanness but not urgent. The rest of the formula is well-separated — separation, target_earn_rate, drop_rate, and YAC-OE are all genuinely independent. **WR formula is healthy.**

### TE (n=332) — same pattern as WR

```
                          rec_epa   yac_oe   sep   earn   succ   drop
rec_epa_per_target           1.00     0.45  0.01   0.14   0.75  -0.15
yac_over_expected_per_rec    0.45     1.00  0.22   0.01   0.26   0.14
separation                   0.01     0.22  1.00  -0.15   0.01  -0.03
target_earn_rate             0.14     0.01 -0.15   1.00   0.13   0.03
success_rate_per_target      0.75     0.26  0.01   0.13   1.00  -0.25
drop_rate                   -0.15     0.14 -0.03   0.03  -0.25   1.00
```

- `rec_epa_per_target` ↔ `success_rate_per_target` at **r=0.749** (0.35 + 0.08): Same as WR.
- `rec_epa_per_target` ↔ `yac_over_expected_per_rec` at r=0.445 (0.35 + 0.27): Modest, expected (EPA includes YAC). Keep both.

### CB (n=946) — CLEANEST FORMULA

```
                       PR_allowed   yac_allow   target_rate   pbu
passer_rating_allowed        1.00        0.14          0.04  -0.47
yac_per_rec_allowed          0.14        1.00         -0.02  -0.12
target_rate                  0.04       -0.02          1.00  -0.12
pbu_rate                    -0.47       -0.12         -0.12   1.00
```

- `passer_rating_allowed` ↔ `pbu_rate` at r=−0.475 (−0.35 + 0.12): Negative because PBU prevents catches → lower PR allowed. This is **mechanism, not redundancy.** PBU is a distinct active play; PR captures aggregate damage. Keep both.

No other pair above 0.40. **CB formula has the cleanest independence — every component captures a different dimension of cornerback skill.**

### S (n=625) — clean, similar to CB

```
                                  PR_alw   pbu   tgt   tackles/snap   miss_tkl   bf_disrupt
passer_rating_allowed               1.00 -0.44 -0.01           0.14       0.07        -0.02
pbu_rate                           -0.44  1.00 -0.35          -0.29       0.02        -0.11
target_rate                        -0.01 -0.35  1.00           0.39      -0.06         0.26
tackles_per_snap                    0.14 -0.29  0.39           1.00      -0.22         0.33
missed_tackle_rate                  0.07  0.02 -0.06          -0.22       1.00        -0.05
backfield_disruption_per_snap      -0.02 -0.11  0.26           0.33      -0.05         1.00
```

- `passer_rating_allowed` ↔ `pbu_rate` at r=−0.441 (−0.30 + 0.12): Same mechanism as CB. Keep both.

No redundancy issues. **Safety formula is well-separated.**

### EDGE (n=633) — heavy overlap, partly designed

```
                       pressure   sack   tfl   missed_tkl
pressure_rate              1.00   0.73  0.60       -0.08
sack_rate                  0.73   1.00  0.78       -0.18
tfl_rate                   0.60   0.78  1.00       -0.13
missed_tackle_rate        -0.08  -0.18 -0.13        1.00
```

- `pressure_rate` ↔ `sack_rate` at **r=0.728** (0.35 + 0.30): Designed overlap. ADR-0020 explicitly notes "Intentional overlap with pressure_rate to weight the highest-value plays more heavily." Sack rate is a premium-event boost on top of pressure rate.
- `sack_rate` ↔ `tfl_rate` at **r=0.778** (0.30 + 0.15): Less obviously designed. Sacks are excluded from def_tackles_for_loss numerically, but the underlying skill (backfield disruption) is the same.
- `pressure_rate` ↔ `tfl_rate` at r=0.599 (0.35 + 0.15): Same dynamic.

**The three positive components effectively triple-measure "backfield disruption."** The 0.80 of total positive weight has maybe 0.50-0.60 worth of independent signal. The formula isn't broken (designed intentional overlap per ADR), but the methodology page should acknowledge it.

### iDL (n=563) — same pattern as EDGE

```
                  tfl   pressure   sack   missed_tkl
tfl_rate         1.00       0.57   0.74        -0.24
pressure_rate    0.57       1.00   0.78        -0.35
sack_rate        0.74       0.78   1.00        -0.32
missed_tkl_rate -0.24      -0.35  -0.32         1.00
```

All three pass-rush components correlate 0.57-0.78. Same as EDGE. Heavy designed overlap. Acknowledge in ADR.

### LB (n=430) — clean except one modest pair

```
                       tfl   PR_allowed   miss_tkl   pbu   tackle   pressure
tfl_rate              1.00        -0.07       0.13 -0.01     0.04       0.41
passer_rating_allowed -0.07         1.00      -0.02 -0.39     0.12      -0.14
missed_tackle_rate     0.13        -0.02       1.00  0.07    -0.28       0.11
pbu_rate              -0.01        -0.39       0.07  1.00    -0.20       0.07
tackle_rate            0.04         0.12      -0.28 -0.20     1.00      -0.15
pressure_rate          0.41        -0.14       0.11  0.07    -0.15       1.00
```

- `tfl_rate` ↔ `pressure_rate` at r=0.413 (0.20 + 0.07): Modest. Both measure penetration. Keep — distinct enough.

LB formula is well-separated. Six components capture six different LB skills.

## Cross-system patterns

1. **The classic EPA-vs-success-rate redundancy appears everywhere it's possible:**
   - QB epa ↔ success_rate: r=0.88 (worst in system)
   - RB rush_epa ↔ rush_success_rate: r=0.75
   - WR rec_epa ↔ success_rate: r=0.76
   - TE rec_epa ↔ success_rate: r=0.75
   
   Mechanistically, success_rate is just "fraction of plays with positive EPA," so this redundancy is mathematically guaranteed. Wherever both appear in a formula, the success_rate component is largely a smoothed version of the EPA component.

2. **Backfield-disruption stats (pressure / sack / TFL) correlate strongly for all DL positions** — EDGE and iDL both have all three pass-rush components correlated 0.57-0.78. Different play-type breakdowns of the same underlying skill.

3. **Coverage-damage stats (passer_rating_allowed) inversely correlate with PBU** at all three coverage positions (CB −0.47, S −0.44, LB −0.39). This is mechanism, not redundancy — PBUs reduce passer rating allowed by definition.

4. **The two cleanest formulas are CB and S** (defensive backs). Every component captures an independent dimension. Probably because the v1.1 passer-rating-allowed swap consolidated comp%+yds/tgt+INT into one metric — removed previously-existing intra-formula redundancy.

5. **The two messiest are QB (first-shipped) and EDGE/iDL (designed overlap).** QB's overlap is unintended and worth fixing; EDGE/iDL's is documented and intentional.

## Recommended actions

Ranked by priority:

### Priority 1 — QB v1.1 weight tweak

QB EPA ↔ success_rate at r=0.88 is the strongest redundancy in the system, and the weights (0.50 + 0.25) make it the most-impactful. Recommend: lower success_rate from 0.25 to 0.10, leave CPOE at 0.25, leave EPA at 0.50. New sum |w| = 0.85; the combiner normalizes so EPA effectively grows from 50% to 59%, which matches the redundancy structure (success_rate was largely double-counting EPA).

Preview first, but expected: top QBs unchanged, grade range slightly wider, success_rate-heavy seasons (think: clean operators who don't make explosive plays) drop slightly.

### Priority 2 — RB v1.3 rushing-component cleanup (lower urgency)

RB rush_EPA at 0.18 is partly redundant with rush_success_rate (r=0.75) and RYOE (r=0.61). Could drop rush_EPA to ~0.05 and bump RYOE+rush_success_rate to absorb. But the rankings are probably fine; this is a polish-not-fix.

### Priority 3 — EDGE/iDL ADR additions (documentation)

ADR-0020 (EDGE) and ADR-0021 (iDL) should explicitly call out that pressure/sack/TFL overlap is intentional, with the correlation numbers from this audit. Helps future-us not "fix" something that's working as designed.

### Priority 4 — WR/TE success_rate review (low priority, defer)

`wr_success_rate_per_target` and `te_success_rate_per_target` are at 0.08 weight each, partly redundant with rec_EPA. Could drop to 0.05 or remove. Not urgent; harm is bounded by the small weight.

## Why this audit is more useful than YoY r alone

YoY r tells us "does this metric persist as skill across seasons?" Correlation tells us "do we measure the same thing twice?" They're orthogonal questions:

- A component can pass YoY (real signal) and fail correlation (redundant with another component) — that's the QB EPA/success case.
- A component can fail YoY (noisy) and pass correlation (independent signal direction) — that's where we land for fumble/drop/PBU rate.

The methodology needs BOTH checks. The cross-position-YoY audit caught the noise components; this correlation audit caught the QB redundancy that YoY alone missed.
