BEGIN;

-- Team-level offensive line grading (ADR-0025).
--
-- Why team-level: nflverse data does not attribute pressures, sacks, or
-- run-blocking lanes to specific offensive linemen. Without paid PFF data
-- we can't grade individual OL. Instead we grade the OL UNIT per team-season,
-- which is how analysts and coaches discuss OL anyway ("Eagles OL was elite
-- in 2024", not "Lane Johnson was elite").
--
-- Three tables, parallel to player-grading tables but keyed on team_id:
--   team_ol_stats       -- raw per-team-season stats (pass-block, run-block, pen)
--   team_ol_components  -- per-component values (mirrors stat_components shape)
--   team_ol_grades      -- composite grade per team-season (mirrors season_grades)
--
-- Kept entirely separate from season_grades / stat_components so that
-- player-centric queries don't need to learn a team-OL exception.

CREATE TABLE team_ol_stats (
    team_id            INTEGER  NOT NULL REFERENCES teams(team_id),
    season             SMALLINT NOT NULL,
    -- Pass blocking
    dropbacks          INTEGER,           -- pass attempts + sacks + scrambles
    sacks_allowed      SMALLINT,
    qb_hits_allowed    SMALLINT,
    pressures_allowed  SMALLINT,          -- from PFR per-defender pressures, summed by opponent
    -- Run blocking
    rushes             INTEGER,
    rush_yards         INTEGER,
    yards_before_contact INTEGER,         -- summed from pfr_advstats_rush across all team RBs
    rush_epa_total     REAL,
    rushes_success     SMALLINT,          -- count of rushes with epa > 0
    rushes_stuffed     SMALLINT,          -- count of rushes with yards <= 0
    rushes_explosive   SMALLINT,          -- count of rushes with yards >= 10
    -- Penalties (offensive line responsibility — false start, holding)
    false_starts       SMALLINT,
    holdings           SMALLINT,
    PRIMARY KEY (team_id, season)
);

CREATE INDEX team_ol_stats_season_idx ON team_ol_stats (season);


CREATE TABLE team_ol_components (
    team_id            INTEGER  NOT NULL REFERENCES teams(team_id),
    season             SMALLINT NOT NULL,
    component_name     TEXT     NOT NULL,
    raw_value          DOUBLE PRECISION,
    adjusted_value     DOUBLE PRECISION,
    z_score            DOUBLE PRECISION,
    sample_size        INTEGER,
    used_in_composite  BOOLEAN  NOT NULL DEFAULT TRUE,
    PRIMARY KEY (team_id, season, component_name)
);

CREATE INDEX team_ol_components_season_idx ON team_ol_components (season);
CREATE INDEX team_ol_components_name_idx ON team_ol_components (component_name);


CREATE TABLE team_ol_grades (
    team_id            INTEGER  NOT NULL REFERENCES teams(team_id),
    season             SMALLINT NOT NULL,
    composite_grade    DOUBLE PRECISION NOT NULL,
    composite_z        DOUBLE PRECISION NOT NULL,
    percentile         DOUBLE PRECISION,
    confidence         DOUBLE PRECISION,
    data_tier          SMALLINT,
    qualified          BOOLEAN  NOT NULL DEFAULT TRUE,
    data_tier_reason   TEXT,
    PRIMARY KEY (team_id, season)
);

CREATE INDEX team_ol_grades_season_idx ON team_ol_grades (season);

COMMIT;
