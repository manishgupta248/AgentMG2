"""
Console notification channel — prints to stdout. Used for local dev
and as the first concrete proof of the NotificationChannel protocol.
"""

from app.core.logging_setup import logger


class ConsoleChannel:
    name = "console"

    def send(self, message: str, *, title: str | None = None, metadata: dict | None = None) -> bool:
        try:
            header = f"[{title}] " if title else ""
            print(f"\n🔔 NOTIFICATION {header}{message}")
            if metadata:
                print(f"   metadata: {metadata}")
            return True
        except Exception:
            logger.exception("ConsoleChannel failed to send notification.")
            return False


__all__ = ["ConsoleChannel"]