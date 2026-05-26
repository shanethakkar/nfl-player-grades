BEGIN;

-- Team-level overall grading (ADR-0026).
--
-- v1 methodology: two-stage aggregation of EXISTING player grades.
--   Stage 1 — within a position: snap-weighted average of all players
--     who logged snaps at that position on the team.
--   Stage 2 — across positions in a phase: position-weighted sum into
--     Offense / Defense / ST sub-grades.
--   Overall = 0.45 * Off + 0.45 * Def + 0.10 * ST.
--
-- OL is exempted from Stage 1: team_ol_grades.composite_grade is
-- already a team-season number (ADR-0025).
--
-- Two tables, kept separate from season_grades and from team_ol_*:
--   team_grades            -- one row per (team_id, season): overall + phase grades
--   team_grade_components  -- per-position contribution rows (for breakdown UIs)
--
-- No new ingest. All inputs come from already-populated tables
-- (season_grades, team_ol_grades, player_seasons.snaps_*).

CREATE TABLE team_grades (
    team_id              INTEGER          NOT NULL REFERENCES teams(team_id),
    season               SMALLINT         NOT NULL,
    -- Composite + sub-grades on the 0..100 scale (same sigmoid as players, ADR-0008).
    overall_grade        DOUBLE PRECISION NOT NULL,
    offense_grade        DOUBLE PRECISION NOT NULL,
    defense_grade        DOUBLE PRECISION NOT NULL,
    st_grade             DOUBLE PRECISION NOT NULL,
    -- Underlying composite z-scores (pre-sigmoid). Stored for downstream
    -- recomputation (e.g. percentile-rank against an alternate cohort).
    overall_z            DOUBLE PRECISION NOT NULL,
    offense_z            DOUBLE PRECISION NOT NULL,
    defense_z            DOUBLE PRECISION NOT NULL,
    st_z                 DOUBLE PRECISION NOT NULL,
    -- Within-season percentile rank against the 32-team cohort.
    overall_percentile   DOUBLE PRECISION,
    offense_percentile   DOUBLE PRECISION,
    defense_percentile   DOUBLE PRECISION,
    st_percentile        DOUBLE PRECISION,
    -- If a phase had to redistribute weight because a position group was
    -- missing entirely (e.g. team somehow had no qualifying kicker),
    -- describe the fallback here. NULL on the happy path.
    data_tier_reason     TEXT,
    PRIMARY KEY (team_id, season)
);

CREATE INDEX team_grades_season_idx ON team_grades (season);


CREATE TABLE team_grade_components (
    team_id              INTEGER          NOT NULL REFERENCES teams(team_id),
    season               SMALLINT         NOT NULL,
    -- 'offense' | 'defense' | 'st' — keep TEXT not enum so future phase
    -- splits (e.g. splitting ST into K and P columns) don't require a
    -- schema migration.
    phase                TEXT             NOT NULL,
    -- 'QB' | 'RB' | 'WR' | 'TE' | 'OL' | 'EDGE' | 'iDL' | 'LB' | 'CB' | 'S' | 'K' | 'P'
    position             TEXT             NOT NULL,
    -- Snap-weighted aggregate of player grades at this position on this team
    -- (Stage 1 of the methodology). For OL, this is the team_ol_grades value
    -- copied directly (no aggregation needed).
    position_grade       DOUBLE PRECISION NOT NULL,
    -- Position weight applied in Stage 2 (e.g. QB = 0.40 for offense).
    -- Stored so the UI can render "share of phase" without re-deriving
    -- from weights.py, and so audits can spot drift between code + data.
    weight               DOUBLE PRECISION NOT NULL,
    -- Distinct graded players that contributed (>=1 snap at this position).
    -- Useful in the breakdown UI ("based on 4 players").
    n_players            SMALLINT         NOT NULL,
    -- Denominator of the snap-weighted average. 0 for OL (no aggregation).
    total_snaps          INTEGER          NOT NULL,
    PRIMARY KEY (team_id, season, phase, position)
);

CREATE INDEX team_grade_components_season_idx ON team_grade_components (season);
CREATE INDEX team_grade_components_phase_idx  ON team_grade_components (phase);

COMMIT;
