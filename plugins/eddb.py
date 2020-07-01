# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

import pickle
import csv
import os
from os.path import join
import sys
import urllib.parse

from config import config


STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals

this.system_address = None
this.system_population = None
this.station_marketid = None  # Frontier MarketID

# Main window clicks
def system_url(system_address):
    if system_address:
        return 'https://eddb.io/system/ed-address/%s' % system_address
    else:
        return ''

def station_url(system_name, station_name):
    if this.station_marketid:
        return 'https://eddb.io/station/market-id/{}'.format(this.station_marketid)
    else:
        return system_url(this.system_address)

def plugin_start3(plugin_dir):
    return 'eddb'

def plugin_app(parent):
    this.system_link  = parent.children['system']	# system label in main window
    this.system_address = None
    this.station_marketid = None                        # Frontier MarketID
    this.station_link = parent.children['station']	# station label in main window
    this.station_link.configure(popup_copy = lambda x: x != STATION_UNDOCKED)

def prefs_changed(cmdr, is_beta):
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url(this.system_address)	# Override standard URL function


def journal_entry(cmdr, is_beta, system, station, entry, state):
    if config.get('system_provider') == 'eddb':
        this.system_address = entry.get('SystemAddress') or this.system_address
        this.system_link['url'] = system_url(this.system_address)	# Override standard URL function

    if config.get('station_provider') == 'eddb':
        if entry['event'] in ['StartUp', 'Location', 'FSDJump', 'CarrierJump']:
            this.system_population = entry.get('Population')

        if entry['event'] in ['StartUp', 'Location', 'Docked', 'CarrierJump']:
            this.station_marketid = entry.get('MarketID')
        elif entry['event'] in ['Undocked']:
            this.station_marketid = None

        this.station_link['text'] = station or (this.system_population and this.system_population > 0 and STATION_UNDOCKED or '')
        this.station_link.update_idletasks()


def cmdr_data(data, is_beta):
    if config.get('system_provider') == 'eddb':
        this.system_address = data['lastSystem']['id'] or this.system_address
        this.system_link['url'] = system_url(this.system_address)  # Override standard URL function

    if config.get('station_provider') == 'eddb':
        this.station_marketid = data['commander']['docked'] and data['lastStarport']['id']
        this.station_link['text'] = data['commander']['docked'] and data['lastStarport']['name'] or (data['lastStarport']['name'] and data['lastStarport']['name'] != "" and STATION_UNDOCKED or '')
        this.station_link.update_idletasks()
