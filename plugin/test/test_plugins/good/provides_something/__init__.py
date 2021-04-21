"""Test plugin that loads correctly."""
import semantic_version

from plugin.decorators import edmc_plugin, provider
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodPlugin(Plugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        return PluginInfo(
            name="good_provider",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )

    @staticmethod
    @provider('something')
    def something() -> str:
        """Return something."""
        return "something"
