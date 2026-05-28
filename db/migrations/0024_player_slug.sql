BEGIN;

-- Add a URL-friendly slug to every player so player profiles can live at
-- /players/{slug} instead of /players/{numeric_id}. Better SEO, better
-- shareability, friendlier URLs.
--
-- Generation rule (applied in pipeline/scripts/backfill_player_slugs.py):
--   1. Default: lowercase(full_name), non-alphanumeric -> hyphen.
--   2. On collision among graded players: the player with the most
--      graded seasons keeps the bare slug (ties: lowest player_id).
--   3. Secondary colliders get a position suffix (`-cb`, `-qb`, etc.).
--   4. If position also collides: use first-graded-season as suffix.
--   5. Non-graded players with collisions: append player_id.
--
-- This migration only adds the column (nullable, no UNIQUE yet) so the
-- backfill can run before the constraint is enforced. Migration 0025
-- locks in NOT NULL + UNIQUE once the backfill verifies clean.

ALTER TABLE players ADD COLUMN slug TEXT;

-- Index now so the backfill UPDATEs + future ingest UPSERTs are fast.
-- It's a regular (non-unique) index for now — promoted to UNIQUE in 0025.
CREATE INDEX players_slug_idx ON players (slug);

COMMIT;
