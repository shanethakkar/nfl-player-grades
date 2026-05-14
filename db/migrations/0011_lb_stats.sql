BEGIN;

-- Aggregated stats for LB grading (ADR-0022).
-- Sources: pfr_advstats_def (tackles, missed, pressures, sacks, coverage),
-- nflvs_player_stats (TFL, PBU, fumbles forced).
-- Grain: one row per player per season. Used by grading/lb.py.
CREATE TABLE pfr_def_lb (
    player_id       INTEGER  NOT NULL REFERENCES players(player_id),
    season          SMALLINT NOT NULL,
    games           SMALLINT,
    -- Tackling
    comb_tackles    SMALLINT,
    missed_tackles  SMALLINT,
    tfl             REAL,
    -- Pass rush
    pressures       REAL,
    sacks           REAL,
    qb_hits         SMALLINT,
    hurries         SMALLINT,
    -- Coverage
    targets         SMALLINT,
    completions_allowed SMALLINT,
    yards_allowed   REAL,
    ints            SMALLINT,
    pbu             SMALLINT,
    -- Playmaking
    fumbles_forced  SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX pfr_def_lb_season_idx ON pfr_def_lb (season);

COMMIT;
