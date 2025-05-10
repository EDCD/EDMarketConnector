"""
spansh_core.py - Spansh URL provider.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This is an EDMC 'core' plugin.
All EDMC plugins are *dynamically* loaded at run-time.

We build for Windows using `py2exe`.
`py2exe` can't possibly know about anything in the dynamically loaded core plugins.

Thus, you **MUST** check if any imports you add in this file are only
referenced in this file (or only in any other core plugin), and if so...

    YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
    `build.py` TO ENSURE THE FILES ARE ACTUALLY PRESENT
    IN AN END-USER INSTALLATION ON WINDOWS.
"""
# pylint: disable=import-error
from __future__ import annotations

import tkinter as tk
from typing import Any
import requests
from companion import CAPIData
from config import appname, config
from EDMCLogging import get_main_logger
from plugins.common_coreutils import (station_link_common, this_format_common,
                                      cmdr_data_initial_common, station_name_setter_common)

logger = get_main_logger()


class This:
    """Holds module globals."""

    def __init__(self):
        self.parent: tk.Tk
        self.shutting_down = False  # Plugin is shutting down.
        self.system_link: tk.Widget = None  # type: ignore
        self.system_name: str | None = None
        self.system_address: str | None = None
        self.system_population: int | None = None
        self.station_link: tk.Widget = None  # type: ignore
        self.station_name = None
        self.station_marketid = None
        self.on_foot = False


this = This()


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: Name of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
    return 'Spansh'


def plugin_app(parent: tk.Tk) -> None:
    """
    Construct this plugin's main UI, if any.

    :param parent: The tk parent to place our widgets into.
    :return: See PLUGINS.md#display
    """
    this.parent = parent
    this.system_link = parent.nametowidget(f".{appname.lower()}.system")
    this.station_link = parent.nametowidget(f".{appname.lower()}.station")


def plugin_stop() -> None:
    """Plugin shutdown hook."""
    this.shutting_down = True


def journal_entry(
    cmdr: str, is_beta: bool, system: str, station: str, entry: dict[str, Any], state: dict[str, Any]
) -> str:
    """
    Handle a new Journal event.

    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    :param system: Name of current tracked system.
    :param station: Name of current tracked station location.
    :param entry: The journal event.
    :param state: `monitor.state`
    :return: None if no error, else an error string.
    """
    this_format_common(this, state)

    # Only actually change URLs if we are current provider.
    if config.get_str('system_provider') == 'spansh':
        this.system_link['text'] = this.system_name
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'spansh':
        station_name_setter_common(this)
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()

    return ''


def cmdr_data(data: CAPIData, is_beta: bool) -> str | None:
    """
    Process new CAPI data.

    :param data: The latest merged CAPI data.
    :param is_beta: Whether game beta was detected.
    :return: Optional error string.
    """
    cmdr_data_initial_common(this, data)

    # Override standard URL functions
    if config.get_str('system_provider') == 'spansh':
        this.system_link['text'] = this.system_name
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()
    if config.get_str('station_provider') == 'spansh':
        station_link_common(data, this)
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()

    return ''


def system_url(system_name: str) -> str:
    """
    Construct an appropriate spansh URL for the provided system.

    :param system_name: Will be overridden with `this.system_address` if that
      is set.
    :return: The URL, empty if no data was available to construct it.
    """
    if this.system_address:
        return requests.utils.requote_uri(f'https://www.spansh.co.uk/system/{this.system_address}')

    if system_name:
        return requests.utils.requote_uri(f'https://www.spansh.co.uk/search/{system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    """
    Construct an appropriate spansh URL for a station.

    Ignores `station_name` in favour of `this.station_marketid`.

    :param system_name: Name of the system the station is in.
    :param station_name: **NOT USED**
    :return: The URL, empty if no data was available to construct it.
    """
    if this.station_marketid:
        return requests.utils.requote_uri(f'https://www.spansh.co.uk/station/{this.station_marketid}')

    if system_name:
        return system_url(system_name)

    return ''
