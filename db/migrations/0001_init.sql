-- 0001_init.sql
-- Initial schema for NFL Player Grades.
-- Follows the sketch in the project outline; designed so the Python pipeline
-- writes to raw/intermediate tables and the web app reads from grade tables.

BEGIN;

-- ---------------------------------------------------------------------------
-- Reference: teams
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    team_id        SERIAL PRIMARY KEY,
    abbr           TEXT NOT NULL UNIQUE,            -- e.g. 'KC', 'PHI'
    name           TEXT NOT NULL,                   -- 'Kansas City Chiefs'
    conference     TEXT NOT NULL CHECK (conference IN ('AFC', 'NFC')),
    division       TEXT NOT NULL CHECK (division IN ('North', 'South', 'East', 'West')),
    primary_color  TEXT,                            -- hex '#E31837'
    secondary_color TEXT
);

-- ---------------------------------------------------------------------------
-- Team aliases: historical abbreviations -> current team_id
-- nflverse uses contemporary abbreviations (e.g. SD for 2016 Chargers). We
-- normalize all ingested data to the current team_id via this table. Display
-- always uses the current abbr; we never show 'SD' or 'OAK' in the UI.
--
-- See docs/adr/0004-normalize-historical-team-abbreviations.md
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_aliases (
    alias    TEXT PRIMARY KEY,                    -- 'SD', 'OAK', 'STL', 'LAR', etc.
    team_id  INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Players
-- gsis_id is the nflverse canonical id. Kept separate from surrogate PK so we
-- can add other id systems (pfr_id, espn_id) later without migrating FKs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS players (
    player_id        SERIAL PRIMARY KEY,
    gsis_id          TEXT UNIQUE,                   -- nflverse gsis id, nullable for older data
    full_name        TEXT NOT NULL,
    position         TEXT NOT NULL,                 -- listed position (QB, WR, CB, ...)
    birth_date       DATE,
    height_inches    INTEGER,
    weight_lbs       INTEGER,
    draft_year       INTEGER,
    draft_round      INTEGER,
    draft_pick       INTEGER,
    current_team_id  INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
    last_updated     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS players_current_team_idx ON players(current_team_id);
CREATE INDEX IF NOT EXISTS players_position_idx ON players(position);

-- ---------------------------------------------------------------------------
-- Player-seasons
-- One row per player per season per team. A player traded mid-season gets
-- multiple rows. Primary key is composite on (player_id, season, team_id).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_seasons (
    player_id        INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season           INTEGER NOT NULL,
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    position_played  TEXT NOT NULL,                 -- may differ from listed position
    games            INTEGER NOT NULL DEFAULT 0,
    games_started    INTEGER NOT NULL DEFAULT 0,
    snaps_offense    INTEGER NOT NULL DEFAULT 0,
    snaps_defense    INTEGER NOT NULL DEFAULT 0,
    snaps_special    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, season, team_id)
);

CREATE INDEX IF NOT EXISTS player_seasons_season_idx ON player_seasons(season);
CREATE INDEX IF NOT EXISTS player_seasons_team_season_idx ON player_seasons(team_id, season);

-- ---------------------------------------------------------------------------
-- Depth charts
-- End-of-regular-season snapshots in v1. Later we can add intra-season rows.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS depth_charts (
    team_id      INTEGER NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    season       INTEGER NOT NULL,
    week         INTEGER NOT NULL,                  -- 0 for preseason, 1..18 regular, 99 for end-of-season snapshot
    position     TEXT NOT NULL,                     -- QB, RB1, WR1, LCB, etc. (raw depth-chart label)
    depth_order  INTEGER NOT NULL,                  -- 1 = starter
    player_id    INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    PRIMARY KEY (team_id, season, week, position, depth_order)
);

CREATE INDEX IF NOT EXISTS depth_charts_player_idx ON depth_charts(player_id);
CREATE INDEX IF NOT EXISTS depth_charts_team_season_idx ON depth_charts(team_id, season, week);

-- ---------------------------------------------------------------------------
-- Stat components (intermediate)
-- One row per (player, season, component). raw_value is computed from PBP/NGS,
-- adjusted_value is after garbage-time filter + opponent adjustment, z_score
-- is within position within season.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stat_components (
    player_id       INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season          INTEGER NOT NULL,
    component_name  TEXT NOT NULL,                  -- e.g. 'qb_epa_per_dropback', 'wr_yprr'
    raw_value       DOUBLE PRECISION,
    adjusted_value  DOUBLE PRECISION,
    z_score         DOUBLE PRECISION,
    sample_size     INTEGER,                        -- snaps, dropbacks, targets, etc. depending on component
    PRIMARY KEY (player_id, season, component_name)
);

CREATE INDEX IF NOT EXISTS stat_components_season_component_idx
    ON stat_components(season, component_name);

-- ---------------------------------------------------------------------------
-- Season grades (output)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS season_grades (
    player_id        INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season           INTEGER NOT NULL,
    position         TEXT NOT NULL,                 -- position used for grading (may differ from listed)
    composite_grade  DOUBLE PRECISION NOT NULL,     -- 0..100
    composite_z      DOUBLE PRECISION NOT NULL,     -- pre-sigmoid z-score, kept for debugging
    percentile       DOUBLE PRECISION NOT NULL,     -- within position, within season (0..100)
    confidence       DOUBLE PRECISION,              -- posterior precision proxy, 0..1
    data_tier        SMALLINT NOT NULL CHECK (data_tier BETWEEN 1 AND 3),
    qualified        BOOLEAN NOT NULL DEFAULT TRUE, -- false = below minimum sample size
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, season, position)
);

CREATE INDEX IF NOT EXISTS season_grades_season_position_idx
    ON season_grades(season, position);
CREATE INDEX IF NOT EXISTS season_grades_grade_idx
    ON season_grades(season, position, composite_grade DESC);

-- ---------------------------------------------------------------------------
-- Career grades (output, Kalman-style smoothing)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS career_grades (
    player_id    INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    as_of_date   DATE NOT NULL,
    grade        DOUBLE PRECISION NOT NULL,         -- posterior mean, 0..100
    uncertainty  DOUBLE PRECISION NOT NULL,         -- posterior std dev
    last_season  INTEGER NOT NULL,
    n_seasons    INTEGER NOT NULL,
    PRIMARY KEY (player_id, as_of_date)
);

CREATE INDEX IF NOT EXISTS career_grades_grade_idx
    ON career_grades(as_of_date, grade DESC);

-- ---------------------------------------------------------------------------
-- Pipeline metadata: track when each ingestion/grading stage last ran.
-- Useful for idempotent rebuilds and for the web app to show data freshness.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       SERIAL PRIMARY KEY,
    stage        TEXT NOT NULL,                     -- 'ingest.pbp', 'grading.qb', ...
    season       INTEGER,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ,
    status       TEXT NOT NULL DEFAULT 'running',   -- 'running' | 'ok' | 'error'
    rows_written INTEGER,
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS pipeline_runs_stage_idx ON pipeline_runs(stage, started_at DESC);

COMMIT;
