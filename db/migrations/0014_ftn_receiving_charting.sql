BEGIN;

-- FTN per-play receiver charting flags aggregated to season totals.
-- Used by WR v1.1 grading (ADR-0015 revised) for drop_rate component.
-- Source: ftn (per-play) joined to pbp.receiver_player_id.
-- Coverage: 2022+ (FTN charting begins 2022 in nflverse).
CREATE TABLE ftn_receiving_charting (
    player_id           INTEGER  NOT NULL REFERENCES players(player_id),
    season              SMALLINT NOT NULL,
    catchable_balls     SMALLINT,
    drops               SMALLINT,
    contested_balls     SMALLINT,
    created_receptions  SMALLINT,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX ftn_receiving_charting_season_idx ON ftn_receiving_charting (season);

COMMIT;
