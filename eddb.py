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
        r = requests.get('https://eddb.io/archive/v4/' + filename, stream=True)
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

    systems = [
        { 'id'           : int(s['id']),
          'name'         : s['name'].decode('utf-8'),
          'x'            : float(s['x']),
          'y'            : float(s['y']),
          'z'            : float(s['z']),
          'is_populated' : bool(s['is_populated']),
        } for s in csv.DictReader(download('systems.csv').iter_lines())]
    print '%d\tsystems' % len(systems)

    # system_id by system_name (ignoring duplicate names)
    system_ids = dict([
        (str(s['name']), s['id'])
        for s in systems if s['is_populated'] or ((inbubble(s['x'], s['y'], s['z']) or around_jaques(s['x'], s['y'], s['z'])) and all(ord(c) < 128 for c in s['name']))])	# skip unpopulated systems outside the bubble and those with a bogus name

    cut = dict([(s['name'], s) for s in systems if s['is_populated'] and not inbubble(s['x'], s['y'], s['z']) and s['name'] not in ['Colonia', 'Eol Prou RS-T d3-94']])

    # Temporary hack for new Colonia outposts: https://community.elitedangerous.com/galnet/uid/5800bf2d9657bab47f9912eb
    cut.update({ 'Blu Thua AI-A c14-10':     { 'id':   64214, 'x':   -54.5,     'y':  149.53125, 'z':  2099.21875 },
                 'Lagoon Sector NI-S b4-10': { 'id':   69637, 'x':  -469.1875,  'y':  -84.84375, 'z':  4456.125   },
                 'Eagle Sector IR-W d1-117': { 'id':  855737, 'x': -2054.09375, 'y':   85.71875, 'z':  6710.875   },
                 'Skaudai CH-B d14-34':      { 'id': 1328989, 'x': -5481.84375, 'y': -579.15625, 'z': 10429.9375  },
                 'Gru Hypue KS-T d3-31':     { 'id': 3288878, 'x': -4990.84375, 'y': -935.71875, 'z': 13387.15625 },
                 'Boewnst KS-S c20-959':     { 'id': 3317609, 'x': -6195.46875, 'y': -140.28125, 'z': 16462.0625  },
    })
    print '\n%d populated systems outside bubble calculation:' % len(cut)
    extra_ids = {}
    for name,o in cut.iteritems():
        ox, oy, oz = o['x'], o['y'], o['z']
        print '%-32s%7d %11.5f %11.5f %11.5f' % (name, o['id'], ox, oy, oz)
        extra_ids.update(dict([
            (str(s['name']), s['id'])
            for s in systems if around_outlier(ox, oy, oz, s['x'], s['y'], s['z']) and all(ord(c) < 128 for c in s['name'])]))
    print '\n%d systems around outliers' % len(extra_ids)
    system_ids.update(extra_ids)

    print '%d systems around Jacques' % len([s for s in systems if around_jaques(s['x'], s['y'], s['z'])])

    cut = [s for s in systems if inbubble(s['x'], s['y'], s['z']) and system_ids.get(s['name']) is None]
    print '\n%d dropped systems inside bubble calculation:' % len(cut)
    for s in cut:
        print '%s%s%7d %11.5f %11.5f %11.5f' % (s['name'].encode('utf-8'), ' '*(32-len(s['name'])), s['id'], s['x'], s['y'], s['z'])

    cut = [s for s in systems if system_ids.get(s['name']) and system_ids[s['name']] != s['id'] and (s['is_populated'] or inbubble(s['x'], s['y'], s['z']))]
    print '\n%d duplicate systems inside bubble calculation:' % len(cut)
    for s in cut:
        print '%-24s%7d %7d %11.5f %11.5f %11.5f' % (s['name'], system_ids[s['name']], s['id'], s['x'], s['y'], s['z'])

    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Almar'] = 750
    system_ids['Arti'] = 60342
    system_ids['Kamba'] = 10358

    # point new name for Jaques at old entry (Eol Prou RS-T d3-94)
    system_ids['Colonia'] = 633211

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = json.loads(download('stations.json').content)	# let json do the utf-8 decode
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
