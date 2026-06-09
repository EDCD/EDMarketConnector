"""
edastro_core.py - Exporting Data to EDAstro.

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

from typing import Any
from tkinter import ttk
import requests
import tkinter as tk
from l10n import translations as tr
from config import config
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb  # noqa: N813
from EDMCLogging import get_main_logger

from plugins.common_coreutils import PADX, PADY, BUTTONX

logger = get_main_logger()

# Module-level globals (Replacing the "This" class architecture)
APP_NAME = "EDAstro"
EDASTRO_PUSH = "https://edastro.com/api/journal"

LOG_ENABLED_VAR: tk.BooleanVar | None = None
LOG_BUTTON: ttk.Checkbutton | None = None

EVENT_FILTERS: dict[str, list[str]] = {
    "CarrierStats": [
        "timestamp",
        "event",
        "Callsign",
        "Name",
        "CarrierID",
        "AllowNotorious",
        "PendingDecommission",
        "DockingAccess",
        "FuelLevel",
        "Crew",
    ],
    "CarrierJumpRequest": [
        "timestamp",
        "event",
        "SystemName",
        "SystemAddress",
        "CarrierID",
        "Body",
        "BodyID",
        "DepartureTime",
    ],
    "ScanOrganic": [
        "timestamp",
        "ScanType",
        "Genus_Localised",
        "Species_Localised",
        "Genus",
        "event",
        "Body",
        "Species",
        "Variant",
        "SystemAddress",
        "Variant_Localised",
    ]
}


def set_config_first_run() -> None:
    """Enable EDAstro if the config key does not exist."""
    if config.get_bool("edastro_send") is None:
        logger.info("EDAstro First Run. Enabling")
        config.set("edastro_send", True)


# Plugin callbacks
def plugin_start3(plugin_dir: str) -> str:
    """
    Start this plugin.

    :param plugin_dir: `str` - The full path to this plugin's directory.
    :return: `str` - Name of this plugin to use in UI.
    """
    set_config_first_run()
    return "EDAstro"


def plugin_app(parent: tk.Tk) -> None:
    """
    Set up any plugin-specific UI.

    In this case we only create the tkinter variable for the user setting
    since this can only be done after the root tk.Tk object is created.

    :param parent: tkinter parent frame.
    :return: See PLUGINS.md#display
    """
    global LOG_ENABLED_VAR
    LOG_ENABLED_VAR = tk.BooleanVar(value=config.get_bool("edastro_send"))


def plugin_prefs(parent: Any, cmdr: str, is_beta: bool) -> nb.Frame:
    """
    Set up Preferences pane for this plugin.

    :param parent: tkinter parent to attach to.
    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :return: The tkinter frame we created.
    """
    global LOG_BUTTON
    edastroframe = nb.Frame(parent)
    edastroframe.columnconfigure(0, weight=1)

    cur_row = 0
    HyperlinkLabel(
        edastroframe,
        text="Elite Dangerous Astronomy",
        background=nb.Label().cget("background"),
        url="https://edastro.com",
        underline=True,
    ).grid(row=cur_row, padx=PADX, pady=PADY, sticky=tk.W)  # Don't translate

    cur_row += 1
    LOG_BUTTON = nb.Checkbutton(
        edastroframe,
        # LANG: Settings>EDAstro - Label on checkbox for 'send data'
        text=tr.tl("Send data to EDAstro"),
        variable=LOG_ENABLED_VAR,
    )

    if LOG_BUTTON:
        LOG_BUTTON.grid(
            row=cur_row, columnspan=2, padx=BUTTONX, pady=PADY, sticky=tk.W
        )
        cur_row += 1

    return edastroframe


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle any changes to Settings once the dialog is closed.

    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    """
    if LOG_ENABLED_VAR:
        config.set("edastro_send", LOG_ENABLED_VAR.get())


def filter_event_data(entry: dict[str, Any]) -> dict[str, Any]:
    """Format Journal Data for EDAstro using specific element structures."""
    event_name = entry.get("event")
    if event_name in EVENT_FILTERS:
        allowed_keys = EVENT_FILTERS[event_name]
        return {key: entry[key] for key in allowed_keys if key in entry}
    return entry


def edastro_update(system: str, entry: dict[str, Any], state: dict[str, Any]) -> None:
    """Send a processed event to EDAstro."""
    event_name = str(entry.get("event", "UnknownEvent"))
    filtered_entry = filter_event_data(entry)

    app_header = {
        "appName": APP_NAME,
        "odyssey": state.get("Odyssey"),
        "system": system,
    }
    event_object = [app_header, filtered_entry]

    try:
        # Use requests json conversion instead of manual
        response = requests.post(
            url=EDASTRO_PUSH, json=event_object, timeout=20
        )

        if response.status_code == 200:
            edastro = response.json()
            status = edastro.get("status")

            if status in (200, "200", 401, "401"):
                # 200 = at least one event accepted, 401 = none were accepted, but no errors either
                logger.info(f"EDAstro: Data sent! ({event_name})")
            else:
                logger.debug(
                    f"Error Response:\nRequest: {EDASTRO_PUSH}\n "
                    f'Response ({status}): \n{edastro.get("message")}'
                )
        else:
            logger.debug(
                f"Unexpected Response:\nRequest: {EDASTRO_PUSH}\n "
                f"Response ({response.status_code}):\n{response.text}"
            )
    except Exception as ex:
        logger.warning(
            f"Failed to submit EDAstro data:\nRequest: {EDASTRO_PUSH}",
            exc_info=ex,
        )


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> str | None:
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
    if (
        LOG_ENABLED_VAR is not None
        and LOG_ENABLED_VAR.get()
        and entry.get("event") in EVENT_FILTERS
    ):
        edastro_update(system, entry, state)

    return None
