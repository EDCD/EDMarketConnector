"""Export various CSV formats."""
# -*- coding: utf-8 -*-

import time
from os.path import join

from config import config
from edmc_data import commodity_bracketmap as bracketmap

# DEFAULT means semi-colon separation
# CSV means comma separation
(COMMODITY_DEFAULT, COMMODITY_CSV) = range(2)


def export(data, kind=COMMODITY_DEFAULT, filename=None) -> None:
    """
    Export commodity data from the given CAPI data.

    :param data: CAPI data.
    :param kind: The type of file to write.
    :param filename: Filename to write to, or None for a standard format name.
    :return:
    """
    querytime = config.get_int('querytime', default=int(time.time()))

    if not filename:
        filename_system = data['lastSystem']['name'].strip(),
        filename_starport = data['lastStarport']['name'].strip(),
        filename_time = time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)),
        filename_kind = 'csv'
        filename = f'{filename_system}.{filename_starport}.{filename_time}.{filename_kind}'
        filename = join(config.get_str('outdir'), filename)

    if kind == COMMODITY_CSV:
        sep = ';'  # BUG: for fixing later after cleanup
        header = sep.join(('System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', '', 'Supply', '', 'Date', '\n'))
        rowheader = sep.join((data['lastSystem']['name'], data['lastStarport']['name']))

    else:
        sep = ','
        header = sep.join(
            ('System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', '', 'Supply', '', 'Average', 'FDevID', 'Date\n')
        )

        rowheader = sep.join((data['lastSystem']['name'], data['lastStarport']['name']))

    with open(filename, 'wt') as h:  # codecs can't automatically handle line endings, so encode manually where required
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
                line = sep.join(
                    (
                        line,
                        str(int(commodity['meanPrice'])),
                        str(commodity['id']),
                        data['timestamp'] + '\n'
                    )
                )

            else:
                line = sep.join((line, data['timestamp'] + '\n'))

            h.write(line)
