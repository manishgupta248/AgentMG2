"""
Personal AI Agent — Entrypoint
Milestone: M1 (Foundation) — config + logging + SQLite persistence wired in.
"""

from app.core.config import settings
from app.core.logging_setup import setup_logging, logger
from app.core.database import init_db, db_cursor


def main() -> None:
    setup_logging()
    logger.info("Agent starting up.")
    logger.debug("DB path: {}", settings.db_path)

    init_db()

    # Sanity check: list tables that now exist
    with db_cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
    logger.info("Tables present: {}", tables)

    print("Agent scaffold OK. DB initialized. Ready for M1 Step 4 (domain exception hierarchy).")


if __name__ == "__main__":
    main()