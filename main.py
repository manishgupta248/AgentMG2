"""
Personal AI Agent — Entrypoint
Milestone: M1 (Foundation) — full core wired: config, logging, SQLite,
exceptions, plugin registry, approval handler, call_tool executor.
"""

from app.core.config import settings
from app.core.logging_setup import setup_logging, logger
from app.core.database import init_db, db_cursor
from app.core.registry import autodiscover_tools, list_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler


def main() -> None:
    setup_logging()
    logger.info("Agent starting up.")

    init_db()
    autodiscover_tools()
    tools = list_tools()
    logger.info("Tools registered: {}", list(tools.keys()))

    # Exercise call_tool end-to-end on a READ tool (auto-approves, no prompt)
    result = call_tool("ping", {}, approval_handler=AutoApprovalHandler())
    print("call_tool('ping') ->", result)

    result2 = call_tool("echo", {"text": "hello agent"}, approval_handler=AutoApprovalHandler())
    print("call_tool('echo', text='hello agent') ->", result2)

    # Confirm the execution_history audit rows were written
    with db_cursor() as cur:
        cur.execute("SELECT tool_name, status, result FROM execution_history ORDER BY id DESC LIMIT 5")
        rows = cur.fetchall()
    print("\nRecent execution_history rows:")
    for row in rows:
        print(" ", row)

    print("\nAgent scaffold OK. call_tool executor verified end-to-end with audit logging.")
    print("Ready for M1 Step 7 (Pydantic input validation wired into tools) — or M2 if this concludes M1.")


if __name__ == "__main__":
    main()