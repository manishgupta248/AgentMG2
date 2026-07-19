"""
TelegramChannel — real NotificationChannel implementation using the
bot to send messages to a configured chat_id. Satisfies the exact
same protocol as ConsoleChannel, so NotificationManager needs zero
changes to use it.

IMPORTANT (lesson from prior build): this uses a fresh, short-lived
Bot() call per send, NOT a second long-poll connection. Telegram
allows only ONE getUpdates() long-poll per bot token — that's the
bot application's job (M6 Step 3+). Sending a message via bot.send_message()
is a normal one-off API call and does NOT conflict with polling.
"""

from __future__ import annotations

import asyncio

from telegram import Bot

from app.core.config import settings
from app.core.logging_setup import logger


class TelegramChannel:
    name = "telegram"

    def __init__(self, chat_id: str | None = None):
        self.chat_id = chat_id or settings.telegram_chat_id
        self._bot = Bot(token=settings.telegram_bot_token)

    def send(self, message: str, *, title: str | None = None, metadata: dict | None = None) -> bool:
        try:
            text = f"*{title}*\n{message}" if title else message
            self._run_async(self._bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown"))
            return True
        except Exception:
            logger.exception("TelegramChannel failed to send notification.")
            return False

    @staticmethod
    def _run_async(coro):
        """
        Detects if an event loop is already running (e.g. we're being
        called from inside the bot's own async context) and dispatches
        appropriately — nested asyncio.run() raises RuntimeError, per
        the exact lesson from the prior build.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No loop running — safe to use asyncio.run() directly.
            return asyncio.run(coro)

        # A loop IS already running (e.g. called from within the bot's
        # own event loop) — must not call asyncio.run() here. Run the
        # coroutine in a separate thread with its own event loop instead.
        import concurrent.futures

        def _runner():
            return asyncio.run(coro)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_runner)
            return future.result()


__all__ = ["TelegramChannel"]