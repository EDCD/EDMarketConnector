"""Plugin that errors on load()."""

import pathlib

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class Broken(Plugin):
    def load(self) -> PluginInfo:
        raise Exception("Exception in load")
