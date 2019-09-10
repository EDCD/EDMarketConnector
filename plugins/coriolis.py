#!/usr/bin/python
#
# build ship and module databases from https://github.com/EDCD/coriolis-data/
#

from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
import csv
import base64
from collections import OrderedDict
import pickle
import json
from traceback import print_exc

from config import config
import outfitting
import companion


if __name__ == "__main__":

    def add(modules, name, attributes):
        assert name not in modules or modules[name] == attributes, '%s: %s!=%s' % (name, modules.get(name), attributes)
        assert name not in modules, name
        modules[name] = attributes


    data = json.load(open('coriolis-data/dist/index.json'))

    # Map Coriolis's names to names displayed in the in-game shipyard
    coriolis_ship_map = {
        'Cobra Mk III' : 'Cobra MkIII',
        'Cobra Mk IV'  : 'Cobra MkIV',
        'Krait Mk II'  : 'Krait MkII',
        'Viper'        : 'Viper MkIII',
        'Viper Mk IV'  : 'Viper MkIV',
    }

    # Symbolic name from in-game name
    reverse_ship_map = {v: k for k, v in companion.ship_map.items()}

    bulkheads = list(outfitting.armour_map.keys())

    ships = {}
    modules = {}

    # Ship and armour masses
    for m in list(data['Ships'].values()):
        name = coriolis_ship_map.get(m['properties']['name'], str(m['properties']['name']))
        assert name in reverse_ship_map, name
        ships[name] = { 'hullMass' : m['properties']['hullMass'] }
        for i in range(len(bulkheads)):
            modules['_'.join([reverse_ship_map[name], 'armour', bulkheads[i]])] = { 'mass': m['bulkheads'][i]['mass'] }

    ships = OrderedDict([(k,ships[k]) for k in sorted(ships)])	# sort for easier diffing
    pickle.dump(ships, open('ships.p', 'wb'))

    # Module masses
    for cat in list(data['Modules'].values()):
        for grp, mlist in cat.items():
            for m in mlist:
                assert 'symbol' in m, m
                key = str(m['symbol'].lower())
                if grp == 'fsd':
                    modules[key] = {
                        'mass'      : m['mass'],
                        'optmass'   : m['optmass'],
                        'maxfuel'   : m['maxfuel'],
                        'fuelmul'   : m['fuelmul'],
                        'fuelpower' : m['fuelpower'],
                    }
                elif grp == 'gfsb':
                    modules[key] = {
                        'mass'      : m['mass'],
                        'jumpboost' : m['jumpboost'],
                    }
                else:
                    modules[key] = { 'mass': m.get('mass', 0) }	# Some modules don't have mass

    # Pre 3.3 modules
    add(modules, 'int_stellarbodydiscoveryscanner_standard',     { 'mass': 2 })
    add(modules, 'int_stellarbodydiscoveryscanner_intermediate', { 'mass': 2 })
    add(modules, 'int_stellarbodydiscoveryscanner_advanced',     { 'mass': 2 })

    # Missing
    add(modules, 'hpt_mining_subsurfdispmisle_fixed_small',      { 'mass': 2 })
    add(modules, 'hpt_mining_subsurfdispmisle_fixed_medium',     { 'mass': 4 })
    add(modules, 'hpt_multicannon_fixed_small_advanced',         { 'mass': 2 })
    add(modules, 'hpt_multicannon_fixed_medium_advanced',        { 'mass': 4 })

    modules = OrderedDict([(k,modules[k]) for k in sorted(modules)])	# sort for easier diffing
    pickle.dump(modules, open('modules.p', 'wb'))

    # Check data is present for all modules
    with open('outfitting.csv') as csvfile:
        reader = csv.DictReader(csvfile, restval='')
        for row in reader:
            try:
                module = outfitting.lookup({ 'id': row['id'], 'name': row['symbol'] }, companion.ship_map)
            except:
                print(row['symbol'])
                print_exc()
