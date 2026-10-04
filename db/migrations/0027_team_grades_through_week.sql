BEGIN;

-- Provisional team and OL grades (ADR-0031). NULL through_week = a
-- completed season, as on season_grades (0026).

ALTER TABLE team_grades    ADD COLUMN through_week SMALLINT;
ALTER TABLE team_ol_grades ADD COLUMN through_week SMALLINT;

-- Early in a season no kicker or punter has qualified yet, so a team can
-- have no ST grade. Overall is then the Offense/Defense mix with the phase
-- weights renormalized.
ALTER TABLE team_grades
    ALTER COLUMN st_grade DROP NOT NULL,
    ALTER COLUMN st_z     DROP NOT NULL;

COMMIT;
