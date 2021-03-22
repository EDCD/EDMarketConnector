"""Plugin that errors on __init__()."""

import pathlib
from plugin.plugin_info import PluginInfo
from plugin.plugin import Plugin
from plugin.decorators import edmc_plugin


@edmc_plugin
class Broken(Plugin):
    def __init__(self, logger, manager, path) -> None:
        super().__init__(logger, manager, path)
        raise Exception("Exception in init")

    def load(self) -> PluginInfo:
        return super().load()
