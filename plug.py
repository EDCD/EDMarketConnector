"""
Plugin hooks for EDMC - Ian Norton, Jonathan Harris
"""
from builtins import str
from builtins import object
import os
import importlib
import sys
import operator
import threading	# We don't use it, but plugins might
from traceback import print_exc

import tkinter as tk
import myNotebook as nb

from config import config


# Dashboard Flags constants
FlagsDocked = 1<<0		# on a landing pad
FlagsLanded = 1<<1		# on planet surface
FlagsLandingGearDown = 1<<2
FlagsShieldsUp = 1<<3
FlagsSupercruise = 1<<4
FlagsFlightAssistOff = 1<<5
FlagsHardpointsDeployed = 1<<6
FlagsInWing = 1<<7
FlagsLightsOn = 1<<8
FlagsCargoScoopDeployed = 1<<9
FlagsSilentRunning = 1<<10
FlagsScoopingFuel = 1<<11
FlagsSrvHandbrake = 1<<12
FlagsSrvTurret = 1<<13		# using turret view
FlagsSrvUnderShip = 1<<14	# turret retracted
FlagsSrvDriveAssist = 1<<15
FlagsFsdMassLocked = 1<<16
FlagsFsdCharging = 1<<17
FlagsFsdCooldown = 1<<18
FlagsLowFuel = 1<<19		# <25%
FlagsOverHeating = 1<<20	# > 100%
FlagsHasLatLong = 1<<21
FlagsIsInDanger = 1<<22
FlagsBeingInterdicted = 1<<23
FlagsInMainShip = 1<<24
FlagsInFighter = 1<<25
FlagsInSRV = 1<<26
FlagsAnalysisMode = 1<<27	# Hud in Analysis mode
FlagsNightVision = 1<<28
FlagsAverageAltitude = 1<<29		# Altitude from Average radius
FlagsFsdJump = 1<<30
FlagsSrvHighBeam = 1<<31

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

# For asynchronous error display
last_error = {
    'msg':  None,
    'root': None,
}


class Plugin(object):

    def __init__(self, name, loadfile):
        """
        Load a single plugin
        :param name: module name
        :param loadfile: the main .py file
        :raises Exception: Typically ImportError or OSError
        """

        self.name = name	# Display name.
        self.folder = name	# basename of plugin folder. None for internal plugins.
        self.module = None	# None for disabled plugins.

        if loadfile:
            sys.stdout.write('loading plugin {} from "{}"\n'.format(name.replace('.', '_'), loadfile))
            module = importlib.machinery.SourceFileLoader('plugin_{}'.format(name.encode(encoding='ascii', errors='replace').decode('utf-8').replace('.', '_')), loadfile).load_module()
            if module.plugin_start.__code__.co_argcount == 0:
                newname = module.plugin_start()
            else:
                newname = module.plugin_start(os.path.dirname(loadfile))
            self.name = newname and str(newname) or name
            self.module = module
        else:
            sys.stdout.write('plugin %s disabled\n' % name)

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
            except:
                print_exc()
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
                if plugin_prefs.__code__.co_argcount == 1:
                    frame = plugin_prefs(parent)
                else:
                    frame = plugin_prefs(parent, cmdr, is_beta)
                if not isinstance(frame, nb.Frame):
                    raise AssertionError
                return frame
            except:
                print_exc()
        return None


def load_plugins(master):
    """
    Find and load all plugins
    """
    last_error['root'] = master

    internal = []
    for name in os.listdir(config.internal_plugin_dir):
        if name.endswith('.py') and not name[0] in ['.', '_']:
            try:
                plugin = Plugin(name[:-3], os.path.join(config.internal_plugin_dir, name))
                plugin.folder = None	# Suppress listing in Plugins prefs tab
                internal.append(plugin)
            except:
                print_exc()
    PLUGINS.extend(sorted(internal, key = lambda p: operator.attrgetter('name')(p).lower()))

    # Add plugin folder to load path so packages can be loaded from plugin folder
    sys.path.append(config.plugin_dir)

    found = []
    # Load any plugins that are also packages first
    for name in sorted(os.listdir(config.plugin_dir),
                       key = lambda n: (not os.path.isfile(os.path.join(config.plugin_dir, n, '__init__.py')), n.lower())):
        if not os.path.isdir(os.path.join(config.plugin_dir, name)) or name[0] in ['.', '_']:
            pass
        elif name.endswith('.disabled'):
            name, discard = name.rsplit('.', 1)
            found.append(Plugin(name, None))
        else:
            try:
                # Add plugin's folder to load path in case plugin has internal package dependencies
                sys.path.append(os.path.join(config.plugin_dir, name))
                found.append(Plugin(name, os.path.join(config.plugin_dir, name, 'load.py')))
            except:
                print_exc()
    PLUGINS.extend(sorted(found, key = lambda p: operator.attrgetter('name')(p).lower()))

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
                newerror = plugin_stop()
                error = error or newerror
            except:
                print_exc()
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
            except:
                print_exc()


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
                if prefs_changed.__code__.co_argcount == 0:
                    prefs_changed()
                else:
                    prefs_changed(cmdr, is_beta)
            except:
                print_exc()


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
    error = None
    for plugin in PLUGINS:
        journal_entry = plugin._get_func('journal_entry')
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                if journal_entry.__code__.co_argcount == 4:
                    newerror = journal_entry(cmdr, system, station, dict(entry))
                elif journal_entry.__code__.co_argcount == 5:
                    newerror = journal_entry(cmdr, system, station, dict(entry), dict(state))
                else:
                    newerror = journal_entry(cmdr, is_beta, system, station, dict(entry), dict(state))
                error = error or newerror
            except:
                print_exc()
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
            except:
                print_exc()
    return error


def notify_system_changed(timestamp, system, coordinates):
    """
    Send notification data to each plugin when we arrive at a new system.
    :param timestamp:
    :param system:
    .. deprecated:: 2.2
    Use :func:`journal_entry` with the 'FSDJump' event.
    """
    for plugin in PLUGINS:
        system_changed = plugin._get_func('system_changed')
        if system_changed:
            try:
                if system_changed.__code__.co_argcount == 2:
                    system_changed(timestamp, system)
                else:
                    system_changed(timestamp, system, coordinates)
            except:
                print_exc()


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
                if cmdr_data.__code__.co_argcount == 1:
                    newerror = cmdr_data(data)
                else:
                    newerror = cmdr_data(data, is_beta)
                error = error or newerror
            except:
                print_exc()
    return error


def show_error(err):
    """
    Display an error message in the status line of the main window.
    :param err:
    .. versionadded:: 2.3.7
    """
    if err and last_error['root']:
        last_error['msg'] = str(err)
        last_error['root'].event_generate('<<PluginError>>', when="tail")
