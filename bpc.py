# Export in Slopey's BPC format
# -*- coding: utf-8 -*-

from os.path import join
import codecs
import time

from config import config
from companion import categorymap, commoditymap, bracketmap

def export(data, csv=False):

    querytime = config.getint('querytime') or int(time.time())

    filename = join(config.get('outdir'), '%s.%s.%s.%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)), csv and 'csv' or 'bpc'))

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))
    header = 'System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\n'
    rowheader = '%s;%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())
    if not csv:	# bpc
        header = 'userID;' + header
        rowheader = '%s;%s' % (data['commander']['name'].replace(';',':').strip(), rowheader)

    h = open(filename, 'wt')	# codecs can't automatically handle line endings, so encode manually where required
    h.write(header)

    for commodity in data['lastStarport']['commodities']:
        if commodity.get('categoryname') and categorymap.get(commodity['categoryname'], True):
            h.write(('%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % (
                rowheader,
                commoditymap.get(commodity['name'].strip(), commodity['name'].strip()),
                commodity.get('sellPrice') and int(commodity['sellPrice']) or '',
                commodity.get('buyPrice') and int(commodity['buyPrice']) or '',
                int(commodity.get('demand', 0)) if commodity.get('demandBracket') else '',
                bracketmap.get(commodity.get('demandBracket'), ''),
                int(commodity.get('stock', 0)) if commodity.get('stockBracket') else '',
                bracketmap.get(commodity.get('stockBracket'), ''),
                timestamp)).encode('utf-8'))

    h.close()
