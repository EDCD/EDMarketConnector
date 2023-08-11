"""
constants.py - Export Ships as CSV

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import csv
import companion
from edmc_data import ship_name_map


def export(data: companion.CAPIData, filename: str) -> None:
    """
    Write shipyard data in Companion API JSON format.

    :param data: The CAPI data.
    :param filename: Optional filename to write to.
    :return:
    """
    assert data['lastSystem'].get('name')
    assert data['lastStarport'].get('name')
    assert data['lastStarport'].get('ships')

    with open(filename, 'w', newline='') as csv_file:
        csv_line = csv.writer(csv_file)
        csv_line.writerow(('System', 'Station', 'Ship', 'FDevID', 'Date'))

        for (name, fdevid) in [
            (
                ship_name_map.get(ship['name'].lower(), ship['name']),
                ship['id']
            ) for ship in list(
                (data['lastStarport']['ships'].get('shipyard_list') or {}).values()
            ) + data['lastStarport']['ships'].get('unavailable_list')
        ]:
            csv_line.writerow((
                data['lastSystem']['name'], data['lastStarport']['name'],
                name, fdevid, data['timestamp']
            ))
