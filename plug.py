"""
plug.py - Plugin API.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import copy
import importlib.util
import logging
import operator
import os
import sys
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import ttk
from typing import Any, Mapping, MutableMapping

import companion
import myNotebook as nb  # noqa: N813
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

# List of loaded Plugins
PLUGINS = []


# For asynchronous error display
class LastError:
    """Holds the last plugin error."""

    msg: str | None
    root: tk.Tk

    def __init__(self) -> None:
        self.msg = None


last_error = LastError()


class Plugin:
    """An EDMC plugin."""

    def __init__(self, name: str, folder: str, loadfile: Path | None, plugin_logger: logging.Logger | None):  # noqa: CCR001
        """
        Load a single plugin.

        :param name: Base name of the file being loaded from.
        :param loadfile: Full path/filename of the plugin.
        :param plugin_logger: The logging instance for this plugin to use.
        :raises Exception: Typically, ImportError or OSError
        """
        self.name: str = name  # Display name.
        self.folder: str | None = folder  # basename of plugin folder. None for internal plugins.
        self.module = None  # None for disabled plugins.
        self.logger: logging.Logger | None = plugin_logger
        self.frame_id = 0   # Not 0 is shown in main window
        self.broken: str = None  # Error message

        if loadfile:
            logger.info(f'loading plugin "{name.replace(".", "_")}" from "{loadfile}"')
            try:
                filename = 'plugin_'
                filename += name.encode(encoding='ascii', errors='replace').decode('utf-8').replace('.', '_')
                spec = importlib.util.spec_from_file_location(filename, loadfile)
                # Replaces older load_module() code. Includes a safety check that the module name is set.
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module.__name__] = module
                    spec.loader.exec_module(module)
                    if getattr(module, 'plugin_start3', None):
                        newname = module.plugin_start3(Path(loadfile).resolve().parent)
                        self.name = str(newname) if newname else self.name
                        self.module = module
                        self.broken = None
                    elif getattr(module, 'plugin_start', None):
                        self.broken = f'plugin {name} needs migrating'
                        logger.warning(f'plugin {name} needs migrating\n')
                    else:
                        self.broken = 'needs python 3 migration'
                        logger.error(f'plugin {name} has no plugin_start3() function')
                else:
                    self.broken = 'Failed to load from load.py'
                    logger.error(f'Failed to load Plugin "{name}" from file "{loadfile}"')
            except Exception as e:
                self.broken = f'Error: {e}'
                logger.exception(f': Failed for Plugin "{name}"')
                raise
        else:
            logger.info(f'plugin {name} disabled')

    def _get_func(self, funcname: str):
        """
        Get a function from a plugin.

        :param funcname:
        :returns: The function, or None if it isn't implemented.
        """
        return getattr(self.module, funcname, None)

    def get_app(self, parent: tk.Frame) -> tk.Frame | None:
        """
        If the plugin provides mainwindow content create and return it.

        :param parent: the parent frame for this entry.
        :returns: None, a tk Widget, or a pair of tk.Widgets
        """
        plugin_app = self._get_func('plugin_app')
        if plugin_app:
            try:
                appitem = plugin_app(parent)
                if appitem is None:
                    return None

                if isinstance(appitem, tuple):
                    if (
                        len(appitem) != 2
                        or not isinstance(appitem[0], tk.Widget)
                        or not isinstance(appitem[1], tk.Widget)
                    ):
                        raise AssertionError

                elif not isinstance(appitem, tk.Widget):
                    raise AssertionError

                return appitem

            except Exception:
                logger.exception(f'Failed for Plugin "{self.name}"')

        return None

    def get_prefs(self, parent: ttk.Notebook, cmdr: str | None, is_beta: bool) -> nb.Frame | None:
        """
        If the plugin provides a prefs frame, create and return it.

        :param parent: the parent frame for this preference tab.
        :param cmdr: current Cmdr name (or None). Relevant if you want to have
           different settings for different user accounts.
        :param is_beta: whether the player is in a Beta universe.
        :returns: a myNotebook Frame
        """
        plugin_prefs = self._get_func('plugin_prefs')
        if plugin_prefs:
            try:
                frame = plugin_prefs(parent, cmdr, is_beta)
                if isinstance(frame, nb.Frame):
                    return frame
                raise AssertionError
            except Exception:
                logger.exception(f'Failed for Plugin "{self.name}"')
        return None


def load_plugins(master: tk.Tk) -> None:
    """Find and load all plugins."""
    last_error.root = master

    internal = _load_internal_plugins()
    PLUGINS.extend(sorted(internal, key=lambda p: operator.attrgetter('name')(p).lower()))

    # Add plugin folder to load path so packages can be loaded from plugin folder
    sys.path.append(config.plugin_dir)

    sync_all_plugins()


def _load_internal_plugins():
    internal = []
    for name in sorted(os.listdir(config.internal_plugin_dir_path)):
        if name.endswith('.py') and name[0] not in ('.', '_'):
            try:
                plugin_name = name[:-3]
                plugin_path = config.internal_plugin_dir_path / name
                plugin = Plugin(plugin_name, None, plugin_path, logger)
                internal.append(plugin)
            except Exception:
                logger.exception(f'Failure loading internal Plugin "{name}"')
    return internal


def load_plugin(folder: str):
    if not (config.plugin_dir_path / folder).is_dir() or folder.startswith(('.', '_')):
        return None
    if folder.endswith('.disabled'):
        return None

    disabled_list = config.get_list('disabled_plugins', default=[])
    if disabled_list.count(folder) > 0:
        plugin = Plugin(folder, folder, None, logger)
    else:
        try:
            # Add plugin's folder to load path in case plugin has internal package dependencies
            sys.path.append(str(config.plugin_dir_path / folder))
            import EDMCLogging
            # Create a logger for this 'found' plugin.  Must be before the load.py is loaded.
            plugin_logger = EDMCLogging.get_plugin_logger(folder)
            plugin = Plugin(folder, folder, config.plugin_dir_path / folder / 'load.py', plugin_logger)
        except Exception as e:
            plugin = Plugin(folder, folder, None, logger)
            plugin.broken = f'Error: {e}'
            logger.exception(f'Failure loading found Plugin "{folder}"')
    old = get_plugin_by_folder(folder)
    if old:
        disable_plugin(old, False)
        PLUGINS.remove(old)
    PLUGINS.append(plugin)
    return plugin

def sync_all_plugins():
    # Load any plugins that are also packages first, but note it's *still*
    # 100% relying on there being a `load.py`, as only that will be loaded.
    # The intent here is to e.g. have EDMC-Overlay load before any plugins
    # that depend on it.

    plugin_files = sorted(config.plugin_dir_path.iterdir(), key=lambda p: (
        not (p / '__init__.py').is_file(), p.name.lower()))

    for plugin_file in plugin_files:
        if not get_plugin_by_folder(plugin_file.name):
            load_plugin(plugin_file.name)

    for plugin in list(PLUGINS):
        if plugin.folder and not os.path.exists(os.path.join(config.plugin_dir_path, plugin.folder)):
            disable_plugin(plugin, False)
            plugin.broken = f'Missing folder: {plugin.folder}'
            PLUGINS.remove(plugin)

def provides(fn_name: str) -> list[str]:
    """
    Find plugins that provide a function.

    :param fn_name:
    :returns: list of names of plugins that provide this function
    .. versionadded:: 3.0.2
    """
    return [p.name for p in PLUGINS if p._get_func(fn_name)]


def invoke(
    plugin_name: str, fallback: str | None, fn_name: str, *args: Any
) -> str | None:
    """
    Invoke a function on a named plugin.

    :param plugin_name: preferred plugin on which to invoke the function
    :param fallback: fallback plugin on which to invoke the function, or None
    :param fn_name:
    :param *args: arguments passed to the function
    :returns: return value from the function, or None if the function was not found
    .. versionadded:: 3.0.2
    """
    for plugin in PLUGINS:
        if plugin.name == plugin_name:
            plugin_func = plugin._get_func(fn_name)
            if plugin_func is not None:
                return plugin_func(*args)

    for plugin in PLUGINS:
        if plugin.name == fallback:
            plugin_func = plugin._get_func(fn_name)
            assert plugin_func, plugin.name  # fallback plugin should provide the function
            return plugin_func(*args)

    return None


def notify_stop() -> str | None:
    """
    Notify each plugin that the program is closing.

    If your plugin uses threads then stop and join() them before returning.
    .. versionadded:: 2.3.7
    """
    error = None
    for plugin in PLUGINS:
        plugin_stop = plugin._get_func('plugin_stop')
        if plugin_stop:
            try:
                logger.info(f'Asking plugin "{plugin.name}" to stop...')
                newerror = plugin_stop()
                error = error or newerror
            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')

    logger.info('Done')

    return error


def _notify_prefs_plugins(fn_name: str, cmdr: str | None, is_beta: bool) -> None:
    for plugin in PLUGINS:
        prefs_callback = plugin._get_func(fn_name)
        if prefs_callback:
            try:
                prefs_callback(cmdr, is_beta)
            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')


def notify_prefs_cmdr_changed(cmdr: str | None, is_beta: bool) -> None:
    """
    Notify plugins that the Cmdr was changed while the settings dialog is open.

    Relevant if you want to have different settings for different user accounts.
    :param cmdr: current Cmdr name (or None).
    :param is_beta: whether the player is in a Beta universe.
    """
    _notify_prefs_plugins("prefs_cmdr_changed", cmdr, is_beta)


def notify_prefs_changed(cmdr: str | None, is_beta: bool) -> None:
    """
    Notify plugins that the settings dialog has been closed.

    The prefs frame and any widgets you created in your `get_prefs()` callback
    will be destroyed on return from this function, so take a copy of any
    values that you want to save.
    :param cmdr: current Cmdr name (or None).
    :param is_beta: whether the player is in a Beta universe.
    """
    _notify_prefs_plugins("prefs_changed", cmdr, is_beta)


def notify_journal_entry(
    cmdr: str, is_beta: bool, system: str | None, station: str | None,
    entry: MutableMapping[str, Any],
    state: Mapping[str, Any]
) -> str | None:
    """
    Send a journal entry to each plugin.

    :param cmdr: The Cmdr name, or None if not yet known
    :param system: The current system, or None if not yet known
    :param station: The current station, or None if not docked or not yet known
    :param entry: The journal entry as a dictionary
    :param state: A dictionary containing info about the Cmdr, current ship and cargo
    :param is_beta: whether the player is in a Beta universe.
    :returns: Error message from the first plugin that returns one (if any)
    """
    if entry['event'] in 'Location':
        logger.trace_if('journal.locations', 'Notifying plugins of "Location" event')

    error = None

    if "timestamp" in entry and not config.skip_timecheck:
        # Check that timestamp is recent enough
        dt = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc) - timedelta(minutes=60):
            error = f"Event at {entry['timestamp']} beyond Time Delta of 60 minutes. Skipping."
            return error

    for plugin in PLUGINS:
        journal_entry = plugin._get_func('journal_entry')
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                newerror = journal_entry(cmdr, is_beta, system, station, dict(entry), dict(state))
                error = error or newerror
            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')
    return error


def notify_journal_entry_cqc(
    cmdr: str, is_beta: bool,
    entry: MutableMapping[str, Any],
    state: Mapping[str, Any]
) -> str | None:
    """
    Send an in-CQC journal entry to each plugin.

    :param cmdr: The Cmdr name, or None if not yet known
    :param entry: The journal entry as a dictionary
    :param state: A dictionary containing info about the Cmdr, current ship and cargo
    :param is_beta: whether the player is in a Beta universe.
    :returns: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        cqc_callback = plugin._get_func('journal_entry_cqc')
        if cqc_callback is not None and callable(cqc_callback):
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                newerror = cqc_callback(cmdr, is_beta, copy.deepcopy(entry), copy.deepcopy(state))
                error = error or newerror

            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed while handling CQC mode journal entry')

    return error


def notify_dashboard_entry(cmdr: str, is_beta: bool, entry: MutableMapping[str, Any], ) -> str | None:
    """
    Send a status entry to each plugin.

    :param cmdr: The piloting Cmdr name
    :param is_beta: whether the player is in a Beta universe.
    :param entry: The status entry as a dictionary
    :returns: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        status = plugin._get_func('dashboard_entry')
        if status:
            try:
                # Pass a copy of the status entry in case the callee modifies it
                newerror = status(cmdr, is_beta, dict(entry))
                error = error or newerror
            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')
    return error


def notify_capidata(data: companion.CAPIData, is_beta: bool) -> str | None:
    """
    Send the latest EDMC data from the FD servers to each plugin.

    :param data:
    :param is_beta: whether the player is in a Beta universe.
    :returns: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        # TODO: Handle it being Legacy data
        cmdr_data = plugin._get_func('cmdr_data_legacy' if data.source_host == companion.SERVER_LEGACY else 'cmdr_data')

        if cmdr_data:
            try:
                newerror = cmdr_data(data, is_beta)
                error = error or newerror

            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')

    return error


def notify_capi_fleetcarrierdata(data: companion.CAPIData) -> str | None:
    """
    Send the latest CAPI Fleet Carrier data from the FD servers to each plugin.

    :param data: The CAPIData returned in the CAPI response
    :returns: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        fc_callback = plugin._get_func('capi_fleetcarrier')
        if fc_callback is not None and callable(fc_callback):
            try:
                # Pass a copy of the CAPIData in case the callee modifies it
                newerror = fc_callback(copy.deepcopy(data))
                error = error if error else newerror

            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed on receiving Fleet Carrier data')

    return error


def show_error(err: str) -> None:
    """
    Display an error message in the status line of the main window.

    Will be NOP during shutdown to avoid Tk hang.
    :param err:
    .. versionadded:: 2.3.7
    """
    if config.shutting_down:
        logger.info(f'Called during shutdown: "{str(err)}"')
        return

    if err and last_error.root:
        last_error.msg = str(err)
        last_error.root.event_generate('<<PluginError>>', when="tail")


def enable_plugin(plugin: Plugin, add_to_config = True) -> Plugin:
    if add_to_config:
        disabled_list = config.get_list('disabled_plugins', default=[])
        if disabled_list.count(plugin.folder) > 0:
            disabled_list.remove(plugin.folder)
            config.set('disabled_plugins', disabled_list)
    if loaded := load_plugin(plugin.folder):
        if PLUGINS.count(plugin):
            PLUGINS.remove(plugin)
        PLUGINS.append(loaded)
        return loaded
    return plugin


def disable_plugin(plugin: Plugin, add_to_config = True) -> Plugin:
    if add_to_config:
        disabled_list = config.get_list('disabled_plugins', default=[])
        if disabled_list.count(plugin.folder) == 0:
            disabled_list.append(plugin.folder)
            config.set('disabled_plugins', disabled_list)
    if plugin.module:
        plugin_stop = plugin._get_func('plugin_stop')
        if plugin_stop:
            try:
                logger.info(f'Asking plugin "{plugin.name}" to stop...')
                plugin_stop()
            except Exception:
                logger.exception(f'Plugin "{plugin.name}" failed')
        plugin.module = None
    return plugin

def get_plugin_by_folder(folder: str) -> Plugin | None:
    for plugin in PLUGINS:
        if plugin.folder == folder:
            return plugin
    return None
