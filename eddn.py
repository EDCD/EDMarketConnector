# Export to EDDN
# -*- coding: utf-8 -*-

import datetime
import hashlib
import json
import requests
from platform import system
from sys import platform
import time

from config import applongname, appversion, config
from bpc import commoditymap, bracketmap

upload = 'http://eddn-gateway.elite-markets.net:8080/upload/'
schema = 'http://schemas.elite-markets.net/eddn/commodity/1'

def export(data, callback):

    callback('Sending data to EDDN...')

    header = { 'softwareName': '%s [%s]' % (applongname, platform=='darwin' and "Mac OS" or system()),
               'softwareVersion': appversion,
               'uploaderID': data.get('commander').get('name') } # was hashlib.md5(config.read('username')).hexdigest() }
    systemName = data.get('lastSystem').get('name').strip()
    stationName = data.get('lastStarport').get('name').strip()
    timestamp = datetime.datetime.utcfromtimestamp(config.read('querytime') or int(time.time())).isoformat()

    # route all requests through a session in the hope of using keep-alive
    session = requests.Session()
    session.headers['connection'] = 'keep-alive'	# can help through a proxy?

    commodities = data.get('lastStarport').get('commodities')
    i=0
    for commodity in commodities:
        i = i+1
        callback('Sending %d/%d' % (i, len(commodities)))
        if commodity.get('categoryname') and commodity.get('categoryname') != 'NonMarketable':
            msg = { '$schemaRef': schema,
                    'header': header,
                    'message': {
                        'systemName': systemName,
                        'stationName': stationName,
                        'itemName': commoditymap.get(commodity.get('name').strip(), commodity.get('name').strip()),
                        'buyPrice': int(commodity.get('buyPrice')),
                        'stationStock': int(commodity.get('stock')),
                        'sellPrice': int(commodity.get('sellPrice')),
                        'demand': int(commodity.get('demand')),
                        'timestamp': timestamp,
                    }
                }
            if commodity.get('stockBracket'):
                msg['message']['supplyLevel'] = bracketmap.get(commodity.get('stockBracket'))
            if commodity.get('demandBracket'):
                msg['message']['demandLevel'] = bracketmap.get(commodity.get('demandBracket'))

            r = requests.post(upload, data=json.dumps(msg), verify=True)

        elif __debug__:
            print 'Skipping %s : %s' % (commodity.get('name'), commodity.get('categoryname'))

    session.close()
