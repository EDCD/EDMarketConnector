# Export to EDDN

import hashlib
import json
import numbers
import requests
from platform import system
from sys import platform
import time

from config import applongname, appversion, config
import companion
import outfitting

### upload = 'http://localhost:8081/upload/'	# testing
upload = 'http://eddn-gateway.elite-markets.net:8080/upload/'

timeout= 10	# requests timeout

# Map API ship names to EDDN schema names
# https://raw.githubusercontent.com/jamesremuscat/EDDN/master/schemas/shipyard-v1.0.json
ship_map = dict(companion.ship_map)
ship_map['asp'] = 'Asp'			# Pre E:D 1.5 name for backwards compatibility
ship_map['cobramkiii'] = 'Cobra Mk III'	#	ditto
ship_map['viper'] = 'Viper'		#	ditto

bracketmap = { 1: 'Low',
               2: 'Med',
               3: 'High', }

def send(cmdr, msg):
    msg['header'] = {
        'softwareName'    : '%s [%s]' % (applongname, platform=='darwin' and "Mac OS" or system()),
        'softwareVersion' : appversion,
        'uploaderID'      : config.getint('anonymous') and hashlib.md5(cmdr.encode('utf-8')).hexdigest() or cmdr.encode('utf-8'),
    }
    msg['message']['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(config.getint('querytime') or int(time.time())))

    r = requests.post(upload, data=json.dumps(msg), timeout=timeout)
    if __debug__ and r.status_code != requests.codes.ok:
        print 'Status\t%s'  % r.status_code
        print 'URL\t%s'  % r.url
        print 'Headers\t%s' % r.headers
        print ('Content:\n%s' % r.text).encode('utf-8')
    r.raise_for_status()


def export_commodities(data):
    # Don't send empty commodities list - schema won't allow it
    if data['lastStarport'].get('commodities'):
        commodities = []
        for commodity in data['lastStarport'].get('commodities', []):
            commodities.append({
                'name'      : commodity['name'],
                'buyPrice'  : commodity['buyPrice'],
                'supply'    : int(commodity['stock']),
                'sellPrice' : commodity['sellPrice'],
                'demand'    : int(commodity['demand']),
            })
            if commodity['stockBracket']:
                commodities[-1]['supplyLevel'] = bracketmap[commodity['stockBracket']]
            if commodity['demandBracket']:
                commodities[-1]['demandLevel'] = bracketmap[commodity['demandBracket']]

        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/commodity/2',
            'message'    : {
                'systemName'  : data['lastSystem']['name'].strip(),
                'stationName' : data['lastStarport']['name'].strip(),
                'commodities' : commodities,
            }
        })

def export_outfitting(data):
    # Don't send empty modules list
    if data['lastStarport'].get('modules'):
        schemakeys = ['category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating']
        modules = []
        for v in data['lastStarport'].get('modules', {}).itervalues():
            try:
                module = outfitting.lookup(v, ship_map)
                if module:
                    modules.append({ k: module[k] for k in schemakeys if k in module })	# just the relevant keys
            except AssertionError as e:
                if __debug__: print 'Outfitting: %s' % e	# Silently skip unrecognized modules
            except:
                if __debug__: raise

        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/outfitting/1',
            'message'    : {
                'systemName'  : data['lastSystem']['name'].strip(),
                'stationName' : data['lastStarport']['name'].strip(),
                'modules'     : modules,
            }
        })

def export_shipyard(data):
    # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
    if data['lastStarport'].get('ships'):
        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/shipyard/1',
            'message'    : {
                'systemName'  : data['lastSystem']['name'].strip(),
                'stationName' : data['lastStarport']['name'].strip(),
                'ships'       : [ship_map[ship['name'].lower()] for ship in (data['lastStarport']['ships'].get('shipyard_list') or {}).values() + data['lastStarport']['ships'].get('unavailable_list') if ship['name'].lower() in ship_map],
            }
        })
