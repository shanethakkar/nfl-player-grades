# QB Exhaustive Candidate Audit — 2026-05-14

First production application of the four-criterion audit framework. Scored every plausible QB candidate stat from our data inventory against:

1. **Reliability** — YoY Pearson r across 7+ consecutive season pairs (2017→2018 through 2024→2025)
2. **Cross-sectional discrimination** — within-season std of the candidate
3. **Independence** — max abs Pearson r vs currently-shipped QB components (in z-units, qualified player-seasons)
4. **Predictive validity** — Pearson r between this-year candidate value and next-year Pro Bowl selection

**Cohort:** qualified QB-seasons across 2017-2024 (n=344 for stat_components-derived; n=312 for NGS data 2017+; n=273 for PFR data 2018+).

Tool: `nflgrades audit-candidates --position QB` (framework in [pipeline/src/nfl_grades/grading/exhaustive_audit.py](../../../pipeline/src/nfl_grades/grading/exhaustive_audit.py)).

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped (re-scored with self-excluded):** | | | | | | | |
| `qb_epa_per_dropback` | 344 | +0.415 | 0.13 | **+0.863** | qb_success_rate | +0.158 | STRONG REDUNDANCY |
| `qb_cpoe` | 344 | +0.377 | 3.33 | +0.726 | qb_success_rate | +0.146 | MEANINGFUL OVERLAP |
| `qb_success_rate` | 344 | +0.467 | 0.04 | **+0.848** | qb_epa_per_dropback | +0.130 | MEANINGFUL OVERLAP |
| **nflvs_player_stats-derived:** | | | | | | | |
| `qb_td_rate` | 344 | +0.398 | 0.01 | +0.729 | qb_epa_per_dropback | **+0.260** | MEANINGFUL OVERLAP |
| `qb_int_rate` | 344 | +0.165 | 0.01 | −0.450 | qb_epa_per_dropback | −0.150 | NOISE |
| `qb_first_down_rate` | 344 | +0.481 | 0.04 | **+0.863** | qb_success_rate | +0.113 | STRONG REDUNDANCY |
| `qb_sack_rate_suffered` | 344 | +0.456 | 0.02 | −0.514 | qb_epa_per_dropback | −0.020 | Independent / weak validity |
| `qb_sack_fumble_rate` | 344 | +0.096 | 0.07 | −0.059 | qb_cpoe | −0.035 | NOISE |
| `qb_pacr` | 344 | +0.498 | 0.12 | +0.516 | qb_success_rate | +0.044 | Independent / weak validity |
| `qb_rush_epa_per_rush` | 339 | +0.398 | 0.31 | −0.084 | qb_success_rate | +0.041 | Independent / weak validity |
| **NGS passing (2017+):** | | | | | | | |
| `qb_ngs_aggressiveness` | 312 | +0.435 | 2.71 | −0.169 | qb_cpoe | **−0.213** | Independent / weak validity |
| `qb_ngs_time_to_throw` | 312 | **+0.667** | 0.15 | −0.157 | qb_success_rate | +0.114 | Independent / weak validity |
| `qb_ngs_air_yards_to_sticks` | 312 | +0.356 | 0.97 | +0.226 | qb_epa_per_dropback | +0.111 | Independent / weak validity |
| `qb_ngs_air_yards_differential` | 312 | +0.438 | 0.55 | +0.439 | qb_success_rate | −0.036 | Independent / weak validity |
| `qb_ngs_intended_air_yards` | 312 | +0.445 | 0.98 | +0.113 | qb_epa_per_dropback | +0.113 | Independent / weak validity |
| `qb_ngs_expected_completion_pct` | 312 | +0.472 | 2.27 | +0.316 | qb_success_rate | +0.076 | Independent / weak validity |
| `qb_ngs_cpoe` | 312 | +0.491 | 3.02 | +0.807 | qb_cpoe | +0.055 | MEANINGFUL OVERLAP |
| **PFR advanced (2018+):** | | | | | | | |
| `qb_pfr_bad_throw_pct` | 273 | +0.493 | 0.03 | −0.577 | qb_cpoe | +0.041 | Independent / weak validity |
| `qb_pfr_pressure_rate_faced` | 273 | +0.553 | 0.05 | −0.461 | qb_success_rate | +0.098 | Independent / weak validity |

## Per-candidate verdict + reasoning

### Currently shipped (decide whether to keep / change weight)

**`qb_epa_per_dropback` — KEEP at 0.50 weight.**
- Strong YoY (0.415), best validity of the three current components (0.158). The primary QB production signal.
- The 0.863 redundancy with success_rate is the formula's main problem, not this component's problem. Fix from the success_rate side.

**`qb_cpoe` — KEEP at 0.25 weight.**
- Modest YoY (0.377), middle validity (0.146). The only component that captures accuracy as a separable skill from production. EPA can be high with mediocre accuracy if YAC carries the play; CPOE catches accuracy specifically.
- Overlap with success_rate (+0.726) is real but more conceptually distinct than EPA↔success.

**`qb_success_rate` — LOWER to 0.10 weight.**
- Strongest YoY of the three (0.467) but **weakest validity (0.130) and most heavily redundant with EPA (+0.848).** Mathematically: success_rate ≈ "fraction of plays with positive EPA"; EPA per dropback = mean. Two views of the same underlying skill.
- The correlation audit flagged this independently; this audit confirms it. Lowering to 0.10 is the right call.

### Other candidates with strong signal

**`qb_td_rate` — REJECT despite highest validity.**
- YoY 0.398 + validity **+0.260** (highest of all candidates). Tempting to add.
- BUT: 0.729 correlated with EPA (meaningful overlap). TD rate ≈ "EPA conditioned on red zone." Adding it would mostly double-count outcome value already in EPA.
- Adding it would also chase consensus signal — TDs drive Pro Bowl voting more than they drive skill. Resist.

**`qb_first_down_rate` — REJECT.**
- YoY 0.481 (strong), validity 0.113. But **+0.863 with success_rate** — essentially the same metric. Moving the chains = positive EPA.

**`qb_pfr_bad_throw_pct` — REJECT.**
- YoY 0.493 (very stable!), validity 0.041 (weak). Correlated −0.577 with CPOE.
- "Bad throw" is the inverse of CPOE from PFR's subjective lens. Same accuracy skill from a different vantage. Adding it would replicate CPOE.

**`qb_pfr_pressure_rate_faced` — REJECT.**
- YoY 0.553, validity 0.098. Independent (max_r −0.461 with success_rate).
- BUT: pressure faced is **partly OL quality, partly QB pocket presence.** We can't separate the two with public data. Adding it would conflate offensive line quality with QB skill. Skip.

**`qb_sack_rate_suffered` — REJECT.**
- YoY 0.456, validity essentially zero (−0.020).
- Same OL-vs-QB conflation problem as pressure_rate. The strong YoY mostly reflects OL stability across seasons, not QB skill. Validity confirms it doesn't predict Pro Bowl.

### NGS metrics — all rejected

**`qb_ngs_time_to_throw` — REJECT.** YoY 0.667 (most stable in the audit!), validity 0.114. **High stability but no predictive validity.** Time-to-throw is a style indicator — Mahomes (long) and Burrow (quick) both win Pro Bowls. Not measuring skill, measuring approach.

**`qb_ngs_aggressiveness` — REJECT.** YoY 0.435, validity **−0.213 (negative!).** More aggressive throws → LESS Pro Bowl recognition. Reflects style not skill (and possibly a selection effect — desperate QBs throw aggressively).

**`qb_ngs_cpoe` — REJECT (duplicate of existing CPOE).** YoY 0.491, **+0.807 with qb_cpoe.** NGS's version of the same metric we already pull from PBP. The 0.81 correlation (not 1.0) reflects slight definitional differences. Not worth swapping for marginal gain.

**`qb_ngs_air_yards_to_sticks` / `air_yards_differential` / `intended_air_yards` / `expected_completion_percentage`** — all reject for weak validity (0.07-0.11) and conceptual overlap with existing components. Mostly style/usage markers.

### Rate-event noise — rejected

**`qb_int_rate` — NOISE.** YoY 0.165 (below threshold). Same pattern as fumble_rate for WRs — INT events are too rare per season (median ~12-15) to stabilize. Already implicitly captured by EPA (each INT is a hugely-negative-EPA play).

**`qb_sack_fumble_rate` — NOISE.** YoY 0.096. Rare event compounded by another rare event (sack THEN fumble). Pure noise.

### Mobility — borderline, parked for now

**`qb_rush_epa_per_rush` — REJECT for v1.1 (revisit later).**
- YoY 0.398, validity +0.041 (weak), max_r −0.084 (truly independent).
- **Skill-tree argument**: mobile QB value (Lamar, Allen, Hurts) isn't in the current formula. Adding it would partially address that gap.
- **Against**: weak validity (Pro Bowl voters reward passing, not rushing). Per-rush EPA mixes scramble value with designed-rush value — hard to interpret.
- **Decision**: don't add in this revision. Worth revisiting when we have better data — e.g., scramble-vs-design split, or a separate "QB rushing sub-grade" surfaced separately rather than baked into the composite.

## What this audit confirms

1. **The correlation audit was right.** QB v1's three components are heavily overlapping. Lowering `qb_success_rate` is the right fix — it has the worst combination of redundancy (+0.848 with EPA) and validity (0.130, lowest of the three).

2. **No new components emerged as compelling adds.** The most interesting candidates by validity (td_rate +0.260) or YoY (time_to_throw +0.667) all either overlap with existing components or fail the validity bar.

3. **The 3-component QB formula is the right shape** — EPA + CPOE + (a third dimension). The question is just what the third dimension should be and at what weight.

4. **Mobility (rush_epa_per_rush) is the only conceptual gap.** Documented as known limitation; not addressed in v1.1.

## Decision: QB v1.1 weight change

**Lower `qb_success_rate` from 0.25 → 0.10. Keep EPA at 0.50, CPOE at 0.25. New sum |w| = 0.85** (combiner normalizes; EPA effectively grows from 50% → 59%).

Expected impact based on the preview workflow:

- **Top QBs unchanged** at the very top (Mahomes, Allen, Burrow archetype).
- **Slightly wider grade range** — extreme players grade less compressed.
- **Slight relative drop for "clean operator" QBs** (Brock Purdy, Goff archetype — high success rate, modest explosive plays) compared to "high-EPA-with-some-variance" QBs (Allen, Jackson).

**Validity gate:** the preview/regrade workflow needs to produce a validity correlation that matches or beats the current baseline of +0.237. If it drops, back out.

## Article-worthy artifact

This audit is the first complete application of the four-criterion exhaustive process. Anyone asking "why did you pick these QB stats?" gets pointed at this document — 19 candidates evaluated, each with the four scores, each with a documented verdict (kept / rejected / why). The audit log is the methodology defense.

Format and approach will be replicated for each of the remaining 8 shipped positions (queue items 5-12).
