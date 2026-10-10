BEGIN;

-- Weekly grain for the two RB/WR/TE Component sources that were stored only
-- as season totals: FTN receiver charting (drop rate) and PFR rush advanced
-- stats (yards after contact). The evaluation harness (ADR-0029, #13) needs
-- per-week values for its odd/even-week Reliability panels; the graders sum
-- these tables over the season, which gives the same totals as before.
--
-- These replace ftn_receiving_charting (0014) and pfr_rb_rush (0015). The
-- old tables stay until the code that writes them is no longer deployed;
-- a later migration drops them.

-- FTN per-play receiver charting flags, summed per receiver and REG week.
-- Coverage: 2022+.
CREATE TABLE ftn_receiving_weekly (
    player_id           INTEGER  NOT NULL REFERENCES players(player_id),
    season              SMALLINT NOT NULL,
    week                SMALLINT NOT NULL,
    catchable_balls     SMALLINT NOT NULL,
    drops               SMALLINT NOT NULL,
    contested_balls     SMALLINT NOT NULL,
    created_receptions  SMALLINT NOT NULL,
    PRIMARY KEY (player_id, season, week)
);

CREATE INDEX ftn_receiving_weekly_season_idx ON ftn_receiving_weekly (season);

-- PFR rush advanced stats per RB and REG week (one game per week).
-- Coverage: 2018+.
CREATE TABLE pfr_rb_rush_weekly (
    player_id            INTEGER  NOT NULL REFERENCES players(player_id),
    season               SMALLINT NOT NULL,
    week                 SMALLINT NOT NULL,
    carries              INTEGER,
    yards_after_contact  INTEGER,
    yards_before_contact INTEGER,
    broken_tackles       SMALLINT,
    PRIMARY KEY (player_id, season, week)
);

CREATE INDEX pfr_rb_rush_weekly_season_idx ON pfr_rb_rush_weekly (season);

COMMIT;
