-- CB v1 (ADR-0018): PFR advanced defensive coverage stats per CB per season.
--
-- Populated by pipeline/src/nfl_grades/ingest/pfr.py from
-- nflreadpy.load_pfr_advstats(stat_type="def").
-- Coverage begins in 2018 (first year PFR published per-CB coverage data).
--
-- Grain: one row per (player_id, season). A CB traded mid-season gets one
-- aggregated row (PFR publishes season totals, not per-team splits).

BEGIN;

CREATE TABLE IF NOT EXISTS pfr_def_coverage (
    player_id       INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    season          INTEGER NOT NULL,

    -- Volume
    games           INTEGER NOT NULL DEFAULT 0,
    targets         INTEGER,            -- times targeted in coverage

    -- Outcomes allowed
    completions     INTEGER,            -- completions allowed
    yards           INTEGER,            -- yards allowed
    yac             REAL,               -- yards after catch allowed (NULL if not published)
    tds             INTEGER,            -- touchdowns allowed

    -- Positive defensive plays
    ints            INTEGER,            -- interceptions
    pass_breakups   INTEGER,            -- passes defended (PBU)

    -- Alignment
    slot_pct        REAL,               -- fraction of snaps in slot (0.0 – 1.0; NULL if unknown)

    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS pfr_def_coverage_season_idx ON pfr_def_coverage(season);

COMMIT;
