#!/usr/bin/python
#
# eddb.io station database
#

import cPickle
import os
from os.path import dirname, join, normpath
import sys
from sys import platform

from config import config

class EDDB:

    HAS_MARKET = 1
    HAS_OUTFITTING = 2
    HAS_SHIPYARD = 4

    def __init__(self):
        self.system_ids  = cPickle.load(open(join(config.respath, 'systems.p'),  'rb'))
        self.station_ids = cPickle.load(open(join(config.respath, 'stations.p'), 'rb'))

    # system_name -> system_id or 0
    def system(self, system_name):
        return self.system_ids.get(system_name, 0)	# return 0 on failure (0 is not a valid id)

    # (system_name, station_name) -> (station_id, has_market, has_outfitting, has_shipyard)
    def station(self, system_name, station_name):
        (station_id, flags) = self.station_ids.get((self.system_ids.get(system_name), station_name), (0,0))
        return (station_id, bool(flags & EDDB.HAS_MARKET), bool(flags & EDDB.HAS_OUTFITTING), bool(flags & EDDB.HAS_SHIPYARD))


#
# build databases from files systems_populated.json and stations.json from http://eddb.io/api
#
if __name__ == "__main__":
    import json

    # system_name by system_id
    systems  = dict([(x['id'], str(x['name'])) for x in json.load(open('systems_populated.json'))])

    stations = json.load(open('stations.json'))

    # check that all populated systems have known coordinates
    coords = dict([(x['id'], x['x'] or x['y'] or x['z']) for x in json.load(open('systems_populated.json'))])
    for x in stations:
        assert x['system_id'] == 17072 or coords[x['system_id']], (x['system_id'], systems[x['system_id']])

    # system_id by system_name - populated systems only
    system_ids = dict([(systems[x['system_id']], x['system_id']) for x in stations])
    cPickle.dump(system_ids,  open('systems.p',  'wb'), protocol = cPickle.HIGHEST_PROTOCOL)

    # station_id by (system_id, station_name)
    station_ids = dict([(
        (x['system_id'], str(x['name'])),
        (x['id'],
         (EDDB.HAS_MARKET     if x['has_market']     else 0) |
         (EDDB.HAS_OUTFITTING if x['has_outfitting'] else 0) |
         (EDDB.HAS_SHIPYARD   if x['has_shipyard']   else 0)))
                        for x in stations])
    cPickle.dump(station_ids, open('stations.p', 'wb'), protocol = cPickle.HIGHEST_PROTOCOL)
