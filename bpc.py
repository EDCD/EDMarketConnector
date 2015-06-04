# Export in Slopey's BPC format
# -*- coding: utf-8 -*-

from os.path import join
import codecs
import time

from config import config
from companion import commoditymap, bracketmap

def export(data, csv=False):

    querytime = config.getint('querytime') or int(time.time())

    filename = join(config.get('outdir'), '%s.%s.%s.%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)), csv and 'csv' or 'bpc'))

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))
    if csv:
        header = 'System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\n'
        rowheader = '%s;%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())
    else:	# bpc
        header = 'userID;System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\n'
        rowheader = '%s;%s;%s' % (data['commander']['name'].replace(';',':').strip(), data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())

    h = open(filename, 'wt')	# codecs can't automatically handle line endings, so encode manually where required
    h.write(header.encode('utf-8'))

    for commodity in data['lastStarport']['commodities']:
        if commodity.get('categoryname') and commodity['categoryname'] != 'NonMarketable':
            h.write('%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % (
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
