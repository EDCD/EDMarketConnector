#!/usr/bin/python
#
# build databases from files systems.csv and stations.json from http://eddb.io/api
#

import cPickle
import csv
import json
import requests

def download(filename):
    r = requests.get('https://eddb.io/archive/v6/' + filename, stream=True)
    print '\n%s\t%dK' % (filename, len(r.content) / 1024)
    return r

if __name__ == "__main__":

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
    RJ2 = 80 * 80	# Furthest populated system is Pekoe at 50.16 Ly

    def around_jaques(x, y, z):
        return ((x - JX) * (x - JX) + (y - JY) * (y - JY) + (z - JZ) * (z - JZ)) <= RJ2

    # Sphere around outliers
    RO2 = 40 * 40
    def around_outlier(cx, cy, cz, x, y, z):
        return ((x - ox) * (x - ox) + (y - oy) * (y - oy) + (z - oz) * (z - oz)) <= RO2

    systems = { int(s['id']) : {
        'name'         : s['name'].decode('utf-8'),
        'x'            : float(s['x']),
        'y'            : float(s['y']),
        'z'            : float(s['z']),
        'is_populated' : int(s['is_populated']),
    } for s in csv.DictReader(download('systems.csv').iter_lines()) }
    #} for s in csv.DictReader(open('systems.csv')) }
    print '%d\tsystems' % len(systems)

    # (system_id, is_populated) by system_name (ignoring duplicate names)
    system_ids = {
        str(s['name']) : (k, s['is_populated'])
        for k,s in systems.items() if inbubble(s['x'], s['y'], s['z'])
    }
    print '%d\tsystems in bubble' % len(system_ids)

    extra_ids = {
        str(s['name']) : (k, s['is_populated'])
        for k,s in systems.items() if around_jaques(s['x'], s['y'], s['z'])
    }
    system_ids.update(extra_ids)
    print '%d\tsystems in Colonia' % len(extra_ids)

    cut = {
        k : s for k, s in systems.items()
        if s['is_populated'] and s['name'] not in system_ids
    }
    print '%d\toutlying populated systems:' % len(cut)
    extra_ids = {}
    for k1,o in sorted(cut.items()):
        ox, oy, oz = o['x'], o['y'], o['z']
        extra = {
            str(s['name']) : (k, s['is_populated'])
            for k,s in systems.items() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z'])
        }
        print '%-30s%7d %11.5f %11.5f %11.5f %4d' % (o['name'], k1, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d\tsystems around outliers' % len(extra_ids)
    system_ids.update(extra_ids)

    cut = {
        k : s
        for k,s in systems.items() if s['name'] in system_ids and system_ids[s['name']][0] != k
    }
    print '\n%d duplicate systems' % len(cut)
    for k,s in sorted(cut.items()):
        print '%-20s%8d %8d %11.5f %11.5f %11.5f' % (s['name'], system_ids[s['name']][0], k, s['x'], s['y'], s['z'])

    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Amo'] = (866, True)
    system_ids['C Puppis']  = (25068, False)
    system_ids['q Velorum'] = (15843, True)
    system_ids['M Carinae'] = (22627, False)
    system_ids['HH 17']     = (61275, False)
    system_ids['K Carinae'] = (375886, False)
    system_ids['d Velorum'] = (406476, False)
    system_ids['L Velorum'] = (2016580, False)
    system_ids['N Velorum'] = (3012033, False)
    system_ids['i Velorum'] = (3387990, False)

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = json.loads(download('stations.json').content)	# let json do the utf-8 decode
    station_ids = {
        (x['system_id'], x['name'].encode('utf-8')) : x['id']	# Pilgrim's Ruin in HR 3005 id 70972 has U+2019 quote
        for x in stations if x['max_landing_pad_size']
    }

    with open('stations.p', 'wb') as h:
        cPickle.dump(station_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved stations' % len(station_ids)
