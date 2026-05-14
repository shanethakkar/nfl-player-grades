BEGIN;

-- Stores aggregated PFR rush advanced stats for RB v1.4+ grading.
-- Sourced from nflreadpy.load_pfr_advstats(stat_type='rush'), aggregated
-- to season totals. Grain: one row per player per season.
--
-- Primary use: rb.py computes `rb_yards_after_contact_per_carry`, added
-- in v1.4 (ADR-0014) after the exhaustive RB audit identified it as the
-- highest-validity candidate (+0.192 vs next-year Pro Bowl, higher than
-- any current RB component).
--
-- The yards_before_contact + broken_tackles columns are stored for
-- future use even though they're not currently in the formula —
-- yards_before_contact reflects OL quality (would be useful for
-- eventual unit-OL grading); broken_tackles is a borderline candidate
-- that might be added in a future revision.
--
-- Coverage begins 2018 (PFR per-player data limitation).
CREATE TABLE pfr_rb_rush (
    player_id            INTEGER  NOT NULL REFERENCES players(player_id),
    season               SMALLINT NOT NULL,
    games                SMALLINT,
    carries              INTEGER,
    yards_after_contact  INTEGER,
    yards_before_contact INTEGER,
    broken_tackles       SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX pfr_rb_rush_season_idx ON pfr_rb_rush (season);

COMMIT;
