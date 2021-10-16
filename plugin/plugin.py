"""
EDMC specific plugin implementations.

See base_plugin.py for base plugin implementation.

base_plugin.py and plugin.py are distinct to allow for simpler testing -- this
file imports many different chunks of EDMC that are not needed for testing of the plugin system itself.
"""
from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any, Optional, final

import config
import constants
import killswitch
import l10n
import monitor  # TODO: This SHOULD be fine, at the time we're loaded
from plugin.base_plugin import BasePlugin
from theme import _Theme, theme

if TYPE_CHECKING:
    import semantic_version

    from EDMCLogging import LoggerMixin
    from plugin.manager import PluginManager

# the import of things like monitor is intentionally *NOT* using a `from` import
# this is because internally, we might modify or replace monitor at some point.
# and if a from import was used here, the resolution would break.
# additionally, due to the way we work with plugins and hooks, the value should
# always be correct, assuming you're *not* accessing them from a thread. If you
# ARE accessing them from a thread, the GIL promises that they wont be modified
# at the same time you work with them (from a internal-to-python data race
# perspective.) However, it *may* still change during your processing.
# Caveat Emptor. If you want to be sure its safe, store a copy of the result


class EDMCPlugin(BasePlugin):
    """Elite Dangerous Market Connector plugin base."""

    def __init__(self, logger: LoggerMixin, manager: PluginManager, path: pathlib.Path) -> None:
        super().__init__(logger, manager, path)

        self.killswitch: killswitch.KillSwitchSet = killswitch.active  # Not final so plugins can set their own

    @final
    def translate(self, s: str, context: Optional[str] = None) -> str:
        """
        Translate the given string.

        :param s: String to translate
        :param context: Context to find the translation files, defaults to the plugins directory
        :return: The translated string
        """
        if context is None:
            context = str(self.path)

        return l10n.Translations.translate(s, context=context)

    @final
    def show_status_msg(self, msg: str) -> None:
        """
        Show a message on the main UI status bar.

        This relies on crossing a few times. It may not be instant. But it will not block plugin code.

        :param msg: The message to show
        """
        self._manager.status_msg_queue.put(msg)

    # Properties for accessing various bits of EDMC data

    @property
    @final
    def theme(self) -> _Theme:
        """Theming for plugin widgets."""
        return theme

    @property
    @final
    def edmc_name(self) -> str:
        """EDMC appname."""
        return constants.appname

    @property
    @final
    def edmc_long_name(self) -> str:
        """EDMC applongname."""
        return constants.applongname

    @property
    @final
    def edmc_cmd_name(self) -> str:
        """EDMC cmdname."""
        return config.appcmdname

    @final
    def edmc_version(self, no_build=False) -> semantic_version.Version:
        """Return the current EDMC Version."""
        if no_build:
            return config.appversion_nobuild()
        return config.appversion()

    @property
    @final
    def edmc_copyright(self) -> str:
        """Return the current EDMC Copyright statement."""
        return config.copyright

    @property
    @final
    def is_beta(self) -> bool:
        """Return whether or not the running ED instance is a prerelease."""
        return monitor.monitor.is_beta

    @property
    @final
    def commander(self) -> str | None:
        """Return the current commander, if any."""
        return monitor.monitor.cmdr

    @property
    @final
    def system(self) -> str | None:
        """Return the current system, if any."""
        return monitor.monitor.system

    @property
    @final
    def system_address(self) -> int | None:
        """Return the current system address, if any."""
        return monitor.monitor.systemaddress

    @property
    @final
    def system_population(self) -> int | None:
        """Return the current system population, if known."""
        return monitor.monitor.systempopulation

    @property
    @final
    def station(self) -> str | None:
        """Return the current station, if any."""
        return monitor.monitor.station

    @property
    @final
    def station_marketid(self) -> int | None:
        """Return the current marketid for the current station, if any."""
        return monitor.monitor.station_marketid

    @property
    @final
    def state(self) -> dict[str, Any]:
        """Return the currently tracked state, if any."""
        return monitor.monitor.state
