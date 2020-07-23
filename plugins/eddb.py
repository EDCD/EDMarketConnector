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
import requests

from config import config


STATION_UNDOCKED: str = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals

# Main window clicks
this.system_link = None
this.system = None
this.system_address = None
this.system_population = None
this.station_link = None
this.station = None
this.station_marketid = None


def system_url(system_name: str) -> str:
    if this.system_address:
        return requests.utils.requote_uri(f'https://eddb.io/system/ed-address/{this.system_address}')
    elif system_name:
        return requests.utils.requote_uri(f'https://eddb.io/system/name/{system_name}')
    else:
        return ''

def station_url(system_name: str, station_name: str) -> str:
    if this.station_marketid:
        return requests.utils.requote_uri(f'https://eddb.io/station/market-id/{this.station_marketid}')
    else:
        return system_url('')

def plugin_start3(plugin_dir):
    return 'eddb'

def plugin_app(parent):
    this.system_link  = parent.children['system']  # system label in main window
    this.system = None
    this.system_address = None
    this.station = None
    this.station_marketid = None  # Frontier MarketID
    this.station_link = parent.children['station']  # station label in main window
    this.station_link.configure(popup_copy = lambda x: x != STATION_UNDOCKED)

def prefs_changed(cmdr, is_beta):
    # Override standard URL functions
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url(this.system)
    if config.get('station_provider') == 'eddb':
        this.station_link['url'] = station_url(this.system, this.station)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    # Always update, even if we're not the *current* system or station provider.
    this.system_address = entry.get('SystemAddress') or this.system_address
    this.system = entry.get('StarSystem') or this.system

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName') or this.station
    this.station_marketid = entry.get('MarketID') or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if entry['event'] in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    # Only actually change URLs if we are current provider.
    if config.get('system_provider') == 'eddb':
        this.system_link['text'] = this.system
        this.system_link['url'] = system_url(this.system)  # Override standard URL function
        this.system_link.update_idletasks()

    # But only actually change the URL if we are current station provider.
    if config.get('station_provider') == 'eddb':
        this.station_link['text'] = this.station or (this.system_population and this.system_population > 0 and STATION_UNDOCKED or '')
        this.station_link['url'] = station_url(this.system, this.station)  # Override standard URL function
        this.station_link.update_idletasks()


def cmdr_data(data, is_beta):
    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid:
        this.station_marketid = data['commander']['docked'] and data['lastStarport']['id']
    # Only trust CAPI if these aren't yet set
    this.system = this.system or data['lastSystem']['name']
    this.station = this.station or data['commander']['docked'] and data['lastStarport']['name']

    # Override standard URL functions
    if config.get('system_provider') == 'eddb':
        this.system_link['text'] = this.system
        this.system_link['url'] = system_url(this.system)
        this.system_link.update_idletasks()
    if config.get('station_provider') == 'eddb':
        if data['commander']['docked']:
            this.station_link['text'] = this.station
        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED
        else:
            this.station_link['text'] = ''

        this.station_link['url'] = station_url(this.system, this.station)
        this.station_link.update_idletasks()

