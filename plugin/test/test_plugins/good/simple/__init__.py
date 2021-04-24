"""Test plugin that loads correctly."""
import semantic_version

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodPlugin(BasePlugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        return PluginInfo(
            name="good",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )
