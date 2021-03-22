"""Plugin that errors on __init__()."""

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(Plugin):
    """Test plugin."""

    def __init__(self, logger, manager, path) -> None:
        super().__init__(logger, manager, path)
        raise Exception('Exception in init')

    def load(self) -> PluginInfo:
        """Required."""
        return super().load()
