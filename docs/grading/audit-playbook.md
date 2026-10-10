# Grading Formula Methodology: Audit + Design Process

How to design, audit and change any position's Formula. Rewritten 2026-10-04
(#12) after the [2026-09-27 system audit](audits/2026-09-27-system-audit.md)
found the previous process unsound. Decisions: [ADR-0027](../adr/0027-grade-measures-attributable-performance.md)
(what a Grade measures), [ADR-0029](../adr/0029-reputation-free-evaluation.md)
(how changes are judged).

**The framing principle:** a Grade measures season performance *attributable
to the player* (ADR-0027). Weights are reasoned from the skill tree, then
**tested** for whether they measure the player reliably. Reputation (Pro Bowl
voting, consensus top-10 lists) is a sanity check, never a target.

## What changed, and why

The 2026-05-14 framework scored every Component on four criteria (YoY r,
cross-sectional spread, independence, next-year Pro Bowl r) and let
"context-dependent skill" keep low-YoY Components at full weight. Both are
**retired**:

- **Next-year Pro Bowl r can't resolve the changes it justified.** Its SE is
  0.03–0.07; the deltas used to ship changes were +0.005–0.02. Its labels had
  bugs (name-only join, unlabeled seasons counted as "not selected"), and it
  mostly measures persistence plus reputation.
- **"Context-dependent skill" was the loophole that kept team context in the
  grade.** Wide spread in a noisy Component *is* the noise, and the YoY that
  survived was largely the team (QB EPA/db YoY .43 for stayers, .10 for team
  changers).
- **"Cross-sectional discrimination"** was a raw-unit SD: unit-dependent and
  not a measure of skill.
- **No hold-out was ever run.**

## The ship rule

Every Formula change (a weight change, a removed Component or a Candidate) is
judged with `nflgrades evaluate` on three reputation-free criteria:

| Criterion | What it measures | How |
|---|---|---|
| **Reliability** | How much of the Composite is signal rather than sampling noise within one season | Odd-week vs even-week Composite r, stepped up to a full season with Spearman-Brown |
| **Portability** | Whether the grade measures the player rather than the team | Composite YoY for players who changed teams |
| **Next-season prediction** | Whether the grade carries forward | Composite N → Composite N+1, and Composite N → the primary Component in N+1 |

Each is estimated on a **2016–2022 fit window** and a **2023–2025 hold-out**.
A window only sees its own seasons; YoY pairs straddling 2022→2023 belong to
neither. Use the fit window to explore. **The decision is made on the
hold-out.**

A change **ships** only if, on the hold-out:

1. neither Reliability nor Portability falls beyond noise (the paired delta's
   95% CI is not entirely below zero), **and**
2. at least one of Reliability, Portability or next-season prediction
   improves with a paired-delta CI excluding zero, **and**
3. it passes the skill-tree review and face check below.

`nflgrades evaluate` prints a PASS/FAIL for (1) and (2). Paired deltas use a
player-clustered bootstrap (all of a player's seasons resample together), so
the CI reflects player-to-player variation, not just row count.

### Reading the numbers

- Per-metric CIs are Fisher-z and treat player-seasons as independent, so
  they run a little narrow. Trust the paired-delta CIs for decisions.
- Portability rests on few rows (hold-out team changers: QB ~11, RB ~14,
  WR ~20, TE ~5). A wide Portability CI is normal; the rule only blocks a
  change if Portability falls *beyond* noise. At TE it can neither block nor
  support one.
- Next-season prediction against the primary Component favours that
  Component. Read it alongside Composite YoY.
- Split-half Reliability is an *upper* bound on individual skill: both halves
  share the QB and the scheme. Portability is the check against that.
- Same-season, position-matched **Pro Bowl r** is printed as face validity.
  It never gates a change.

## The design process

### Step 1: Skill-tree mapping

List the distinct skills a great player at the position needs. Map each
Component to one or more skills. Identify:

- **Gaps**: skills with no Component.
- **Redundancy**: several Components covering the same skill.
- **Attribution**: for each Component, how much belongs to the player and how
  much to the QB, scheme or teammates (ADR-0027). Prefer Components that
  isolate the player (K FGOE, OL YBC vs RB yards after contact) over raw
  outcome efficiency.

### Step 2: Redundancy check

Pairwise correlation of Component z-scores across Qualified player-seasons:

- **|r| ≥ 0.85**: the same measurement twice.
- **0.60–0.85**: meaningful overlap; decide which carries the skill.
- **< 0.60**: independent enough.

Classic patterns: EPA per X ↔ success rate per X (success rate is mostly
smoothed EPA); pressure / sack / TFL for DL; passer rating allowed ↔ PBU rate
(mechanism, not redundancy). See [audits/2026-05-14-correlation.md](audits/2026-05-14-correlation.md).

### Step 3: Evaluate

```bash
# Baseline: the current Formula
nflgrades evaluate --position QB

# A weight change
nflgrades evaluate --position QB --weight qb_success_rate=0.05

# A Candidate Component (registered in grading/panels.py)
nflgrades evaluate --position QB --candidate qb_sack_rate --weight qb_sack_rate=-0.10
```

Iterate on the fit window. When you have one proposal, read its hold-out
verdict once. Re-tuning against the hold-out until it passes turns the
hold-out into a fit window.

To score a new Candidate, add a `Candidate` to `grading/panels.py`: an
extract that takes `(conn, season, week_parity)` and returns `player_id`,
`raw` (the per-play rate) and `n` (its sample size), plus a shrinkage k.

### Step 4: Skill-tree review and face check

1. Re-read the change against the skill tree: does the new weighting say what
   a good player at this position does, and is it attributable to him?
2. Preview it ([iteration-workflow.md](iteration-workflow.md)) and read the
   top 10 and bottom 5 for a couple of seasons. If the names are implausible,
   the Component is measuring something other than you think, or the data has
   a gap.
3. **Don't tune to flatter known players.** A good player grading low is a
   documented limitation, not a reason to move weights.

### Step 5: Ship and record

Follow [iteration-workflow.md](iteration-workflow.md) (preview → sync web
weights → regrade every season, including the in-progress one). Add an entry
to the position's ADR revision history with the hold-out table from
`nflgrades evaluate`: current, proposed and paired delta for every metric.

## Candidates: document every verdict

When auditing a position, score every plausible Candidate from the
[data inventory](data-inventory.md), not just the favourites, and record the
verdict for each (shipped, rejected, and why) in
`docs/grading/audits/YYYY-MM-DD-<pos>.md`. Anyone asking "why these stats?"
should find the rejected ones too.

Don't add a stat because PFF or another public model has it. Many are
unavailable in public data (YPRR, CROE) or are usage artifacts (RACR,
contested rate). It goes through the same ship rule as anything else.

## Coverage

`nflgrades evaluate` covers QB, RB, WR and TE. The defensive positions,
specialists and OL (#14) follow. Until a position is covered, a Formula
change there waits for its harness slice. Baselines for the current
Formulas: [RB/WR/TE](audits/2026-10-10-evaluation-baseline-rb-wr-te.md).

`scripts/verify_evaluation_panels.py` checks that a position's full-season
panel still reproduces the stored Components and Composites. Run it after
changing a grader's extract.

## Tooling

| Tool | Purpose |
|---|---|
| `nflgrades evaluate --position P [--weight k=v] [--candidate name]` | The ship rule: Reliability, Portability, next-season prediction, fit vs hold-out, paired deltas |
| `nflgrades preview` | What-if weights on one season's leaderboard (face check), read-only |
| `pipeline/scripts/preview_extract.py` | Face check for grader code changes (Path B) |
| `nflgrades regrade` | Apply weight changes from stored z-scores |
| `nflgrades validity` | Same-season, position-matched Pro Bowl face-validity report (not a gate) |
| `nflgrades audit-candidates --position P` | Legacy four-criterion table; its verdict hints predate ADR-0029. Use for redundancy (max_r) only |
| `pipeline/scripts/sync_weights_to_web.py` | Keep `grades.ts` weights in sync with `weights.py` |
| `pipeline/scripts/audit_2026_09_27/` | The system audit's analysis scripts, frozen as run |
