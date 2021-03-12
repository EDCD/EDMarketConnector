"""Test unloading of plugins."""
import logging
import pathlib

import pytest

from plugin.manager import PluginManager

from .conftest import bad_path, good_path

UNLOAD_TESTS = [
    (good_path / "simple", None),
    (bad_path / "unload_exception", "fire unload callback on unload_exception: Bang!"),
    (bad_path / "unload_shutdown", "attempted to stop the running interpreter! Catching!"),
]


@pytest.mark.parametrize(["path", "expected_log"], UNLOAD_TESTS)
def test_unload(plugin_manager: PluginManager, caplog: pytest.LogCaptureFixture, path: pathlib.Path, expected_log):
    """Test various plugin unload scenarios."""
    loaded = plugin_manager.load_plugin(path)
    assert loaded is not None, "Unexpected load failure"

    plugin_name = loaded.info.name

    with caplog.at_level(logging.INFO):
        plugin_manager.unload_plugin(plugin_name)

    assert not plugin_manager.is_plugin_loaded(plugin_name)

    if expected_log is None:
        return

    messages = caplog.text

    if isinstance(expected_log, str):
        assert expected_log in messages

    elif isinstance(expected_log, list):
        for expected in expected_log:
            assert expected in messages
