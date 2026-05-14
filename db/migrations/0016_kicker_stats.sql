BEGIN;

-- Per-season aggregated kicker stats for K v1 grading (ADR-0023).
-- Sources: nflvs_player_stats (per-game; aggregated to season totals).
-- Grain: one row per (player_id, season). Used by grading/kicker.py.
--
-- v1 scope: placekicking only (FG + XP). Kickoffs intentionally excluded
-- because the 2024 dynamic-kickoff rule change broke continuity of
-- touchback/return rates; those will be a separate v2 component if added.
CREATE TABLE kicker_stats (
    player_id        INTEGER  NOT NULL REFERENCES players(player_id),
    season           SMALLINT NOT NULL,
    games            SMALLINT,
    -- Field goals
    fg_att           SMALLINT,
    fg_made          SMALLINT,
    fg_blocked       SMALLINT,
    fg_long          SMALLINT,
    -- Distance buckets
    fg_att_0_19      SMALLINT,
    fg_made_0_19     SMALLINT,
    fg_att_20_29     SMALLINT,
    fg_made_20_29    SMALLINT,
    fg_att_30_39     SMALLINT,
    fg_made_30_39    SMALLINT,
    fg_att_40_49     SMALLINT,
    fg_made_40_49    SMALLINT,
    fg_att_50_59     SMALLINT,
    fg_made_50_59    SMALLINT,
    fg_att_60_plus   SMALLINT,
    fg_made_60_plus  SMALLINT,
    -- Extra points
    pat_att          SMALLINT,
    pat_made         SMALLINT,
    pat_blocked      SMALLINT,
    -- Game-winning FGs (per nflverse definition)
    gwfg_att         SMALLINT,
    gwfg_made        SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX kicker_stats_season_idx ON kicker_stats (season);

COMMIT;
