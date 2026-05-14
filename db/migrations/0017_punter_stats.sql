BEGIN;

-- Per-season aggregated punter stats for P v1 grading (ADR-0024).
-- Sources: pbp (play-by-play) — aggregated to season totals.
-- Grain: one row per (player_id, season). Used by grading/punter.py.
--
-- Note: nflverse player_stats doesn't carry detailed punting columns,
-- so we aggregate directly from pbp punt_attempt rows by punter_player_id.
CREATE TABLE punter_stats (
    player_id        INTEGER  NOT NULL REFERENCES players(player_id),
    season           SMALLINT NOT NULL,
    -- Volume
    punts            INTEGER,
    gross_yards      INTEGER,
    return_yards     INTEGER,
    net_yards        INTEGER,
    -- Outcomes
    inside_20        SMALLINT,
    touchbacks       SMALLINT,
    blocked          SMALLINT,
    fair_catches     SMALLINT,
    out_of_bounds    SMALLINT,
    downed           SMALLINT,
    -- Value (EPA from pbp, summed across all punts)
    epa_total        REAL,
    -- Power
    long_punt        SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX punter_stats_season_idx ON punter_stats (season);

COMMIT;
