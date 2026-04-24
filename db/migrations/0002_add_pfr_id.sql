-- 0002_add_pfr_id.sql
-- Add Pro Football Reference player id to the players master.
--
-- nflreadpy.load_snap_counts() (and several other PFR-derived sources) key
-- on pfr_player_id rather than gsis_id. We populate pfr_id during rosters
-- ingestion from nflreadpy.load_players() and then snap-counts / any other
-- PFR source joins directly against players.pfr_id.
--
-- See ingest/rosters.py::_transform_players and ingest/snap_counts.py.

BEGIN;

ALTER TABLE players ADD COLUMN IF NOT EXISTS pfr_id TEXT;

-- Not UNIQUE: a tiny fraction of historical players may share a PFR id
-- collision across totally different eras; UNIQUE constraint would require
-- careful vetting. Use a non-unique index for lookup speed only.
CREATE INDEX IF NOT EXISTS players_pfr_id_idx ON players(pfr_id);

COMMIT;
