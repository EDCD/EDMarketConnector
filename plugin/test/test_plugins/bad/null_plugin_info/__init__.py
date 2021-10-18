"""Test Plugin."""
from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class BadPlugInfo(BasePlugin):
    """Plugin that returns a bad PluginInfo object."""

    def load(self) -> PluginInfo:
        """Intentionally broken load()."""
        return None  # type: ignore # Its intentional
