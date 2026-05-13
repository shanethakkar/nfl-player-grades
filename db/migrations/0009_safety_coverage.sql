-- Safety v1 (ADR-0019): PFR advanced defensive stats per safety per season.
--
-- Populated by pipeline/src/nfl_grades/ingest/pfr_safety.py.
-- Coverage begins 2018 (PFR published per-defender coverage data from 2018).
--
-- Grain: one row per (player_id, season). Season-level totals; traded
-- players get one aggregated row.
--
-- Sources:
--   pfr_advstats_def  → targets, completions, yards, ints
--   nflvs_player_stats → pass_breakups, comb_tackles, tfl, sacks
--   pfr_advstats_def  → missed_tackles (attempted; NULL if column absent)

BEGIN;

CREATE TABLE IF NOT EXISTS pfr_def_coverage_s (
    player_id        INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season           INTEGER NOT NULL,

    -- Volume
    games            INTEGER NOT NULL DEFAULT 0,
    targets          INTEGER,            -- times targeted in coverage

    -- Coverage outcomes allowed
    completions      INTEGER,            -- completions allowed
    yards            INTEGER,            -- yards allowed
    ints             INTEGER,            -- interceptions

    -- Playmaking (from nflverse def_pass_defended)
    pass_breakups    INTEGER,

    -- Tackling (from nflverse player_stats)
    comb_tackles     INTEGER,            -- solo + assisted
    tfl              INTEGER,            -- tackles for loss
    sacks            REAL,

    -- Missed tackles (from PFR advstats; NULL if not in source)
    missed_tackles   INTEGER,

    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS pfr_def_coverage_s_season_idx ON pfr_def_coverage_s(season);

COMMIT;
