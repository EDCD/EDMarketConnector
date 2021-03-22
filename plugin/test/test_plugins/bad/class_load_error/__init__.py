"""Plugin that errors on load()."""

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(Plugin):
    """Test Plugin."""

    def load(self) -> PluginInfo:
        """Plugin startup."""
        raise Exception('Exception in load')
