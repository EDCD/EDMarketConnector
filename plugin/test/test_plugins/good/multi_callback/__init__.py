"""Test plugin that loads correctly."""
import semantic_version

from plugin.base_plugin import BasePlugin
from plugin.decorators import edmc_plugin, hook
from plugin.event import BaseEvent
from plugin.plugin_info import PluginInfo


@edmc_plugin
class GoodPlugin(BasePlugin):
    """Plugin that loads correctly."""

    def load(self) -> PluginInfo:
        """Nothing Special."""
        self.called: list[BaseEvent] = []

        return PluginInfo(
            name="good",
            version=semantic_version.Version.coerce('0.0.1'),
            authors=['A_D']
        )

    @hook('core.journal_event')
    @hook('uncore.not_journal_event')
    def multiple_things(self, e: BaseEvent):
        """Multiple hooks on one method."""
        self.called.append(e)

    print(id(multiple_things))
