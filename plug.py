"""
Plugin hooks for EDMC - Ian Norton, Jonathan Harris
"""
from builtins import str
from builtins import object
import os
import importlib
import sys
import operator
import threading  # noqa: F401 - We don't use it, but plugins might
from typing import Optional
import tkinter as tk

import myNotebook as nb  # noqa: N813

from config import appcmdname, appname, config
from EDMCLogging import get_main_logger
import logging

logger = get_main_logger()

# Dashboard Flags constants
FlagsDocked = 1 << 0  # on a landing pad
FlagsLanded = 1 << 1  # on planet surface
FlagsLandingGearDown = 1 << 2
FlagsShieldsUp = 1 << 3
FlagsSupercruise = 1 << 4
FlagsFlightAssistOff = 1 << 5
FlagsHardpointsDeployed = 1 << 6
FlagsInWing = 1 << 7
FlagsLightsOn = 1 << 8
FlagsCargoScoopDeployed = 1 << 9
FlagsSilentRunning = 1 << 10
FlagsScoopingFuel = 1 << 11
FlagsSrvHandbrake = 1 << 12
FlagsSrvTurret = 1 << 13  # using turret view
FlagsSrvUnderShip = 1 << 14  # turret retracted
FlagsSrvDriveAssist = 1 << 15
FlagsFsdMassLocked = 1 << 16
FlagsFsdCharging = 1 << 17
FlagsFsdCooldown = 1 << 18
FlagsLowFuel = 1 << 19  # <25%
FlagsOverHeating = 1 << 20  # > 100%
FlagsHasLatLong = 1 << 21
FlagsIsInDanger = 1 << 22
FlagsBeingInterdicted = 1 << 23
FlagsInMainShip = 1 << 24
FlagsInFighter = 1 << 25
FlagsInSRV = 1 << 26
FlagsAnalysisMode = 1 << 27  # Hud in Analysis mode
FlagsNightVision = 1 << 28
FlagsAverageAltitude = 1 << 29  # Altitude from Average radius
FlagsFsdJump = 1 << 30
FlagsSrvHighBeam = 1 << 31

# Dashboard GuiFocus constants
GuiFocusNoFocus = 0
GuiFocusInternalPanel = 1	# right hand side
GuiFocusExternalPanel = 2	# left hand side
GuiFocusCommsPanel = 3		# top
GuiFocusRolePanel = 4		# bottom
GuiFocusStationServices = 5
GuiFocusGalaxyMap = 6
GuiFocusSystemMap = 7
GuiFocusOrrery = 8
GuiFocusFSS = 9
GuiFocusSAA = 10
GuiFocusCodex = 11


# List of loaded Plugins
PLUGINS = []
PLUGINS_not_py3 = []

# For asynchronous error display
last_error = {
    'msg':  None,
    'root': None,
}


class Plugin(object):

    def __init__(self, name: str, loadfile: str, plugin_logger: Optional[logging.Logger]):
        """
        Load a single plugin
        :param name: module name
        :param loadfile: the main .py file
        :raises Exception: Typically ImportError or OSError
        """

        self.name = name  # Display name.
        self.folder = name  # basename of plugin folder. None for internal plugins.
        self.module = None  # None for disabled plugins.
        self.logger = plugin_logger

        if loadfile:
            logger.info(f'loading plugin "{name.replace(".", "_")}" from "{loadfile}"')
            try:
                module = importlib.machinery.SourceFileLoader('plugin_{}'.format(
                    name.encode(encoding='ascii', errors='replace').decode('utf-8').replace('.', '_')),
                    loadfile).load_module()
                if getattr(module, 'plugin_start3', None):
                    newname = module.plugin_start3(os.path.dirname(loadfile))
                    self.name = newname and str(newname) or name
                    self.module = module
                elif getattr(module, 'plugin_start', None):
                    logger.warning(f'plugin {name} needs migrating\n')
                    PLUGINS_not_py3.append(self)
                else:
                    logger.error(f'plugin {name} has no plugin_start3() function')
            except Exception as e:
                logger.exception(f': Failed for Plugin "{name}"')
                raise
        else:
            logger.info(f'plugin {name} disabled')

    def _get_func(self, funcname):
        """
        Get a function from a plugin
        :param funcname:
        :returns: The function, or None if it isn't implemented.
        """
        return getattr(self.module, funcname, None)

    def get_app(self, parent):
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
                elif isinstance(appitem, tuple):
                    if len(appitem) != 2 or not isinstance(appitem[0], tk.Widget) or not isinstance(appitem[1], tk.Widget):
                        raise AssertionError
                elif not isinstance(appitem, tk.Widget):
                    raise AssertionError
                return appitem
            except Exception as e:
                logger.exception(f'Failed for Plugin "{self.name}"')
        return None

    def get_prefs(self, parent, cmdr, is_beta):
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
                if not isinstance(frame, nb.Frame):
                    raise AssertionError
                return frame
            except Exception as e:
                logger.exception(f'Failed for Plugin "{self.name}"')
        return None


def load_plugins(master):
    """
    Find and load all plugins
    """
    last_error['root'] = master

    internal = []
    for name in sorted(os.listdir(config.internal_plugin_dir)):
        if name.endswith('.py') and not name[0] in ['.', '_']:
            try:
                plugin = Plugin(name[:-3], os.path.join(config.internal_plugin_dir, name), logger)
                plugin.folder = None  # Suppress listing in Plugins prefs tab
                internal.append(plugin)
            except Exception as e:
                logger.exception(f'Failure loading internal Plugin "{name}"')
    PLUGINS.extend(sorted(internal, key=lambda p: operator.attrgetter('name')(p).lower()))

    # Add plugin folder to load path so packages can be loaded from plugin folder
    sys.path.append(config.plugin_dir_str)

    found = []
    # Load any plugins that are also packages first
    for name in sorted(os.listdir(config.plugin_dir),
                       key = lambda n: (not os.path.isfile(os.path.join(config.plugin_dir, n, '__init__.py')), n.lower())):
        if not os.path.isdir(os.path.join(config.plugin_dir, name)) or name[0] in ['.', '_']:
            pass
        elif name.endswith('.disabled'):
            name, discard = name.rsplit('.', 1)
            found.append(Plugin(name, None, logger))
        else:
            try:
                # Add plugin's folder to load path in case plugin has internal package dependencies
                sys.path.append(os.path.join(config.plugin_dir, name))

                # Create a logger for this 'found' plugin.  Must be before the
                # load.py is loaded.
                import EDMCLogging

                plugin_logger = EDMCLogging.get_plugin_logger(name)
                found.append(Plugin(name, os.path.join(config.plugin_dir, name, 'load.py'), plugin_logger))
            except Exception as e:
                logger.exception(f'Failure loading found Plugin "{name}"')
                pass
    PLUGINS.extend(sorted(found, key=lambda p: operator.attrgetter('name')(p).lower()))


def provides(fn_name):
    """
    Find plugins that provide a function
    :param fn_name:
    :returns: list of names of plugins that provide this function
    .. versionadded:: 3.0.2
    """
    return [p.name for p in PLUGINS if p._get_func(fn_name)]

def invoke(plugin_name, fallback, fn_name, *args):
    """
    Invoke a function on a named plugin
    :param plugin_name: preferred plugin on which to invoke the function
    :param fallback: fallback plugin on which to invoke the function, or None
    :param fn_name:
    :param *args: arguments passed to the function
    :returns: return value from the function, or None if the function was not found
    .. versionadded:: 3.0.2
    """
    for plugin in PLUGINS:
        if plugin.name == plugin_name and plugin._get_func(fn_name):
            return plugin._get_func(fn_name)(*args)
    for plugin in PLUGINS:
        if plugin.name == fallback:
            assert plugin._get_func(fn_name), plugin.name	# fallback plugin should provide the function
            return plugin._get_func(fn_name)(*args)


def notify_stop():
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
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')

    logger.info('Done')

    return error


def notify_prefs_cmdr_changed(cmdr, is_beta):
    """
    Notify each plugin that the Cmdr has been changed while the settings dialog is open.
    Relevant if you want to have different settings for different user accounts.
    :param cmdr: current Cmdr name (or None).
    :param is_beta: whether the player is in a Beta universe.
    """
    for plugin in PLUGINS:
        prefs_cmdr_changed = plugin._get_func('prefs_cmdr_changed')
        if prefs_cmdr_changed:
            try:
                prefs_cmdr_changed(cmdr, is_beta)
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')


def notify_prefs_changed(cmdr, is_beta):
    """
    Notify each plugin that the settings dialog has been closed.
    The prefs frame and any widgets you created in your `get_prefs()` callback
    will be destroyed on return from this function, so take a copy of any
    values that you want to save.
    :param cmdr: current Cmdr name (or None).
    :param is_beta: whether the player is in a Beta universe.
    """
    for plugin in PLUGINS:
        prefs_changed = plugin._get_func('prefs_changed')
        if prefs_changed:
            try:
                prefs_changed(cmdr, is_beta)
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')


def notify_journal_entry(cmdr, is_beta, system, station, entry, state):
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
    if entry['event'] in ('Location'):
        logger.trace('Notifying plugins of "Location" event')

    error = None
    for plugin in PLUGINS:
        journal_entry = plugin._get_func('journal_entry')
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                newerror = journal_entry(cmdr, is_beta, system, station, dict(entry), dict(state))
                error = error or newerror
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')
    return error


def notify_dashboard_entry(cmdr, is_beta, entry):
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
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')
    return error


def notify_newdata(data, is_beta):
    """
    Send the latest EDMC data from the FD servers to each plugin
    :param data:
    :param is_beta: whether the player is in a Beta universe.
    :returns: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        cmdr_data = plugin._get_func('cmdr_data')
        if cmdr_data:
            try:
                newerror = cmdr_data(data, is_beta)
                error = error or newerror
            except Exception as e:
                logger.exception(f'Plugin "{plugin.name}" failed')
    return error


def show_error(err):
    """
    Display an error message in the status line of the main window.

    Will be NOP during shutdown to avoid Tk hang.
    :param err:
    .. versionadded:: 2.3.7
    """
    if config.shutting_down():
        logger.info(f'Called during shutdown: "{str(err)}"')
        return

    if err and last_error['root']:
        last_error['msg'] = str(err)
        last_error['root'].event_generate('<<PluginError>>', when="tail")
