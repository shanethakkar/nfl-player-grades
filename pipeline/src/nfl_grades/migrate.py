"""Apply SQL migrations from db/migrations/ in order, tracked in schema_migrations.

Conventions (see docs/adr/0006-forward-only-tracked-migrations.md):

- Migration files: db/migrations/NNNN_description.sql, lexically ordered.
- Forward-only. To fix a bad migration, ship a new one.
- Each migration runs inside a transaction.
- Once applied, a migration is recorded in `schema_migrations` with its
  sha256. If the file content changes after being applied, this script will
  refuse to run and warn you (don't edit applied migrations).
- Seeds are separate. They are idempotent (use ON CONFLICT) and re-run every
  time you pass `seeds=True`.

Invoked via `nflgrades migrate [--seeds] [--dry-run]`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import text

from .config import REPO_ROOT
from .db import get_engine
from .logging import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
SEEDS_DIR = REPO_ROOT / "db" / "seeds"

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename     TEXT PRIMARY KEY,
    sha256       TEXT NOT NULL,
    applied_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class MigrationModifiedError(RuntimeError):
    """Raised when an already-applied migration's file content has changed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _list_migrations() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _list_seeds() -> list[Path]:
    return sorted(SEEDS_DIR.glob("*.sql"))


def run(seeds: bool = False, dry_run: bool = False) -> int:
    """Apply all pending migrations. Returns count of migrations applied."""
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text(SCHEMA_MIGRATIONS_DDL))
        applied = {
            row.filename: row.sha256
            for row in conn.execute(text("SELECT filename, sha256 FROM schema_migrations"))
        }

    pending: list[Path] = []
    for path in _list_migrations():
        digest = _sha256(path)
        if path.name in applied:
            if applied[path.name] != digest:
                raise MigrationModifiedError(
                    f"{path.name} was modified after being applied "
                    f"(stored sha={applied[path.name]}, file sha={digest}). "
                    "Forward-only: ship a new migration."
                )
            continue
        pending.append(path)

    if not pending:
        log.info("No pending migrations.")
    else:
        log.info("Pending migrations: %s", [p.name for p in pending])

    if dry_run:
        return 0

    for path in pending:
        log.info("Applying %s", path.name)
        sql = path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.execute(text(sql))
            conn.execute(
                text("INSERT INTO schema_migrations (filename, sha256) VALUES (:f, :s)"),
                {"f": path.name, "s": _sha256(path)},
            )

    if seeds:
        for path in _list_seeds():
            log.info("Seeding %s", path.name)
            sql = path.read_text(encoding="utf-8")
            with engine.begin() as conn:
                conn.execute(text(sql))

    return len(pending)
