"""Testing suite for plugin loading system."""
import pathlib
from contextlib import nullcontext
from typing import ContextManager

import pytest

from plugin.manager import (
    PluginAlreadyLoadedException, PluginDoesNotExistException, PluginHasNoPluginClassException, PluginLoadingException,
    PluginManager
)

from .conftest import bad_path, good_path


def _idfn(test_data) -> str:
    if isinstance(test_data, pathlib.Path):
        return test_data.parts[-1]

    return ""


TESTS = [
    (good_path / "simple", nullcontext()),
    (bad_path / "no_plugin", pytest.raises(PluginHasNoPluginClassException)),
    (bad_path / "error", pytest.raises(PluginLoadingException, match="This doesn't load")),
    (bad_path / "class_init_error", pytest.raises(PluginLoadingException, match="Exception in init")),
    (bad_path / "class_load_error", pytest.raises(PluginLoadingException, match="Exception in load")),
    (bad_path / "no_exist", pytest.raises(PluginDoesNotExistException)),
    (bad_path / "null_plugin_info", pytest.raises(PluginLoadingException, match="did not return a valid PluginInfo"))
]


@pytest.mark.parametrize('path,context', TESTS, ids=_idfn)
def test_load(plugin_manager: PluginManager, context: ContextManager, path: pathlib.Path) -> None:
    """
    Test that plugins load as expected.

    :param plugin_manager: a plugin.PluginManager instance to run tests against
    :param context: Context manager to run the test in, pytest.raises is used to assert that an exception is raised
    :param path: path to the plugin
    """
    with context:
        plugin_manager.load_plugin(path)


def test_double_load(plugin_manager: PluginManager) -> None:
    """Attempt to load a plugin twice."""
    plugin_manager.load_plugin(bad_path / "double_load")
    with pytest.raises(PluginAlreadyLoadedException):
        plugin_manager.load_plugin(bad_path / "double_load")


def test_unload_call(plugin_manager: PluginManager):
    """Load and unload a single plugin."""
    target = good_path / "simple"
    plug = plugin_manager.load_plugin(target)
    assert plugin_manager.is_plugin_loaded("good")
    assert plug is not None

    unload_called = False
    real_unload = plug.plugin.unload

    def mock_unload():
        nonlocal unload_called
        unload_called = True
        real_unload()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(plug.plugin, 'unload', mock_unload)  # patch the unload method
        plugin_manager.unload_plugin("good")

    assert not plugin_manager.is_plugin_loaded("good")
    assert unload_called
