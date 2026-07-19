"""
NotificationChannel protocol — the abstraction that lets email,
desktop notifications, WhatsApp, or Telegram all be added later
without touching calling code. Telegram (M6) will be one concrete
implementation of this protocol, not a hardcoded assumption.
"""

from __future__ import annotations

from typing import Protocol


class NotificationChannel(Protocol):
    name: str

    def send(self, message: str, *, title: str | None = None, metadata: dict | None = None) -> bool:
        """Send a notification. Returns True on success, False on failure.
        Must NOT raise — channel failures are the caller's concern to log,
        not to propagate as exceptions (a broken channel must never crash
        the thing that triggered the notification)."""
        ...


__all__ = ["NotificationChannel"]