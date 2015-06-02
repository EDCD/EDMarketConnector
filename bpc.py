# Export in Slopey's BPC format
# -*- coding: utf-8 -*-

from os.path import join
import codecs
import datetime
import hashlib
import time

from config import config

commoditymap = { 'Agricultural Medicines': 'Agri-Medicines',
                 'Atmospheric Extractors': 'Atmospheric Processors',
                 'Auto Fabricators': 'Auto-Fabricators',
                 'Basic Narcotics': 'Narcotics',
                 'Bio Reducing Lichen': 'Bioreducing Lichen',
                 'Hazardous Environment Suits': 'H.E. Suits',
                 'Heliostatic Furnaces': 'Microbial Furnaces',
                 'Marine Supplies': 'Marine Equipment',
                 'Non Lethal Weapons': 'Non-Lethal Weapons',
                 'Terrain Enrichment Systems': 'Land Enrichment Systems' }

bracketmap = { 0: '',
               1: 'Low',
               2: 'Med',
               3: 'High' }


def export(data):

    querytime = config.read('querytime') or int(time.time())

    filename = join(config.read('outdir'), '%s.%s.%s.bpc' % (data.get('lastSystem').get('name').strip(), data.get('lastStarport').get('name').strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))

    timestamp = datetime.datetime.utcfromtimestamp(querytime).isoformat()
    rowheader = '%s;%s;%s' % (data.get('commander').get('name').replace(';',':'), data.get('lastSystem').get('name').strip(), data.get('lastStarport').get('name').strip())

    h = codecs.open(filename, 'w', 'utf-8')
    h.write('userID;System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\r\n')

    for commodity in data.get('lastStarport').get('commodities'):
        if commodity.get('categoryname') and commodity.get('categoryname') != 'NonMarketable':
            h.write('%s;%s;%s;%s;%s;%s;%s;%s;%s;\r\n' % (
                rowheader,
                commoditymap.get(commodity.get('name').strip(), commodity.get('name').strip()),
                commodity.get('sellPrice') and int(commodity.get('sellPrice')) or '',
                commodity.get('buyPrice') and int(commodity.get('buyPrice')) or '',
                commodity.get('demandBracket') and int(commodity.get('demand')) or '',
                bracketmap.get(commodity.get('demandBracket'), ''),
                commodity.get('stockBracket') and int(commodity.get('stock')) or '',
                bracketmap.get(commodity.get('stockBracket'), ''),
                timestamp))
        elif __debug__:
            print 'Skipping %s : %s' % (commodity.get('name'), commodity.get('categoryname'))

    h.close()
