"""
Plugin hooks for EDMC - Ian Norton
"""
import os
import imp
import sys

from config import config

"""
Dictionary of loaded plugin modules.
"""
PLUGINS = dict()


def find_plugins():
    """
    Look for plugin entry points.
    :return:
    """
    found = dict()
    plug_folders = os.listdir(config.plugin_dir)
    for name in plug_folders:
        loadfile = os.path.join(config.plugin_dir, name, "load.py")
        if os.path.isfile(loadfile):
            found[name] = loadfile
    return found


def load_plugins():
    """
    Load all found plugins
    :return:
    """
    found = find_plugins()
    imp.acquire_lock()
    for plugname in found:
        try:
            with open(found[plugname], "rb") as plugfile:
                plugmod = imp.load_module(plugname, plugfile, found[plugname],
                                          (".py", "r", imp.PY_SOURCE))
                if "plugin_start" in dir(plugmod):
                    newname = plugmod.plugin_start()
                    PLUGINS[newname and unicode(newname) or plugname] = plugmod

        except Exception as plugerr:
            sys.stderr.write('%s: %s\n' % (plugname, plugerr))	# appears in %TMP%/EDMarketConnector.log in packaged Windows app

    imp.release_lock()


def _get_plugin_func(plugname, funcname):
    """
    Get a function from a plugin, else return None if it isn't implemented.
    :param plugname:
    :param funcname:
    :return:
    """
    if funcname in dir(PLUGINS[plugname]):
        return getattr(PLUGINS[plugname], funcname)
    return None


def get_plugin_app(plugname, parent):
    """
    If the plugin provides mainwindow content create and return it.
    :param plugname: name of the plugin
    :param parent: the parent frame for this entry.
    :return:
    """
    plugin_app = _get_plugin_func(plugname, "plugin_app")
    if plugin_app:
        return plugin_app(parent)
    return None


def get_plugin_prefs(plugname, parent):
    """
    If the plugin provides a prefs frame, create and return it.
    :param plugname: name of the plugin
    :param parent: the parent frame for this preference tab.
    :return:
    """
    plugin_prefs = _get_plugin_func(plugname, "plugin_prefs")
    if plugin_prefs:
        return plugin_prefs(parent)
    return None


def notify_prefs_changed():
    """
    Notify each plugin that the settings dialog has been closed.
    :return:
    """
    for plugname in PLUGINS:
        prefs_changed = _get_plugin_func(plugname, "prefs_changed")
        if prefs_changed:
            try:
                prefs_changed()
            except Exception as plugerr:
                print plugerr


def notify_journal_entry(cmdr, system, station, entry, state):
    """
    Send a journal entry to each plugin.
    :param cmdr: The Cmdr name, or None if not yet known
    :param system: The current system, or None if not yet known
    :param station: The current station, or None if not docked or not yet known
    :param entry: The journal entry as a dictionary
    :param state: A dictionary containing info about the Cmdr, current ship and cargo
    :return:
    """
    for plugname in PLUGINS:
        journal_entry = _get_plugin_func(plugname, "journal_entry")
        if journal_entry:
            try:
                # Pass a copy of the journal entry in case the callee modifies it
                if journal_entry.func_code.co_argcount == 4:
                    journal_entry(cmdr, system, station, dict(entry))
                else:
                    journal_entry(cmdr, system, station, dict(entry), dict(state))
            except Exception as plugerr:
                print plugerr


def notify_system_changed(timestamp, system, coordinates):
    """
    Send notification data to each plugin when we arrive at a new system.
    :param timestamp:
    :param system:
    :return:
    deprecated:: 2.2
    Use :func:`journal_entry` with the 'FSDJump' event.
    """
    for plugname in PLUGINS:
        system_changed = _get_plugin_func(plugname, "system_changed")
        if system_changed:
            try:
                if system_changed.func_code.co_argcount == 2:
                    system_changed(timestamp, system)
                else:
                    system_changed(timestamp, system, coordinates)
            except Exception as plugerr:
                print plugerr


def notify_newdata(data):
    """
    Send the latest EDMC data from the FD servers to each plugin
    :param data:
    :return:
    """
    for plugname in PLUGINS:
        cmdr_data = _get_plugin_func(plugname, "cmdr_data")
        if cmdr_data:
            try:
                cmdr_data(data)
            except Exception as plugerr:
                print plugerr
