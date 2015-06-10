# Export in Slopey's BPC format
# -*- coding: utf-8 -*-

from os.path import join
import hashlib
import codecs
import numbers
import time

from config import config

bracketmap = { 0: '',
               1: 'Low',
               2: 'Med',
               3: 'High', }

def export(data, csv=False):

    querytime = config.getint('querytime') or int(time.time())

    filename = join(config.get('outdir'), '%s.%s.%s.%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)), csv and 'csv' or 'bpc'))

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))
    header = 'System;Station;Commodity;Sell;Buy;Demand;;Supply;;Date;\n'
    rowheader = '%s;%s' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())
    if not csv:	# bpc
        header = 'userID;' + header
        cmdr = data['commander']['name'].strip()
        rowheader = '%s;%s' % (config.getint('anonymous') and hashlib.md5(cmdr.encode('utf-8')).hexdigest() or cmdr.replace(';',':'), rowheader)

    h = open(filename, 'wt')	# codecs can't automatically handle line endings, so encode manually where required
    h.write(header)

    for commodity in data['lastStarport']['commodities']:
        h.write(('%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % (
            rowheader,
            commodity['name'],
            commodity['sellPrice'] or '',
            commodity['buyPrice'] or '',
            int(commodity['demand']) if commodity['demandBracket'] else '',
            bracketmap[commodity['demandBracket']],
            int(commodity['stock']) if commodity['stockBracket'] else '',
            bracketmap[commodity['stockBracket']],
            timestamp)).encode('utf-8'))

    h.close()
