"""
SQLite persistence layer.

- db_cursor(): context manager for connection + cursor lifecycle,
  commits on success, rolls back on exception, always closes.
- init_db(): creates ALL base tables in one call. Test fixtures must
  call this directly rather than assuming it happens elsewhere — a
  prior build had a test module hit "no such table" because a shared
  fixture didn't actually run schema init itself.
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.core.config import settings
from app.core.logging_setup import logger


@contextmanager
def db_cursor(db_path=None) -> Iterator[sqlite3.Cursor]:
    """
    Yields a sqlite3 cursor. Commits on clean exit, rolls back and
    re-raises on exception. Always closes the connection.
    """
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("DB operation failed, rolled back. path={}", path)
        raise
    finally:
        conn.close()


def init_db(db_path=None) -> None:
    """
    Creates all base tables if they don't exist yet. Idempotent —
    safe to call on every startup and from every test fixture.
    """
    with db_cursor(db_path) as cur:
        # Mandatory audit trail — every call_tool() invocation writes here,
        # success or failure, automatically (built inside call_tool itself,
        # not left to individual tools to remember — see M2).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                tool_kwargs TEXT,
                status TEXT NOT NULL,           -- success | failure
                result TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            )
            """
        )

        # Central Knowledge Base — structured from day one so embeddings
        # can be added later without a schema rewrite.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,             -- note | contact | preference | memory
                title TEXT,
                content TEXT NOT NULL,
                metadata TEXT,                  -- JSON string, open-ended
                embedding BLOB,                 -- nullable, populated in a later phase
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Job Queue — status tracking for async long-running tasks (M10)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                payload TEXT,                   -- JSON string
                status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|succeeded|failed
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )

        # Scheduler — recurring job definitions (M11)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                job_type TEXT NOT NULL,
                payload TEXT,
                schedule_expr TEXT NOT NULL,    -- cron-like or interval expression
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                next_run_at TEXT
            )
            """
        )

    logger.info("Database initialized. path={}", db_path or settings.db_path)


__all__ = ["db_cursor", "init_db"]