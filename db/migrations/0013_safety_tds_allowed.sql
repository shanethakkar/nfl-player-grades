BEGIN;

-- Add TDs allowed in coverage to pfr_def_coverage_s. Used to compute
-- season-long passer rating allowed for Safety v1.1 grading (ADR-0019 revision).
ALTER TABLE pfr_def_coverage_s
    ADD COLUMN tds_allowed SMALLINT;

COMMIT;
