"""Test plugin."""
import semantic_version

from plugin import event
from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin, hook
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodCallbackPlugin(BasePlugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        self.called: list[event.BaseEvent] = []
        return PluginInfo(
            name="good_callback",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )

    @hook('core.journal_event')
    def on_journal(self, e: event.JournalEvent):
        """Fake callback."""
        self.called.append(e)
