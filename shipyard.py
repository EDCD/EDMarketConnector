# Export list of ships as CSV

import time

from config import config
from util_ships import ship_map


def export(data, filename):

    querytime = config.get_int('querytime', default=int(time.time()))

    assert data['lastSystem'].get('name')
    assert data['lastStarport'].get('name')
    assert data['lastStarport'].get('ships')

    header = 'System,Station,Ship,FDevID,Date\n'
    rowheader = '%s,%s' % (data['lastSystem']['name'], data['lastStarport']['name'])

    h = open(filename, 'wt')
    h.write(header)
    for (name,fdevid) in [(ship_map.get(ship['name'].lower(), ship['name']), ship['id']) for ship in list((data['lastStarport']['ships'].get('shipyard_list') or {}).values()) + data['lastStarport']['ships'].get('unavailable_list')]:
        h.write('%s,%s,%s,%s\n' % (rowheader, name, fdevid, data['timestamp']))
    h.close()
