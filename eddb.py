#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# build databases from files systems.csv and stations.json from http://eddb.io/api
#

import cPickle
import csv
import json
import requests

if __name__ == "__main__":


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
    RJ2 = 50 * 50	# Furthest populated system is Eol Prou IW-W e1-1456 at 49.47 Ly

    def around_jaques(x, y, z):
        return ((x - JX) * (x - JX) + (y - JY) * (y - JY) + (z - JZ) * (z - JZ)) <= RJ2

    # Sphere around outliers
    RO2 = 40 * 40
    def around_outlier(cx, cy, cz, x, y, z):
        return ((x - ox) * (x - ox) + (y - oy) * (y - oy) + (z - oz) * (z - oz)) <= RO2

    # Get Points Of Interest from Canonn Research - https://api.canonn.technology/api/docs/#!/System/V1StellarSystemsGet
    POIS = [(s['name'], s['edsmCoordX'], s['edsmCoordY'], s['edsmCoordZ'])
            for s in requests.get('https://api.canonn.technology/api/v1/stellar/systems').json()
            if s.get('edsmCoordX') and s.get('edsmCoordY') and s.get('edsmCoordZ')]
    POIS.extend([
        # http://elite-dangerous.wikia.com/wiki/Alien_Crash_Site
        ('Pleiades Sector AB-W b2-4', -137.56250, -118.25000, -380.43750),
        ('HIP 17862',                  -81.43750, -151.90625, -359.59375),
        ('HIP 17403',                  -93.68750, -158.96875, -367.62500),
        # http://elite-dangerous.wikia.com/wiki/Thargoid_Surface_Site
        ('HIP 19026',                 -117.87500,  -65.12500, -330.90625),
        # POI
        ('HIP 22460',                  -41.31250,  -58.96875, -354.78125),
        ('Col 70 Sector FY-N c21-3',   687.06250, -362.53125, -697.06250),
    ])
    POIS.sort()

    systems = { int(s['id']) : {
        'name'         : s['name'].decode('utf-8'),
        'x'            : float(s['x']),
        'y'            : float(s['y']),
        'z'            : float(s['z']),
        'is_populated' : int(s['is_populated']),
    } for s in csv.DictReader(download('systems.csv').iter_lines()) }
    #} for s in csv.DictReader(open('systems.csv')) }
    print '%d\tsystems' % len(systems)

    # system_id by system_name (ignoring duplicate names)
    system_ids = {
        str(s['name']) : k
        for k,s in systems.iteritems() if s['is_populated'] or inbubble(s['x'], s['y'], s['z']) or around_jaques(s['x'], s['y'], s['z'])	# skip unpopulated systems outside the bubble and those with a bogus name
    }

    print '\n%d systems around Jacques' % len([s for s in systems.itervalues() if around_jaques(s['x'], s['y'], s['z'])])

    cut = {
        k : s for k,s in systems.iteritems()
        if s['is_populated'] and not inbubble(s['x'], s['y'], s['z']) and not around_jaques(s['x'], s['y'], s['z'])
    }
    print '\n%d populated systems outside bubble calculation:' % len(cut)
    extra_ids = {}
    for k1,o in sorted(cut.iteritems()):
        ox, oy, oz = o['x'], o['y'], o['z']
        extra = {
            str(s['name']) : k
            for k,s in systems.iteritems() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z'])
        }
        print '%-30s%7d %11.5f %11.5f %11.5f %4d' % (o['name'], k1, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d systems around outliers' % len(extra_ids)
    system_ids.update(extra_ids)

    print '\n%d POIs:' % len(POIS)
    extra_ids = {}
    for name,ox,oy,oz in POIS:
        extra = {
            str(s['name']) : k
            for k,s in systems.iteritems() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z'])
        }
        print '%-37s %11.5f %11.5f %11.5f %4d' % (name, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d systems around POIs' % len(extra_ids)
    system_ids.update(extra_ids)

    cut = {
        k : s
        for k,s in systems.iteritems() if inbubble(s['x'], s['y'], s['z']) and system_ids.get(s['name']) is None
    }
    print '\n%d dropped systems inside bubble calculation:' % len(cut)
    for k,s in sorted(cut.iteritems()):
        print '%s%s%7d %11.5f %11.5f %11.5f' % (s['name'].encode('utf-8'), ' '*(30-len(s['name'])), k, s['x'], s['y'], s['z'])

    cut = {
        k : s
        for k,s in systems.iteritems() if system_ids.get(s['name']) and system_ids[s['name']] != k and (s['is_populated'] or inbubble(s['x'], s['y'], s['z']))
    }
    print '\n%d duplicate systems inside bubble calculation:' % len(cut)
    for k,s in sorted(cut.iteritems()):
        print '%-20s%8d %8d %11.5f %11.5f %11.5f' % (s['name'], system_ids[s['name']], k, s['x'], s['y'], s['z'])

    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Amo'] = 866
    system_ids['Ogma'] = 14915		# in bubble, not Colonia
    system_ids['Ratri'] = 16001		#   "
    system_ids['K Carinae'] = 375886	# both unpopulated

    # 2.4 Colonia renames - https://github.com/themroc5/eddb.io/issues/136
    system_ids['Poe'] = 2751046
    system_ids['White Sun'] = 2277522
    system_ids['Chrysus'] = 2911665
    system_ids['Juniper'] = 692229
    system_ids['Rodentia'] = 1481196
    system_ids['Kajuku'] = 1937790
    system_ids['Lycanthrope'] = 2221090
    system_ids['Ogmar'] = 10931086
    system_ids['Ratraii'] = 10918695
    system_ids['Farwell'] = 9132855
    system_ids['Carlota'] = 1218013
    system_ids['Morpheus'] = 684221
    system_ids['Earth Expeditionary Fleet'] = 8262285
    system_ids['Centralis'] = 1581643

    # Some extra interesting systems
    system_ids['Sagittarius A*']       =   21276
    system_ids["Thor's Eye"]           =   34950
    system_ids['Great Annihilator']    =   35985
    system_ids['Beagle Point']         =   47005
    system_ids['Rendezvous Point']     =   91161
    system_ids['Myeia Thaa ZE-R d4-0'] =  125069	# Podar
    system_ids['Iorant FR-C c26-0']    =  141581	# The Treehouse
    system_ids['Phae Phlai AA-A h0']   =  144202	# Explorer's End
    system_ids['Oevasy SG-Y d0']       =  145249	# Salomé's Reach / Semotus Beacon / Ishum's Reach
    system_ids['Syreadiae JX-F c0']    = 8538488	# Zurara

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = json.loads(download('stations.json').content)	# let json do the utf-8 decode
    station_ids = {
        (x['system_id'], str(x['name'])) : x['id']
        for x in stations if x['max_landing_pad_size']
    }

    cut = [ x for x in stations if any(ord(c) >= 128 for c in x['name']) ]
    print '\n%d dropped stations:' % len(cut)
    for s in cut:
        print '%-30s%7d %s' % (s['name'], s['id'], systems[s['system_id']]['name'])

    with open('stations.p', 'wb') as h:
        cPickle.dump(station_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved stations' % len(station_ids)
