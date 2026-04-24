"""Shared logging setup. Uses `rich` for pretty console output."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

from .config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
