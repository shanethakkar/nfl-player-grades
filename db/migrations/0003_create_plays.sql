-- 0003_create_plays.sql
-- Thin play-by-play fact table. Schema is a ~40-column projection of
-- nflreadpy.load_pbp()'s 372 columns, chosen to cover QB grading (v1),
-- RB/WR grading (v2), defensive attribution, and UI drill-downs.
-- See docs/adr/0011-thin-plays-table-in-postgres.md.

BEGIN;

CREATE TABLE IF NOT EXISTS plays (
    -- identifiers --------------------------------------------------------
    game_id                 TEXT NOT NULL,
    play_id                 INTEGER NOT NULL,

    -- game context -------------------------------------------------------
    season                  INTEGER NOT NULL,
    season_type             TEXT NOT NULL,   -- 'REG' | 'POST'
    week                    INTEGER,
    game_date               DATE,

    -- teams (TEXT, not FK; see ADR-0011) ---------------------------------
    posteam                 TEXT,
    defteam                 TEXT,
    home_team               TEXT,
    away_team               TEXT,

    -- situational --------------------------------------------------------
    qtr                     SMALLINT,
    down                    SMALLINT,
    ydstogo                 SMALLINT,
    yardline_100            SMALLINT,
    score_differential      SMALLINT,
    game_seconds_remaining  INTEGER,
    half_seconds_remaining  INTEGER,
    wp                      REAL,

    -- play classification ------------------------------------------------
    play_type               TEXT,            -- 'pass'|'run'|'punt'|'field_goal'|'kickoff'|'extra_point'|'qb_kneel'|'qb_spike'|'no_play'|null
    qb_dropback             BOOLEAN,
    pass_attempt            BOOLEAN,
    rush_attempt            BOOLEAN,
    sack                    BOOLEAN,
    qb_scramble             BOOLEAN,
    qb_spike                BOOLEAN,
    qb_kneel                BOOLEAN,
    aborted_play            BOOLEAN,
    two_point_attempt       BOOLEAN,
    penalty                 BOOLEAN,

    -- player attribution (gsis_ids, TEXT) --------------------------------
    passer_player_id        TEXT,
    rusher_player_id        TEXT,
    receiver_player_id      TEXT,
    sack_player_id          TEXT,
    interception_player_id  TEXT,

    -- outcomes -----------------------------------------------------------
    yards_gained            INTEGER,
    epa                     REAL,
    wpa                     REAL,
    cpoe                    REAL,
    success                 BOOLEAN,
    air_yards               INTEGER,
    yards_after_catch       INTEGER,
    complete_pass           BOOLEAN,
    incomplete_pass         BOOLEAN,
    interception            BOOLEAN,
    fumble_lost             BOOLEAN,
    pass_touchdown          BOOLEAN,
    rush_touchdown          BOOLEAN,
    touchdown               BOOLEAN,

    -- debugging / UI -----------------------------------------------------
    play_desc               TEXT,            -- renamed from nflverse 'desc' (SQL reserved)

    PRIMARY KEY (game_id, play_id)
);

-- Indexes chosen for the two dominant access patterns:
--   1. "All REG plays for season S"                -> grading bulk read
--   2. "All plays where player X was the passer"   -> per-player feature extraction / UI
CREATE INDEX IF NOT EXISTS plays_season_idx
    ON plays(season, season_type);

CREATE INDEX IF NOT EXISTS plays_passer_season_idx
    ON plays(passer_player_id, season)
    WHERE passer_player_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS plays_rusher_season_idx
    ON plays(rusher_player_id, season)
    WHERE rusher_player_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS plays_receiver_season_idx
    ON plays(receiver_player_id, season)
    WHERE receiver_player_id IS NOT NULL;

COMMIT;
