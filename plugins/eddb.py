# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#


import cPickle
import csv
import os
from os.path import dirname, join, normpath
import sys

import Tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel

from config import config


STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

this = sys.modules[__name__]	# For holding module globals
this.system = None	# name of current system

with open(join(config.respath, 'systems.p'),  'rb') as h:
    this.system_ids  = cPickle.load(h)

with open(join(config.respath, 'stations.p'), 'rb') as h:
    this.station_ids = cPickle.load(h)


# system_name -> system_id or 0
def system_id(system_name):
    return this.system_ids.get(system_name, 0)	# return 0 on failure (0 is not a valid id)

# (system_name, station_name) -> station_id or 0
def station_id(system_name, station_name):
    return this.station_ids.get((this.system_ids.get(system_name), station_name), 0)

def station_url(text):
    if text:
        station = station_id(this.system, text)
        if station:
            return 'https://eddb.io/station/%d' % station

        system = system_id(this.system)
        if system:
            return 'https://eddb.io/system/%d' % system

    return None


def plugin_start():
    return '~eddb'

def plugin_app(parent):
    this.station_label = tk.Label(parent, text = _('Station') + ':')	# Main window
    this.station = HyperlinkLabel(parent, url = station_url, popup_copy = lambda x: x != STATION_UNDOCKED)
    return (this.station_label, this.station)

def prefs_changed(cmdr, is_beta):
    this.station_label['text'] = _('Station') + ':'

def journal_entry(cmdr, is_beta, system, station, entry, state):
    this.system = system
    this.station['text'] = station or (system_id(system) and STATION_UNDOCKED or '')

def cmdr_data(data, is_beta):
    this.system = data['lastSystem']['name']
    this.station['text'] = data['commander']['docked'] and data['lastStarport']['name'] or (system_id(data['lastSystem']['name']) and STATION_UNDOCKED or '')
