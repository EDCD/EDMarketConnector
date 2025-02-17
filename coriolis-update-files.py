#!/usr/bin/env python3
"""
coriolis-update-files.py - Build ship and module databases from https://github.com/EDCD/coriolis-data/.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This script also utilizes the file outfitting.csv. Due to how collate.py
both reads and writes to this file, a local copy in the root of the
project structure is used for this purpose. If you want to utilize the
FDevIDs/ version of the file, copy it over the local one.
"""


import json
import subprocess
import sys

import outfitting
from edmc_data import coriolis_ship_map, ship_name_map

if __name__ == "__main__":

    def add(modules, name, attributes) -> None:
        """Add the given module to the modules dict."""
        assert name not in modules or modules[name] == attributes, f'{name}: {modules.get(name)} != {attributes}'
        assert name not in modules, name
        modules[name] = attributes

    try:
        # Regenerate coriolis-data distribution
        subprocess.check_call('npm install', cwd='coriolis-data', shell=True, stdout=sys.stdout, stderr=sys.stderr)
    except NotADirectoryError:
        sys.exit("Coriolis-Data Directory not found! Have you set up your submodules? \n"
                 "https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source#obtain-a-copy-of-the-application-source")  # noqa: E501

    file_path = 'coriolis-data/dist/index.json'
    with open(file_path) as file:
        data = json.load(file)

    # Symbolic name from in-game name
    reverse_ship_map = {v: k for k, v in list(ship_name_map.items())}

    bulkheads = list(outfitting.armour_map.keys())

    ships = {}
    modules = {}

    # Ship and armour masses
    for m in list(data['Ships'].values()):
        name = coriolis_ship_map.get(m['properties']['name'], str(m['properties']['name']))
        assert name in reverse_ship_map, name
        ships[name] = {'hullMass': m['properties']['hullMass'],
                       'reserveFuelCapacity': m['properties']['reserveFuelCapacity']}
        for i, bulkhead in enumerate(bulkheads):
            modules['_'.join([reverse_ship_map[name], 'armour', bulkhead])] = {'mass': m['bulkheads'][i]['mass']}

    ships = {k: ships[k] for k in sorted(ships)}
    with open("ships.json", "w") as ships_file:
        json.dump(ships, ships_file, indent=4)

    # Module masses
    for cat in list(data['Modules'].values()):
        for grp, mlist in list(cat.items()):
            for m in mlist:
                assert 'symbol' in m, m
                key = str(m['symbol'].lower())
                if grp == 'fsd':
                    modules[key] = {
                        'mass':       m['mass'],
                        'optmass':    m['optmass'],
                        'maxfuel':    m['maxfuel'],
                        'fuelmul':    m['fuelmul'],
                        'fuelpower':  m['fuelpower'],
                    }
                elif grp == 'gfsb':
                    modules[key] = {
                        'mass':       m['mass'],
                        'jumpboost':  m['jumpboost'],
                    }
                else:
                    modules[key] = {'mass': m.get('mass', 0)}  # Some modules don't have mass

    # Pre 3.3 modules
    add(modules, 'int_stellarbodydiscoveryscanner_standard',      {'mass': 2})
    add(modules, 'int_stellarbodydiscoveryscanner_intermediate',  {'mass': 2})
    add(modules, 'int_stellarbodydiscoveryscanner_advanced',      {'mass': 2})

    modules = {k: modules[k] for k in sorted(modules)}
    with open("modules.json", "w") as modules_file:
        json.dump(modules, modules_file, indent=4)
