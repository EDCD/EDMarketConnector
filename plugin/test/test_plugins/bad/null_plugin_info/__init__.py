"""Test Plugin."""
from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin, PluginInfo


@edmc_plugin
class BadPlugInfo(Plugin):
    """Plugin that returns a bad PluginInfo object."""

    def load(self) -> PluginInfo:
        """Intentionally broken load()."""
        return None  # type: ignore # Its intentional
