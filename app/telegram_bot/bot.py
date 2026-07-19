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

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.core.config import settings
from app.core.logging_setup import logger
from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Agent MG is online. Try /ping to check connectivity."
    )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = call_tool("ping", {}, approval_handler=AutoApprovalHandler())
    await update.message.reply_text(f"pong! ({result.data['message']})")


def build_application() -> Application:
    autodiscover_tools()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(True)  # MANDATORY — see module docstring
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ping", ping_command))

    logger.info("Telegram bot application built. concurrent_updates=True.")
    return application


def run_bot() -> None:
    application = build_application()
    logger.info("Starting Telegram bot polling...")
    application.run_polling(drop_pending_updates=True)


__all__ = ["build_application", "run_bot"]