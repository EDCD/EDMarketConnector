#!/usr/bin/python
#
# build databases from files systems.csv and stations.json from http://eddb.io/api
#

import cPickle
import csv
import json
import requests

def download(filename):
    r = requests.get('https://eddb.io/archive/v5/' + filename, stream=True)
    print '\n%s\t%dK' % (filename, len(r.content) / 1024)
    return r

if __name__ == "__main__":

    # system_id by system_name
    systems = json.loads(download('systems_populated.json').content)	# let json do the utf-8 decode
    system_ids = {
        str(s['name']) : s['id']
        for s in systems
    }
    # Hack - ensure duplicate system names are pointing at the more interesting system
    system_ids['Amo'] = 866
    system_ids['K Carinae'] = 375886	# both unpopulated

    with open('systems.p',  'wb') as h:
        cPickle.dump(system_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved systems' % len(system_ids)

    # station_id by (system_id, station_name)
    stations = json.loads(download('stations.json').content)	# let json do the utf-8 decode
    station_ids = {
        (x['system_id'], str(x['name'])) : x['id']
        for x in stations if x['max_landing_pad_size']
    }

    with open('stations.p', 'wb') as h:
        cPickle.dump(station_ids, h, protocol = cPickle.HIGHEST_PROTOCOL)
    print '\n%d saved stations' % len(station_ids)
