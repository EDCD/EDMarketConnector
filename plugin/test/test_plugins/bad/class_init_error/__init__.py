"""Plugin that errors on __init__()."""

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(BasePlugin):
    """Test plugin."""

    def __init__(self, logger, manager, path) -> None:
        super().__init__(logger, manager, path)
        raise Exception('Exception in init')

    def load(self) -> PluginInfo:
        """Implement method required by ABC."""
        return super().load()
