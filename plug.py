"""
Plugin hooks for EDMC - Ian Norton, Jonathan Harris
"""
import os
import imp
import sys
import operator
import threading	# We don't use it, but plugins might
from traceback import print_exc

import Tkinter as tk
import myNotebook as nb

from config import config, appname


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
            sys.stdout.write('loading plugin %s\n' % name)
            with open(loadfile, 'rb') as plugfile:
                module = imp.load_module(name, plugfile, loadfile.encode(sys.getfilesystemencoding()),
                                         ('.py', 'r', imp.PY_SOURCE))
                newname = module.plugin_start()
                self.name = newname and unicode(newname) or name
                self.module = module
        else:
            sys.stdout.write('plugin %s disabled\n' % name)

    def _get_func(self, funcname):
        """
        Get a function from a plugin, else return None if it isn't implemented.
        :param funcname:
        :return:
        """
        return getattr(self.module, funcname, None)

    def get_app(self, parent):
        """
        If the plugin provides mainwindow content create and return it.
        :param parent: the parent frame for this entry.
        :return:
        """
        plugin_app = self._get_func('plugin_app')
        if plugin_app:
            try:
                appitem = plugin_app(parent)
                if isinstance(appitem, tuple):
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
        :return:
        """
        plugin_prefs = self._get_func('plugin_prefs')
        if plugin_prefs:
            try:
                if plugin_prefs.func_code.co_argcount == 1:
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
    :return:
    """
    last_error['root'] = master

    imp.acquire_lock()

    internal = []
    for name in os.listdir(config.internal_plugin_dir):
        if name.endswith('.py') and not name[0] in ['.', '_'] and not name.startswith(appname):
            try:
                plugin = Plugin(name[:-3], os.path.join(config.internal_plugin_dir, name))
                plugin.folder = None	# Suppress listing in Plugins prefs tab
                internal.append(plugin)
            except:
                print_exc()
    PLUGINS.extend(sorted(internal, key = lambda p: operator.attrgetter('name')(p).lower()))

    found = []
    for name in os.listdir(config.plugin_dir):
        if name[0] in ['.', '_']:
            pass
        elif name.endswith('.disabled'):
            name, discard = name.rsplit('.', 1)
            found.append(Plugin(name, None))
        else:
            try:
                # Add plugin's folder to Python's load path in case plugin has dependencies.
                sys.path.append(os.path.join(config.plugin_dir, name))
                found.append(Plugin(name, os.path.join(config.plugin_dir, name, 'load.py')))
            except:
                print_exc()
    PLUGINS.extend(sorted(found, key = lambda p: operator.attrgetter('name')(p).lower()))

    imp.release_lock()


def notify_stop():
    """
    Notify each plugin that the program is closing.
    If your plugin uses threads then stop and join() them before returning.
    versionadded:: 2.3.7
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
    :return:
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
    :return:
    """
    for plugin in PLUGINS:
        prefs_changed = plugin._get_func('prefs_changed')
        if prefs_changed:
            try:
                if prefs_changed.func_code.co_argcount == 0:
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
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        journal_entry = plugin._get_func('journal_entry')
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                if journal_entry.func_code.co_argcount == 4:
                    newerror = journal_entry(cmdr, system, station, dict(entry))
                elif journal_entry.func_code.co_argcount == 5:
                    newerror = journal_entry(cmdr, system, station, dict(entry), dict(state))
                else:
                    newerror = journal_entry(cmdr, is_beta, system, station, dict(entry), dict(state))
                error = error or newerror
            except:
                print_exc()
    return error


def notify_interaction(cmdr, is_beta, entry):
    """
    Send an interaction entry to each plugin.
    :param cmdr: The piloting Cmdr name
    :param is_beta: whether the player is in a Beta universe.
    :param entry: The interaction entry as a dictionary
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        interaction = plugin._get_func('interaction')
        if interaction:
            try:
                # Pass a copy of the interaction entry in case the callee modifies it
                if interaction.func_code.co_argcount == 2:
                    newerror = interaction(cmdr, dict(entry))
                else:
                    newerror = interaction(cmdr, is_beta, dict(entry))
                error = error or newerror
            except:
                print_exc()
    return error


def notify_system_changed(timestamp, system, coordinates):
    """
    Send notification data to each plugin when we arrive at a new system.
    :param timestamp:
    :param system:
    :return:
    deprecated:: 2.2
    Use :func:`journal_entry` with the 'FSDJump' event.
    """
    for plugin in PLUGINS:
        system_changed = plugin._get_func('system_changed')
        if system_changed:
            try:
                if system_changed.func_code.co_argcount == 2:
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
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        cmdr_data = plugin._get_func('cmdr_data')
        if cmdr_data:
            try:
                if cmdr_data.func_code.co_argcount == 1:
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
    versionadded:: 2.3.7
    """
    if err and last_error['root']:
        last_error['msg'] = unicode(err)
        last_error['root'].event_generate('<<PluginError>>', when="tail")
