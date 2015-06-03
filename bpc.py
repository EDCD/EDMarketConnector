# Export in Slopey's BPC format
# -*- coding: utf-8 -*-

from os.path import join
import codecs
import time

from config import config
from companion import commoditymap, bracketmap

def export(data):

    querytime = config.read('querytime') or int(time.time())

    filename = join(config.read('outdir'), '%s.%s.%s.bpc' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(querytime))
    rowheader = '%s;%s;%s' % (data['commander']['name'].replace(';',':').strip(), data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())

    h = codecs.open(filename, 'w', 'utf-8')
    h.write('userID;System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\r\n')

    for commodity in data['lastStarport']['commodities']:
        if commodity.get('categoryname') and commodity['categoryname'] != 'NonMarketable':
            h.write('%s;%s;%s;%s;%s;%s;%s;%s;%s;\r\n' % (
                rowheader,
                commoditymap.get(commodity['name'].strip(), commodity['name'].strip()),
                commodity.get('sellPrice') and int(commodity['sellPrice']) or '',
                commodity.get('buyPrice') and int(commodity['buyPrice']) or '',
                int(commodity['demand']) if commodity.get('demandBracket') else '',
                bracketmap.get(commodity.get('demandBracket'), ''),
                int(commodity['stock']) if commodity.get('stockBracket') else '',
                bracketmap.get(commodity.get('stockBracket'), ''),
                timestamp))

    h.close()
