"""Behavioral tests for explicit Kosmos logging configuration."""

import importlib
import io
import logging
import re

import pytest

import kosmos.core.logging as kosmos_logging


@pytest.fixture(autouse=True)
def restore_kosmos_logger() -> None:
    logger = logging.getLogger(kosmos_logging.LOGGER_NAME)
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    yield
    logger.handlers = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ],
)
def test_configures_supported_levels(configured: str, expected: int) -> None:
    logger = kosmos_logging.configure_logging(configured, io.StringIO())

    assert logger.level == expected
    assert logger.handlers[-1].level == expected


def test_formats_timestamp_logger_level_and_message() -> None:
    stream = io.StringIO()
    logger = kosmos_logging.configure_logging("INFO", stream)

    logger.info("service ready")

    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4} kosmos INFO service ready\n",
        stream.getvalue(),
    )


def test_repeated_configuration_does_not_duplicate_handlers() -> None:
    logger = kosmos_logging.configure_logging("INFO", io.StringIO())
    count_after_first_call = len(logger.handlers)

    configured_again = kosmos_logging.configure_logging("DEBUG", io.StringIO())

    assert configured_again is logger
    assert len(logger.handlers) == count_after_first_call


def test_preserves_external_handlers_and_root_configuration() -> None:
    logger = logging.getLogger(kosmos_logging.LOGGER_NAME)
    external_handler = logging.NullHandler()
    logger.addHandler(external_handler)
    root = logging.getLogger()
    root_handlers = root.handlers[:]
    root_level = root.level

    kosmos_logging.configure_logging("INFO", io.StringIO())

    assert external_handler in logger.handlers
    assert root.handlers == root_handlers
    assert root.level == root_level


def test_import_has_no_logging_side_effects() -> None:
    logger = logging.getLogger(kosmos_logging.LOGGER_NAME)
    logger.handlers.clear()
    root = logging.getLogger()
    root_handlers = root.handlers[:]
    root_level = root.level

    importlib.reload(kosmos_logging)

    assert logger.handlers == []
    assert root.handlers == root_handlers
    assert root.level == root_level
