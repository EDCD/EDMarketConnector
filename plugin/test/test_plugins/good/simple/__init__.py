"""Test plugin that loads correctly."""
import pathlib

import semantic_version

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodPlugin(Plugin):
    """Plugin that loads correctly."""

    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """Nothing Special."""
        return PluginInfo(
            name="good",
            version=semantic_version.Version.coerce("0.0.1"),
            authors=["A_D"]
        )
