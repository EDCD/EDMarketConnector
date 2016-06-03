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
    :return:
    """
    sys.stderr.write("example plugin started\n")	# appears in %TMP%/EDMarketConnector.log in packaged Windows app


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


def system_changed(timestamp, system, coordinates):
    """
    Arrived in a new System
    :param timestamp: when we arrived
    :param system: the name of the system
    :param coordinates: tuple of (x,y,z) ly relative to Sol, or None if unknown
    :return:
    """
    if coordinates:
        sys.stderr.write("Arrived at {} ({},{},{})\n".format(system, *coordinates))
    else:
        sys.stderr.write("Arrived at {}\n".format(system))


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

