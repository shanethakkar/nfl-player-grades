-- 0005_add_fumble_and_xyac_to_plays.sql
-- Additive columns for RB v1.1 grading refinement:
--   * fumble             - any fumble by the ball carrier (broader than fumble_lost,
--                          which only counts fumbles recovered by the defense).
--                          Used for rb_fumble_rate so that recovery (largely a
--                          coin flip) doesn't drive the metric.
--   * xyac_mean_yardage  - nflfastR's expected-YAC model output on completions.
--                          Used to derive rb_yac_over_expected_per_rec, since
--                          NGS receiving does not publish RB rows.
-- Both columns are nullable. Existing rows are NULL until PBP is re-ingested.
-- See docs/adr/0014-rb-v1-grading-formula.md for the v1.1 refinement notes.

BEGIN;

ALTER TABLE plays
    ADD COLUMN IF NOT EXISTS fumble             BOOLEAN,
    ADD COLUMN IF NOT EXISTS xyac_mean_yardage  REAL;

COMMIT;
