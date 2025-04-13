"""
common_coreutils.py - Common Plugin Functions.

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

from typing import Any, Mapping, cast
import tkinter as tk
import base64
import gzip
import io
import json
import myNotebook as nb  # noqa: N813
from EDMCLogging import get_main_logger
from companion import CAPIData
from l10n import translations as tr

logger = get_main_logger()

# Global Padding Preferences
PADX = 10
BUTTONX = 12  # indent Checkbuttons and Radiobuttons
PADY = 1  # close spacing
BOXY = 2  # box spacing
SEPY = 10  # seperator line spacing
STATION_UNDOCKED = '×'  # "Station" name to display when not docked = U+00D7


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: NAme of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
    return 'CommonCoreUtils'


def api_keys_label_common(this, cur_row: int, frame: nb.Frame):
    """
    Prepare the box for API Key Loading. This is an EDMC Common Function.

    :param this: The module global from the calling module.
    :param cur_row: The current row in the calling module's config page.
    :param frame: The current frame in the calling module's config page.
    :return: The updated module global from the calling module.
    """
    # LANG: EDSM API key label
    this.apikey_label = nb.Label(frame, text=tr.tl('API Key'))
    this.apikey_label.grid(row=cur_row, padx=PADX, pady=PADY, sticky=tk.W)
    this.apikey = nb.EntryMenu(frame, show="*", width=50)
    this.apikey.grid(row=cur_row, column=1, padx=PADX, pady=BOXY, sticky=tk.EW)
    return this


def show_pwd_var_common(frame: nb.Frame, cur_row: int, this):
    """
    Allow unmasking of the API Key. This is an EDMC Common Function.

    :param cur_row: The current row in the calling module's config page.
    :param frame: The current frame in the calling module's config page.
    """
    show_password_var.set(False)  # Password is initially masked

    show_password_checkbox = nb.Checkbutton(
        frame,
        text=tr.tl('Show API Key'),  # LANG: Text EDSM Show API Key
        variable=show_password_var,
        command=lambda: toggle_password_visibility_common(this)
    )
    show_password_checkbox.grid(row=cur_row, columnspan=2, padx=BUTTONX, pady=PADY, sticky=tk.W)


# Return a URL for the current ship
def shipyard_url_common(loadout: Mapping[str, Any]) -> str:
    """
    Construct a URL for ship loadout. This is an EDMC Common Function.

    :param loadout: The ship loadout data.
    :return: The constructed URL for the ship loadout.
    """
    # Convert loadout to JSON and gzip compress it
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if not string:
        return ''

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    encoded_data = base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
    return encoded_data


def station_link_common(data: CAPIData, this):
    """
    Set the Staion Name. This is an EDMC Common Function.

    :param data: A CAPI Data Entry.
    :param this: The module global from the calling module.
    """
    if data['commander']['docked'] or this.on_foot and this.station_name:
        this.station_link['text'] = this.station_name
    elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
        this.station_link['text'] = STATION_UNDOCKED
    else:
        this.station_link['text'] = ''


def this_format_common(this, state: Mapping[str, Any]):
    """
    Gather Common 'This' Elements. This is an EDMC Common Function.

    :param this: The module global from the calling module.
    :param state: `monitor.state`.
    """
    this.system_address = state['SystemAddress']
    this.system_name = state['SystemName']
    this.system_population = state['SystemPopulation']
    this.station_name = state['StationName']
    this.station_marketid = state['MarketID']
    this.station_type = state['StationType']
    this.on_foot = state['OnFoot']


def toggle_password_visibility_common(this):
    """
    Toggle if the API Key is visible or not. This is an EDMC Common Function.

    :param this: The module global from the calling module.
    """
    if show_password_var.get():
        this.apikey.config(show="")  # type: ignore
    else:
        this.apikey.config(show="*")  # type: ignore


def station_name_setter_common(this):
    """
    Set the Station Name. This is an EDMC Common Function.

    :param this: The module global from the calling module.
    """
    to_set: str = cast(str, this.station_name)
    if not to_set:
        if this.system_population is not None and this.system_population > 0:
            to_set = STATION_UNDOCKED
        else:
            to_set = ''

    this.station_link['text'] = to_set


def cmdr_data_initial_common(this, data: CAPIData):
    """
    Set the common CMDR Data. This is an EDMC Common Function.

    :param this: The module global from the calling module.
    :param data: The latest merged CAPI data.
    """
    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid and data['commander']['docked']:
        this.station_marketid = data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    if not this.system_name:
        this.system_name = data['lastSystem']['name']
    if not this.station_name and data['commander']['docked']:
        this.station_name = data['lastStarport']['name']


show_password_var = tk.BooleanVar()
