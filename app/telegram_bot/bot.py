"""
Telegram Bot application.

CRITICAL LESSON FROM PRIOR BUILD: Application.builder().concurrent_updates(True)
is mandatory. Without it, a command handler that blocks waiting for human
approval (a separate incoming update — the button tap) creates a circular
wait: the approval tap can't be processed until the first handler finishes,
but the first handler is waiting for the approval tap. concurrent_updates(True)
allows multiple updates to be processed concurrently, breaking this deadlock.
"""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from app.core.config import settings
from app.core.logging_setup import logger
from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import ApprovalDeniedError
from app.telegram_bot.approval_handler import TelegramApprovalHandler


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Agent MG is online. Try /ping to check connectivity, or /testdelete to test the approval flow."
    )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = call_tool("ping", {}, approval_handler=AutoApprovalHandler())
    await update.message.reply_text(f"pong! ({result.data['message']})")


async def testdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Exercises the real approval flow end-to-end: delete_demo is a
    DELETE-permission tool, so TelegramApprovalHandler will send an
    inline-button prompt and block until the person taps YES/NO.

    call_tool() is SYNCHRONOUS and the approval wait blocks a real
    thread (threading.Event.wait) — so we run it via asyncio.to_thread
    to avoid blocking the bot's own event loop while waiting.
    """
    approval_handler: TelegramApprovalHandler = context.bot_data["approval_handler"]

    await update.message.reply_text("Requesting approval for a simulated delete action...")

    try:
        result = await asyncio.to_thread(
            call_tool,
            "delete_demo",
            {"target": "test_file.txt"},
            approval_handler=approval_handler,
        )
        await update.message.reply_text(f"Result: {result.data}")
    except ApprovalDeniedError:
        await update.message.reply_text("Action was denied. Nothing was deleted.")

async def _on_post_init(application: Application) -> None:
    """Runs once, inside the bot's own event loop, right after startup.
    This is the reliable place to capture the running loop — build_application()
    itself runs before the loop exists."""
    import asyncio
    approval_handler: TelegramApprovalHandler = application.bot_data["approval_handler"]
    approval_handler.set_loop(asyncio.get_running_loop())
    logger.info("TelegramApprovalHandler loop captured via post_init.")

    # Register Telegram as a real notification channel now that the
    # bot (and thus a valid chat_id target) is confirmed running.
    from app.notifications.manager import notification_manager
    from app.notifications.telegram_channel import TelegramChannel
    from app.notifications.event_subscriber import wire_notifications_to_event_bus

    notification_manager.register_channel(TelegramChannel())
    wire_notifications_to_event_bus()
    logger.info("TelegramChannel registered with NotificationManager; failure notifications now go to Telegram.")

def build_application() -> Application:
    autodiscover_tools()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(True)  # MANDATORY — see module docstring
        .post_init(_on_post_init)
        .build()
    )

    approval_handler = TelegramApprovalHandler(application)
    application.bot_data["approval_handler"] = approval_handler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("testdelete", testdelete_command))
    application.add_handler(CallbackQueryHandler(approval_handler.handle_callback, pattern=r"^approve:"))

    logger.info("Telegram bot application built. concurrent_updates=True.")
    return application


def run_bot() -> None:
    application = build_application()
    logger.info("Starting Telegram bot polling...")
    application.run_polling(drop_pending_updates=True)


__all__ = ["build_application", "run_bot"]