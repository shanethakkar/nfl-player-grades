# 0017 - v1 face-check: offense-context contamination in high-volume receiver grades

- **Status**: Accepted (v1 limitation, documented; fix deferred to v1.5)
- **Date**: 2026-04-24
- **Companion to**: ADR-0014 (RB v1), ADR-0015 (WR v1), ADR-0016 (TE v1)

## Context

After shipping WR v1 and TE v1 and running both against the 2024/2025
seasons, a face-check surfaced a recurring pattern: several high-volume
receivers on bad offenses graded notably lower than their tape/production
would suggest. The prompting case was **Brock Bowers (LV, 2024)** — the
rookie-target-record holder at 153 targets who landed at grade **50.4 /
rank 14 of 34** qualified TEs.

The open question was whether v1's grader has a systematic bias (treat all
bad-offense receivers as underrated) or something narrower. We ran a
pre-check on the 2024 data before picking a direction; the data shows the
confound is narrower than "all bad-offense receivers" and also real enough
to need written disclosure before declaring v1 done.

## Finding

### Affected WRs — 2024, top-15 by targets

| Name | Tm | Tgt | Grade | Rk / 84 | Tm EPA# | Top QB |
|---|---|---:|---:|---:|---:|---:|
| Garrett Wilson | NYJ | 154 | 43.3 | 50 | 17 | 33.8 |
| Jerry Jeudy | CLE | 148 | 55.1 | 32 | 32 | 28.8 |
| Malik Nabers | NYG | 172 | 55.2 | 31 | 28 | 45.4 |

- **Wilson**: 1,100+ yds despite Rodgers' worst NFL season; ranked in the
  bottom 40% of qualified WRs.
- **Jeudy**: 1,229 yds on the league's worst offense (CLE, −0.183 EPA/play);
  ranked #32 is defensible but feels light.
- **Nabers**: rookie target record, 37th percentile grade.

### Affected TEs — 2024, top-10 by targets

| Name | Tm | Tgt | Grade | Rk / 34 | Tm EPA# | Top QB |
|---|---|---:|---:|---:|---:|---:|
| David Njoku | CLE | 99 | 21.2 | 34 | 32 | 28.8 |
| Dalton Schultz | HOU | 93 | 30.0 | 31 | 22 | 31.7 |
| Brock Bowers | LV | 153 | 50.4 | 14 | 31 | 29.5 |

- **Njoku**: last among all qualified TEs despite 1,000+ snaps, solid
  reputation. Strongest single data point for offense contamination.
- **Schultz**: rank 31/34 with 93 targets on the Stroud-injured/Young HOU
  offense.
- **Bowers**: mid-pack grade for the highest TE target volume in 2024.

Six players across the two positions, all on offenses with top-QB grade
below ~46. Matches the "bad QB play × high receiver volume" pattern.

## What v1 handles correctly

The methodology is **not** uniformly biased against receivers on weak
offenses. Two cases prove the grader distinguishes efficient play from
volume-only play inside a bad offensive environment:

### Brian Thomas Jr. — 2024 WR, JAX

- 135 targets, team EPA rank **#18**, top QB grade **44.9** (Lawrence's
  rough season)
- **Grade 73.9, rank 10 / 84** — top-12 WR by grade despite the weak
  passing context.

A naive "bad offense → underrate" bias would predict Thomas below the
WR median. He's in the top 12%.

### Jonnu Smith — 2024 TE, MIA

- 111 targets, team EPA rank **#21**, top QB grade **80.0**
- **Grade 71.4, rank 4 / 34** — top-5 TE.

MIA wasn't great offensively (below-average EPA), yet Smith's per-target
efficiency was high enough to surface a top-5 grade.

Zach Ertz (WAS, 2024) is the inverse counter-example worth noting: WAS
was a **top-4 offense by EPA** (top QB 78.7), Ertz ranked 24/34. Strong
offense did not lift a clearly declining player. The grade was right.

These three cases together show the grader is responsive to per-target
efficiency rather than team context as such.

## The specific confound

The failure mode is narrower than "bad-offense receivers underrated". It
is specifically:

> **High-volume receivers whose targets are forced by their role on a
> team with below-replacement QB play.**

Mechanics:

- `wr_rec_epa_per_target` and `te_rec_epa_per_target` carry ~35% of the
  composite. EPA is QB-dependent — the same route/catch generates less
  EPA when the QB throws late, off-platform, or low-completion.
- `wr_yac_over_expected_per_rec` / `te_yac_over_expected_per_rec` carry
  ~27%. xYAC is calibrated on league-average receptions; on a bad-QB
  offense, contested catches and off-schedule throws reduce real YAC
  relative to xYAC without the receiver doing anything wrong.
- `wr_target_earn_rate` / `te_target_earn_rate` carries only ~10% and
  is a volume-adjacent signal — it helps, but not enough to outweigh
  the 62%+ from EPA and YAC-over-expected when both are QB-suppressed.

So a receiver who is forced to absorb record target volume on a team
whose QB depresses EPA/target and YAC-over-expected across the board
gets dinged twice (two big components each running 0.5–1.0 z below
true skill) and credited once (one small component at +1.5 to +2.0
z for volume). Net: 5–15 composite points below a reasonable estimate.

The Thomas / Jonnu Smith counter-examples work because their
per-target efficiency was high enough in absolute terms to offset
the QB context — they weren't just surviving on forced volume.

## Why naive offense adjustment is wrong

The intuitive "residualize components by team offensive EPA" would:

1. **Over-correct Thomas and Jonnu Smith** — they already showed the
   efficiency needed; an additional boost for "bad offense" makes their
   grades unjustifiably high and distorts the top of the leaderboard.
2. **Under-correct Bowers / Njoku** relative to what they actually need —
   their issue is specifically per-target efficiency suppression from
   QB play, not general offense-level depression. Team EPA mixes run
   game + line play + YAC culture, so a team-EPA adjustment would dilute
   the QB-specific signal.
3. **Create new problems on good offenses** — a good-offense receiver
   who's actually mediocre (Ertz 2024) would get a negative context
   adjustment and drop below where he belongs.

The right fix is **usage-conditional** and **QB-specific**: adjust
per-target efficiency components for the QB quality the receiver
was playing with, but only for the portion of targets that are
"forced" (high target share on bad QB), and leave
already-efficient-despite-bad-QB players unadjusted.

That is not a hotfix. It is a methodology change.

## Decision

**Ship v1 as-is.** Document the confound here. Do not modify weights,
thresholds, or components. Do not layer a naive offense adjustment on
top of v1.

Defer the real fix to **v1.5**.

### v1.5 plan candidates (do not pick now; analyze first)

1. **QB-quality-conditional z-scoring** — when z-scoring
   `*_rec_epa_per_target` and `*_yac_over_expected_per_rec`, condition on
   the receiver's primary-QB composite grade (or a CPOE-derived QB
   quality score). Requires a second regression pass over historical
   seasons to calibrate.
2. **Usage-residualized volume** — add a "forced target share" signal
   and partially upweight it when the receiver's QB is below a
   threshold. Functions as a compensating positive weight only for
   the high-volume-on-bad-QB cell.
3. **Combination** — (1) corrects the EPA/YAC depression, (2) credits
   the fact that absorbing forced volume is itself a skill signal.

All three need a validation pass against multi-season data before
picking. Historical backfill of 2016–2023 (already flagged as the other
major pending work) is a prerequisite — single-season analysis can't
separate noise from true context effects.

### UI mitigation for v1

On player pages, display alongside the composite grade:

- Team offensive EPA/play and its league rank that season.
- Top QB grade on the player's team that season.
- If the player is a receiver (WR/TE/RB) with top-15 volume and their
  team's top QB grade is below ~45, a small inline note: "grade may be
  suppressed by QB context — see ADR-0017."

This does **not** change the grade. It surfaces the context the grade
doesn't fully capture, so a user reading Bowers' 50.4 sees "Raiders
offense #31, top QB 29.5" next to it and understands what they're
looking at.

The note trigger is deliberately narrow (top-volume + bad QB) so it
doesn't fire on every bad-offense receiver — that would dilute its
meaning and contradict what the data actually shows (see Thomas / Smith).

## Consequences

**Easier:**
- v1 ships with a known, bounded limitation instead of an unfinished
  methodology fix. The boundary is written down and visible to users.
- v1.5 has a clear mandate backed by specific player cases to validate
  against (Wilson, Jeudy, Nabers, Njoku, Schultz, Bowers; counter-
  examples Thomas, Jonnu Smith, Ertz).

**Harder:**
- Until v1.5 lands, six named players per season carry visibly
  suppressed grades and users have to read the context panel to
  interpret them correctly. Acceptable for an MVP; not acceptable
  long-term.
- The UI has to carry context columns that wouldn't be needed if the
  grade self-adjusted.

**Explicitly given up:**
- Claiming v1 is "context-neutral". It isn't. It is "per-target
  efficiency-weighted within the population", which is adjacent but
  not the same. The /about page and the ADR index should both reflect
  that honestly.

## References

- 2024 face-check data (throwaway query, not committed) — results
  inlined above in §Finding and §What v1 handles correctly.
- ADR-0015 §Validation — the WR YoY-r band that would inform v1.5
  calibration.
- ADR-0016 §Validation — TE YoY-r band.
- Pending: multi-season backfill (2016–2023) to enable usage-
  conditional z-scoring without overfitting to one season.
