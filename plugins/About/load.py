"""
A Skeleton EDMC Plugin
"""
import Tkinter as tk


def plugin_start():
    """
    Start this plugin
    :return:
    """
    print "example plugin started"


def plugin_prefs(parent):
    """
    Return a TK Frame for adding to the EDMC settings dialog.
    """
    prefs = tk.Frame(parent)
    prefs.columnconfigure(1, weight=1)
    prefs.rowconfigure(4, weight=1)

    tk.Label(prefs, text="Elite Dangerous Market Connector").grid(row=0, column=0, sticky=tk.W)
    tk.Label(prefs, text="Fly Safe!").grid(row=2, column=0, sticky=tk.W)

    if cmdr_data.last is not None:
        datalen = len(str(cmdr_data.last))
        tk.Label(prefs, text="FD sent {} chars".format(datalen)).grid(row=3, column=0, sticky=tk.W)

    return prefs


def plugin_app(parent):
    """
    Return a TK Frame for adding to the EDMC main window.
    :param parent:
    :return:
    """
    return None


def system_changed(timestamp, system):
    """
    Arrived in a new System
    :param timestamp: when we arrived
    :param system: the name of the system
    :return:
    """
    print "Arrived at {}".format(system)


def cmdr_data(data):
    """
    Obtained new data from Frontier about our commander, location and ships
    :param data:
    :return:
    """
    cmdr_data.last = data
    print "Got new data ({} chars)".format(len(str(data)))

cmdr_data.last = None

