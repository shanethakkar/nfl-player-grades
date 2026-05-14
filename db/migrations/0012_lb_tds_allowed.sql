BEGIN;

-- Add TDs allowed in coverage to pfr_def_lb. Used to compute season-long
-- passer rating allowed for LB grading (ADR-0022 v1 update).
ALTER TABLE pfr_def_lb
    ADD COLUMN tds_allowed SMALLINT;

COMMIT;
