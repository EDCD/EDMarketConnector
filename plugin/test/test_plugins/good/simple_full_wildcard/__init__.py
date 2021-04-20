"""Test plugin."""
import semantic_version

from plugin import event
from plugin.decorators import edmc_plugin, hook
from plugin.plugin import Plugin
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodCallbackPlugin(Plugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        self.called: list[event.BaseEvent] = []
        return PluginInfo(
            name="good_callback_wildcard",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )

    @hook('*')
    def on_journal(self, e: event.JournalEvent):
        """Fake callback."""
        self.called.append(e)
