"""Setup constants and fixtures for plugin tests."""
import pathlib
import sys
import typing

from pytest import fixture

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from plugin.manager import PluginManager  # noqa: E402 # Has to be after the path fiddling


@fixture
def plugin_manager() -> typing.Generator[PluginManager, None, None]:
    """Provide a PluginManager as a fixture."""
    yield PluginManager()


current_path = pathlib.Path.cwd() / "plugin/test/test_plugins"
good_path = current_path / "good"
bad_path = current_path / "bad"
