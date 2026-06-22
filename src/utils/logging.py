from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger as _logger

from src.utils.paths import LOGS_DIR, ensure_dir

_CONFIGURED = False


def _configure(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    ensure_dir(LOGS_DIR)
    _logger.remove()
    _logger.add(
        sys.stderr,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
    )
    _logger.add(
        Path(LOGS_DIR) / "app.log",
        level=level,
        rotation="10 MB",
        retention="14 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
    )
    _CONFIGURED = True


def get_logger(name: str | None = None, level: str = "INFO"):
    _configure(level=level)
    if name is None:
        return _logger
    return _logger.bind(name=name)
