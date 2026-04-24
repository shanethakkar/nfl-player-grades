# 0003 - Data tier and `qualified` flag as first-class columns

- **Status**: Accepted
- **Date**: 2026-04-22

## Context

Our grades come in three data-quality tiers:

- **Tier 1** (QB/RB/WR/TE): rich data, full pipeline incl. opponent adjustment
- **Tier 2** (CB/S/EDGE): decent data
- **Tier 3** (OL/iDL/off-ball LB/ST): proxy stats, directional only

We also have to handle players who fall below minimum-snaps thresholds:
their season exists in data but the grade isn't reliable enough to display
as if it were.

Options for representing both:

1. **Compute on read** — the web app derives tier from position and
   `qualified` from a snap-count join.
2. **First-class columns on `season_grades`** — `data_tier SMALLINT` and
   `qualified BOOLEAN` written by the pipeline, read directly.
3. **Separate views per tier** — `season_grades_tier1`, etc.

## Decision

**First-class columns** on `season_grades`:

- `data_tier SMALLINT NOT NULL CHECK (data_tier BETWEEN 1 AND 3)`
- `qualified BOOLEAN NOT NULL DEFAULT TRUE`

The pipeline sets both at write time. The web app reads them directly and
shows a tier badge / "insufficient sample" pill without any joins or
recomputation.

## Consequences

**Easier:**
- One query returns everything the UI needs to render a grade with full
  context (`SELECT composite_grade, data_tier, qualified ...`).
- Tier-mapping logic lives in one place (the pipeline) and isn't duplicated
  between Python and TS.
- Filtering ("only show qualified Tier 1 grades") is a trivial WHERE clause
  with index support.

**Harder:**
- Changing the tier-mapping rules requires re-running grading to refresh
  the column. We accept this; tiers don't change often.
- A small amount of data redundancy: tier is implied by position. We accept
  this for query simplicity.

**Explicitly given up:**
- Computed-on-read flexibility. If we ever need per-user tier overrides
  (we won't), we'd have to add them as a separate table.

## See also

- ADR-0016 — TE `role` and `data_tier_reason` (era + blocking-role merge) written
  alongside `data_tier` on `season_grades`.
