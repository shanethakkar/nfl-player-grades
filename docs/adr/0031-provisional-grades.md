# 0031 - Grade an in-progress season as Provisional, through week N

- **Status**: Accepted
- **Date**: 2026-10-04
- **Issues**: #7, #8, #9, #10, #11 (spec #1, Phase 2)

## Context

The site had no grades for a season until it ended. Running the graders on
a partial season didn't work: every volume threshold assumes 17 games, so in
October almost nobody qualified, the z-score collapsed and positions came out
as all-50s. Team grades went NaN when kickers and punters hadn't qualified.

The Formulas themselves are partial-season safe: every Component is a
per-play rate (audit 2026-09-27 §3). What has to change is the volume
gating, the Composite scale, and how the site labels the result.

## Decision

**A season is Provisional until its final regular-season week is in
`plays`.** `grading.progress` reads the last REG week and the average games
per team from `plays`. A season through week 17 (2016–2020) or 18 (2021+) is
complete and grades exactly as before.

**Grade rows carry `through_week`.** `season_grades`, `team_grades` and
`team_ol_grades` have a nullable `through_week`; NULL means a completed
season. "Provisional" is derived from it rather than stored separately. The
weekly refresh restates the whole season each week, so there is no
per-week history (spec #1, out of scope).

**Volume thresholds pro-rate by games / 17, with a floor of three games.**
Min-to-grade, Qualified, the confidence denominator and the role gates (TE
blocking label, LB off-ball targets, EDGE OLB pressure gate, RB sub-cohorts)
all scale. Rates (e.g. the LB target-rate gate) don't. Below three games the
shrinkage prior dominates and a tiny bar would qualify one-game cameos, so
thresholds stop shrinking there.

**Provisional Composites use the pooled completed-season SD.** A week-3
cohort is too small to estimate the Composite's spread, so `scoring.score`
divides by the pooled within-season SD of the raw Composite over every
completed season of the position, under current weights
(`preview.pooled_composite_sd`). `preview` and `regrade` do the same for a
Provisional season, so preview still matches `grade`. The minimum Qualified
cohort (`MIN_QUALIFIED_COHORT = 10`, ADR-0028) still applies; a position
below it is not graded, its rows for the season are deleted, and the site
shows "Not enough games yet". (A completed season below the minimum keeps
its rows, as before.)

**Team grades renormalize over the phases that exist.** With no K/P grades
yet, ST is NULL and Overall is the Offense/Defense mix with its weights
renormalized, instead of NaN. A team without Offense or Defense grades is
not graded and doesn't count toward the 32-team standardization.

**One command refreshes a season** (`nflgrades weekly`). It fetches every
nflverse source once, caps week-keyed sources at the schedule's last
completed regular-season week, and refuses to write anything if a source
lags that week, or if an NGS season-summary row (which can't be capped)
already includes the next week. Grading, OL, team grades and team context
are written in one
transaction, so the site never sees a half-graded season (no NULL
`team_abbr`, no mixed weeks). Rosters and snap counts are written together
for the same reason: rosters recreate `player_seasons` with zero snaps.

**It runs weekly on GitHub Actions** (Wednesday morning ET, after Monday
Night Football and the nflverse refresh), against Neon's direct endpoint,
with no persistent cache. Setup and failure handling: `docs/weekly-refresh.md`.

**Provisional seasons stay out of career summaries.** Career average, best
season, the headline grade, the career chart, grade-tier examples, the
methodology "current top" lists and OG images skip rows with a
`through_week`.

## Consequences

- Early-season grades are noisy by construction. The label says so, and
  shrinkage (hand-set k until #15 derives it) pulls small samples toward
  the mean. The z-scores are still within-season, so a week-3 grade ranks
  players against each other, not against full seasons.
- Grades are restated every week; a player's week-3 grade is gone by
  week 4. That is intended (spec #1).
- `MAX(week)` in `plays` defines "through week". A manual `grade` run on a
  Sunday sees a partial week. The weekly command is the supported path: it
  caps sources at the last completed week first.
- A position that drops below the cohort minimum in a later week disappears
  until it qualifies again, rather than showing last week's grades as
  current.
- One lagging source blocks every position that week. That is deliberate:
  a run never mixes weeks. Re-running later in the day is the fix.
- Completed seasons are untouched: progress is 17/17, the cohort SD is used,
  `through_week` is NULL.
