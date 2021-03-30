# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

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


import sys
from typing import TYPE_CHECKING, Any, Optional

import requests

import EDMCLogging
import killswitch
import plug
from companion import CAPIData
from config import config

if TYPE_CHECKING:
    from tkinter import Tk


logger = EDMCLogging.get_main_logger()


STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7

this: Any = sys.modules[__name__]  # For holding module globals

# Main window clicks
this.system_link: Optional[str] = None
this.system: Optional[str] = None
this.system_address: Optional[str] = None
this.system_population: Optional[int] = None
this.station_link: 'Optional[Tk]' = None
this.station: Optional[str] = None
this.station_marketid: Optional[int] = None
this.on_foot = False


def system_url(system_name: str) -> str:
    if this.system_address:
        return requests.utils.requote_uri(f'https://eddb.io/system/ed-address/{this.system_address}')

    if system_name:
        return requests.utils.requote_uri(f'https://eddb.io/system/name/{system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    if this.station_marketid:
        return requests.utils.requote_uri(f'https://eddb.io/station/market-id/{this.station_marketid}')

    return system_url(system_name)


def plugin_start3(plugin_dir):
    return 'eddb'


def plugin_app(parent: 'Tk'):
    this.system_link = parent.children['system']  # system label in main window
    this.system = None
    this.system_address = None
    this.station = None
    this.station_marketid = None  # Frontier MarketID
    this.station_link = parent.children['station']  # station label in main window
    this.station_link.configure(popup_copy=lambda x: x != STATION_UNDOCKED)


def prefs_changed(cmdr, is_beta):
    # Do *NOT* set 'url' here, as it's set to a function that will call
    # through correctly.  We don't want a static string.
    pass


def journal_entry(cmdr, is_beta, system, station, entry, state):
    if (ks := killswitch.get_disabled('plugins.eddb.journal')).disabled:
        logger.warning(f'Journal processing for EDDB has been disabled: {ks.reason}')
        plug.show_error('EDDB Journal processing disabled. See Log')
        return

    elif (ks := killswitch.get_disabled(f'plugins.eddb.journal.event.{entry["event"]}')).disabled:
        logger.warning(f'Processing of event {entry["event"]} has been disabled: {ks.reason}')
        return

    this.on_foot = state['on_foot']
    # Always update our system address even if we're not currently the provider for system or station, but dont update
    # on events that contain "future" data, such as FSDTarget
    if entry['event'] in ('Location', 'Docked', 'CarrierJump', 'FSDJump'):
        this.system_address = entry.get('SystemAddress') or this.system_address
        this.system = entry.get('StarSystem') or this.system

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName') or this.station
    # on_foot station detection
    if not this.station and entry['event'] == 'Location' and entry['BodyType'] == 'Station':
        this.station = entry['Body']

    this.station_marketid = entry.get('MarketID') or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if entry['event'] in ('Undocked', 'FSDJump', 'SupercruiseEntry', 'Embark'):
        this.station = None
        this.station_marketid = None

    # Only actually change URLs if we are current provider.
    if config.get_str('system_provider') == 'eddb':
        this.system_link['text'] = this.system
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    # But only actually change the URL if we are current station provider.
    if config.get_str('station_provider') == 'eddb':
        text = this.station
        if not text:
            if this.system_population is not None and this.system_population > 0:
                text = STATION_UNDOCKED

            else:
                text = ''

        this.station_link['text'] = text
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()


def cmdr_data(data: CAPIData, is_beta):
    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid and data['commander']['docked']:
        this.station_marketid = data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    if not this.system:
        this.system = data['lastSystem']['name']

    if not this.station and data['commander']['docked']:
        this.station = data['lastStarport']['name']

    # Override standard URL functions
    if config.get_str('system_provider') == 'eddb':
        this.system_link['text'] = this.system
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'eddb':
        if data['commander']['docked'] or this.on_foot and this.station:
            this.station_link['text'] = this.station

        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED

        else:
            this.station_link['text'] = ''

        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()
