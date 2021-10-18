"""Test Plugin."""
import semantic_version

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(BasePlugin):
    """Valid (but not loadable twice) plugin."""

    def load(self) -> PluginInfo:
        """Load."""
        return PluginInfo('double_load', semantic_version.Version.coerce('0.0.1'))
