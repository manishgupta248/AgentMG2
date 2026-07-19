"""
Personal AI Agent — Entrypoint
Milestone: M5 (Notification Framework) — console channel wired to
event bus, notifying on tool failures.
"""

from app.core.config import settings
from app.core.logging_setup import setup_logging, logger
from app.core.database import init_db, db_cursor
from app.core.registry import autodiscover_tools, list_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.notifications.manager import notification_manager
from app.notifications.console_channel import ConsoleChannel
from app.notifications.event_subscriber import wire_notifications_to_event_bus


def main() -> None:
    setup_logging()
    logger.info("Agent starting up.")

    init_db()
    autodiscover_tools()

    notification_manager.register_channel(ConsoleChannel())
    wire_notifications_to_event_bus()

    # Successful call -> no notification expected
    call_tool("ping", {})

    # Failing call -> SHOULD trigger a console notification automatically
    try:
        call_tool("echo", {})  # missing required 'text' -> validation failure
    except Exception as e:
        logger.info("Expected failure occurred: {}", e)

    print("\nAgent scaffold OK. Notification Framework wired: console channel notified on tool failure above.")
    print("Ready for M5 Step 2 (regression tests) or M6 (Telegram as a NotificationChannel).")


if __name__ == "__main__":
    main()