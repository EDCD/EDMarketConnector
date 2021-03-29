"""Test plugin."""
from plugin import event
import semantic_version

from plugin.decorators import edmc_plugin, hook
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodCallbackPlugin(Plugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        return PluginInfo(
            name="good_callback",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )

    @hook('core.journal_event')
    def on_journal(self, e: event.BaseEvent):
        """Fake callback."""
        ...
