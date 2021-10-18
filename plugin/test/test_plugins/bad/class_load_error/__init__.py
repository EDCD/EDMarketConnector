"""Plugin that errors on load()."""

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(BasePlugin):
    """Test Plugin."""

    def load(self) -> PluginInfo:
        """Plugin startup."""
        raise Exception('Exception in load')
