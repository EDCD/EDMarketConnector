"""Export list of ships as CSV."""
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
    system_name = data['lastSystem'].get('name')
    if not system_name:
        raise ValueError("Missing 'name' in 'lastSystem'")
    starport = data['lastStarport']
    station_name = starport.get('name')
    ships_info = starport.get('ships')

    if not station_name:
        raise ValueError("Missing 'name' in 'lastStarport'")
    if not ships_info:
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
