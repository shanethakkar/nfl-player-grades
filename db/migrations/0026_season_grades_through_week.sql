BEGIN;

-- Provisional grades (ADR-0031): a season still in progress is graded
-- weekly from games "through week N". NULL = a completed season. A row is
-- Provisional iff through_week IS NOT NULL.

ALTER TABLE season_grades ADD COLUMN through_week SMALLINT;

COMMIT;
