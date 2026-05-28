BEGIN;

-- Now that the backfill has populated every players.slug, lock in
-- NOT NULL + UNIQUE. The plain index from 0024 becomes a unique index.

ALTER TABLE players ALTER COLUMN slug SET NOT NULL;

DROP INDEX players_slug_idx;
CREATE UNIQUE INDEX players_slug_idx ON players (slug);

COMMIT;
