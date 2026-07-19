"""
Standalone entrypoint for running the Telegram bot.
Run this in its own terminal window — it blocks forever polling.
Press Ctrl+C to stop.
"""

from app.core.logging_setup import setup_logging
from app.telegram_bot.bot import run_bot


def main() -> None:
    setup_logging()
    run_bot()


if __name__ == "__main__":
    main()