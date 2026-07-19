"""
Loguru-based logging setup.
Rotating file sink with EXPLICIT UTF-8 encoding — a prior build issue
was PowerShell Get-Content mis-rendering log files without this.
"""

import sys
from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """Configure Loguru sinks. Safe to call once at startup."""
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()  # remove default stderr sink to control format explicitly

    # Console sink (human-readable, colored)
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Rotating file sink — UTF-8 explicit
    logger.add(
        settings.logs_dir / "agent.log",
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        encoding="utf-8",
        enqueue=True,  # thread-safe writes, needed once Telegram/async threads exist
        backtrace=True,
        diagnose=True,
    )

    logger.info("Logging initialized. Level={}", settings.log_level)


__all__ = ["logger", "setup_logging"]