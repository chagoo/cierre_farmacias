"""Utility helpers for application logging configuration."""

from __future__ import annotations

import logging
from logging import Handler

from pythonjsonlogger import jsonlogger


def setup_logging(level: str) -> None:
    """Configure root logger to output JSON with the given level.

    Parameters
    ----------
    level:
        Logging level name, e.g. ``"INFO"`` or ``"DEBUG"``.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler: Handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter())

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [handler]
