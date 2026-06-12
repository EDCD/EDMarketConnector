"""
spansh_core.py - Spansh URL provider.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
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

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Any
from urllib.parse import quote
from companion import CAPIData
from config import appname, config
from EDMCLogging import get_main_logger
from plugins.common_coreutils import (station_link_common, this_format_common,
                                      cmdr_data_initial_common, station_name_setter_common)

logger = get_main_logger()

# Module-Level Application State Constants & Variables
IDENTIFIER = "Spansh"

PARENT_ROOT: tk.Tk | None = None
SHUTTING_DOWN: bool = False

SYSTEM_LINK: ttk.Widget | None = None
SYSTEM_NAME: str | None = None
SYSTEM_ADDRESS: int | str | None = None
SYSTEM_POPULATION: int | None = None

STATION_LINK: ttk.Widget | None = None
STATION_NAME: str | None = None
STATION_MARKETID: int | str | None = None
STATION_TYPE: str | None = None
ON_FOOT: bool = False

# Resolve module namespace reference once globally for common_coreutils compatibility
CURRENT_MODULE = sys.modules[__name__]


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: Name of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
    return IDENTIFIER


def plugin_app(parent: tk.Tk) -> None:
    """
    Construct this plugin's main UI, if any.

    :param parent: The tk parent to place our widgets into.
    """
    global PARENT_ROOT, SYSTEM_LINK, STATION_LINK

    PARENT_ROOT = parent
    base_path = f".{appname.lower()}"

    SYSTEM_LINK = parent.nametowidget(f"{base_path}.system")
    STATION_LINK = parent.nametowidget(f"{base_path}.station")


def plugin_stop() -> None:
    """Plugin shutdown hook."""
    global SHUTTING_DOWN
    SHUTTING_DOWN = True


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
    this_format_common(CURRENT_MODULE, state)

    # Only actually change URLs if we are the designated active provider.
    if config.get_str("system_provider") == "spansh" and SYSTEM_LINK:
        SYSTEM_LINK["text"] = SYSTEM_NAME
        # Do *NOT* set 'url' here, as it's set to a function that will call through correctly.
        SYSTEM_LINK.update_idletasks()

    if config.get_str("station_provider") == "spansh" and STATION_LINK:
        station_name_setter_common(CURRENT_MODULE)
        # Do *NOT* set 'url' here, as it's set to a function that will call through correctly.
        STATION_LINK.update_idletasks()

    return ""


def cmdr_data(data: CAPIData, is_beta: bool) -> str | None:
    """
    Process new CAPI data.

    :param data: The latest merged CAPI data.
    :param is_beta: Whether game beta was detected.
    :return: Optional error string.
    """
    cmdr_data_initial_common(CURRENT_MODULE, data)

    # Override standard URL labels if targeted
    if config.get_str("system_provider") == "spansh" and SYSTEM_LINK:
        SYSTEM_LINK["text"] = SYSTEM_NAME
        SYSTEM_LINK.update_idletasks()

    if config.get_str("station_provider") == "spansh" and STATION_LINK:
        station_link_common(data, CURRENT_MODULE)
        STATION_LINK.update_idletasks()

    return ""


def system_url(system_name: str) -> str:
    """
    Construct an appropriate spansh URL for the provided system.

    :param system_name: Name of the star system.
    :return: The URL, empty if no data was available to construct it.
    """
    if system_name:
        return f"https://www.spansh.co.uk/search/{quote(system_name)}"

    if SYSTEM_ADDRESS:
        return f"https://www.spansh.co.uk/system/{quote(str(SYSTEM_ADDRESS))}"

    return ""


def station_url(system_name: str, station_name: str) -> str:
    """
    Construct an appropriate spansh URL for a station.

    :param system_name: Name of the system the station is in.
    :param station_name: **NOT USED**
    :return: The URL, empty if no data was available to construct it.
    """
    if system_name:
        return system_url(system_name)

    if STATION_MARKETID:
        return f"https://www.spansh.co.uk/station/{quote(str(STATION_MARKETID))}"

    return ""
