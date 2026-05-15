BEGIN;

-- Per-season aggregated box-score volume stats for skill positions (RB/WR/TE).
-- Sources: nflvs_player_stats (per-week; aggregated to season totals, REG only).
-- Grain: one row per (player_id, season). Used for leaderboard CONTEXT columns
-- on the RB/WR/TE tabs — NOT inputs to the grade.
--
-- One shared table because WR + TE have identical box-score lines and RB just
-- adds rushing on top. Keeps ingest to one module, leaderboard to one JOIN.
-- QB has its own table (qb_season_stats) because passing cols are conceptually
-- different and were already shipped.
CREATE TABLE skill_player_season_stats (
    player_id        INTEGER  NOT NULL REFERENCES players(player_id),
    season           SMALLINT NOT NULL,
    games            SMALLINT,
    -- Rushing (RBs primarily; some receivers see jet sweeps/end-arounds)
    rush_attempts    SMALLINT,
    rush_yards       INTEGER,
    rush_tds         SMALLINT,
    -- Receiving (RBs/WRs/TEs)
    targets          SMALLINT,
    receptions       SMALLINT,
    rec_yards        INTEGER,
    rec_tds          SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX skill_player_season_stats_season_idx
    ON skill_player_season_stats (season);

COMMIT;
