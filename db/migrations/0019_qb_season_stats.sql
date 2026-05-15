BEGIN;

-- Per-season aggregated QB context stats (box-score volume).
-- Sources: nflvs_player_stats (per-week; aggregated to season totals, REG only).
-- Grain: one row per (player_id, season). Used for leaderboard CONTEXT columns
-- on the QB tab — NOT inputs to the grade. The grading formula stays at
-- EPA/dropback + CPOE + success_rate (ADR-0013 v1.1).
--
-- Pattern mirrors kicker_stats / punter_stats: dedicated context table keeps
-- season_grades position-agnostic and avoids NULL-heavy schema bloat.
CREATE TABLE qb_season_stats (
    player_id          INTEGER  NOT NULL REFERENCES players(player_id),
    season             SMALLINT NOT NULL,
    games              SMALLINT,
    -- Passing
    pass_attempts      SMALLINT,
    pass_completions   SMALLINT,
    pass_yards         INTEGER,
    pass_tds           SMALLINT,
    interceptions      SMALLINT,
    sacks_taken        SMALLINT,
    -- Rushing (mobile QBs)
    rush_attempts      SMALLINT,
    rush_yards         INTEGER,
    rush_tds           SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX qb_season_stats_season_idx ON qb_season_stats (season);

COMMIT;
