from __future__ import annotations

import warnings
# import myNotebook as nb  # noqa: N813
from typing import TYPE_CHECKING, Any, Dict, Optional

from config import config
from EDMCLogging import get_main_logger

# """
# Plugin hooks for EDMC - Ian Norton, Jonathan Harris
# """
# import copy
# import importlib
# import logging
# import operator
# import os
# import sys
# import tkinter as tk
# from builtins import object, str
# from typing import Optional


if TYPE_CHECKING:
    from plugin.manager import LoadedPlugin, PluginManager
    from tkinter import Tk
    from typing import TypedDict

    class LastError(TypedDict):
        msg: str | None
        root: Tk
        ...

logger = get_main_logger()

# # List of loaded Plugins
# PLUGINS = []
# PLUGINS_not_py3 = []

# # For asynchronous error display
last_error: LastError = {
    'msg':  None,
    'root': None,  # type: ignore
}

_OLD_PROVIDER_LUT = {
    'inara_notify_ship': 'inara.notify_ship',
    'inara_notify_location': 'inara.notify_location',
}

_manager: Optional[PluginManager] = None


def provides(name: str) -> list[str]:
    """
    Find plugins that provide a given function.

    Note this is a STUB that makes use of the provider system internally,
    if possible.

    :param name: The name to look for.
    :return: A list of plugin names.
    """
    warnings.warn('plug.py is in general deprecated. Please update to newer plugin systems', DeprecationWarning)
    if _manager is None:
        raise ValueError('Unexpected None Manager')

    providers = _manager.get_providers(_OLD_PROVIDER_LUT.get(name, name))
    for plugin in _manager.legacy_plugins:
        if plugin in providers:
            continue

        # only do this for legacy plugins. new-style plugins should register
        # stuff as providers, even for old-style access.
        if getattr(plugin.module, name):
            providers.append(plugin)

    return [p.info.name for p in providers]


def _invoke_function(plugin: LoadedPlugin, name: str, args: tuple[Any, ...], kwargs: dict[Any, Any]) -> Any:
    """
    Invoke the given provider name.

    If the provider does not exist, and the plugin is a MigratedPlugin, attempt to invoke the name directly.
    """
    func = plugin.provides(name)
    if func is not None:
        return func(*args, **kwargs)

    # We get here if the func doesn't exist.
    if not plugin.is_legacy:
        return None

    logger.info(f'name {name!r} invoked via plug on {plugin!r}')

    attr = getattr(plugin.module, name)
    if attr is None:
        logger.warning(f'Unable to find name {name!r} on {plugin!r} to invoke. bailing!')
        return None

    if not callable(attr):
        logger.warning(f'Found {name!r} on {plugin!r}, but it is not callable! {attr=}, {type(attr)=}')
        return None

    return attr(*args, **kwargs)


def invoke(plugin: LoadedPlugin | str, fallback: str, func_name: str, *args, **kwargs) -> Any:
    """
    Invoke a name on a plugin.

    This is a deprecated plugin. use manager.get_providers instead.

    :param plugin: The plugin to invoke the function on.
    :param fallback: A fallback plugin to invoke the function on if plugin doesn't exist or doesn't have the function.
    :param func_name: The name of the function to call (this may be translated to a provider name).
    :return: The return of the function, if any.
    """
    if _manager is None:
        raise ValueError('Unexpected None Manager')

    real_plugin = plugin if isinstance(plugin, LoadedPlugin) else _manager.get_plugin(plugin)
    fallback_plugin = fallback if isinstance(fallback, LoadedPlugin) else _manager.get_plugin(fallback)

    if real_plugin is not None:
        return _invoke_function(real_plugin, func_name, args, kwargs)

    if fallback_plugin is not None:
        return _invoke_function(fallback_plugin, func_name, args, kwargs)


def show_error(err):
    """
    Display an error message in the status line of the main window.

    Will be NOP during shutdown to avoid Tk hang.
    :param err:
    .. versionadded:: 2.3.7
    """
    if config.shutting_down:
        logger.info(f'Called during shutdown: "{str(err)}"')
        return

    if err and last_error['root']:
        last_error['msg'] = str(err)
        last_error['root'].event_generate('<<PluginError>>', when="tail")
