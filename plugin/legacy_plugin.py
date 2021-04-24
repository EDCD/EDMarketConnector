"""Loading machinery for legacy EDMC plugins."""

from __future__ import annotations

import inspect
import pathlib
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

import semantic_version

from plugin import decorators, event
from plugin.base_plugin import BasePlugin
from plugin.exceptions import LegacyPluginHasNoStart3, LegacyPluginNeedsMigrating
from plugin.plugin_info import PluginInfo

if TYPE_CHECKING:
    from EDMCLogging import LoggerMixin
    from plugin.manager import PluginManager

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


LEGACY_CALLBACK_BREAKOUT_LUT: Dict[str, Callable[..., Tuple[Any, ...]]] = {
    # All of these callables should accept an event.BaseEvent or a subclass thereof
    # 'core.setup_ui': 'plugin_app',
    # 'core.setup_preferences_ui': 'plugin_prefs',
    # 'core.preferences_closed': 'prefs_changed',
    'core.journal_entry': lambda e: (e.commander, e.is_beta, e.system, e.station, e.data, e.state),
    # 'core.dashboard_entry': 'dashboard_entry',
    # 'core.commander_data': 'cmdr_data',

    # 'inara.notify_ship': 'inara_notify_ship',
    # 'inara.notify_location': 'inara_notify_location',
    # 'edsm.notify_system': 'edsm_notify_system',
}


class MigratedPlugin(BasePlugin):
    """MigratedPlugin is a wrapper for old-style plugins."""

    OSTR = Optional[str]
    JOURNAL_EVENT_SIG = Callable[[str, bool, OSTR, OSTR, Dict[str, Any], Dict[str, Any]], None]

    def __init__(self, logger: LoggerMixin, module: ModuleType, manager: PluginManager, path: pathlib.Path) -> None:
        super().__init__(logger, manager, path)
        self.can_reload = False
        self.module = module
        # Find start3
        plugin_start3: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start3', None)
        plugin_start: Optional[Callable[[str], str]] = getattr(self.module, 'plugin_start', None)

        if plugin_start3 is None:
            if plugin_start is not None:
                raise LegacyPluginNeedsMigrating

            raise LegacyPluginHasNoStart3

        self.enforce_load3_signature(plugin_start3)
        self.start3 = plugin_start3

        # We have a start3, lets see what else we have and get ready to prepare hooks for them
        self.setup_callbacks()

    def setup_callbacks(self) -> None:
        """
        Set up shimmed callbacks for any event the legacy plugin may have.

        See ARCHITECHTURE.md for more explanation.
        """
        for new_hook, old_callback in LEGACY_CALLBACK_LUT.items():
            callback: Optional[Callable] = getattr(self.module, old_callback, None)
            if callback is None:
                continue

            target_name = f"_SYNTHETIC_CALLBACK_{old_callback}"
            breakout = LEGACY_CALLBACK_BREAKOUT_LUT.get(new_hook, lambda e: ())

            wrapped = self.generic_callback_handler(callback, breakout)
            setattr(self, target_name, decorators.hook(new_hook)(wrapped))

    def load(self) -> PluginInfo:
        """
        Load the legacy plugin.

        Do our best to get any comment or version information that may exist in old-style variables and docstrings

        :param plugin_path: The path to this plugin
        :return: PluginInfo telling the world about us
        """
        name = self.start3(str(self.path))

        if (version_str := getattr(self.module, "__version__", None)) is not None:
            version = semantic_version.Version(version_str)

        else:
            version = semantic_version.Version('0.0.0+UNKNOWN')

        authors = getattr(self.module, '__author__', None)
        if authors is None:
            authors = getattr(self.module, "__credits__", None)

        if authors is not None and not isinstance(authors, list):
            authors = [authors]

        comment = getattr(self.module, "__doc__", None)

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

    @staticmethod
    def generic_callback_handler(f: Callable, breakout: Callable[..., Tuple[Any, ...]]):
        """
        Wrap the given callback with the given event breakout.

        It is expected that `breakout` is a callable that accepts any subclass of event.BaseEvent

        :param f: The callback to wrap
        :param breakout: The breakout method
        """
        def wrapper(e: event.BaseEvent):
            return f(*breakout(e))

        setattr(wrapper, "original_func", f)
        return wrapper

    def unload(self) -> None:
        """Legacy plugins do not support unloading."""
        raise NotImplementedError('Legacy plugins do not support unloading')
