"""Testing suite for plugin loading system."""
import pathlib
from contextlib import nullcontext
from plugin.plugin import LEGACY_CALLBACK_LUT
from typing import Any, ContextManager, List, Tuple

import pytest

from plugin.manager import (
    PluginAlreadyLoadedException, PluginDoesNotExistException, PluginHasNoPluginClassException, PluginLoadingException,
    PluginManager
)

from plugin.decorators import CALLBACK_MARKER

from .conftest import bad_path, good_path, legacy_bad_path, legacy_good_path, legacy_path


def _idfn(test_data) -> str:
    if not isinstance(test_data, pathlib.Path):
        return ""

    if legacy_path in test_data.parents:
        return f'Legacy_{test_data.parts[-1]}'

    return test_data.parts[-1]


LEGACY_TESTS: List[Tuple[pathlib.Path, Any]] = [
    (legacy_good_path / 'simple', nullcontext()),
    (legacy_good_path / 'all_callbacks', nullcontext()),
    (legacy_bad_path / "load_error", pytest.raises(PluginLoadingException, match=r'Exception in load method.*BANG!$')),
    (
        legacy_bad_path / 'import_error',
        pytest.raises(
            PluginLoadingException,
            match="No module named 'ThisDoesNotExistEDMCLibNeedsMoreTextToEnsureUnique'"
        )
    ),
]

TESTS = [
    (good_path / 'simple', nullcontext()),
    (bad_path / 'no_plugin', pytest.raises(PluginHasNoPluginClassException)),
    (bad_path / 'error', pytest.raises(PluginLoadingException, match="This doesn't load")),
    (bad_path / 'class_init_error', pytest.raises(PluginLoadingException, match='Exception in init')),
    (bad_path / 'class_load_error', pytest.raises(PluginLoadingException, match='Exception in load')),
    (bad_path / 'no_exist', pytest.raises(PluginDoesNotExistException)),
    (bad_path / 'null_plugin_info', pytest.raises(PluginLoadingException, match='did not return a valid PluginInfo')),
    (
        bad_path / 'str_plugin_info',
        pytest.raises(
            PluginLoadingException, match='returned an invalid type for its PluginInfo'
        )
    ),

    # Legacy plugins

] + LEGACY_TESTS


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


def test_legacy_load(plugin_manager: PluginManager):
    """Test that legacy loading system correctly loads a plugin, and creates synthetic hooks for it."""
    target = legacy_good_path / 'all_callbacks'
    loaded = plugin_manager.load_plugin(target)
    assert loaded is not None

    target_name = '_SYNTHETIC_CALLBACK_journal_entry'

    # does the callback exist
    assert hasattr(loaded.plugin, target_name)
    # does the callback have the same function as the module, _explicitly_ an identity check over an equality check
    # as a function equality is shaky at best
    assert getattr(loaded.plugin, target_name) is getattr(loaded.module, 'journal_entry')
    # has the callback been decorated with hook()?
    assert hasattr(getattr(loaded.plugin, target_name), CALLBACK_MARKER)
    # have all of the functions created automatically as part of callbacks been found by the callback search code?
    assert len(loaded.callbacks) == len(LEGACY_CALLBACK_LUT)


def test_double_load(plugin_manager: PluginManager) -> None:
    """Attempt to load a plugin twice."""
    plugin_manager.load_plugin(bad_path / 'double_load')
    with pytest.raises(PluginAlreadyLoadedException):
        plugin_manager.load_plugin(bad_path / 'double_load')


def test_unload_call(plugin_manager: PluginManager):
    """Load and unload a single plugin."""
    target = good_path / "simple"
    plug = plugin_manager.load_plugin(target)
    assert plugin_manager.is_plugin_loaded('good')
    assert plug is not None

    unload_called = False
    real_unload = plug.plugin.unload

    def mock_unload():
        nonlocal unload_called
        unload_called = True
        real_unload()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(plug.plugin, 'unload', mock_unload)  # patch the unload method
        plugin_manager.unload_plugin('good')

    assert not plugin_manager.is_plugin_loaded('good')
    assert unload_called
