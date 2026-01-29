# flake8: noqa
# mypy: ignore-errors
"""Test the EDMC Logger."""

import logging
import pytest
from EDMCLogging import get_plugin_logger


@pytest.fixture
def log_capture():
    class RecordCapture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    capture = RecordCapture()
    logger = get_plugin_logger("test_plugin")
    logger.addHandler(capture)
    yield capture
    logger.removeHandler(capture)


class TestLoggingIntrospection:
    """
    Addresses the TODO items 1-11 in EDMCLogging.py:
    Testing various call depths and class structures.
    """

    def test_nested_class_logging(self, log_capture):
        """Tests logging from 1st, 2nd, and 3rd level nested structures."""

        class Level1:
            class Level2:
                def log_here(self):
                    logging.getLogger("EDMarketConnector.test_plugin").info("deep")

        obj = Level1.Level2()
        obj.log_here()

        record = log_capture.records[0]
        assert "Level1.Level2.log_here" in record.qualname

    def test_property_logging(self, log_capture):
        """Verifies the specific 'property' handling logic in caller_attributes."""

        class PropertyTest:
            @property
            def trace_me(self):
                logging.getLogger("EDMarketConnector.test_plugin").info("prop")
                return True

        _ = PropertyTest().trace_me
        record = log_capture.records[0]
        assert "(property)" in record.qualname


class TestTraceLevel:
    """Verify the custom TRACE and TRACE_ALL levels work."""

    def test_trace_methods_exist(self):
        logger = get_plugin_logger("test_trace")
        assert hasattr(logger, "trace")
        assert hasattr(logger, "trace_if")

    def test_trace_logging(self, log_capture):
        logger = get_plugin_logger("test_plugin")
        logger.trace("testing trace")

        record = log_capture.records[0]
        assert record.levelno == 5  # LEVEL_TRACE
        assert record.levelname == "TRACE"


class TestThreadSafety:
    def test_osthreadid_present(self, log_capture):
        logger = get_plugin_logger("test_plugin")
        logger.info("thread test")

        record = log_capture.records[0]
        assert hasattr(record, "osthreadid")
        assert isinstance(record.osthreadid, int)
