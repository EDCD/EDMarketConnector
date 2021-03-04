"""Testing suite for plugin loading system."""
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from plugin.manager import PluginManager  # noqa: E402 # Cant be at the top


class TestPluginLoad:
    """Test plugin loading."""

    def test_good_load(self) -> None:
        """Test that loading a known good plugin works."""
        manager = PluginManager()
        res = manager.load_plugin(pathlib.Path("./plugin/test/test_plugins/good").absolute())

        assert res, "Good plugin did not load correctly"
