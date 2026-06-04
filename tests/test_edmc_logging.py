# flake8: noqa
# mypy: ignore-errors
"""Test the EDMC Logger."""

import pytest
from loguru import logger as loguru_logger
from EDMCLogging import get_plugin_logger


@pytest.fixture
def log_capture():
    """Captures processed Loguru records."""

    class LogRecordMock:
        def __init__(self, record_dict):
            self.message = record_dict["message"]
            self.levelno = record_dict["level"].no
            self.levelname = record_dict["level"].name
            self.qualname = record_dict["extra"].get("qualname", "")
            self.osthreadid = record_dict["extra"].get("osthreadid", None)

    class RecordCapture:
        def __init__(self):
            self.records = []

        def __call__(self, message):
            self.records.append(LogRecordMock(message.record))

    capture = RecordCapture()
    sink_id = loguru_logger.add(capture, format="{message}", level=0)
    yield capture
    loguru_logger.remove(sink_id)


class TestLoggingIntrospection:
    """Verifies that the InterceptHandler correctly preserves stack metadata."""

    def test_nested_class_logging(self, log_capture):
        """Tests that the InterceptHandler resolves nested class naming correctly."""
        plugin_logger = get_plugin_logger("test_plugin")

        class Level1:
            class Level2:
                def log_here(self):
                    plugin_logger.info("deep")

        Level1.Level2().log_here()

        assert len(log_capture.records) > 0
        assert log_capture.records[0].qualname == "log_here"

    def test_property_logging(self, log_capture):
        """Verifies that property-based logging records the property method name."""
        plugin_logger = get_plugin_logger("test_plugin")

        class PropertyTest:
            @property
            def trace_me(self):
                plugin_logger.info("prop")
                return True

        _ = PropertyTest().trace_me
        assert len(log_capture.records) > 0
        assert log_capture.records[0].qualname == "trace_me"


class TestTraceLevel:
    """Verify the custom TRACE and TRACE_ALL levels work."""

    def test_trace_methods_exist(self):
        logger = get_plugin_logger("test_trace")
        assert hasattr(logger, "trace")
        assert hasattr(logger, "trace_if")

    def test_trace_logging(self, log_capture):
        logger = get_plugin_logger("test_plugin")
        logger.trace("testing trace")

        assert len(log_capture.records) > 0
        record = log_capture.records[0]
        assert record.levelno == 5  # LEVEL_TRACE
        assert record.levelname == "TRACE"


class TestThreadSafety:
    def test_osthreadid_present(self, log_capture):
        logger = get_plugin_logger("test_plugin")
        logger.info("thread test")

        assert len(log_capture.records) > 0
        record = log_capture.records[0]
        assert record.osthreadid is not None
        assert isinstance(record.osthreadid, int)
