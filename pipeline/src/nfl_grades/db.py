"""SQLAlchemy engine and session helpers.

Pipeline code should use `get_engine()` or the `session()` context manager
instead of constructing engines ad hoc. This gives us one place to tune pool
size, statement timeouts, and logging.
"""

from __future__ import annotations

import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine."""
    # SQLAlchemy expects 'postgresql://' rather than 'postgres://'.
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True, future=True)


_SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session() -> Iterator[Session]:
    """Context manager yielding a SQLAlchemy session with commit/rollback."""
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ---------------------------------------------------------------------------
# pipeline_runs lifecycle
# ---------------------------------------------------------------------------


@dataclass
class RunHandle:
    """Mutable handle yielded by `pipeline_run()`. Set `rows_written` and
    optionally append to `notes` from inside the context body; the context
    manager writes them to `pipeline_runs` on exit."""

    run_id: int
    stage: str
    season: int | None
    rows_written: int = 0
    notes_lines: list[str] = field(default_factory=list)

    def note(self, line: str) -> None:
        """Append a free-form note line; concatenated and stored on exit."""
        self.notes_lines.append(line)


@contextmanager
def pipeline_run(stage: str, season: int | None = None) -> Iterator[RunHandle]:
    """Wrap a pipeline stage in a `pipeline_runs` row with status lifecycle.

    Inserts a row with ``status='running'`` on entry, then on clean exit
    updates to ``status='ok'`` with the handle's ``rows_written`` and notes.
    On exception, marks ``status='error'`` with a truncated traceback in
    ``notes`` and re-raises.

    Each row uses its own short-lived connection — the stage body is free
    to open its own transactions for the actual work. We deliberately do
    **not** wrap the stage body in a transaction here, since ingest stages
    typically span minutes and we don't want a single Postgres tx open
    that whole time.

    Args:
        stage: Free-form stage label, e.g. 'ingest:rosters'.
        season: Optional season for the row's ``season`` column.

    Yields:
        ``RunHandle`` — set ``handle.rows_written = N`` from inside the body.
    """
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO pipeline_runs (stage, season, started_at, status)
                VALUES (:stage, :season, NOW(), 'running')
                RETURNING run_id
                """
            ),
            {"stage": stage, "season": season},
        )
        run_id = result.scalar_one()

    handle = RunHandle(run_id=run_id, stage=stage, season=season)
    try:
        yield handle
    except Exception:
        tb = traceback.format_exc()
        notes = "\n".join(handle.notes_lines + [tb])[:4000]
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE pipeline_runs
                       SET finished_at = NOW(),
                           status      = 'error',
                           rows_written = :rows,
                           notes       = :notes
                     WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id, "rows": handle.rows_written, "notes": notes},
            )
        raise
    else:
        notes = "\n".join(handle.notes_lines)[:4000] or None
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE pipeline_runs
                       SET finished_at = NOW(),
                           status      = 'ok',
                           rows_written = :rows,
                           notes       = :notes
                     WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id, "rows": handle.rows_written, "notes": notes},
            )
