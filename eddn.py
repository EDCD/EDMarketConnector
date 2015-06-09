# Export to EDDN
# -*- coding: utf-8 -*-

import json
import numbers
import requests
from platform import system
from sys import platform
import time

from config import applongname, appversion, config

upload = 'http://eddn-gateway.elite-markets.net:8080/upload/'
schema = 'http://schemas.elite-markets.net/eddn/commodity/1'

bracketmap = { 1: 'Low',
               2: 'Med',
               3: 'High', }

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
        data = { '$schemaRef': schema,
                 'header': header,
                 'message': {
                     'systemName': systemName,
                     'stationName': stationName,
                     'itemName': commodity['name'],
                     'buyPrice': commodity['buyPrice'],
                     'stationStock': int(commodity['stock']),
                     'sellPrice': commodity['sellPrice'],
                     'demand': int(commodity['demand']),
                     'timestamp': timestamp,
                 }
             }
        if commodity['stockBracket']:
            data['message']['supplyLevel'] = bracketmap[commodity['stockBracket']]
        if commodity['demandBracket']:
            data['message']['demandLevel'] = bracketmap[commodity['demandBracket']]

        r = session.post(upload, data=json.dumps(data))
        if __debug__ and r.status_code != requests.codes.ok:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s'  % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
        r.raise_for_status()

    session.close()
