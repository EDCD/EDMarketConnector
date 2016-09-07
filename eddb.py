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
        with open(join(config.respath, 'systems.p'),  'rb') as h:
            self.system_ids  = cPickle.load(h)
        with open(join(config.respath, 'stations.p'), 'rb') as h:
            self.station_ids = cPickle.load(h)

    # system_name -> system_id or 0
    def system(self, system_name):
        return self.system_ids.get(system_name, 0)	# return 0 on failure (0 is not a valid id)

    # (system_name, station_name) -> (station_id, has_market, has_outfitting, has_shipyard)
    def station(self, system_name, station_name):
        (station_id, flags) = self.station_ids.get((self.system_ids.get(system_name), station_name), (0,0))
        return (station_id, bool(flags & EDDB.HAS_MARKET), bool(flags & EDDB.HAS_OUTFITTING), bool(flags & EDDB.HAS_SHIPYARD))


#
# build databases from files systems.json and stations.json from http://eddb.io/api
#
if __name__ == "__main__":

    import json
    import requests

    def download(filename):
        r = requests.get('https://eddb.io/archive/v4/' + filename)
        print '\n%s\t%dK' % (filename, len(r.content) / 1024)
        return json.loads(r.content)	# let json do the utf-8 decode

    # Ellipsoid that encompasses most of the systems in the bubble (but not outliers like Sothis)
    RX = RZ = 260
    CY = -50
    RY = 300

    RX2 = RX * RX
    RY2 = RY * RY
    RZ2 = RZ * RZ

    def inbubble(x, y, z):
        return (x * x)/RX2 + ((y - CY) * (y - CY))/RY2 + (z * z)/RZ2 <= 1

    # Sphere around Jaques
    JX, JY, JZ = -9530.50000, -910.28125, 19808.12500
    RJ2 = 40 * 40

    def around_jaques(x, y, z):
        return ((x - JX) * (x - JX))/RJ2 + ((y - JY) * (y - JY))/RJ2 + ((z - JZ) * (z - JZ))/RJ2 <= 1

    systems = download('systems.json')
    print '%d\tsystems' % len(systems)

    # system_id by system_name (ignoring duplicate names)
    system_ids = dict([
        (str(s['name']), s['id'])
        for s in systems if s['is_populated'] or (inbubble(s['x'], s['y'], s['z']) and all(ord(c) < 128 for c in s['name'])) or around_jaques(s['x'], s['y'], s['z'])])	# skip unpopulated systems outside the bubble and those with a bogus name

    cut = [s for s in systems if s['is_populated'] and not inbubble(s['x'], s['y'], s['z'])]
    print '\n%d populated systems outside bubble calculation:' % len(cut)
    for s in cut:
        print '%-32s%7d %11.5f %11.5f %11.5f' % (s['name'], s['id'], s['x'], s['y'], s['z'])

    cut = [s for s in systems if inbubble(s['x'], s['y'], s['z']) and system_ids.get(s['name']) is None]
    print '\n%d dropped systems inside bubble calculation:' % len(cut)
    for s in cut:
        print '%s%s%7d %11.5f %11.5f %11.5f' % (s['name'].encode('utf-8'), ' '*(32-len(s['name'])), s['id'], s['x'], s['y'], s['z'])

    cut = [s for s in systems if (s['is_populated'] or inbubble(s['x'], s['y'], s['z'])) and system_ids.get(s['name']) and system_ids[s['name']] != s['id']]
    print '\n%d duplicate systems inside bubble calculation:' % len(cut)
    for s in cut:
        print '%-24s%7d %7d %11.5f %11.5f %11.5f' % (s['name'], system_ids[s['name']], s['id'], s['x'], s['y'], s['z'])

    print '\n%d systems around Jacques' % len([s for s in systems if around_jaques(s['x'], s['y'], s['z'])])

    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Almar'] = 750
    system_ids['Arti'] = 60342
    system_ids['Kamba'] = 10358

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = download('stations.json')
    station_ids = dict([(
        (x['system_id'], str(x['name'])),
        (x['id'],
         (EDDB.HAS_MARKET     if x['has_market']     else 0) |
         (EDDB.HAS_OUTFITTING if x['has_outfitting'] else 0) |
         (EDDB.HAS_SHIPYARD   if x['has_shipyard']   else 0)))
                        for x in stations])
    with open('stations.p', 'wb') as h:
        cPickle.dump(station_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '%d saved stations' % len(station_ids)
