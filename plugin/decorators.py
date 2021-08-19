"""Decorators for marking plugins and callbacks."""


import functools
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Type, TypeVar, Union, overload

from EDMCLogging import get_main_logger
from plugin.base_plugin import BasePlugin

if TYPE_CHECKING:
    import tkinter as tk

    from plugin.event import JournalEvent

    _UI_SETUP_FUNC = TypeVar(
        '_UI_SETUP_FUNC', bound=Union[
            Callable[[Any, tk.Frame], Optional[tk.Widget]],
            Callable[[tk.Frame], Optional[tk.Widget]],
        ]
    )

    _JOURNAL_FUNC = TypeVar(
        '_JOURNAL_FUNC',
        bound=Union[
            Callable[[JournalEvent], None],
            Callable[[Any, JournalEvent], None]
        ]
    )

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
@overload
def hook(name: Literal['core.setup_ui']) -> Callable[[_UI_SETUP_FUNC], _UI_SETUP_FUNC]: ...


@overload
def hook(name: Literal['core.journal_event']) -> Callable[[_JOURNAL_FUNC], _JOURNAL_FUNC]: ...


@overload
def hook(name: str) -> Callable[['_F'], _F]: ...


def hook(name: str) -> Callable[['_F'], _F]:
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
