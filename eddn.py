# Export to EDDN
# -*- coding: utf-8 -*-

import json
import numbers
import requests
from platform import system
from sys import platform
import time

from config import applongname, appversion, config
from companion import categorymap, commoditymap, bracketmap

upload = 'http://eddn-gateway.elite-markets.net:8080/upload/'
schema = 'http://schemas.elite-markets.net/eddn/commodity/1'

def export(data, callback):

    callback('Sending data to EDDN...')

    querytime = config.getint('querytime') or int(time.time())

    header = { 'softwareName': '%s [%s]' % (applongname, platform=='darwin' and "Mac OS" or system()),
               'softwareVersion': appversion,
               'uploaderID': data['commander']['name'].strip() }
    systemName = data['lastSystem']['name'].strip()
    stationName = data['lastStarport']['name'].strip()
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))

    # route all requests through a session in the hope of using keep-alive
    session = requests.Session()
    session.headers['connection'] = 'keep-alive'	# can help through a proxy?

    commodities = data['lastStarport']['commodities']
    i=0
    for commodity in commodities:
        i = i+1
        callback('Sending %d/%d' % (i, len(commodities)))
        if isinstance(commodity.get('demandBracket'), numbers.Integral) and commodity.get('categoryname') and categorymap.get(commodity['categoryname'], True):
            msg = { '$schemaRef': schema,
                    'header': header,
                    'message': {
                        'systemName': systemName,
                        'stationName': stationName,
                        'itemName': commoditymap.get(commodity['name'].strip(), commodity['name'].strip()),
                        'buyPrice': int(commodity.get('buyPrice', 0)),
                        'stationStock': commodity.get('stockBracket') and int(commodity.get('stock', 0)) or 0,
                        'sellPrice': int(commodity.get('sellPrice', 0)),
                        'demand': commodity.get('demandBracket') and int(commodity.get('demand', 0)) or 0,
                        'timestamp': timestamp,
                    }
                }
            if commodity.get('stockBracket'):
                msg['message']['supplyLevel'] = bracketmap.get(commodity['stockBracket'])
            if commodity.get('demandBracket'):
                msg['message']['demandLevel'] = bracketmap.get(commodity['demandBracket'])

            r = session.post(upload, data=json.dumps(msg))
            r.raise_for_status()

    session.close()
