"""
edastro_core.py - Exporting Data to EDAstro.

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

import json
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


class This:
    """Holds module globals."""

    app_name = "EDAstro"
    edastro_push = "https://edastro.com/api/journal"

    event_filters = {
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
            "BodyID"
            "DepartureTime"
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

    def __init__(self):
        self.log: tk.IntVar | None = None
        self.log_button: ttk.Checkbutton | None = None


this = This()


def set_config_first_run() -> None:
    """Enable EDAstro if the config key does not exist."""
    if config.get_int("edastro_send", default=None) is None:
        logger.info("EDAstro First Run. Enabling")
        config.set("edastro_send", 1)


# Plugin callbacks
def plugin_start3(plugin_dir: str) -> str:
    """
    Start this plugin.

    :param plugin_dir: `str` - The full path to this plugin's directory.
    :return: `str` - Name of this plugin to use in UI.
    """
    set_config_first_run()
    return "EDAstro"


def plugin_prefs(parent, cmdr: str, is_beta: bool) -> nb.Frame:
    """
    Set up Preferences pane for this plugin.

    :param parent: tkinter parent to attach to.
    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :return: The tkinter frame we created.
    """
    edastroframe = nb.Frame(parent)
    edastroframe.columnconfigure(0, weight=1)

    cur_row = 0
    HyperlinkLabel(
        edastroframe,
        text="Elite Dangerous Astronomy",
        background=nb.Label().cget("background"),
        url="https://edastro.com",
        underline=True,
    ).grid(
        row=cur_row, padx=PADX, pady=PADY, sticky=tk.W
    )  # Don't translate
    cur_row += 1
    this.log = tk.IntVar(value=config.get_int("edastro_send") and 1)
    this.log_button = nb.Checkbutton(
        edastroframe,
        # LANG: Settings>EDAstro - Label on checkbox for 'send data'
        text=tr.tl("Send data to EDAstro"),
        variable=this.log,
    )
    if this.log_button:
        this.log_button.grid(
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
    if this.log:
        config.set("edastro_send", this.log.get())


def filter_event_data(entry) -> dict[str, Any]:
    """Format Journal Data for EDAstro."""
    if entry["event"] in this.event_filters:
        return {
            key: entry[key]
            for key in this.event_filters[entry["event"]]
            if key in entry
        }
    return entry


def edastro_update(system, entry, state):
    """Send a processed event to EDAstro."""
    event_name = str(entry["event"])
    filtered_entry = filter_event_data(entry)
    app_header = {
        "appName": this.app_name,
        "odyssey": state.get("Odyssey"),
        "system": system,
    }
    event_object = [app_header, filtered_entry]
    event_data = json.dumps(event_object)
    try:
        json_header = {"Content-Type": "application/json"}
        response = requests.post(
            url=this.edastro_push, headers=json_header, data=event_data, timeout=20
        )
        if response.status_code == 200:
            edastro = json.loads(response.text)
            if str(edastro["status"]) == "200" or str(edastro["status"]) == "401":
                # 200 = at least one event accepted, 401 = none were accepted, but no errors either
                logger.info(f"EDAstro: Data sent! ({event_name})")
            else:
                logger.debug(
                    f"Error Response:\nRequest: {this.edastro_push}\n "
                    f'Response ({edastro["status"]}): \n{edastro["message"]}'
                )
        else:
            logger.debug(
                f"Unexpected Response:\nRequest: {this.edastro_push}\n "
                f"Response ({response.status_code}):\n{response.text}"
            )
    except Exception as ex:
        logger.warning(
            f"Failed to submit EDAstro data:\nRequest: {this.edastro_push}",
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
    if this.log and entry["event"] in ["CarrierStats", "CarrierJumpRequest", "ScanOrganic"]:
        edastro_update(system, entry, state)

    return None
