"""Plugin that generates an Exception on unload."""

import semantic_version

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class UnloadException(BasePlugin):
    """Throws an exception during unload."""

    def load(self) -> PluginInfo:
        """Load."""
        return PluginInfo('unload_exception', semantic_version.Version.coerce('0.0.1'))

    def unload(self) -> None:
        """Bang!."""
        raise ValueError('Bang!')
