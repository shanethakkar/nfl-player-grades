# 0030 - A roster DE is iDL when both career positions say interior

- **Status**: Accepted
- **Date**: 2026-10-04
- **Issue**: #4

## Context

`player_seasons.position_played` comes from the season roster's
`depth_chart_position`, and `canonical_position` maps every `DE` to EDGE.
In a 3-4 front the DE is a 5-technique who lines up inside: Derrick Brown and
A'Shawn Robinson (CAR 2024–25), DeForest Buckner, Dexter Lawrence, Kenny
Clark, Christian Wilkins. They entered the EDGE cohort and were graded
against edge rushers. Their median pressure rate (~0.02 per snap) sits with
iDL, well below the EDGE median (~0.035), so they were both underrated
themselves and a drag on the EDGE z-scores.

No source has a clean per-season signal. PFR snap counts and the depth
charts also call 3-4 ends `DE`. The two career-level sources are each wrong
on their own:

- `load_players.position` is the latest listing. Al-Quadin Muhammad and
  Mario Addison are edge rushers whose master position later became `DT`.
  Chris Jones, Cameron Heyward and Leonard Williams are interior players
  whose master position is `DE`.
- `load_players.pff_position` (`ED` / `DI`) is also career-level. Used
  alone, it would move 15–24 qualified EDGE per season to iDL, including
  hybrid seasons like J.J. Watt 2018 (91.9 EDGE) and Stephon Tuitt 2020.

## Decision

A roster EDGE becomes iDL only when **both** the master position is
interior (DT/NT/DI/DL) **and** `pff_position` is `DI`. The rule is
`ingest._positions.season_dl_position`, applied in the rosters ingest, so
`position_played` is right for every consumer and the EDGE/iDL extracts
need no special case. The rule is not role-based: it only arbitrates
between listed positions when the roster label is ambiguous.

Effect on 2018–2025 (preview, rolled back): 9–26 roster rows per season
flip, of which 5–9 are qualified pass rushers. No player is in both cohorts.
Rank order among players who don't move is unchanged (Spearman ≥ 0.999 for
EDGE and 1.000 for iDL). Examples of the movers' EDGE → iDL grades:
Buckner 2018 79 → 88, Ioannidis 2019 67 → 93, Autry 2021 64 → 93, Kancey
2024 69 → 93, Eboigbe 2025 61 → 91, Derrick Brown 2025 29 → 57. Muhammad
2025 stays EDGE (87).

## Consequences

- **Known residual:** 3-4 interior players whose master position is still
  `DE` (Heyward, Campbell, Jonathan Allen, Leonard Williams and Arik
  Armstead in some seasons) stay EDGE when their roster says DE. That is the
  price of not moving J.J. Watt-type hybrids. Revisit if an alignment
  source (e.g. FTN or participation data) becomes available.
- **Career data is applied to past seasons.** A player whose master and PFF
  positions later become interior (Denico Autry) is iDL for his earlier DE
  seasons too.
- **Past seasons depend on the master snapshot.** Re-ingesting rosters with
  a refreshed `load_players` can change an old season's EDGE/iDL split.
  This was already true of `players.position`.
- **Restating** means re-running, per season: `ingest rosters` (it deletes
  and reinserts `player_seasons` with snaps at 0), then `ingest snap-counts`,
  then `grade --position EDGE` and `--position iDL`,
  `backfill-team-context` and `grade-teams`. `pfr_def_pass_rush` is keyed by
  player and holds both DL groups, so it needs no re-ingest.
