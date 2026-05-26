# ADR-0026 — Team v1 Grading Formula

**Status:** Accepted (v1 design — 2026-05-25, pre-implementation)
**Date:** 2026-05-25

---

## Context

With all 12 individual positions graded (ADR-0013 through ADR-0025), the
natural next layer is **team grades**. Fans, analysts, and the methodology
article itself benefit from a single number per team per season — and from
the Offense / Defense / Special Teams split that breaks the number into
its meaningful parts.

This ADR is structurally a sibling to ADR-0025 (OL v1) — both are
team-level grades. But where OL grades a team-unit from raw pbp data,
**team grades aggregate the existing player grades**. The aggregation
methodology itself is what this ADR locks down.

### Why aggregate player grades (not compute fresh from team stats)

Four approaches were considered:

1. **Pure player aggregation.** Composite of the per-position grades we
   already produce. Cleanest because every team grade reduces to "the
   players on this team." Can't capture pure team-level effects
   (scheme, coaching).
2. **Fresh team-level audit.** Build a new 13th audit from team-aggregated
   pbp. Captures team-as-system but duplicates the work, and the result
   doesn't connect to the audited player grades.
3. **Hybrid (players + team adjusters).** Player grades plus a few
   team-only signals (turnover margin, hidden ST yardage). Best ceiling
   but hardest to defend in v1.
4. **PFF-style phase grades on top of player grades.** Three sub-grades
   (Offense, Defense, ST) built from the relevant position grades, plus
   an Overall composite.

We chose **option 4**. It uses the audited player grades as the
foundation, produces three sub-grades that are themselves the most
useful presentation, and matches how fans and analysts already think
about teams. The hybrid layer is a documented v2.

---

## Data Sources

| Source | Used for |
|---|---|
| `season_grades` (existing) | Per-position grades that feed each phase |
| `player_seasons.snaps_offense / snaps_defense / snaps_st` | Snap-weighting within a position |
| `team_ol_grades` (existing, ADR-0025) | OL unit grade — already team-level, no snap-weighting needed |

No new ingest. All inputs come from already-populated tables.

---

## Two-Stage Aggregation

### Stage 1 — within a position

For each (team, season, position), compute a snap-weighted average of
every player who logged snaps at that position on the team:

```
position_team_grade(p, team) =
    Σ(player.composite_grade × player.snaps_at_position)
  / Σ(player.snaps_at_position)
```

- Below-qualification players still count — their grade exists, their
  snaps are real, and excluding them would distort the actual team output.
- An injured starter and his replacement average proportionally — which
  is correct, because that *is* what the team got from the position.
- A 95%-snap starter dominates; a 20%-snap backup is a rounding error.

**OL is exempt** — `team_ol_grades.composite_grade` is already a single
team-season number from ADR-0025; no aggregation needed.

### Stage 2 — across positions in a phase

Position-weighted sum of the per-position team grades:

```
phase_grade(team) = Σ position_weight(p) × position_team_grade(p, team)
```

Position weights below codify "QB matters more than RB."

### Overall composite

```
overall_grade(team) =
    w_off × offense_grade
  + w_def × defense_grade
  + w_st  × st_grade
```

---

## Position Weights (v1.0)

Weights were derived empirically — see
[docs/grading/audits/2026-05-25-team-weights.md](../grading/audits/2026-05-25-team-weights.md)
for the full audit (ridge regression of team success vs. snap-weighted
per-position team grades, anchored by salary cap allocation as a market
signal). Values below are the reconciliation of the two anchors plus
the original priors; reasoning per row.

### Offense (sums to 1.00)

| Position | Weight | Reasoning |
|---|---:|---|
| QB | **0.45** | Regression coefficient 0.61, univariate r=0.74 — the single dominant signal. Trimmed from full regression value because some of QB's apparent weight is multicollinear with WR. |
| OL | **0.25** | Regression supports 0.23, cap allocation supports higher; held at prior. 5-player unit affecting every play. |
| WR | **0.13** | Drops to ~0 in multivariate regression (multicollinear with QB) but univariate r=0.52 — WR genuinely matters, the regression just can't separate it from QB. Held meaningful. |
| RB | **0.09** | Devalued in modern offensive analytics; cap allocation agrees (~5%). |
| TE | **0.08** | Variable role; starter matters but ceiling lower than QB/WR. |

### Defense (sums to 1.00)

| Position | Weight | Reasoning |
|---|---:|---|
| EDGE | **0.24** | Pass rush is the "QB of defense." Regression + cap both around 0.25. |
| CB | **0.24** | Coverage on the ball. Highest univariate r in defense (0.39). |
| LB | **0.22** | Regression supports a slight bump from prior. Front-7 anchor + nickel coverage. |
| S | **0.20** | Regression bumped from prior 0.15 → 0.23; landed at 0.20. Last-line value real. |
| iDL | **0.10** | Regression coefficient 0.01, univariate r=0.12 — weakest of any position. Reduced from prior 0.15 while keeping non-trivial weight (the iDL formula itself may under-capture interior pressure). |

### Special Teams (sums to 1.00)

| Position | Weight | Reasoning |
|---|---:|---|
| K | **0.52** | Slight edge over punter on regression and cap. |
| P | **0.48** | |

Return units intentionally omitted — public data on KR/PR is too noisy
to grade. Future v2 may add hidden-yardage adjustments.

### Phase weights (sums to 1.00)

| Phase | Weight |
|---|---:|
| Offense | **0.55** |
| Defense | **0.40** |
| ST | **0.05** |

Derived empirically (same audit as the position weights — see
[audit doc](../grading/audits/2026-05-25-team-weights.md), v1.1
section). Phase-level regression of team success on offense/defense/st
phase grades fits at R² = 0.79 (vs point diff) and 0.69 (vs closing
spread). Regression said 0.58–0.64 / 0.34–0.36 / 0.02–0.06; reconciled
toward 0.55 / 0.40 / 0.05.

Offense is meaningfully heavier than defense — modern NFL is
offense-tilted in what moves team outcomes. ST is the small slice,
closer to its salary-cap weight (~2%) than to the original 0.10 prior.

---

## Edge Cases & Rules

### Multi-team players

Snaps are attributed to the team where they were logged. A player traded
mid-season contributes to each team in proportion to that team's snap
share — the per-team aggregation naturally handles this via the
snap-weighted average.

### Players with no snaps at a position

Excluded from that position's denominator. A player who logged 0
offensive snaps doesn't pull the offense grade.

### Teams with a position gap (rare)

If a team has zero graded players at a position (extreme injury wipeout,
or a team somehow with no qualifying kicker), the missing position's
weight is **redistributed proportionally** to the other positions in the
phase. Document the row's `data_tier_reason` field with the position
that was skipped.

### Below-qualification players

Their grade row exists (`qualified=false`), their snaps are real, and
they participate in the snap-weighted average. Excluding them would
distort what the team actually got from the position group.

---

## Schema (new tables)

```sql
team_grades (
    team_id          INT  NOT NULL,
    season           INT  NOT NULL,
    overall_grade    REAL NOT NULL,
    offense_grade    REAL NOT NULL,
    defense_grade    REAL NOT NULL,
    st_grade         REAL NOT NULL,
    overall_percentile REAL,
    offense_percentile REAL,
    defense_percentile REAL,
    st_percentile      REAL,
    data_tier_reason TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (team_id, season)
);

team_grade_components (
    team_id          INT  NOT NULL,
    season           INT  NOT NULL,
    phase            TEXT NOT NULL,   -- 'offense' | 'defense' | 'st'
    position         TEXT NOT NULL,   -- 'QB', 'RB', ..., 'OL', 'K', 'P'
    position_grade   REAL NOT NULL,   -- snap-weighted aggregate
    weight           REAL NOT NULL,   -- position weight applied
    n_players        INT  NOT NULL,   -- distinct graded players that contributed
    total_snaps      INT  NOT NULL,   -- denominator of the snap-weighted avg
    PRIMARY KEY (team_id, season, phase, position)
);
```

Kept separate from `season_grades` and from `team_ol_*` (which stays
focused on the OL unit specifically). Both consume from the same source
data and write to their own table family.

---

## Qualification

Every team that played a season is graded. 32 teams × 10 seasons (2016-2025)
= 320 team-season rows. No threshold gate.

---

## Composite → 0-100

Same sigmoid as player grades (ADR-0008): `grade = 100 / (1 + exp(-k(z - z0)))`
with `k=1.15`, `z0=0`. Calibrated against the league-average team-season,
which means a 50 is a perfectly average team and a 90+ is an elite team
the way a 90+ QB is an elite QB.

---

## Validation Plan

### Face-check (mandatory before ship)

For 2024 and 2023 seasons, the top 5 and bottom 5 by overall grade must
match the recognized contenders / cellar dwellers of those seasons. If
they don't, the position weights are off — adjust and re-check before
shipping.

### Validity ground truth

Same framework as positions (validity = correlation with an external
truth), adapted for teams:

| Source | What it is |
|---|---|
| **Vegas closing line** | Closing point spread / total — market's best estimate of team strength. Available via historical odds archives. **Recommended primary signal.** |
| Point differential | Final regular-season scoring margin. Noisier but principled. |
| Playoff appearance / final W-L | Binary or near-binary; small validity ceiling. |

`nflgrades validity --entity team` would compute Pearson correlation
between the team overall grade and one of these. Target: r ≥ +0.50
against closing line (much higher than per-player validity ceilings,
since closing lines are more informative than Pro Bowl votes).

### YoY reliability

Compute YoY correlation of overall grade. Targets:
- Strong: r ≥ 0.50 (reflects roster + scheme continuity)
- Acceptable: 0.30 ≤ r < 0.50
- Concerning: r < 0.30 (suggests the methodology is too noise-dominated)

### v1.0 face-check (2024 season, shipped 2026-05-25)

| Rank | Team | Overall | Reality check |
|---:|---|---:|---|
| 1 | BAL | 95.2 | ✅ Top-2 offense, strong defense |
| 2 | DET | 90.7 | ✅ 15-2 #1 NFC seed |
| 3 | PHI | 85.0 | ✅ Super Bowl winners |
| 4 | GB  | 73.7 | ✅ 11-6 playoff team |
| 5 | HOU | 72.0 | ✅ 10-7 playoff team, strong defense |
| 6 | BUF | 70.9 | ⚠️ Should arguably be top-3 (13-4, MVP Allen) |
| 7 | ARI | 69.7 | ⚠️ 8-9, missed playoffs (high) |
| 8 | SF  | 67.7 | ❌ 6-11 season due to injuries (clearly too high) |
| 9 | TB  | 64.8 | ✅ NFC South champs |
| 10 | KC | 64.5 | ⚠️ 15-2 Super Bowl runner-up (low — see below) |

Bottom 5: CAR (13.6), TEN (15.7), LV (18.5), CLE (18.8), NE (19.9) — all clear face-check ✅.

**The KC and SF outliers reveal a v1.0 methodology characteristic worth
naming:** the grade measures per-snap player quality, snap-weighted across
each team's available players. It does NOT measure full-season team output.

Implications:
- **Teams with significant injury attrition** (SF 2024) tend to grade
  HIGHER than their record because the grade rewards elite-when-healthy
  players proportionally to the snaps they played, not the games they
  missed. SF's Kittle/Bosa/Purdy snaps look elite; the system gives them
  credit for those snaps and is silent about the games those players
  missed.
- **Teams that outperform their efficiency stats** (KC consistently)
  tend to grade LOWER than their record. KC's per-snap efficiency
  was middling in 2024 (Mahomes had a down year by his standards);
  their wins came from clutch close-game play that doesn't show in
  per-play grades.

Documented as v1.0 limitation rather than fixed in v1.0 — fixing either
would require introducing "team continuity" or "clutch performance"
features, both substantial methodology changes. v2 candidate work.

Otherwise the face-check passes:
- Top 3 matches consensus
- Bottom 5 all clearly bad teams
- Mid-pack ordering is plausible with the two named exceptions

---

## Design Rationale

- **Why snap-weighted within position, not starter-only.** Snap-weighting
  is principled and handles injured-starter cases naturally. Starter-only
  requires defining "starter" (highest snap count? top of depth chart?)
  and creates a cliff effect.
- **Why position weights at all (not equal weighting).** QB matters more
  than RB in real football. Equal weighting would underrate QB-driven
  teams and overrate teams whose strength is a deep skill group.
- **Why ST = 0.10 not 0.20.** Kicker/punter swings are real but small.
  Overweighting ST would let an elite kicker drag a roster-bad team into
  the middle of the league. Roughly matches the share-of-variance estimate
  in public ST research.
- **Why no shrinkage step.** Aggregation is over already-shrunk
  player grades. Adding a second shrinkage layer would double-correct.
- **Why Defense at 0.45 = Offense at 0.45.** Modern NFL is offense-tilted
  in absolute production, but defense matters proportionally in winning.
  Phase balance is the safest starting point; an audit may move it.

---

## Consequences

**Easier:**
- Single number per team that summarizes the audited player work.
- Three sub-grades (Off/Def/ST) that are individually informative.
- Schema is small (2 tables) and decoupled from existing grading tables.
- No new ingest — uses what's already in `season_grades` and
  `team_ol_grades`.

**Harder:**
- Position weights are choices that have to be defended. Each weight
  is a methodological commitment; tuning them is a v1.1 audit.
- A team grade is only as good as the position grades feeding it.
  Bugs in position grading propagate.
- Closing-line data isn't already in the repo. Validation requires
  pulling it (one-time scrape; small CSV).

**Subject to revision:**
- Position weights themselves (v1.1 — audit after face-check + validity).
- ST = 0.10 vs 0.15 (the only phase weight likely to move).
- Hybrid layer adding turnover margin / hidden ST yardage (v2).

---

## Revision History

- **v1.0 (2026-05-25):** Initial design. Snap-weighted within position +
  position-weighted across positions in phase + phase-weighted into
  Overall. Position weights derived empirically (regression + cap
  allocation) per [audit doc 2026-05-25-team-weights.md](../grading/audits/2026-05-25-team-weights.md).
  Major findings vs. original gut-feel priors:
  - QB bumped 0.40 → 0.45 (regression said 0.61 but partly multicollinear with WR)
  - iDL trimmed 0.15 → 0.10 (regression strongly supported a reduction)
  - S bumped 0.15 → 0.20 (regression supported)
  - Phase weights moved from prior 0.45/0.45/0.10 → **0.55/0.40/0.05** based on a second-stage regression of team success on phase grades (R² = 0.79). Offense is meaningfully heavier than defense in modern NFL; ST is closer to its cap weight (~2%) than to the original 0.10.
  - Other moves all within ±0.03 of priors
