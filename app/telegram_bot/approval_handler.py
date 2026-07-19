"""
TelegramApprovalHandler — implements the ApprovalHandler protocol
using inline YES/NO buttons over the bot's EXISTING getUpdates poll.

CRITICAL LESSONS FROM PRIOR BUILD, both addressed here:
1. Telegram allows only ONE getUpdates() long-poll connection per bot
   token. We do NOT open a second poll to wait for the button tap —
   the tap arrives through the bot's own existing poll, handled by a
   CallbackQueryHandler registered on the same Application.
2. A command handler blocking on approval must not deadlock the
   button-tap handler. This works ONLY because concurrent_updates(True)
   is set on the Application (M6 Step 3) — otherwise the button-tap
   update literally cannot be processed until the blocked handler
   returns, which is the exact deadlock from the prior build.

Mechanism: each pending approval gets a unique request_id and a
threading.Event. request_approval() is called from call_tool(), which
runs synchronously inside a worker thread (dispatched via
asyncio.to_thread by the command handler that invokes call_tool).
It registers the pending request, sends the inline-button message,
then blocks on event.wait(timeout=...). The CallbackQueryHandler
(async, runs on the bot's main event loop, NOT blocked) receives the
tap, stores the answer, and sets the event — unblocking the waiting
worker thread.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.types import PermissionLevel
from app.core.logging_setup import logger
from app.core.config import settings

APPROVAL_TIMEOUT_SECONDS = 120


@dataclass
class _PendingApproval:
    event: threading.Event
    answer: bool | None = None


class TelegramApprovalHandler:
    """
    One instance is shared across the bot application (registered as
    a bot_data attribute) so the CallbackQueryHandler and any command
    handler invoking call_tool() see the same pending-request table.
    """

    def __init__(self, application, chat_id: str | None = None):
        self._application = application
        self.chat_id = chat_id or settings.telegram_chat_id
        self._pending: dict[str, _PendingApproval] = {}
        self._lock = threading.Lock()
        self._loop = None  # set via set_loop() once the bot's event loop is running

    def set_loop(self, loop) -> None:
        self._loop = loop

    def request_approval(self, tool_name: str, permission: PermissionLevel, tool_kwargs: dict) -> bool:
        """
        Called synchronously from call_tool() — this method itself
        runs inside a worker thread (see command handler dispatch),
        NOT on the bot's async event loop, so blocking here is safe
        and does not freeze the bot.
        """
        request_id = uuid.uuid4().hex[:12]
        pending = _PendingApproval(event=threading.Event())

        with self._lock:
            self._pending[request_id] = pending

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ YES", callback_data=f"approve:{request_id}:yes"),
                InlineKeyboardButton("❌ NO", callback_data=f"approve:{request_id}:no"),
            ]
        ])
        text = (
            f"⚠️ Approval Required\n"
            f"Tool: {tool_name}\n"
            f"Permission: {permission.value}\n"
            f"Args: {tool_kwargs}\n\n"
            f"Approve?"
        )

        # Schedule the send onto the bot's own event loop from this
        # worker thread using run_coroutine_threadsafe — this is the
        # correct cross-thread-to-async-loop handoff, avoiding a
        # nested asyncio.run() call from inside a running loop.
        import asyncio
        if self._loop is None:
            raise RuntimeError("TelegramApprovalHandler.set_loop() was never called before request_approval().")

        future = asyncio.run_coroutine_threadsafe(
            self._application.bot.send_message(
                chat_id=self.chat_id, text=text, reply_markup=keyboard
            ),
            self._loop,
        )
        future.result(timeout=10)  # confirm the message actually sent before waiting

        logger.info("Approval requested. request_id={} tool={}", request_id, tool_name)

        approved = pending.event.wait(timeout=APPROVAL_TIMEOUT_SECONDS)

        with self._lock:
            self._pending.pop(request_id, None)

        if not approved:
            logger.warning("Approval request timed out. request_id={} tool={}", request_id, tool_name)
            return False  # timeout treated as denial

        logger.info("Approval resolved. request_id={} answer={}", request_id, pending.answer)
        return bool(pending.answer)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Registered as a CallbackQueryHandler on the bot's Application.
        Runs on the bot's own event loop — must NOT block."""
        query = update.callback_query
        await query.answer()  # ack the tap immediately, Telegram UI requirement

        try:
            _, request_id, answer_str = query.data.split(":")
        except ValueError:
            logger.warning("Malformed callback data: {}", query.data)
            return

        with self._lock:
            pending = self._pending.get(request_id)

        if pending is None:
            await query.edit_message_text("This approval request has expired or was already handled.")
            return

        pending.answer = (answer_str == "yes")
        pending.event.set()

        result_text = "✅ Approved" if pending.answer else "❌ Denied"
        await query.edit_message_text(f"{query.message.text}\n\n{result_text}")


__all__ = ["TelegramApprovalHandler", "APPROVAL_TIMEOUT_SECONDS"]