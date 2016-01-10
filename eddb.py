#!/usr/bin/python
#
# eddb.io station database
#

import cPickle
import os
from os.path import dirname, join, normpath
import sys
from sys import platform

class EDDB:

    HAS_MARKET = 1
    HAS_OUTFITTING = 2
    HAS_SHIPYARD = 4

    def __init__(self):
        self.system_ids  = cPickle.load(open(join(self.respath(), 'systems.p'),  'rb'))
        self.station_ids = cPickle.load(open(join(self.respath(), 'stations.p'), 'rb'))

    # system_name -> system_id or 0
    def system(self, system_name):
        return self.system_ids.get(system_name, 0)	# return 0 on failure (0 is not a valid id)

    # (system_name, station_name) -> (station_id, has_market, has_outfitting, has_shipyard)
    def station(self, system_name, station_name):
        (station_id, flags) = self.station_ids.get((self.system_ids.get(system_name), station_name), (0,0))
        return (station_id, bool(flags & EDDB.HAS_MARKET), bool(flags & EDDB.HAS_OUTFITTING), bool(flags & EDDB.HAS_SHIPYARD))

    def respath(self):
        if getattr(sys, 'frozen', False):
            if platform=='darwin':
                return normpath(join(dirname(sys.executable), os.pardir, 'Resources'))
            else:
                return dirname(sys.executable)
        elif __file__:
            return dirname(__file__)
        else:
            return '.'


# build system & station database from files systems.json and stations.json from http://eddb.io/api
if __name__ == "__main__":
    import json

    # still send market and outfitting for currently "suspended" stations -
    # https://community.elitedangerous.com/galnet/uid/568a999f9657ba5e0986a8de
    suspended = set([659, 39328, 5672, 30402, 30653, 21901, 11335])

    # system_name by system_id
    systems  = dict([(x['id'], str(x['name'])) for x in json.loads(open('systems.json').read())])

    stations = json.loads(open('stations.json').read())

    # check that all populated systems have known coordinates
    coords = dict([(x['id'], x['x'] or x['y'] or x['z']) for x in json.loads(open('systems.json').read())])
    for x in stations:
        assert x['system_id'] == 17072 or coords[x['system_id']], (x['system_id'], systems[x['system_id']])

    # system_id by system_name - populated systems only
    system_ids = dict([(systems[x['system_id']], x['system_id']) for x in stations])
    cPickle.dump(system_ids,  open('systems.p',  'wb'), protocol = cPickle.HIGHEST_PROTOCOL)

    # station_id by (system_id, station_name)
    station_ids = dict([(
        (x['system_id'], str(x['name'])),
        (x['id'],
         (EDDB.HAS_MARKET     if x['has_market']     or x['is_planetary'] or x['id'] in suspended else 0) |
         (EDDB.HAS_OUTFITTING if x['has_outfitting'] or x['is_planetary'] or x['id'] in suspended else 0) |
         (EDDB.HAS_SHIPYARD   if x['has_shipyard']   else 0)))
                        for x in stations])
    cPickle.dump(station_ids, open('stations.p', 'wb'), protocol = cPickle.HIGHEST_PROTOCOL)

