# flake8: noqa
# mypy: ignore-errors
"""Test that logging works correctly from a class-definition caller."""

import sys
import inspect

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


def test_class_logger(caplog: "LogCaptureFixture") -> None:
    """
    Test that logging from a class variable doesn't explode.

    In writting a plugin that uses a class variable to hold the logger, EDMCLoggings cleverness to extract data
    regarding the qualified name of a function falls flat, as a class variable does not have a qualname, and at the time
    we did not check for its existence before using it.
    """
    ClassVarLogger.set_logger(logger)

    # Get current line number dynamically
    current_line = inspect.currentframe().f_lineno + 1
    ClassVarLogger.logger.debug("test")

    assert f"test_logging_classvar.py:{current_line} test" in caplog.text
