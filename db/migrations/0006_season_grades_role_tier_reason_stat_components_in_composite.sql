-- TE v1 (ADR-0016): role and explicit data_tier reason; component inclusion flag
-- for tier-differentiated composites (e.g. blocking-TE path omits earn in composite).

BEGIN;

ALTER TABLE season_grades
    ADD COLUMN IF NOT EXISTS role TEXT,
    ADD COLUMN IF NOT EXISTS data_tier_reason TEXT;

ALTER TABLE stat_components
    ADD COLUMN IF NOT EXISTS used_in_composite BOOLEAN NOT NULL DEFAULT TRUE;

COMMIT;
