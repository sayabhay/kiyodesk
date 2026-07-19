"""Structured application logging configuration."""

import sys

from loguru import logger


def configure_logging(log_level: str) -> None:
    """Configure Loguru once for console-friendly structured output."""

    logger.remove()
    logger.add(
        sys.stderr, level=log_level.upper(), serialize=False, backtrace=False, diagnose=False
    )
