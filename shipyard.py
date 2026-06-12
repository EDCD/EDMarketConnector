"""Export list of ships as CSV."""
from __future__ import annotations

import csv
from itertools import chain
import companion
from edmc_data import ship_name_map


def export(data: companion.CAPIData, filename: str) -> None:
    """
    Write shipyard data in Companion API CSV format.

    :param data: The CAPI data.
    :param filename: Target CSV filename
    """
    if not (system_name := data.get('lastSystem', {}).get('name')):
        raise ValueError("Missing 'name' in 'lastSystem'")

    if not (starport := data.get('lastStarport')):
        raise ValueError("Missing 'lastStarport' in data")

    if not (station_name := starport.get('name')):
        raise ValueError("Missing 'name' in 'lastStarport'")

    if not (ships_info := starport.get('ships')):
        raise ValueError("Missing 'ships' in 'lastStarport'")

    shipyard_list = ships_info.get('shipyard_list', {}).values()
    unavailable_list = ships_info.get('unavailable_list', [])
    all_ships = chain(shipyard_list, unavailable_list)

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['System', 'Station', 'Ship', 'FDevID', 'Date'])

        for ship in all_ships:
            name = ship_name_map.get(ship['name'].lower(), ship['name'])
            fdevid = ship['id']
            writer.writerow([system_name, station_name, name, fdevid, data['timestamp']])
