# 0004 - Normalize historical team abbreviations to current

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

`nfl_data_py` uses the contemporary team abbreviation for each season's
data:

- 2016 Chargers are `SD`, 2017+ are `LAC`
- 2016–2019 Raiders are `OAK`, 2020+ are `LV`
- Pre-2016 Rams are `STL`; from 2016 they're `LA` (some sources use `LAR`)
- A few sources sprinkle in `WSH`, `ARZ`, `BLT`, etc.

If we naively join `pbp.posteam = teams.abbr`, 2016 Chargers rows silently
drop or fail FK constraints. We have to handle this somewhere.

Options:

1. **Store historical abbreviations as-is**, display them as-of the season.
   ("In 2016, SD went 5-11" — but they're the *Chargers*, same franchise.)
2. **Normalize everything to the current abbreviation** at ingestion time
   via a `team_aliases` lookup table.
3. **Use `nflverse-team` package mappings** at query time.

## Decision

**Normalize to current abbreviation at ingestion.** The `team_aliases` table
maps every historical abbr (and a few alternate spellings) to the current
`team_id`. Every current abbr aliases to itself, so the lookup is one
unconditional query.

The UI never displays `SD` or `OAK`. A 2016 Chargers depth chart is shown
under "Los Angeles Chargers" with a note that the team relocated.

## Consequences

**Easier:**
- All FK relationships work without special-casing historical abbrs.
- Cross-season queries ("show me all Chargers QBs since 2016") return the
  expected rows without UNIONs or OR clauses.
- Adding a new alias (some future relocation, or a new alternate spelling
  found in PFR data) is one INSERT.

**Harder:**
- Historical "purity" lost — a 2016 game line in our DB will say `LAC`,
  not `SD`. We accept this; the franchise identity matters more than the
  city-of-record for player grading.
- Need a small chunk of UI copy when showing pre-relocation seasons
  ("relocated 2017 from San Diego"). Cheap.

**Explicitly given up:**
- Showing "as the team was named at the time." If we ever build a historical
  game viewer, we'd surface that there.
