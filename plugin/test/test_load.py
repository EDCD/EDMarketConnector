"""Testing suite for plugin loading system."""
import pathlib
import sys
from contextlib import nullcontext
from typing import ContextManager

import pytest

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from plugin.manager import (  # noqa: E402 # Cant be at the top
    PluginAlreadyLoadedException, PluginDoesNotExistException, PluginHasNoPluginClassException, PluginLoadingException,
    PluginManager
)


def _idfn(test_data) -> str:
    if isinstance(test_data, pathlib.Path):
        return test_data.parts[-1]

    return ""


current_path = pathlib.Path.cwd() / "plugin/test/test_plugins"
good_path = current_path / "good"
bad_path = current_path / "bad"

TESTS = [
    (good_path / "simple", nullcontext()),
    (bad_path / "no_plugin", pytest.raises(PluginHasNoPluginClassException)),
    (bad_path / "error", pytest.raises(PluginLoadingException, match="This doesn't load")),
    (bad_path / "class_init_error", pytest.raises(PluginLoadingException, match="Exception in init")),
    (bad_path / "class_load_error", pytest.raises(PluginLoadingException, match="Exception in load")),
    (bad_path / "no_exist", pytest.raises(PluginDoesNotExistException)),
    (bad_path / "null_plugin_info", pytest.raises(PluginLoadingException, match="did not return a valid PluginInfo"))
]


@pytest.fixture
def plugin_manager():
    """Provide a PluginManager as a fixture."""
    yield PluginManager()


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
