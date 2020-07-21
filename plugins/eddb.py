# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

import sys

from config import config


STATION_UNDOCKED: str = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals

this.system_address = None
this.system_population = None
this.station_marketid = None  # Frontier MarketID

# Main window clicks
def system_url(system_name: str) -> str:
    if this.system_address:
        return 'https://eddb.io/system/ed-address/{}'.format(this.system_address)
    elif system_name:
        return 'https://eddb.io/system/name/{}'.format(system_name)
    else:
        return ''

def station_url(system_name: str, station_name: str) -> str:
    if this.station_marketid:
        return 'https://eddb.io/station/market-id/{}'.format(this.station_marketid)
    else:
        return system_url('')

def plugin_start3(plugin_dir):
    return 'eddb'

def plugin_app(parent):
    this.system_link  = parent.children['system']  # system label in main window
    this.system_address = None
    this.station_marketid = None  # Frontier MarketID
    this.station_link = parent.children['station']  # station label in main window
    this.station_link.configure(popup_copy = lambda x: x != STATION_UNDOCKED)

def prefs_changed(cmdr, is_beta):
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url('')  # Override standard URL function


def journal_entry(cmdr, is_beta, system, station, entry, state):
    # Always update, even if we're not the *current* system provider.
    this.system_address = entry.get('SystemAddress') or this.system_address
    # But only actually change the URL if we are current system provider.
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url('')  # Override standard URL function

    # Always update, even if we're not the *current* station provider.
    if entry['event'] in ['StartUp', 'Location', 'FSDJump', 'CarrierJump']:
        this.system_population = entry.get('Population')

    if entry['event'] in ['StartUp', 'Location', 'Docked', 'CarrierJump']:
        this.station_marketid = entry.get('MarketID')
    elif entry['event'] in ['Undocked']:
        this.station_marketid = None

    # But only actually change the URL if we are current station provider.
    if config.get('station_provider') == 'eddb':
        this.station_link['text'] = station or (this.system_population and this.system_population > 0 and STATION_UNDOCKED or '')
        this.station_link.update_idletasks()


def cmdr_data(data, is_beta):
    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid:
        this.station_marketid = data['commander']['docked'] and data['lastStarport']['id']
    # 'eddb' is also the *default* Station provider
    if not config.get('station_provider') or config.get('station_provider') == 'eddb':
        if data['commander']['docked']:
            this.station_link['text'] = data['lastStarport']['name']
        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED
        else:
            this.station_link['text'] = ''

        this.station_link.update_idletasks()
