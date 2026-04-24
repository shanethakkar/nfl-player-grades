-- 0004_create_ngs_tables.sql
-- Next Gen Stats (NGS) from nflreadpy.load_nextgen_stats().
-- Three tables, one per stat type. See docs/adr/0012-ngs-three-tables.md.
-- Coverage: 2016+. Grain: (player, season, season_type, week, team).
-- week=0 is the nflverse convention for "season summary" — the grading
-- pipeline reads those rows for per-season metrics.

BEGIN;

-- ---------------------------------------------------------------------------
-- NGS passing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ngs_passing (
    player_id                               INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season                                  INTEGER NOT NULL,
    season_type                             TEXT NOT NULL,       -- 'REG' | 'POST'
    week                                    INTEGER NOT NULL,    -- 0 = season summary
    team_id                                 INTEGER NOT NULL REFERENCES teams(team_id),

    -- Core NGS tracking metrics
    avg_time_to_throw                       REAL,
    avg_completed_air_yards                 REAL,
    avg_intended_air_yards                  REAL,
    avg_air_yards_differential              REAL,
    aggressiveness                          REAL,                -- % throws into tight window
    max_completed_air_distance              REAL,
    avg_air_yards_to_sticks                 REAL,

    -- Volume
    attempts                                INTEGER,
    pass_yards                              INTEGER,
    pass_touchdowns                         INTEGER,
    interceptions                           INTEGER,
    completions                             INTEGER,
    passer_rating                           REAL,
    completion_percentage                   REAL,

    -- NGS's own CPOE (different model from PBP's cpoe)
    expected_completion_percentage          REAL,
    completion_percentage_above_expectation REAL,

    avg_air_distance                        REAL,
    max_air_distance                        REAL,

    PRIMARY KEY (player_id, season, season_type, week, team_id)
);

CREATE INDEX IF NOT EXISTS ngs_passing_season_week_idx
    ON ngs_passing(season, week);
CREATE INDEX IF NOT EXISTS ngs_passing_player_season_idx
    ON ngs_passing(player_id, season);

-- ---------------------------------------------------------------------------
-- NGS rushing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ngs_rushing (
    player_id                               INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season                                  INTEGER NOT NULL,
    season_type                             TEXT NOT NULL,
    week                                    INTEGER NOT NULL,
    team_id                                 INTEGER NOT NULL REFERENCES teams(team_id),

    efficiency                              REAL,                -- lateral movement efficiency
    percent_attempts_gte_eight_defenders    REAL,
    avg_time_to_los                         REAL,

    rush_attempts                           INTEGER,
    rush_yards                              INTEGER,
    avg_rush_yards                          REAL,
    rush_touchdowns                         INTEGER,

    expected_rush_yards                     REAL,
    rush_yards_over_expected                REAL,
    rush_yards_over_expected_per_att        REAL,                -- RYOE/att — the money metric
    rush_pct_over_expected                  REAL,

    PRIMARY KEY (player_id, season, season_type, week, team_id)
);

CREATE INDEX IF NOT EXISTS ngs_rushing_season_week_idx
    ON ngs_rushing(season, week);
CREATE INDEX IF NOT EXISTS ngs_rushing_player_season_idx
    ON ngs_rushing(player_id, season);

-- ---------------------------------------------------------------------------
-- NGS receiving
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ngs_receiving (
    player_id                               INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season                                  INTEGER NOT NULL,
    season_type                             TEXT NOT NULL,
    week                                    INTEGER NOT NULL,
    team_id                                 INTEGER NOT NULL REFERENCES teams(team_id),

    avg_cushion                             REAL,
    avg_separation                          REAL,                -- the money metric
    avg_intended_air_yards                  REAL,
    percent_share_of_intended_air_yards     REAL,

    receptions                              INTEGER,
    targets                                 INTEGER,
    catch_percentage                        REAL,
    yards                                   INTEGER,
    rec_touchdowns                          INTEGER,

    avg_yac                                 REAL,
    avg_expected_yac                        REAL,
    avg_yac_above_expectation               REAL,                -- YAC over expected

    PRIMARY KEY (player_id, season, season_type, week, team_id)
);

CREATE INDEX IF NOT EXISTS ngs_receiving_season_week_idx
    ON ngs_receiving(season, week);
CREATE INDEX IF NOT EXISTS ngs_receiving_player_season_idx
    ON ngs_receiving(player_id, season);

COMMIT;
