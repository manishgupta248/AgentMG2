"""
Wires the NotificationManager to the Event Bus. Kept as a separate
module (rather than inline in manager.py) so the subscription policy
(which events trigger which notifications) can evolve independently
of the manager's dispatch mechanics.
"""

from app.events.bus import event_bus, Event
from app.notifications.manager import notification_manager
from app.core.logging_setup import logger


def _on_tool_executed(event: Event) -> None:
    """
    For M5 Step 1: only notify on FAILURES. Success notifications for
    every single tool call would be noisy; that policy can be refined
    per-tool or per-permission-level later if needed.
    """
    payload = event.payload
    if payload.get("status") != "failure":
        return

    tool_name = payload.get("tool_name", "unknown")
    error = payload.get("error", "unknown error")
    notification_manager.notify(
        f"Tool '{tool_name}' failed: {error}",
        title="Tool Failure",
        metadata={"tool_name": tool_name},
    )


def wire_notifications_to_event_bus() -> None:
    """Call once at startup (after channels are registered)."""
    event_bus.subscribe("tool.executed", _on_tool_executed)
    logger.info("NotificationManager wired to event bus (tool.executed -> failure notifications).")


__all__ = ["wire_notifications_to_event_bus"]