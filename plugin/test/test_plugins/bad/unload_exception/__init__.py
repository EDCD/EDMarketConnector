"""Plugin that generates an Exception on unload."""

import semantic_version

from plugin.decorators import edmc_plugin
from plugin.plugin import Plugin, PluginInfo


@edmc_plugin
class UnloadException(Plugin):
    """Throws an exception during unload."""

    def load(self) -> PluginInfo:
        """Load."""
        return PluginInfo('unload_exception', semantic_version.Version.coerce('0.0.1'))

    def unload(self) -> None:
        """Bang!."""
        raise ValueError('Bang!')
