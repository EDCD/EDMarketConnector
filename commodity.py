# Export various CSV formats
# -*- coding: utf-8 -*-

from os.path import join
import hashlib
import time

from config import config

bracketmap = {
    0: '',
    1: 'Low',
    2: 'Med',
    3: 'High',
}

(COMMODITY_DEFAULT, COMMODITY_BPC, COMMODITY_CSV) = range(3)


def export(data, kind=COMMODITY_DEFAULT, filename=None):
    querytime = config.getint('querytime') or int(time.time())

    if not filename:
        kind_str = 'bpc'
        if kind != COMMODITY_BPC:
            kind_str = 'csv'

        filename = '{system}.{starport}.{time}.{kind}'.format(
            system=data['lastSystem']['name'].strip(),
            starport=data['lastStarport']['name'].strip(),
            time=time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)),
            kind=kind_str
        )

        filename = join(config.get('outdir'), filename)

    if kind == COMMODITY_CSV:
        sep = ';'  # BUG: for fixing later after cleanup
        header = sep.join(('System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', '', 'Supply', '', 'Date', '\n'))
        rowheader = sep.join((data['lastSystem']['name'], data['lastStarport']['name']))

    elif kind == COMMODITY_BPC:
        sep = ';'
        header = sep.join(
            ('userID', 'System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', '', 'Supply', '', 'Date\n')
        )

        cmdr = data['commander']['name'].strip()

        header_cmdr = cmdr
        if sep in cmdr:
            header_cmdr = f'"{cmdr}"'

        rowheader = sep.join((header_cmdr, data['lastSystem']['name'], data['lastStarport']['name']))

    else:
        sep = ','
        header = sep.join(
            ('System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', '', 'Supply', '', 'Average', 'FDevID', 'Date\n')
        )

        rowheader = sep.join((data['lastSystem']['name'], data['lastStarport']['name']))

    h = open(filename, 'wt')  # codecs can't automatically handle line endings, so encode manually where required
    h.write(header)

    for commodity in data['lastStarport']['commodities']:
        line = sep.join((
            rowheader,
            commodity['name'],
            commodity['sellPrice'] and str(int(commodity['sellPrice'])) or '',
            commodity['buyPrice'] and str(int(commodity['buyPrice'])) or '',
            str(int(commodity['demand'])) if commodity['demandBracket'] else '',
            bracketmap[commodity['demandBracket']],
            str(int(commodity['stock'])) if commodity['stockBracket'] else '',
            bracketmap[commodity['stockBracket']]
        ))

        if kind == COMMODITY_DEFAULT:
            line = sep.join((line, str(int(commodity['meanPrice'])), str(commodity['id']), data['timestamp'] + '\n'))

        else:
            line = sep.join((line, data['timestamp'] + '\n'))

        h.write(line)

    h.close()
