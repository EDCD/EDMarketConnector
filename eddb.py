#!/usr/bin/python
#
# eddb.io station database
#

import cPickle
import csv
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
# build databases from files systems.csv and stations.json from http://eddb.io/api
#
if __name__ == "__main__":

    import json
    import requests

    def download(filename):
        r = requests.get('https://eddb.io/archive/v5/' + filename, stream=True)
        print '\n%s\t%dK' % (filename, len(r.content) / 1024)
        return r

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
        return ((x - JX) * (x - JX) + (y - JY) * (y - JY) + (z - JZ) * (z - JZ)) <= RJ2

    # Sphere around outliers
    RO2 = 30 * 30
    def around_outlier(cx, cy, cz, x, y, z):
        return ((x - ox) * (x - ox) + (y - oy) * (y - oy) + (z - oz) * (z - oz)) <= RO2

    systems = { int(s['id']) : {
        'name'         : s['name'].decode('utf-8'),
        'x'            : float(s['x']),
        'y'            : float(s['y']),
        'z'            : float(s['z']),
        'is_populated' : int(s['is_populated']),
    } for s in csv.DictReader(download('systems.csv').iter_lines()) }
    print '%d\tsystems' % len(systems)

    # system_id by system_name (ignoring duplicate names)
    system_ids = {
        str(s['name']) : k
        for k,s in systems.iteritems() if s['is_populated'] or ((inbubble(s['x'], s['y'], s['z']) or around_jaques(s['x'], s['y'], s['z'])) and all(ord(c) < 128 for c in s['name']))	# skip unpopulated systems outside the bubble and those with a bogus name
    }

    cut = {
        k : s for k,s in systems.iteritems()
        if s['is_populated'] and not inbubble(s['x'], s['y'], s['z']) and not around_jaques(s['x'], s['y'], s['z'])
    }
    print '\n%d populated systems outside bubble calculation:' % len(cut)
    extra_ids = {}
    for k,o in cut.iteritems():
        ox, oy, oz = o['x'], o['y'], o['z']
        extra = {
            str(s['name']) : k
            for k,s in systems.iteritems() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z']) and all(ord(c) < 128 for c in s['name'])
        }
        print '%-30s%7d %11.5f %11.5f %11.5f %3d' % (o['name'], k, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d systems around outliers' % len(extra_ids)
    system_ids.update(extra_ids)

    print '%d systems around Jacques' % len([s for s in systems.itervalues() if around_jaques(s['x'], s['y'], s['z'])])

    cut = {
        k : s
        for k,s in systems.iteritems() if inbubble(s['x'], s['y'], s['z']) and system_ids.get(s['name']) is None
    }
    print '\n%d dropped systems inside bubble calculation:' % len(cut)
    for k,s in cut.iteritems():
        print '%s%s%7d %11.5f %11.5f %11.5f' % (s['name'].encode('utf-8'), ' '*(30-len(s['name'])), k, s['x'], s['y'], s['z'])

    cut = {
        k : s
        for k,s in systems.iteritems() if system_ids.get(s['name']) and system_ids[s['name']] != k and (s['is_populated'] or inbubble(s['x'], s['y'], s['z']))
    }
    print '\n%d duplicate systems inside bubble calculation:' % len(cut)
    for k,s in cut.iteritems():
        print '%-22s%7d %7d %11.5f %11.5f %11.5f' % (s['name'], system_ids[s['name']], k, s['x'], s['y'], s['z'])

    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Aarti'] = 3616854	# bogus data from EDSM
    system_ids['Almar'] = 750
    system_ids['Arti'] = 60342
    system_ids['Futhark'] = 4901	# bogus data from ED-IBE
    system_ids['K Carinae'] = 375886	# both unpopulated
    system_ids['Kamba'] = 10358

    # Ancient ruins
    system_ids['Synuefe XR-H d11-102']     = 3524806	# Site 1 / Beta
    system_ids['IC 2391 Sector GW-V b2-4'] = 3954820	# Site 2
    system_ids['IC 2391 Sector ZE-A d101'] = 6259569	# Site 3 / Alpha
    system_ids['Synuefe ZL-J d10-119']     = 6024386	# https://community.elitedangerous.com/en/galnet/uid/58872def9657ba9230f89d99
    system_ids['Synuefe XO-P c22-17']      = 6259676	#  "

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = json.loads(download('stations.json').content)	# let json do the utf-8 decode
    station_ids = {
        (x['system_id'], str(x['name'])) :
        (x['id'],
         (EDDB.HAS_MARKET     if x['has_market']     else 0) |
         (EDDB.HAS_OUTFITTING if x['has_outfitting'] else 0) |
         (EDDB.HAS_SHIPYARD   if x['has_shipyard']   else 0))
        for x in stations if x['max_landing_pad_size'] and all(ord(c) < 128 for c in x['name']) }

    cut = [ x for x in stations if any(ord(c) >= 128 for c in x['name']) ]
    print '\n%d dropped stations:' % len(cut)
    for s in cut:
        print '%-30s%7d %s' % (s['name'], s['id'], systems[s['system_id']]['name'])

    with open('stations.p', 'wb') as h:
        cPickle.dump(station_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved stations' % len(station_ids)
