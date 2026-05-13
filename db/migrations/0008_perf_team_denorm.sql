-- 0008_perf_team_denorm.sql
-- Performance: denormalize team_abbr onto season_grades so player profiles
-- don't need a LATERAL join against plays per season row. Also adds
-- team_season_epa for pre-computed team offense context, replacing the
-- expensive per-request plays aggregate in getTeamContexts.

BEGIN;

ALTER TABLE season_grades
    ADD COLUMN IF NOT EXISTS team_abbr TEXT;

CREATE TABLE IF NOT EXISTS team_season_epa (
    season        INTEGER NOT NULL,
    team_abbr     TEXT NOT NULL,
    epa_per_play  REAL NOT NULL,
    epa_rank      INTEGER NOT NULL,  -- 1 = best offense that season
    n_teams       INTEGER NOT NULL,
    PRIMARY KEY (season, team_abbr)
);

COMMIT;
