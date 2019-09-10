# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

from future import standard_library
standard_library.install_aliases()
import pickle
import csv
import os
from os.path import join
import sys

from config import config


STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals

# (system_id, is_populated) by system_name
with open(join(config.respath, 'systems.p'),  'rb') as h:
    this.system_ids  = pickle.load(h)

# station_id by (system_id, station_name)
with open(join(config.respath, 'stations.p'), 'rb') as h:
    this.station_ids = pickle.load(h)


# Main window clicks
def system_url(system_name):
    if system_id(system_name):
        return 'https://eddb.io/system/%d' % system_id(system_name)
    else:
        return None

def station_url(system_name, station_name):
    if station_id(system_name, station_name):
        return 'https://eddb.io/station/%d' % station_id(system_name, station_name)
    else:
        return system_url(system_name)

# system_name -> system_id or 0
def system_id(system_name):
    return this.system_ids.get(system_name, [0, False])[0]

# system_name -> is_populated
def system_populated(system_name):
    return this.system_ids.get(system_name, [0, False])[1]

# (system_name, station_name) -> station_id or 0
def station_id(system_name, station_name):
    return this.station_ids.get((system_id(system_name), station_name), 0)


def plugin_start():
    return 'eddb'

def plugin_app(parent):
    this.system_link  = parent.children['system']	# system label in main window
    this.station_link = parent.children['station']	# station label in main window
    this.station_link.configure(popup_copy = lambda x: x != STATION_UNDOCKED)

def prefs_changed(cmdr, is_beta):
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url(system_link['text'])	# Override standard URL function

def journal_entry(cmdr, is_beta, system, station, entry, state):
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url(system)	# Override standard URL function
    this.station_link['text'] = station or (system_populated(system) and STATION_UNDOCKED or '')
    this.station_link.update_idletasks()

def cmdr_data(data, is_beta):
    if config.get('system_provider') == 'eddb':
        this.system_link['url'] = system_url(data['lastSystem']['name'])	# Override standard URL function
    this.station_link['text'] = data['commander']['docked'] and data['lastStarport']['name'] or (system_populated(data['lastSystem']['name']) and STATION_UNDOCKED or '')
    this.station_link.update_idletasks()
