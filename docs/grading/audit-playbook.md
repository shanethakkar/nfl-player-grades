# Grading Formula Methodology — Audit + Design Process

The playbook for designing, auditing, and revising any position's grading formula. Originally developed during WR v1.1 research (2026-05-14), refined after the cross-position YoY audit, the pairwise correlation audit, and the validity baseline. Formalized into the current four-criterion framework on 2026-05-14.

**The framing principle:** Weights are reasoned. Data informs reasoning, never replaces it. We accept that our grades may disagree with consensus in ways an automated system would correct toward; this is intentional, because the grading system's value is the *defined-good* it represents, not its match to crowd-sourced ground truth.

## The four criteria

Every component currently in a formula AND every candidate stat considered for inclusion is scored on these four:

| # | Criterion | What it measures | Threshold |
|---|---|---|---:|
| 1 | **Reliability** (YoY r) | Does the metric persist as skill across seasons? | r ≥ 0.20 modest, ≥ 0.40 strong |
| 2 | **Cross-sectional discrimination** | Does it meaningfully separate players in a single season? | Real spread (not constant) |
| 3 | **Independence** (max \|r\| with existing) | Does it add new information vs current components? | \|r\| < 0.60 |
| 4 | **Predictive validity** (Pro Bowl r) | Does it predict consensus-elite selection next year? | r ≥ 0.15 positive |

A component or candidate that **passes all four** is a strong inclusion. A component that **fails one** needs decision logic — see below.

## Decision tree from the four criteria

After scoring a component/candidate on the four criteria:

- **All four good** (YoY ≥ 0.20, real spread, independent, validity ≥ 0.15) → **ADD or KEEP at full weight.**
- **High YoY r + high redundancy** (max \|r\| ≥ 0.60) → Decide: keep the *stronger* of the redundant pair (by YoY r or validity), drop the weaker, or treat as one effective component when sizing.
- **Low YoY r + low cross-sectional + low validity** → **NOISE, reject** (or weight tiny ≤0.05 if removing requires schema change).
- **Low YoY r BUT high cross-sectional + high validity** → **Context-dependent skill.** Keep at chosen weight; document that YoY noise is structural team-context dependence, not measurement failure. (Example: WR rec_epa_per_target — YoY r 0.171, real spread, real validity.)
- **High YoY r but negative or zero validity** → Investigate; may be measuring style/usage rather than skill. (Example: QB aggressiveness — high YoY r 0.43 but validity −0.21; reflects style, not "good QB.")

## The six-step audit process

For any new component proposal or existing component review:

### Step 1 — Skill-Tree Mapping

List the distinct skills a great player at this position needs. Map each existing formula component to one or more skills. Identify:

- **Gaps**: skills with NO component covering them.
- **Redundancy**: multiple components covering the same skill.

Example (WR): separation, hands/drops, YAC, earning targets, ball security, big plays, consistency, red zone, contested catches.

### Step 2 — Pairwise Correlation Audit (independence check)

For each pair of components in the current formula, compute the Pearson correlation across all qualified player-seasons (z_score, pooled across seasons). Threshold convention:

- **\|r\| ≥ 0.85** — strong redundancy (essentially the same metric).
- **0.60 ≤ \|r\| < 0.85** — meaningful overlap. Decide.
- **0.40 ≤ \|r\| < 0.60** — modest. Document, usually keep.
- **\|r\| < 0.40** — independent enough.

**Classic redundancy patterns to watch for:**

1. **EPA per X ↔ success rate per X** — mathematically related (success rate ≈ "fraction of plays with positive EPA"). Wherever both appear, success_rate is largely smoothed EPA. Observed in QB (r=0.88), RB rush (r=0.75), WR (r=0.76), TE (r=0.75).
2. **Pressure / sack / TFL** for DL positions — all measure "backfield disruption." Observed at r=0.57-0.78 for EDGE and iDL. Partly intentional (sack as pressure-premium); partly real overlap.
3. **Passer rating allowed ↔ PBU rate** for coverage positions — negative correlation because PBUs reduce PR allowed. Mechanism, not redundancy.

See [audits/2026-05-14-correlation.md](audits/2026-05-14-correlation.md) for the cross-system numbers.

### Step 3 — YoY Noise Check (reliability)

For each component, compute year-over-year Pearson r across consecutive season pairs for the qualified cohort.

Interpretation:

- **YoY r > 0.40** — real skill signal, worth weighting meaningfully.
- **0.20 < YoY r < 0.40** — modest signal, weight carefully.
- **YoY r < 0.20** — needs the cross-sectional + validity check before deciding. Two failure modes:
  1. **Pure noise** — also has low cross-sectional spread + low validity. Reject or weight ≤0.05.
  2. **Context-dependent skill** — high cross-sectional spread + meaningful validity. Keep at chosen weight; document the limitation.

**Symmetry rule:** the YoY noise check applies to *additions* as well as *removals*. In WR v1.1, it was applied to fumble_rate (removed) but skipped on drop_rate (added at over-weight). That gap is what triggered the cross-position audit. Symmetric application is the rule.

**Measurement-error suppression caveat:** at small per-player denominators (TE catchable ~47, RB fumble counts, etc.), YoY r is mechanically depressed by measurement noise even if the underlying skill is perfectly stable. When YoY r is weak but face-check is strong year-over-year, the metric likely has real skill content. Land at light weight (≤0.05).

### Step 4 — Downstream Predictive Validity (external truth)

For each component (or candidate), compute correlation with **next-year Pro Bowl selection** across qualified player-seasons.

This is the external check on whether the metric is measuring skill that the broader football world also recognizes. Expected range for healthy metrics: **+0.15 to +0.50** (Pro Bowl voting carries narrative bias; perfect grading can't reach r=1.0 even theoretically).

**Direction note:** "Bad QB" indicators (sack_rate_suffered, drop_rate, missed_tackle_rate) have *negative* validity correlations — that's expected and means they should enter the composite with a *negative* weight. The verdict logic looks at \|validity_r\| for direction-agnostic strength.

Baseline composite-grade Pro Bowl correlations per position are in [audits/2026-05-14-validity-baseline.md](audits/2026-05-14-validity-baseline.md). These are the targets to beat (or at least not degrade) when shipping any weight change.

### Step 5 — Honest Weight Sizing

Weight should be proportional to:

1. **Signal strength** (YoY r and cross-sectional discrimination).
2. **Skill-tree importance** (is this a core position skill or peripheral?).
3. **Independence** (correlation with existing components — penalize overlap).
4. **External validity** (does it predict consensus-elite performance?).
5. **Data quality** (sample size, missing-value rate, source reliability).

Don't reverse-engineer weights to make the leaderboard match consensus. If a known elite player grades low, document the limitation rather than tuning the weights to flatter them.

### Step 6 — Pre-implementation Face-check

Before committing a new formula:

1. Use [iteration-workflow.md](iteration-workflow.md) to preview the change.
2. Sort and inspect the top 10 and bottom 5.
3. Verify the names track real-world reputation. If they don't, either:
   - The stat is measuring something different than you think (revisit the mental model).
   - The data has quality issues (check coverage gaps).
   - Your prior on consensus is wrong (rare but possible).

## Hold-out validation (process norm, 2026-05-14)

For any major change (adding a component, removing a component, or any weight change touching ≥0.10 of formula weight), apply hold-out validation:

1. **Define the change** based on data from 2016-2023 (or 2018-2023 for defensive positions).
2. **Compute the change's effect on the held-out window 2024-2025** — does it improve face-check, predictive validity, or other metrics on data that didn't inform the decision?
3. **Document the held-out performance** in the ADR revision history.

This is a check against overfitting to "all data we've seen." Small weight tweaks (<0.10) and noise-removal cuts don't require formal hold-out — but anything where we're claiming the change "improves" the formula should be validated on data outside the audit window.

## Don't add it just because someone else's grader has it

Other agents / public formulas / PFF will often propose stats we don't have the data for (YPRR, CROE for WRs) or stats that look fancy but are usage artifacts (RACR, contested_rate). Always run them through the full four-criterion audit before adopting. Many "industry standard" WR stats turned out to be redundant with what we already compute. Check [data-inventory.md](data-inventory.md) first — many proposed stats aren't computable in our data.

## The exhaustive candidate audit (article-worthy version)

For each new position (K, P, OL) and for retroactive audits of shipped positions:

1. **Pull every relevant column** from data inventory for that position type.
2. **Filter by mechanical relevance.** Drop volume stats, pure usage markers, columns we already know can't be used (PFF-only with no nflverse equivalent).
3. **Score every survivor on all four criteria** using `nflgrades audit-candidates --position <POS>`.
4. **Skill-tree map the survivors.**
5. **Decide per candidate** — confirm current pick, replace, add, or reject. **Document the verdict for every candidate**, not just the ones included.
6. **Output to `docs/grading/audits/2026-XX-XX-exhaustive-<pos>.md`** so the audit log is reproducible.

The point of documenting rejected candidates is making the methodology defensible. Anyone who asks "why these stats?" can look at the audit log and see exactly which stats were considered, what their four-criterion scores were, and why each non-included one was rejected.

## Tooling

| Tool | Purpose |
|---|---|
| `nflgrades preview` | What-if weight tweaks, read-only |
| `nflgrades regrade` | Apply weight changes without re-extracting features |
| `nflgrades validity` | Run the Pro Bowl predictive validity baseline |
| `nflgrades audit-candidates --position POS` | Run the four-criterion audit on a position's candidate set |
| `pipeline/scripts/sync_weights_to_web.py` | Keep `grades.ts` weights in sync with `weights.py` |
| Cross-position YoY audit script | Per-component YoY check (see [audits/2026-05-14-cross-position-yoy.md](audits/2026-05-14-cross-position-yoy.md)) |
| Pairwise correlation audit script | Per-position redundancy matrix (see [audits/2026-05-14-correlation.md](audits/2026-05-14-correlation.md)) |
