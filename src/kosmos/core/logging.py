"""Explicit logging configuration for Kosmos."""

import logging
from typing import TextIO

from kosmos.core.config import VALID_LOG_LEVELS
from kosmos.core.exceptions import ConfigurationError

LOGGER_NAME = "kosmos"
LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_HANDLER_MARKER = "_kosmos_console_handler"


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> logging.Logger:
    """Configure and return the Kosmos logger without changing the root logger."""

    normalized_level = _normalize_level(level)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(normalized_level)
    logger.propagate = False

    console_handler = next(
        (candidate for candidate in logger.handlers if getattr(candidate, _HANDLER_MARKER, False)),
        None,
    )

    if console_handler is None:
        console_handler = logging.StreamHandler(stream)
        setattr(console_handler, _HANDLER_MARKER, True)
        logger.addHandler(console_handler)
    elif stream is not None and isinstance(console_handler, logging.StreamHandler):
        console_handler.setStream(stream)

    console_handler.setLevel(normalized_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    return logger


def _normalize_level(level: object) -> str:
    if not isinstance(level, str):
        raise ConfigurationError("log level must be a string")

    normalized = level.strip().upper()

    if normalized not in VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ConfigurationError(f"log level must be one of: {allowed}")

    return normalized
