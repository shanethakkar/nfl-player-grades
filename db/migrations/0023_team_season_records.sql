BEGIN;

-- Per-team-season regular-season record + scoring totals.
--
-- Used for the team leaderboard context columns (W-L, point diff). Not
-- input to grading — this is a denormalization of nflreadpy.load_schedules
-- so the web layer doesn't have to do per-request schedule scraping or
-- play-by-play aggregation.
--
-- Regular season only (game_type='REG'). Playoffs are deliberately
-- excluded because:
--   1) playoff teams play different numbers of games, breaking comparisons
--   2) per-game stats during playoffs swing wildly with stakes
--   3) the audit + team grades work is all on regular-season data

CREATE TABLE team_season_records (
    team_id          INTEGER  NOT NULL REFERENCES teams(team_id),
    season           SMALLINT NOT NULL,
    wins             SMALLINT NOT NULL,
    losses           SMALLINT NOT NULL,
    ties             SMALLINT NOT NULL DEFAULT 0,
    points_for       SMALLINT NOT NULL,
    points_against   SMALLINT NOT NULL,
    point_diff       SMALLINT NOT NULL,
    n_games          SMALLINT NOT NULL,
    PRIMARY KEY (team_id, season)
);

CREATE INDEX team_season_records_season_idx ON team_season_records (season);

COMMIT;
