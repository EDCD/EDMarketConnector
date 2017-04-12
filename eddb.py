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
    RJ2 = 50 * 50

    def around_jaques(x, y, z):
        return ((x - JX) * (x - JX) + (y - JY) * (y - JY) + (z - JZ) * (z - JZ)) <= RJ2

    # Sphere around outliers
    RO2 = 40 * 40
    def around_outlier(cx, cy, cz, x, y, z):
        return ((x - ox) * (x - ox) + (y - oy) * (y - oy) + (z - oz) * (z - oz)) <= RO2

    POIS = [
        ('2MASS J03291977+3124572', -379.81250, -382.09375, -954.46875),
        ('Artemis', 14.28125, -63.18750, -24.87500),
        ('California Sector BV-Y c7', -342.31250, -219.28125, -952.71875),
        ('Col 173 Sector AP-Q b21-2', 1127.31250, -154.03125, -237.90625),
        ('Col 173 Sector AV-N b23-5', 1117.03125, -71.03125, -202.15625),
        ('Col 173 Sector CG-M b24-8', 1127.93750, -59.93750, -175.78125),
        ('Col 173 Sector DH-K b25-2', 1027.09375, -80.25000, -163.43750),
        ('Col 173 Sector EC-L d8-54', 1180.56250, -303.34375, -14.09375),
        ('Col 173 Sector FC-L d8-28', 1231.09375, -307.21875, -10.96875),
        ('Col 173 Sector HR-M b23-3', 1024.28125, -191.71875, -193.81250),
        ('Col 173 Sector KN-J b25-5', 1002.90625, -152.28125, -160.25000),
        ('Col 173 Sector KY-Q d5-47', 1043.87500, -100.75000, -246.06250),
        ('Col 173 Sector LY-Q d5-13', 1120.34375, -87.21875, -216.87500),
        ('Col 173 Sector LY-Q d5-59', 1078.09375, -86.56250, -249.46875),
        ('Col 173 Sector OE-P d6-11', 1014.34375, -67.59375, -173.96875),
        ('Col 173 Sector OG-Z c15-35', 1084.12500, 2.59375, 12.93750),
        ('Col 173 Sector OT-Q d5-18', 1150.75000, -124.03125, -216.81250),
        ('Col 173 Sector PV-B c14-1', 1023.65625, -217.40625, -81.09375),
        ('Col 173 Sector UU-O d6-42', 1147.09375, -252.81250, -156.65625),
        ('Col 173 Sector WF-N d7-52', 1186.68750, -166.18750, -80.18750),
        ('Col 173 Sector WN-B b29-1', 1237.75000, -247.37500, -76.90625),
        ('Col 173 Sector WZ-O b22-4', 1011.06250, -131.78125, -210.43750),
        ('Col 173 Sector XG-J c10-17', 1095.25000, -127.56250, -238.40625),
        ('Col 173 Sector YV-M d7-23', 1005.46875, -271.12500, -76.62500),
        ('Crab Sector DL-Y d9', 559.62500, -708.06250, -6947.56250),
        ('Crescent Sector GW-W c1-8', -4842.18750, 210.81250, 1252.21875),
        ('Eagle Sector IR-W d1-105', -2046.21875, 104.40625, 6699.90625),
        ('FW Cephei', -1415.78125, 366.65625, -355.31250),
        ('Flaming Star Sector LX-T b3-0', -243.09375, -77.56250, -1687.71875),
        ('GM Cephei', -2660.96875, 180.15625, -433.15625),
        ('HIP 16813', -57.03125, -143.37500, -268.28125),
        ('HIP 17403', -93.68750, -158.96875, -367.62500),
        ('HIP 17519', 17.37500, -160.84375, -204.50000),
        ('HIP 17862', -81.43750, -151.90625, -359.59375),
        ('HIP 23759', 359.84375, -385.53125, -718.37500),
        ('HIP 39768', 866.59375, -119.12500, -109.03125),
        ('Heart Sector IR-V b2-0', -5303.78125, 130.34375, -5305.40625),
        ('IC 2391 Sector FL-X b1-7', 611.34375, -78.40625, -51.68750),
        ('IC 2391 Sector GW-V b2-4', 587.93750, -51.03125, -38.53125),
        ('IC 2391 Sector ZE-A d101', 526.50000, -86.37500, -37.93750),
        ('Lagoon Sector FW-W d1-122', -467.75000, -93.18750, 4485.62500),
        ('NGC 7822 Sector BQ-Y d12', -2454.18750, 299.06250, -1326.06250),
        ('Omega Sector VE-Q b5-15', -1444.31250, -85.81250, 5319.93750),
        ('PMD2009 48', 594.90625, -431.43750, -1071.78125),
        ('Pencil Sector EL-Y d5', 816.31250, 2.00000, -44.03125),
        ('Pleiades Sector AB-W b2-4', -137.56250, -118.25000, -380.43750),
        ('Pleione', -77.00000, -146.78125, -344.12500),
        ('Runo', 51.12500, -155.53125, 44.28125),
        ('Sadr Region Sector GW-W c1-22', -1792.12500, 52.65625, 369.56250),
        ('Seagull Sector DL-Y d3', 2608.15625, -181.96875, -2692.28125),
        ('Skaudai AM-B d14-138', -5477.59375, -504.15625, 10436.25000),
        ('Soul Sector EL-Y d7', -5043.15625, 85.03125, -5513.09375),
        ('Synuefe CE-R c21-6', 828.18750, -78.00000, -105.18750),
        ('Synuefe LY-I b42-2', 814.71875, -222.78125, -151.15625),
        ('Synuefe NL-N c23-4', 860.12500, -124.59375, -61.06250),
        ('Synuefe TP-F b44-0', 838.75000, -197.84375, -111.84375),
        ('Synuefe XO-P c22-17', 546.90625, -56.46875, -97.81250),
        ('Synuefe XR-H d11-102', 357.34375, -49.34375, -74.75000),
        ('Synuefe ZL-J d10-109', 852.65625, -51.12500, -124.84375),
        ('Synuefe ZL-J d10-119', 834.21875, -51.21875, -154.65625),
        ('Synuefe ZR-I b43-10', 811.40625, -60.43750, -144.71875),
        ('T Tauri', -32.96875, -206.40625, -557.31250),
        ("Thor's Helmet Sector FB-X c1-5", 2704.96875, -23.25000, -2470.78125),
        ('Trifid Sector IR-W d1-52', -612.40625, -31.50000, 5182.87500),
        ('Vela Dark Region EL-Y d32', 1000.65625, -166.21875, -64.15625),
        ('Vela Dark Region HB-X c1-28', 1073.06250, -100.65625, -92.75000),
        ('Vela Dark Region KR-W c1-24', 1036.87500, -163.59375, -85.96875),
        ('Vela Dark Region RC-V b2-5', 1072.75000, -168.18750, -85.12500),
    ]

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
        for k,s in systems.iteritems() if s['is_populated'] or ((inbubble(s['x'], s['y'], s['z']) or around_jaques(s['x'], s['y'], s['z'])) and all(ord(c) < 128 for c in s['name']))	# skip unpopulated systems outside the bubble and those with a bogus name
    }

    print '\n%d systems around Jacques' % len([s for s in systems.itervalues() if around_jaques(s['x'], s['y'], s['z'])])

    cut = {
        k : s for k,s in systems.iteritems()
        if s['is_populated'] and not inbubble(s['x'], s['y'], s['z']) and not around_jaques(s['x'], s['y'], s['z'])
    }
    print '\n%d populated systems outside bubble calculation:' % len(cut)
    extra_ids = {}
    for k1,o in cut.iteritems():
        ox, oy, oz = o['x'], o['y'], o['z']
        extra = {
            str(s['name']) : k
            for k,s in systems.iteritems() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z']) and all(ord(c) < 128 for c in s['name'])
        }
        print '%-30s%7d %11.5f %11.5f %11.5f %3d' % (o['name'], k1, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d systems around outliers' % len(extra_ids)
    system_ids.update(extra_ids)

    print '\n%d POIs:' % len(POIS)
    extra_ids = {}
    for name,ox,oy,oz in POIS:
        extra = {
            str(s['name']) : k
            for k,s in systems.iteritems() if around_outlier(ox, oy, oz, s['x'], s['y'], s['z']) and all(ord(c) < 128 for c in s['name'])
        }
        print '%-37s %11.5f %11.5f %11.5f %3d' % (name, ox, oy, oz, len(extra))
        extra_ids.update(extra)
    print '\n%d systems around POIs' % len(extra_ids)
    system_ids.update(extra_ids)

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
    system_ids['Amo'] = 866
    system_ids['Arti'] = 60342
    system_ids['Futhark'] = 4901	# bogus data from ED-IBE
    system_ids['K Carinae'] = 375886	# both unpopulated

    # Some extra interesting systems
    system_ids['Sagittarius A*']       = 21276
    system_ids["Thor's Eye"]           = 34950
    system_ids['Great Annihilator']    = 35985
    system_ids['Beagle Point']         = 47005
    system_ids['Rendezvous Point']     = 91161
    system_ids['Myeia Thaa ZE-R d4-0'] = 125069
    system_ids['Iorant FR-C c26-0']    = 141581

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
