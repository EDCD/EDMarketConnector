"""Setup constants and fixtures for plugin tests."""
import pathlib
import typing

from pytest import fixture

from plugin.manager import PluginManager


@fixture
def plugin_manager() -> typing.Generator[PluginManager, None, None]:
    """Provide a PluginManager as a fixture."""
    yield PluginManager()


current_path = pathlib.Path.cwd() / 'plugin/test/test_plugins'
good_path = current_path / 'good'
bad_path = current_path / 'bad'
legacy_path = current_path / 'legacy'
legacy_good_path = legacy_path / 'good'
legacy_bad_path = legacy_path / 'bad'
