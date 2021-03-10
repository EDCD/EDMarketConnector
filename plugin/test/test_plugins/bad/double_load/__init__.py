import pathlib

import semantic_version

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(Plugin):
    """Valid (but not loadable twice) plugin."""

    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """Load."""
        return PluginInfo("double_load", semantic_version.Version.coerce("0.0.1"))
