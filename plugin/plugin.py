"""Base plugin class."""
from __future__ import annotations

import abc
import inspect
import pathlib
from typing import TYPE_CHECKING, Callable, Dict, Optional

import semantic_version

from plugin.exceptions import LegacyPluginHasNoStart3, LegacyPluginNeedsMigrating

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
        self.can_reload = True  # Set to false to prevent reload support

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


LEGACY_CALLBACK_LUT: Dict[str, str] = {
    'core.setup_ui': 'plugin_app',
    'core.setup_preferences_ui': 'plugin_prefs',
    'core.preferences_closed': 'prefs_changed',
    'core.journal_entry': 'journal_entry',
    'core.dashboard_entry': 'dashboard_entry',
    'core.commander_data': 'cmdr_data',


    'inara.notify_ship': 'inara_notify_ship',
    'inara.notify_location': 'inara_notify_location',
    'edsm.notify_system': 'edsm_notify_system',
}


class MigratedPlugin(Plugin):
    """MigratedPlugin is a wrapper for old-style plugins."""

    def __init__(self, logger: LoggerMixin, module: ModuleType, manager: PluginManager) -> None:
        super().__init__(logger, manager)
        self.can_reload = False
        self.module = module
        # Find start3
        plugin_start3: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start3')
        plugin_start: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start')

        if plugin_start3 is None:
            if plugin_start is not None:
                raise LegacyPluginNeedsMigrating

            raise LegacyPluginHasNoStart3

        self.enforce_load3_signature(plugin_start3)
        self.start3 = plugin_start3

        # We have a start3, lets see what else we have and get ready to prepare hooks for them
        for new_hook, old_callback in LEGACY_CALLBACK_LUT.items():
            callback: Optional[Callable] = getattr(self.module, old_callback)
            if callback is None:
                continue

            target_name = f"_SYNTHETIC_CALLBACK_{old_callback}"
            setattr(self, target_name, decorators.hook(new_hook)(old_callback))
            self.log.trace(
                f"Successfully created fake callback wrapper {target_name} for old callback {old_callback} ({callback})"
            )

    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """
        Load the legacy plugin.

        Do our best to get any comment or version information that may exist in old-style variables and docstrings

        :param plugin_path: The path to this plugin
        :return: PluginInfo telling the world about us
        """
        name = self.start3(str(plugin_path))

        if (version_str := getattr(self.module, "__version__")) is not None:
            version = semantic_version.Version.coerce(version_str)

        else:
            version = semantic_version.Version.coerce('0.0.0+UNKNOWN')

        authors = getattr(self.module, '__author__')
        if authors is None:
            authors = getattr(self.module, "__credits__")

        if authors is not None and not isinstance(authors, list):
            authors = [authors]

        comment = getattr(self.module, "__doc__")

        return PluginInfo(name, version, authors=authors, comment=comment)

    @staticmethod
    def enforce_load3_signature(load3: Callable):
        """
        Ensure that plugin_load3 is the expected function.

        :param load3: The callable to check
        :raises ValueError: If the given callable is not actually a callable
        :raises ValueError: If the given callable accepts the wrong number of args
        """
        if not callable(load3):
            raise ValueError(f'load3 provided by plugin is not callable: {load3!r}')

        sig = inspect.signature(load3)
        if not len(sig.parameters) == 1:
            raise ValueError(
                'load3 provided by legacy plugin takes an unexpected arg count:'
                f'{len(sig.parameters)}; {sig.parameters}'
            )
