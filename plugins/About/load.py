"""
A Skeleton EDMC Plugin
"""
import sys
import ttk
import Tkinter as tk

from config import applongname, appversion
import myNotebook as nb


def plugin_start():
    """
    Start this plugin
    :return: Plugin name
    """
    sys.stderr.write("example plugin started\n")	# appears in %TMP%/EDMarketConnector.log in packaged Windows app
    return 'About'


def plugin_prefs(parent):
    """
    Return a TK Frame for adding to the EDMC settings dialog.
    """
    frame = nb.Frame(parent)

    nb.Label(frame, text="{NAME} {VER}".format(NAME=applongname, VER=appversion)).grid(sticky=tk.W)
    nb.Label(frame).grid()	# spacer
    nb.Label(frame, text="Fly Safe!").grid(sticky=tk.W)
    nb.Label(frame).grid()	# spacer

    if cmdr_data.last is not None:
        datalen = len(str(cmdr_data.last))
        nb.Label(frame, text="FD sent {} chars".format(datalen)).grid(sticky=tk.W)

    return frame


def plugin_app(parent):
    """
    Return a TK Widget for the EDMC main window.
    :param parent:
    :return:
    """
    plugin_app.status = tk.Label(parent, text="---")
    return plugin_app.status


def journal_entry(cmdr, system, station, entry):
    """
    E:D client made a journal entry
    :param cmdr: The Cmdr name, or None if not yet known
    :param system: The current system, or None if not yet known
    :param station: The current station, or None if not docked or not yet known
    :param entry: The journal entry as a dictionary
    :return:
    """
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        if 'StarPos' in entry:
            sys.stderr.write("Arrived at {} ({},{},{})\n".format(entry['StarSystem'], *tuple(entry['StarPos'])))
        else:
            sys.stderr.write("Arrived at {}\n".format(entry['StarSystem']))


def cmdr_data(data):
    """
    Obtained new data from Frontier about our commander, location and ships
    :param data:
    :return:
    """
    cmdr_data.last = data
    plugin_app.status['text'] = "Got new data ({} chars)".format(len(str(data)))
    sys.stderr.write("Got new data ({} chars)\n".format(len(str(data))))

cmdr_data.last = None

