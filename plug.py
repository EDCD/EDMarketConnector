"""
Plugin hooks for EDMC - Ian Norton, Jonathan Harris
"""
import os
import imp
import sys
import operator
import threading	# We don't use it, but plugins might
from traceback import print_exc

from config import config, appname

# List of loaded Plugins
PLUGINS = []


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
        try:
            plugin_app = self._get_func('plugin_app')
            return plugin_app and plugin_app(parent)
        except:
            print_exc()
            return None

    def get_prefs(self, parent):
        """
        If the plugin provides a prefs frame, create and return it.
        :param parent: the parent frame for this preference tab.
        :return:
        """
        try:
            plugin_prefs = self._get_func('plugin_prefs')
            return plugin_prefs and plugin_prefs(parent)
        except:
            print_exc()
            return None


def load_plugins():
    """
    Find and load all plugins
    :return:
    """
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
        if name[0] == '.':
            pass
        elif name.endswith('.disabled'):
            name, discard = name.rsplit('.', 1)
            found.append(Plugin(name, None))
        else:
            try:
                found.append(Plugin(name, os.path.join(config.plugin_dir, name, 'load.py')))
            except:
                print_exc()
    PLUGINS.extend(sorted(found, key = lambda p: operator.attrgetter('name')(p).lower()))

    imp.release_lock()


def notify_prefs_changed():
    """
    Notify each plugin that the settings dialog has been closed.
    :return:
    """
    for plugin in PLUGINS:
        prefs_changed = plugin._get_func('prefs_changed')
        if prefs_changed:
            try:
                prefs_changed()
            except:
                print_exc()


def notify_journal_entry(cmdr, system, station, entry, cmdr_state):
    """
    Send a journal entry to each plugin.
    :param cmdr: The Cmdr name, or None if not yet known
    :param system: The current system, or None if not yet known
    :param station: The current station, or None if not docked or not yet known
    :param entry: The journal entry as a dictionary
    :param cmdr_state: A dictionary containing info about the Cmdr, current ship and cargo
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        journal_entry = plugin._get_func('journal_entry')
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                if journal_entry.func_code.co_argcount == 4:
                    error = error or journal_entry(cmdr, system, station, dict(entry))
                else:
                    error = error or journal_entry(cmdr, system, station, dict(entry), dict(cmdr_state))
            except:
                print_exc()
    return error


def notify_interaction(cmdr, entry):
    """
    Send an interaction entry to each plugin.
    :param cmdr: The piloting Cmdr name
    :param entry: The interaction entry as a dictionary
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        interaction = plugin._get_func('interaction')
        if interaction:
            try:
                # Pass a copy of the interaction entry in case the callee modifies it
                error = error or interaction(cmdr, dict(entry))
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


def notify_newdata(data):
    """
    Send the latest EDMC data from the FD servers to each plugin
    :param data:
    :return: Error message from the first plugin that returns one (if any)
    """
    error = None
    for plugin in PLUGINS:
        cmdr_data = plugin._get_func('cmdr_data')
        if cmdr_data:
            try:
                error = error or cmdr_data(data)
            except:
                print_exc()
    return error
