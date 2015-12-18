# Export list of ships as CSV

import time

from companion import ship_map
from config import config


def export(data, filename):

    querytime = config.getint('querytime') or int(time.time())

    assert data['lastSystem'].get('name')
    assert data['lastStarport'].get('name')
    assert data['lastStarport'].get('ships')

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))
    header = 'System,Station,Ship,Date\n'
    rowheader = '%s,%s' % (data['lastSystem']['name'], data['lastStarport']['name'])

    h = open(filename, 'wt')
    h.write(header)
    for name in [ship_map[ship['name'].lower()] for ship in (data['lastStarport']['ships'].get('shipyard_list') or {}).values() + data['lastStarport']['ships'].get('unavailable_list') if ship['name'].lower() in ship_map]:
        h.write('%s,%s,%s\n' % (rowheader, name, timestamp))
    h.close()
