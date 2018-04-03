# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

import cPickle
import csv
import os
from os.path import join
import sys

from config import config


STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals

with open(join(config.respath, 'systems.p'),  'rb') as h:
    this.system_ids  = cPickle.load(h)

with open(join(config.respath, 'stations.p'), 'rb') as h:
    this.station_ids = cPickle.load(h)


# Main window clicks
def station_url(system_name, station_name):
    if station_id(system_name, station_name):
        return 'https://eddb.io/station/%d' % station_id(system_name, station_name)
    elif system_id(system_name):
        return 'https://eddb.io/system/%d' % system_id(system_name)
    else:
        return None

# system_name -> system_id or 0
def system_id(system_name):
    return this.system_ids.get(system_name, 0)	# return 0 on failure (0 is not a valid id)

# (system_name, station_name) -> station_id or 0
def station_id(system_name, station_name):
    return this.station_ids.get((this.system_ids.get(system_name), station_name), 0)


def plugin_start():
    return 'eddb'

def plugin_app(parent):
    this.station = parent.children['station']	# station label in main window
    this.station.configure(popup_copy = lambda x: x != STATION_UNDOCKED)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    this.system = system
    this.station['text'] = station or (system_id(system) and STATION_UNDOCKED or '')
    this.station.update_idletasks()

def cmdr_data(data, is_beta):
    this.system = data['lastSystem']['name']
    this.station['text'] = data['commander']['docked'] and data['lastStarport']['name'] or (system_id(data['lastSystem']['name']) and STATION_UNDOCKED or '')
    this.station.update_idletasks()
