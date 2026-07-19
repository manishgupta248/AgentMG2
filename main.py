"""
Personal AI Agent — Entrypoint
Milestone: M1 (Foundation) — config, logging, SQLite, exceptions,
and plugin registry with recursive discovery, all wired in.
"""

from app.core.config import settings
from app.core.logging_setup import setup_logging, logger
from app.core.database import init_db, db_cursor
from app.core.registry import autodiscover_tools, list_tools


def main() -> None:
    setup_logging()
    logger.info("Agent starting up.")

    init_db()

    with db_cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
    logger.info("Tables present: {}", tables)

    modules_imported = autodiscover_tools()
    tools = list_tools()

    logger.info("Modules imported: {}", modules_imported)
    logger.info("Tools registered: {}", list(tools.keys()))

    for name, t in tools.items():
        print(f"  - {name} (permission={t.permission.value}): {t.description}")

    print(f"\nAgent scaffold OK. {len(tools)} tool(s) discovered, including one from a nested subfolder.")
    print("Ready for M1 Step 6 (ApprovalHandler protocol + call_tool executor).")


if __name__ == "__main__":
    main()