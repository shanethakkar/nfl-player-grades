# QB Grading Formula v1 — Proposal (Strawman)

**Status:** Draft / debating — NOT a decision record yet.
**Author:** pipeline, 2026-04-23
**Purpose:** Agree on the v1 QB grading formula *before* writing the
code, so we don't discover disagreements after the plumbing is done.
Will become **ADR-0012** once agreed.

## TL;DR

I'm proposing a **3-component composite** built from per-play EPA
(Expected Points Added) and CPOE (Completion % Over Expected), with
league-mean shrinkage for small samples and no opponent adjustment in
v1.

```
grade = sigmoid( composite_z )

composite_z = 0.50 * z(EPA_per_dropback)
            + 0.25 * z(CPOE)
            + 0.25 * z(success_rate)
```

Every piece below is up for debate. Things with ❓ are the ones I most
want your opinion on.

---

## What we're grading

**Target population:** QBs with ≥ 200 dropbacks in the season
(qualified). QBs below that threshold still get a grade but are
flagged `qualified = false` in the UI.

**Definition of "dropback":** nflverse `qb_dropback == 1`.
Includes pass attempts + sacks + scrambles. **Excludes** spikes, kneels,
and aborted snaps. This is the standard public-analytics convention.

**Scope for v1:** Regular season only. Playoffs not folded in
(too few games per QB, would distort the sample).

---

## The three components

### 1. `qb_epa_per_dropback` — weight 0.50 (the core signal)

**Definition:** mean `epa` over all dropback plays in the filtered set.

**Why 50% of the composite:** EPA is the closest thing football has to
"runs created." It bakes in down, distance, field position, and time
remaining, so a 5-yard completion on 3rd-and-3 is worth more than a
5-yard completion on 3rd-and-8. It automatically penalizes sacks,
fumbles lost, and interceptions (they're big negative EPA events). And
it's been validated against winning more than any other single public
QB stat.

**What it misses:** Doesn't isolate the QB from the supporting cast.
A great OL inflates EPA (fewer sacks, better fields). Great receivers
inflate it (YAC). That's why we add CPOE.

### 2. `qb_cpoe` — weight 0.25 (accuracy, WR-independent)

**Definition:** mean `cpoe` over pass attempts (not all dropbacks —
`cpoe` is null for sacks/scrambles).

**Why include it:** CPOE is computed against an expected completion
rate based on pass depth, angle, situation, and defender proximity. It
isolates QB accuracy from WR drop rate / separation. A QB who completes
66% of passes at 10-yard ADOT is better than one who completes 66% at
6-yard ADOT — raw completion % misses this; CPOE catches it.

**What it misses:** Decision-making, ball security, escaping pressure.
All of those show up in EPA.

### 3. `qb_success_rate` — weight 0.25 (consistency vs. boom-bust)

**Definition:** fraction of dropbacks where `success == 1` (nflverse's
standard: play gained ≥40% of needed yards on 1st, ≥60% on 2nd, 100%
on 3rd/4th).

**Why include it:** Two QBs can have identical EPA/db with very
different profiles — one grinds out steady positive plays, the other
alternates 60-yard bombs with 5-yard sacks. Sustained drives win
games more reliably than boom-bust. Success rate rewards the grinder.

**Correlation concern:** Success rate and EPA/db are moderately
correlated (r ~ 0.7 historically). They're not redundant, but double-
counting is a real risk. I'm OK with 25% weight; if we find they're
telling the same story we can redistribute to CPOE.

### Why not these others (for v1)?

I considered and rejected:

| Component | Why out |
|---|---|
| Sack rate | Already inside EPA (sacks = big negative EPA events). Adding it double-counts the penalty. Also ~40% OL / 60% QB so it's noisy. |
| INT rate | Already inside EPA. Plus raw INT rate is extremely noisy (tipped balls, WR falls). We'd want "turnover-worthy play" rate (PFF) which we don't have. |
| TD rate | Already in EPA, and heavily confounded by red-zone opportunity (which is offensive-line + RB driven). |
| Passer rating / QBR | Closed formulas that bundle what we're trying to decompose. |
| ADOT (avg depth of target) | Not a quality stat — it's a style descriptor. Will be stored as a display stat but NOT in the composite. |
| Air yards per attempt | Same as ADOT. Descriptor. |
| Time-to-throw | Requires NGS player-tracking data. Good candidate for v2. |
| Pressure-to-sack rate | Requires PFF or NGS pressure tags. v2. |
| Clutch / leverage weighting (QBR-style) | Adds a lot of complexity for a second-order effect. Skip. |

❓ **Question for you:** Do any of these feel like must-haves that I'm
wrong to cut?

---

## The filter — which plays count?

Applied before any per-player aggregation:

```
play must satisfy ALL of:
  - play_type in ('pass', 'qb_spike' excluded)  -- via qb_dropback == 1
  - season_type == 'REG'
  - not a garbage-time play (see below)
  - not a 2-point conversion
  - not an aborted snap (two_point_attempt == 0, aborted_play == 0)
```

### Garbage-time definition

Proposal:

```
garbage_time = (
    (qtr >= 4 AND abs(score_differential) > 21)
    OR
    (qtr == 4 AND game_seconds_remaining < 300 AND abs(score_differential) > 14)
)
```

In English:
- Any 4th-quarter play with a 3+ score (>21 point) lead, OR
- The final 5 minutes when it's a 2+ score (>14 point) game

This is slightly tighter than the most common public definition
(`wp < 0.05 or wp > 0.95`), which I'd argue throws out too many plays
because nflverse's WP model is aggressive about "locking in" wins.

❓ **Question for you:** Are you happy with this threshold, or do you
want the wp-based version? Or something stricter / looser?

---

## Shrinkage (empirical Bayes)

QBs with small samples get pulled toward the league mean. Formula per
component:

```
shrunk_value = (n * raw_value + k * league_mean) / (n + k)
```

where `n` is the player's sample size (dropbacks) and `k` is the
shrinkage strength (a pseudo-sample size representing the prior).

**Proposal:** `k = 150 dropbacks` for EPA/db and success rate,
`k = 100` for CPOE.

In effect:
- A QB with 600 dropbacks gets (600 × actual + 150 × mean) / 750 →
  80% of their own signal, 20% of the prior. Barely any pull.
- A QB with 50 dropbacks (cameo appearance) gets
  (50 × actual + 150 × mean) / 200 → 25% their signal, 75% prior.
  Heavy pull toward mean. "We don't trust this sample much."

**Why two different k's:** CPOE has lower variance than EPA/db, so
less shrinkage is needed to stabilize it.

❓ **Question for you:** k=150 is a starting point; I pulled it from
rules of thumb (half a full-season starter's load). Want me to tune it
empirically by looking at retrodicted stability year-over-year?

---

## Opponent adjustment — **deferred to v2**

The right way to do this is per-play: for each dropback, subtract the
defense's league-adjusted EPA-allowed-per-dropback from the play's
EPA, then average.

I'm proposing we **skip this for v1** for two reasons:

1. It adds a separate data-building step (team-season defensive
   baselines) that's non-trivial.
2. The effect size in practice is small. The top-10 QB list barely
   shuffles after opponent adjustment in most public analyses.

For v1, `adjusted_value = raw_value` on every component. We can
revisit after we see the unadjusted grades and decide whether the
schedule-strength complaints are loud enough to bother with.

❓ **Question for you:** OK with deferring, or is "schedule-aware from
day one" important to you?

---

## Composite weighting

Proposed:

```
composite_z = 0.50 * z(EPA_per_dropback)
            + 0.25 * z(CPOE)
            + 0.25 * z(success_rate)
```

Where `z(x)` = within-position, within-season standardization (subtract
mean, divide by standard deviation, using only qualified QBs for the
mean/sd).

**Why these weights:**
- **0.50 on EPA/db** because it's the one metric closest to "how much
  did this QB move the ball and score." If you forced me to pick one,
  it'd be this.
- **0.25 on CPOE** for accuracy isolation. CPOE is probably the most
  replicable (lowest year-over-year noise) of the three, so it could
  arguably deserve more. But it's narrow — it only measures throwing
  accuracy, nothing else.
- **0.25 on success rate** to keep boom-bust QBs from dominating.

### Alternative weightings to consider

| Scheme | EPA | CPOE | Success | Rationale |
|---|---|---|---|---|
| **Proposed** | 0.50 | 0.25 | 0.25 | EPA-dominant, balanced accuracy/consistency |
| "Modern analytics" | 0.40 | 0.30 | 0.30 | More faith in CPOE as a true-skill signal |
| "Old school" | 0.60 | 0.10 | 0.30 | EPA and consistency carry it |
| "Inverse-noise" | computed | computed | computed | Let data decide via 1/variance |

❓ **Question for you:** Which of these feels most right to you?
Or something else entirely?

### Why not inverse-noise for v1

Inverse-noise weighting (ADR-0007 mentions it) computes weights from
per-player variance: noisier components get downweighted automatically.
Mathematically cleaner, but:
- Weights become hard to explain ("why is CPOE worth 0.31 this year?")
- Opaque changes year-over-year
- Harder to debate

For v1, hand-picked weights let us argue about them. We can adopt
inverse-noise in v2 once we trust the formula's shape.

---

## Minimum sample (`qualified`) threshold

Proposal: **≥ 200 dropbacks** for REG season to be `qualified = true`.

- A full-season starter is ~550-650 dropbacks (17 games × ~35/game).
- 200 ≈ 6 games of starter workload OR heavy backup time.
- Below 200: grade is computed (for the record) but `qualified = false`
  so the UI can hide or de-emphasize.

❓ **Question for you:** 200 feels right to me; some public sites use
150 or "10+ starts". Preference?

---

## Expected end-state output, concretely

After running this against 2024 REG season, we should see roughly:

| Rank | QB | Expected grade |
|---|---|---|
| 1 | Joe Burrow | 90–95 |
| 2-3 | Lamar Jackson / Josh Allen | 88–92 |
| 4-8 | Goff / Jayden Daniels / Mahomes / Stroud / Geno | 80–88 |
| mid | Herbert / Hurts / Love / Purdy / Darnold | 70–80 |
| ... | | |
| bottom qualified | Cousins (injured), Bo Nix (rookie ups/downs) | 55–65 |

If the actual output puts Mahomes at 65 or a random backup at 92,
**the formula is broken and we iterate** — adjust weights, revisit
shrinkage, tighten the filter, etc. Face-validity check is the final
arbiter before we ship v1.

---

## Decisions I need from you

Ranked by how much they matter:

1. **Are the three components right?** (EPA/db, CPOE, success rate at
   50/25/25.) Or push me toward adding/removing one.
2. **Weighting scheme** — proposed, "modern", "old school", or something
   custom?
3. **Garbage-time definition** — my proposed threshold or the wp-based
   alternative?
4. **Opponent adjustment deferred to v2?** Or must-have from day one?
5. **Qualified threshold** — 200 dropbacks, or different?
6. **Shrinkage k=150** — OK as starting point, or tune empirically?

Once we agree, I'll:
- Write this up as **ADR-0012: QB v1 grading formula** (supersedable)
- Build the plumbing: PBP ingest (E1), QB features (E2), grading (F)
- Surface the top-30 QB list for 2024 and 2025 for face-validity
- Iterate on the formula if the list is off, without changing the
  plumbing.
