"""Loading machinery for legacy EDMC plugins."""

from __future__ import annotations

import inspect
import pathlib
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, Union, cast

import semantic_version

from plugin import decorators, event
from plugin.exceptions import LegacyPluginHasNoStart3, LegacyPluginNeedsMigrating
from plugin.plugin import EDMCPlugin
from plugin.plugin_info import PluginInfo
from plugin.provider import EDMCProviders

if TYPE_CHECKING:
    import tkinter as tk  # see implementation of STARTUP_UI_EVENT below

    from EDMCLogging import LoggerMixin
    from plugin.manager import PluginManager

    _LEGACY_UI_FUNC = Callable[
        [tk.Frame], Union[
            Tuple[tk.Widget, tk.Widget],
            tk.Widget,
        ]
    ]

LEGACY_CALLBACK_LUT: Dict[str, str] = {
    # event.EDMCPluginEvents.STARTUP_UI: 'plugin_app',
    event.EDMCPluginEvents.PREFERENCES: 'plugin_prefs',
    event.EDMCPluginEvents.PREFERENCES_CLOSED: 'prefs_changed',
    event.EDMCPluginEvents.JOURNAL_ENTRY: 'journal_entry',
    event.EDMCPluginEvents.DASHBOARD_ENTRY: 'dashboard_entry',
    event.EDMCPluginEvents.CAPI_DATA: 'cmdr_data',
    event.EDMCPluginEvents.EDMC_SHUTTING_DOWN: 'plugin_stop',


    'inara.notify_ship': 'inara_notify_ship',
    'inara.notify_location': 'inara_notify_location',
    'edsm.notify_system': 'edsm_notify_system',
}

LEGACY_CALLBACK_BREAKOUT_LUT: Dict[str, Callable[[Any, 'MigratedPlugin'], Tuple[Any, ...]]] = {
    # All of these callables should accept an event.BaseEvent or a subclass thereof
    # event.EDMCPluginEvents.STARTUP_UI: lambda e, s: (e.data,),
    event.EDMCPluginEvents.PREFERENCES: lambda e, s: (e.notebook, s.commander, s.is_beta),
    event.EDMCPluginEvents.PREFERENCES_CLOSED: lambda e, s: (s.commander, s.is_beta),
    # 'core.setup_preferences_ui': 'plugin_prefs',
    # 'core.preferences_closed': 'prefs_changed',
    event.EDMCPluginEvents.JOURNAL_ENTRY: lambda e, s: (s.commander, s.is_beta, s.system, s.station, e.data, s.state),
    # 'core.dashboard_entry': 'dashboard_entry',
    event.EDMCPluginEvents.CAPI_DATA: lambda e, s: (e.data, s.is_beta),

    # 'inara.notify_ship': 'inara_notify_ship',
    # 'inara.notify_location': 'inara_notify_location',
    # 'edsm.notify_system': 'edsm_notify_system',
}

LEGACY_PROVIDER_LUT: Dict[str, str] = {
    EDMCProviders.SYSTEM: 'system_url',
    EDMCProviders.STATION: 'station_url',
    EDMCProviders.SHIPYARD: 'shipyard_url'
}

LEGACY_PROVIDER_CONVERT_LUT: Dict[str, Callable[..., Tuple[Tuple[Any, ...], Dict[Any, Any]]]] = {
    EDMCProviders.SHIPYARD: lambda ship_name, loadout, /, self: ((loadout, self.is_beta), {})
}  # converting args from old to new


class MigratedPlugin(EDMCPlugin):
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
        self.setup_providers()

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
            breakout = LEGACY_CALLBACK_BREAKOUT_LUT.get(new_hook, lambda e, self: ())

            wrapped = self.generic_callback_handler(callback, breakout)
            setattr(self, target_name, decorators.hook(new_hook)(wrapped))

    def setup_providers(self) -> None:
        """Set up shimmed providers for any providers the legacy plugin may have."""
        for new_name, old_name in LEGACY_PROVIDER_LUT.items():
            callback: Optional[Callable] = getattr(self.module, old_name, None)
            if callback is None:
                continue

            def default_wrapper(*args, **kwargs):
                return args, kwargs

            convert = LEGACY_PROVIDER_CONVERT_LUT.get(new_name, default_wrapper)
            wrapped = self.generic_provider_handler(callback, convert)
            setattr(self, f'_SYNTHETIC_PROVIDER_{old_name}', decorators.provider(new_name)(wrapped))

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

    def generic_callback_handler(self, f: Callable, breakout: Callable[[event.BaseEvent, MigratedPlugin], Tuple[Any, ...]]):
        """
        Wrap the given callback with the given event breakout.

        It is expected that `breakout` is a callable that accepts any subclass of event.BaseEvent

        :param f: The callback to wrap
        :param breakout: The breakout method
        """
        def wrapper(e: event.BaseEvent):
            return f(*breakout(e, self))

        setattr(wrapper, "original_func", f)
        return wrapper

    def generic_provider_handler(self, f: Callable, convert: Callable):
        def wrapper(*args, **kwargs):
            new_args, new_kwargs = convert(*args, self=self, **kwargs)
            return f(*new_args, **new_kwargs)

        setattr(wrapper, 'original_func', f)

        return wrapper

    @decorators.hook(event.EDMCPluginEvents.STARTUP_UI)
    def ui_wrapper(self, data_event: event.BaseDataEvent) -> Optional[tk.Widget]:
        """Wrap the legacy UI system with the new system that always expects a single widget."""
        import tkinter as tk  # Importing this here to make most subclasses of this not HAVE to have this sitting here
        frame: tk.Frame = data_event.data
        if (f := getattr(self.module, 'plugin_app', None)) is None:
            return None

        f = cast('_LEGACY_UI_FUNC', f)
        res = f(frame)
        if res is None:
            return None

        if isinstance(res, tk.Widget):
            return res

        elif (
            isinstance(res, tuple)
            and len(res) == 2
            and isinstance(res[0], tk.Widget)
            and isinstance(res[1], tk.Widget)
        ):
            # Its expected that these used out_frame above as their master, thus we simply need to grid them here
            # before sending our frame (in a frame, because why not) upwards to the UI
            res[0].grid(column=0, row=0)
            res[1].grid(column=1, row=0)

            return frame

        self.log.warning(
            f'plugin_app returned something unexpected: {type(res)=}, {res=}! Assuming its unsafe and bailing on its UI'
        )
        return None

    def unload(self) -> None:
        """Legacy plugins do not support unloading."""
        raise NotImplementedError('Legacy plugins do not support unloading')
