# Export to EDDN

from collections import OrderedDict
import hashlib
import json
import numbers
from platform import system
import re
import requests
from sys import platform
import time

from config import applongname, appversion, config
from companion import category_map


### upload = 'http://localhost:8081/upload/'	# testing
upload = 'http://eddn-gateway.elite-markets.net:8080/upload/'

timeout= 10	# requests timeout
module_re = re.compile('^Hpt_|^Int_|_Armour_')


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
    commodities = []
    for commodity in data['lastStarport'].get('commodities') or []:
        if category_map.get(commodity['categoryname'], True):	# Check marketable
            commodities.append(OrderedDict([
                ('name',          commodity['name']),
                ('meanPrice',     int(commodity['meanPrice'])),
                ('buyPrice',      int(commodity['buyPrice'])),
                ('stock',         int(commodity['stock'])),
                ('stockBracket',  commodity['stockBracket']),
                ('sellPrice',     int(commodity['sellPrice'])),
                ('demand',        int(commodity['demand'])),
                ('demandBracket', commodity['demandBracket']),
            ]))
            if commodity['statusFlags']:
                commodities[-1]['statusFlags'] = commodity['statusFlags']

    # Don't send empty commodities list - schema won't allow it
    if commodities:
        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/commodity/3',
            'message'    : {
                'systemName'  : data['lastSystem']['name'],
                'stationName' : data['lastStarport']['name'],
                'commodities' : commodities,
            }
        })

def export_outfitting(data):
    # Don't send empty modules list - schema won't allow it
    if data['lastStarport'].get('modules'):
        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/outfitting/2',
            'message'    : {
                'systemName'  : data['lastSystem']['name'],
                'stationName' : data['lastStarport']['name'],
                'modules'     : sorted([module['name'] for module in (data['lastStarport'].get('modules') or {}).values() if module_re.search(module['name']) and module.get('sku') in [None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'] and module['name'] != 'Int_PlanetApproachSuite']),
            }
        })

def export_shipyard(data):
    # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
    if data['lastStarport'].get('ships'):
        send(data['commander']['name'], {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/shipyard/2',
            'message'    : {
                'systemName'  : data['lastSystem']['name'],
                'stationName' : data['lastStarport']['name'],
                'ships'       : sorted([ship['name'] for ship in (data['lastStarport']['ships'].get('shipyard_list') or {}).values() + data['lastStarport']['ships'].get('unavailable_list')]),
            }
        })
