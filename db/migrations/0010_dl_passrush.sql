BEGIN;

-- Stores aggregated pass-rush stats for EDGE and iDL players, sourced
-- from pfr_advstats_def (pressures/sacks/hits/hurries/missed tackles)
-- and nflvs_player_stats (TFL, reported separately from sacks in nflverse).
-- Grain: one row per player per season. Used by grading/edge.py and
-- grading/idl.py.
CREATE TABLE pfr_def_pass_rush (
    player_id       INTEGER  NOT NULL REFERENCES players(player_id),
    season          SMALLINT NOT NULL,
    games           SMALLINT,
    pressures       REAL,
    sacks           REAL,
    qb_hits         SMALLINT,
    hurries         SMALLINT,
    comb_tackles    SMALLINT,
    missed_tackles  SMALLINT,
    tfl             REAL,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX pfr_def_pass_rush_season_idx ON pfr_def_pass_rush (season);

COMMIT;
