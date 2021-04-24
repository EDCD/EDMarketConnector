"""Plugin that generates a SystemExit on unload."""

import sys

import semantic_version

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class UnloadSystemExit(BasePlugin):
    """Throws an exception during unload."""

    def load(self) -> PluginInfo:
        """Load."""
        return PluginInfo("unload_exception", semantic_version.Version.coerce('0.0.1'))

    def unload(self) -> None:
        """Bang!."""
        sys.exit(1337)
