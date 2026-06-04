# flake8: noqa
# mypy: ignore-errors
"""Test that logging works correctly from various calling contexts."""

import sys
import inspect
from pathlib import Path
from loguru import logger as loguru_logger

sys.path += "../"  # Don't ask me why for this one it breaks, it just does.
from typing import TYPE_CHECKING  # noqa: E402

from EDMCLogging import get_plugin_logger  # noqa: E402

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

logger = get_plugin_logger("EDMCLogging.py")


class ClassVarLogger:
    """Test class with logger attached."""

    @classmethod
    def set_logger(cls, logger) -> None:
        """Set the passed logger onto the _class_."""
        ClassVarLogger.logger = logger  # type: ignore


def log_stuff(msg: str) -> None:
    """Wrap logging in another function."""
    ClassVarLogger.logger.debug(msg)  # type: ignore # its there


def test_class_logger() -> None:
    """
    Test that logging from a class variable doesn't explode.

    Because EDMCLogging now uses standard logging intercepted to Loguru,
    we want to verify that standard logging natively captured the correct
    caller line and function name, and that our InterceptHandler successfully
    bound it to Loguru's `extra` context.
    """
    ClassVarLogger.set_logger(logger)
    captured_records = []

    sink_id = loguru_logger.add(
        lambda msg: captured_records.append(msg.record),
        format="{message}"
    )

    try:
        current_line = inspect.currentframe().f_lineno + 1
        ClassVarLogger.logger.debug("test class variable logging")

        assert len(captured_records) > 0, "Loguru failed to capture the intercepted log."
        log_record = captured_records[0]

        assert log_record["message"] == "test class variable logging"
        assert log_record["extra"]["custom_lineno"] == current_line
        assert log_record["extra"]["qualname"] == "test_class_logger"

    finally:
        loguru_logger.remove(sink_id)


def test_function_wrapper_logger() -> None:
    """Test that logging wrapped inside another function correctly tracks the wrapper."""
    ClassVarLogger.set_logger(logger)
    captured_records = []

    sink_id = loguru_logger.add(
        lambda msg: captured_records.append(msg.record),
        format="{message}"
    )

    try:
        log_stuff("test function wrapper")

        assert len(captured_records) > 0
        log_record = captured_records[0]

        assert log_record["message"] == "test function wrapper"
        assert log_record["extra"]["qualname"] == "log_stuff"

    finally:
        loguru_logger.remove(sink_id)


def test_legacy_trace_monkeypatch() -> None:
    """Test that the legacy plugin .trace() command translates to Loguru."""
    ClassVarLogger.set_logger(logger)
    captured_records = []

    sink_id = loguru_logger.add(
        lambda msg: captured_records.append(msg.record),
        level="TRACE_ALL",
        format="{message}"
    )

    try:
        ClassVarLogger.logger.trace("test trace level propagation")

        assert len(captured_records) > 0
        log_record = captured_records[0]
        assert log_record["message"] == "test trace level propagation"
        assert log_record["level"].name == "TRACE"

    finally:
        loguru_logger.remove(sink_id)
