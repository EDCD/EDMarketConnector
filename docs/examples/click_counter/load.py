"""
Example EDMC plugin.

It adds a single button to the EDMC interface that displays the number of times it has been clicked.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from config import appname, config
from myNotebook import EntryMenu

# This **MUST** match the name of the folder the plugin is in.
PLUGIN_NAME = "click_counter"

logger = logging.getLogger(f"{appname}.{PLUGIN_NAME}")


class ClickCounter:
    """
    ClickCounter implements the EDMC plugin interface.

    It adds a button to the EDMC UI that displays the number of times it has been clicked, and a preference to set
    the number directly.
    """

    def __init__(self) -> None:
        # Be sure to use names that wont collide in our config variables
        self.click_count = tk.StringVar(value=str(config.get_int('click_counter_count')))
        logger.info("ClickCounter instantiated")

    def on_load(self) -> str:
        """
        on_load is called by plugin_start3 below.

        It is the first point EDMC interacts with our code after loading our module.

        :return: The name of the plugin, which will be used by EDMC for logging and for the settings window
        """
        return PLUGIN_NAME

    def on_unload(self) -> None:
        """
        on_unload is called by plugin_stop below.

        It is the last thing called before EDMC shuts down. Note that blocking code here will hold the shutdown process.
        """
        self.on_preferences_closed("", False)  # Save our prefs

    def setup_preferences(self, parent: ttk.Notebook, cmdr: str, is_beta: bool) -> ttk.Frame | None:
        """
        setup_preferences is called by plugin_prefs below.

        It is where we can setup our own settings page in EDMC's settings window. Our tab is defined for us.

        :param parent: the tkinter parent that our returned Frame will want to inherit from
        :param cmdr: The current ED Commander
        :param is_beta: Whether or not EDMC is currently marked as in beta mode
        :return: The frame to add to the settings window
        """
        current_row = 0
        frame = ttk.Frame(parent)

        # setup our config in a "Click Count: number"
        ttk.Label(frame, text='Click Count').grid(row=current_row)
        EntryMenu(frame, textvariable=self.click_count).grid(row=current_row, column=1)
        current_row += 1  # Always increment our row counter, makes for far easier tkinter design.
        return frame

    def on_preferences_closed(self, cmdr: str, is_beta: bool) -> None:
        """
        on_preferences_closed is called by prefs_changed below.

        It is called when the preferences dialog is dismissed by the user.

        :param cmdr: The current ED Commander
        :param is_beta: Whether or not EDMC is currently marked as in beta mode
        """
        # You need to cast to `int` here to store *as* an `int`, so that
        # `config.get_int()` will work for re-loading the value.
        config.set('click_counter_count', int(self.click_count.get()))

    def setup_main_ui(self, parent: ttk.Frame) -> ttk.Frame:
        """
        Create our entry on the main EDMC UI.

        This is called by plugin_app below.

        :param parent: EDMC main window Tk
        :return: Our frame
        """
        current_row = 0
        frame = ttk.Frame(parent)
        button = ttk.Button(
            frame,
            text="Count me",
            command=lambda: self.click_count.set(str(int(self.click_count.get()) + 1))
        )
        button.grid(row=current_row)
        current_row += 1
        ttk.Label(frame, text="Count:").grid(row=current_row, sticky=tk.W)
        ttk.Label(frame, textvariable=self.click_count).grid(row=current_row, column=1)
        return frame


cc = ClickCounter()


# Note that all of these could be simply replaced with something like:
# plugin_start3 = cc.on_load
def plugin_start3(plugin_dir: str) -> str:
    """
    Handle start up of the plugin.

    See PLUGINS.md#startup
    """
    return cc.on_load()


def plugin_stop() -> None:
    """
    Handle shutdown of the plugin.

    See PLUGINS.md#shutdown
    """
    return cc.on_unload()


def plugin_prefs(parent: ttk.Notebook, cmdr: str, is_beta: bool) -> ttk.Frame | None:
    """
    Handle preferences tab for the plugin.

    See PLUGINS.md#configuration
    """
    return cc.setup_preferences(parent, cmdr, is_beta)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle any changed preferences for the plugin.

    See PLUGINS.md#configuration
    """
    return cc.on_preferences_closed(cmdr, is_beta)


def plugin_app(parent: ttk.Frame) -> ttk.Frame | None:
    """
    Set up the UI of the plugin.

    See PLUGINS.md#display
    """
    return cc.setup_main_ui(parent)
