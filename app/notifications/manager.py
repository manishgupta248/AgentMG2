"""
NotificationManager — dispatches notifications to one or more
registered NotificationChannel implementations. Also subscribes to
the Event Bus so tool activity can trigger notifications without
tools needing to know about the Notification Framework at all
(Section 4.6 event-driven decoupling in practice).
"""

from __future__ import annotations

from app.notifications.channel import NotificationChannel
from app.core.logging_setup import logger


class NotificationManager:
    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    def register_channel(self, channel: NotificationChannel) -> None:
        self._channels[channel.name] = channel
        logger.info("Notification channel registered: {}", channel.name)

    def unregister_channel(self, name: str) -> None:
        self._channels.pop(name, None)

    def notify(self, message: str, *, title: str | None = None, metadata: dict | None = None, channels: list[str] | None = None) -> dict[str, bool]:
        """
        Sends to all registered channels by default, or a specific
        subset via `channels`. Returns {channel_name: success_bool}.
        A failure in one channel does not stop others from being tried.
        """
        targets = channels or list(self._channels.keys())
        results: dict[str, bool] = {}

        for name in targets:
            channel = self._channels.get(name)
            if channel is None:
                logger.warning("notify() requested unknown channel '{}', skipping.", name)
                results[name] = False
                continue
            try:
                results[name] = channel.send(message, title=title, metadata=metadata)
            except Exception:
                logger.exception("Channel '{}' raised during send() (should not happen; channels must not raise).", name)
                results[name] = False

        return results


# Process-wide singleton
notification_manager = NotificationManager()

__all__ = ["NotificationManager", "notification_manager"]