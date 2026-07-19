"""
In-process Event Bus — synchronous pub/sub.

Design intent (Section 4.6 of the rebuild spec): tools communicate
through published events instead of direct function coupling, so the
Notification Framework, Job Queue, and future subsystems can react to
tool activity without those tools knowing about them.

Kept deliberately simple for M3: synchronous, in-process, no external
broker. If a subscriber raises, it's logged and does NOT prevent other
subscribers from running, and does NOT propagate back to the publisher
(a bad notification handler must never break the tool call that
triggered it).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.logging_setup import logger

EventHandler = Callable[["Event"], None]


@dataclass
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)
        logger.debug("Subscribed handler '{}' to event '{}'", getattr(handler, "__name__", repr(handler)), event_name)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler in self._subscribers.get(event_name, []):
            self._subscribers[event_name].remove(handler)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(name=event_name, payload=payload or {})
        handlers = self._subscribers.get(event_name, [])
        logger.debug("Publishing event '{}' to {} subscriber(s)", event_name, len(handlers))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # A broken subscriber must never break the publisher or
                # other subscribers.
                logger.exception(
                    "Event handler '{}' raised while handling event '{}' (non-fatal, continuing)",
                    getattr(handler, "__name__", repr(handler)),
                    event_name,
                )
        return event


# Process-wide singleton — subsystems import this shared instance.
event_bus = EventBus()

__all__ = ["Event", "EventBus", "event_bus"]