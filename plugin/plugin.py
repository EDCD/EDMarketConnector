"""Base plugin class."""
from __future__ import annotations

import abc
import inspect
import pathlib
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from plugin.exceptions import LegacyPluginNeedsMigrating

if TYPE_CHECKING:
    from EDMCLogging import LoggerMixin
    from types import ModuleType
    from plugin.manager import PluginManager

from plugin import decorators
from plugin.plugin_info import PluginInfo


class Plugin(abc.ABC):
    """Base plugin class."""

    # TODO: a similar level of paranoia about defined methods where needed

    def __init__(self, logger: LoggerMixin, manager: PluginManager) -> None:
        self.log = logger
        self._manager = manager

    @abc.abstractmethod
    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """
        Load this plugin.

        :param plugin_path: the path at which this module was found.
        """
        raise NotImplementedError

    def unload(self) -> None:
        """Unload this plugin."""
        ...

    def show_error(self):
        # TODO: replacement of plug.show_error
        ...


class MigratedPlugin(Plugin):
    """MigratedPlugin is a wrapper for old-style plugins."""

    OLD_CALLBACKS_AND_BEHAVIOUR = (
        ('plugin_app', lambda x: decorators.hook("core.plugin_ui_setup")(x)),
        ('plugin_prefs', lambda x: decorators.hook('core.plugin_preferences_setup')(x))
    )

    def __init__(self, logger: LoggerMixin, module: ModuleType, manager: PluginManager) -> None:
        super().__init__(logger, manager)
        self.module = module
        # TODO: fill this dict and then generate hooks for everything that needs it
        self.callbacks: Dict[str, List[Callable]] = {
            'core.setup_ui': [],
            'core.setup_preferences_ui': [],
            'core.preferences_changed': [],
            'core.journal_entry': [],
            'core.dashboard_entry': [],
            'core.commander_data': [],


            'inara.notify_ship': [],
            'inara.notify_location': [],
            'edsm.notify_system': [],
        }

    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        plugin_start3: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start3')
        plugin_start: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start')

        if plugin_start3 is None:
            if plugin_start is not None:
                raise LegacyPluginNeedsMigrating

            raise ValueError('Plugin does not define a plugin_start3 method')

        self.enforce_load3_signature(plugin_start3)

        # We have a start3, lets see what else we have and get ready to prepare hooks for them

        return super().load(plugin_path)

    @staticmethod
    def enforce_load3_signature(load3: Callable):
        if not callable(load3):
            raise ValueError(f'Plugin3 provided by plugin is not callable: {load3!r}')

        sig = inspect.signature(load3)
        if not len(sig.parameters) == 1:
            raise ValueError(f'Plugin3 provided by legacy plugin takes an unexpected arg count: {len(sig.parameters)}')

    ...
