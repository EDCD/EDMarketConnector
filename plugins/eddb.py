"""Station display and eddb.io lookup."""
# Tests:
#
# As there's a lot of state tracking in here, need to ensure (at least)
# the URL text and link follow along correctly with:
#
#  1) Game not running, EDMC started.
#  2) Then hit 'Update' for CAPI data pull
#  3) Login fully to game, and whether #2 happened or not:
#      a) If docked then update Station
#      b) Either way update System
#  4) Undock, SupercruiseEntry, FSDJump should change Station text to 'x'
#    and link to system one.
#  5) RequestDocking should populate Station, no matter if the request
#    succeeded or not.
#  6) FSDJump should update System text+link.
#  7) Switching to a different provider and then back... combined with
#    any of the above in the interim.
#


# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
#
# This is an EDMC 'core' plugin.
#
# All EDMC plugins are *dynamically* loaded at run-time.
#
# We build for Windows using `py2exe`.
#
# `py2exe` can't possibly know about anything in the dynamically loaded
# core plugins.
#
# Thus you **MUST** check if any imports you add in this file are only
# referenced in this file (or only in any other core plugin), and if so...
#
#     YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
#     `Build-exe-and-msi.py` SO AS TO ENSURE THE FILES ARE ACTUALLY PRESENT IN
#     AN END-USER INSTALLATION ON WINDOWS.
#
#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
import tkinter
from typing import TYPE_CHECKING, Any, Mapping

import requests

import EDMCLogging
import killswitch
import plug
from companion import CAPIData
from config import appname, config

if TYPE_CHECKING:
    from tkinter import Tk

    def _(x: str) -> str:
        return x

logger = EDMCLogging.get_main_logger()


class This:
    """Holds module globals."""

    STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7

    def __init__(self) -> None:
        # Main window clicks
        self.system_link: tkinter.Widget
        self.system_name: str | None = None
        self.system_address: str | None = None
        self.system_population: int | None = None
        self.station_link: tkinter.Widget
        self.station: str | None = None
        self.station_marketid: int | None = None
        self.on_foot = False


this = This()


def system_url(system_name: str) -> str:
    """
    Construct an appropriate EDDB.IO URL for the provided system.

    :param system_name: Will be overridden with `this.system_address` if that
      is set.
    :return: The URL, empty if no data was available to construct it.
    """
    if this.system_address:
        return requests.utils.requote_uri(f'https://eddb.io/system/ed-address/{this.system_address}')

    if system_name:
        return requests.utils.requote_uri(f'https://eddb.io/system/name/{system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    """
    Construct an appropriate EDDB.IO URL for a station.

    Ignores `station_name` in favour of `this.station_marketid`.

    :param system_name: Name of the system the station is in.
    :param station_name: **NOT USED**
    :return: The URL, empty if no data was available to construct it.
    """
    if this.station_marketid:
        return requests.utils.requote_uri(f'https://eddb.io/station/market-id/{this.station_marketid}')

    return system_url(system_name)


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: NAme of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
    return 'eddb'


def plugin_app(parent: 'Tk'):
    """
    Construct this plugin's main UI, if any.

    :param parent: The tk parent to place our widgets into.
    :return: See PLUGINS.md#display
    """
    # system label in main window
    this.system_link = parent.nametowidget(f".{appname.lower()}.system")
    this.system_name = None
    this.system_address = None
    this.station = None
    this.station_marketid = None  # Frontier MarketID
    # station label in main window
    this.station_link = parent.nametowidget(f".{appname.lower()}.station")
    this.station_link['popup_copy'] = lambda x: x != this.STATION_UNDOCKED


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Update any saved configuration after Settings is closed.

    :param cmdr: Name of Commander.
    :param is_beta: If game beta was detected.
    """
    # Do *NOT* set 'url' here, as it's set to a function that will call
    # through correctly.  We don't want a static string.
    pass


def journal_entry(  # noqa: CCR001
    cmdr: str, is_beta: bool, system: str, station: str,
    entry: dict[str, Any],
    state: Mapping[str, Any]
):
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
    should_return: bool
    new_entry: dict[str, Any] = {}

    should_return, new_entry = killswitch.check_killswitch('plugins.eddb.journal', entry)
    if should_return:
        # LANG: Journal Processing disabled due to an active killswitch
        plug.show_error(_('EDDB Journal processing disabled. See Log.'))
        return

    should_return, new_entry = killswitch.check_killswitch(f'plugins.eddb.journal.event.{entry["event"]}', new_entry)
    if should_return:
        return

    this.on_foot = state['OnFoot']
    this.system_address = state['SystemAddress']
    this.system_name = state['SystemName']

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName') or this.station
    # on_foot station detection
    if entry['event'] == 'Location' and entry['BodyType'] == 'Station':
        this.station = entry['Body']

    this.station_marketid = entry.get('MarketID') or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if entry['event'] in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    if entry['event'] == 'Embark' and not entry.get('OnStation'):
        # If we're embarking OnStation to a Taxi/Dropship we'll also get an
        # Undocked event.
        this.station = None
        this.station_marketid = None

    # Only actually change URLs if we are current provider.
    if config.get_str('system_provider') == 'eddb':
        this.system_link['text'] = this.system_name
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    # But only actually change the URL if we are current station provider.
    if config.get_str('station_provider') == 'eddb':
        text = this.station
        if not text:
            if this.system_population is not None and this.system_population > 0:
                text = this.STATION_UNDOCKED

            else:
                text = ''

        this.station_link['text'] = text
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()


def cmdr_data(data: CAPIData, is_beta: bool) -> str | None:
    """
    Process new CAPI data.

    :param data: The latest merged CAPI data.
    :param is_beta: Whether game beta was detected.
    :return: Optional error string.
    """
    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid and data['commander']['docked']:
        this.station_marketid = data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    if not this.system_name:
        this.system_name = data['lastSystem']['name']

    if not this.station and data['commander']['docked']:
        this.station = data['lastStarport']['name']

    # Override standard URL functions
    if config.get_str('system_provider') == 'eddb':
        this.system_link['text'] = this.system_name
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'eddb':
        if data['commander']['docked'] or this.on_foot and this.station:
            this.station_link['text'] = this.station

        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = this.STATION_UNDOCKED

        else:
            this.station_link['text'] = ''

        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()

    return ''
