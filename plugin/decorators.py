"""Decorators for marking plugins and callbacks."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Literal, Optional, Type, TypeVar, Union, overload

from EDMCLogging import get_main_logger
from plugin.base_plugin import BasePlugin
from plugin.event import BaseDataEvent, BaseEvent

logger = get_main_logger()

CALLBACK_MARKER = "__edmc_callback_marker__"
PLUGIN_MARKER = "__edmc_plugin_marker__"
PROVIDER_MARKER = "__edmc_provider_marker__"


def edmc_plugin(cls: Type[BasePlugin]) -> Type[BasePlugin]:
    """Mark any classes decorated with this function."""
    logger.info(f"Found plugin class {cls!r}")

    if not issubclass(cls, BasePlugin):
        raise ValueError(f"Cannot decorate non-subclass of Plugin {cls!r} as EDMC Plugin")

    if hasattr(cls, PLUGIN_MARKER):
        raise ValueError(f"Cannot re-register plugin class {cls!r}")

    setattr(cls, PLUGIN_MARKER, 0)
    logger.trace(f"Successfully marked class {cls!r} as EDMC plugin")
    return cls

# Variadic generics are _not_ currently supported, see https://github.com/python/typing/issues/193


_F = TypeVar('_F', bound=Callable[..., Any])


def _list_decorate(attr_name: str, attr_content: str, func: _F) -> _F:
    logger.trace(f'Found function {func!r} to be marked with attr {attr_name!r} and content {attr_content!r}')
    if not hasattr(func, attr_name):
        setattr(func, attr_name, [attr_content])
        return func

    res: list[str] = getattr(func, attr_name)
    if not isinstance(res, list):
        raise ValueError(f'Unexpected type on attribute {attr_name!r}: {type(res)=} {res=}')

    if attr_content in res:
        raise ValueError(f'Name {attr_content!r} already exists in {func!r}s {attr_name!r} attribute!')

    res.append(attr_content)
    setattr(func, attr_name, res)
    return func


# these are overloads to make typing "normal" edmc hooks easier. they are not special, they can be ignored.
# these names should be up to date with those in event.py -- Unfortunately those constants cannot be used here.

if TYPE_CHECKING:
    # I would put all this in a stub file but it seems mypy continues to vex me.
    import tkinter as tk

    from companion import CAPIData
    from plugin.event import JournalEvent
    from prefs import PreferencesEvent

    # TODO: The rest of these
    _TKW = TypeVar('_TKW', bound=tk.Widget)
    OWidget = Optional[_TKW]
    # _ANY_PREFS_EVENT
    _STARTUP_UI = Union[Callable[[Any, BaseDataEvent], OWidget], Callable[[BaseDataEvent], OWidget]]
    _JOURNAL_FUNC = Union[Callable[[JournalEvent], None], Callable[[Any, JournalEvent], None]]

    _PLUGIN_PREFS_FUNC = Union[
        Callable[[PreferencesEvent], OWidget],
        Callable[[Any, PreferencesEvent], OWidget],
    ]

    _NOTIFY_FUNC = Union[Callable[[Any, BaseEvent], None], Callable[[BaseEvent], None]]

    _BDE_DSA = BaseDataEvent[Dict[str, Any]]
    _DASHBOARD_FUNC = Union[Callable[[Any, _BDE_DSA], None], Callable[[_BDE_DSA], None]]
    _CAPI_ENTRY = Union[Callable[[Any, BaseDataEvent[CAPIData]], None], Callable[[BaseDataEvent[CAPIData]], None]]
    _SHUTTING_DOWN_FUNC = _NOTIFY_FUNC
    _PREFS_CMDR_CHANGED = _NOTIFY_FUNC
    _PREFS_CLOSED = _NOTIFY_FUNC


# These overloads cover all of the core events. The Literals for name *MUST* be kept in-sync with those
# found in event.EDMCPluginEvents, otherwise it *fails silently*.
# Unfortunately there is no way to use the annotations from that class.
@overload
def hook(name: Literal['core.setup_ui']) -> Callable[[_STARTUP_UI], _STARTUP_UI]: ...
@overload
def hook(name: Literal['core.journal_event']) -> Callable[[_JOURNAL_FUNC], _JOURNAL_FUNC]: ...
@overload
def hook(name: Literal['core.cqc_journal_event']) -> Callable[[_JOURNAL_FUNC], _JOURNAL_FUNC]: ...
@overload
def hook(name: Literal['core.dashboard_event']) -> Callable[[_DASHBOARD_FUNC], _DASHBOARD_FUNC]: ...
@overload
def hook(name: Literal['core.capi_data']) -> Callable[[_CAPI_ENTRY], _CAPI_ENTRY]: ...
@overload
def hook(name: Literal['core.shutdown']) -> Callable[[_SHUTTING_DOWN_FUNC], _SHUTTING_DOWN_FUNC]: ...
@overload
def hook(name: Literal['core.setup_preferences_ui']) -> Callable[[_PLUGIN_PREFS_FUNC], _PLUGIN_PREFS_FUNC]: ...
@overload
def hook(name: Literal['core.preferences_cmdr_changed']) -> Callable[[_PREFS_CMDR_CHANGED], _PREFS_CMDR_CHANGED]: ...
@overload
def hook(name: Literal['core.preferences_closed']) -> Callable[[_PREFS_CLOSED], _PREFS_CLOSED]: ...
@overload
def hook(name: str) -> Callable[[_F], _F]: ...


def hook(name: str):  # return type explicitly left to be inferred, because magic is magic.
    """
    Create event callback.

    :param name: The event to hook onto
    :return: (Internal python decoration implementation)
    """
    def _decorate(func: _F) -> _F:
        return _list_decorate(CALLBACK_MARKER, name, func)

    return _decorate


def provider(name: str) -> Callable[[_F], _F]:
    """
    Create a provider callback.

    :param name: The provider ID that this provider provides data to
    :return: (Internal python decoration implementation)
    """
    def _decorate(func: _F) -> _F:
        return _list_decorate(PROVIDER_MARKER, name, func)

    return _decorate
