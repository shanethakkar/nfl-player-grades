BEGIN;

-- Per-season aggregated defensive box-score volume stats for CB/S/EDGE/iDL/LB.
-- Sources: nflvs_player_stats (per-week; aggregated to season totals, REG only).
-- Grain: one row per (player_id, season). Used for leaderboard CONTEXT columns
-- on the defensive tabs — NOT inputs to the grades.
--
-- Single shared table because every defensive position draws from the same
-- box-score taxonomy (tackles / sacks / TFLs / INTs / FF / PBU). The
-- leaderboard JOIN selects different subsets per position.
--
-- sacks and tackles_for_loss are REAL because half-credits exist
-- (two players splitting a sack get 0.5 each in official stats).
CREATE TABLE defensive_player_season_stats (
    player_id          INTEGER  NOT NULL REFERENCES players(player_id),
    season             SMALLINT NOT NULL,
    games              SMALLINT,
    -- Tackles
    tackles_solo       SMALLINT,
    tackle_assists     SMALLINT,
    tackles_for_loss   REAL,
    -- Pass rush
    sacks              REAL,
    qb_hits            SMALLINT,
    -- Coverage
    pass_defended      SMALLINT,
    interceptions      SMALLINT,
    int_yards          SMALLINT,
    -- Ball production
    forced_fumbles     SMALLINT,
    def_tds            SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX defensive_player_season_stats_season_idx
    ON defensive_player_season_stats (season);

COMMIT;
