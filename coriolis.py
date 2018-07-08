#!/usr/bin/python
#
# build ship and module databases from https://github.com/EDCD/coriolis-data/
#

import base64
from collections import OrderedDict
import cPickle
import json

from config import config
import outfitting
import companion


if __name__ == "__main__":
    data = json.load(open('coriolis-data/dist/index.json'))

    # Map Coriolis's names to names displayed in the in-game shipyard
    coriolis_ship_map = {
        'Cobra Mk III' : 'Cobra MkIII',
        'Cobra Mk IV'  : 'Cobra MkIV',
        'Viper'        : 'Viper MkIII',
        'Viper Mk IV'  : 'Viper MkIV',
    }

    # Symbolic name from in-game name
    reverse_ship_map = {v: k for k, v in companion.ship_map.iteritems()}

    bulkheads = outfitting.armour_map.keys()

    ships = {}
    modules = {}

    # Ship and armour masses
    for m in data['Ships'].values():
        name = coriolis_ship_map.get(m['properties']['name'], str(m['properties']['name']))
        assert name in reverse_ship_map, name
        ships[name] = { 'hullMass' : m['properties']['hullMass'] }
        for i in range(len(bulkheads)):
            modules['_'.join([reverse_ship_map[name], 'armour', bulkheads[i]])] = { 'mass': m['bulkheads'][i]['mass'] }

    ships = OrderedDict([(k,ships[k]) for k in sorted(ships)])	# sort for easier diffing
    cPickle.dump(ships, open('ships.p', 'wb'))

    # Module masses
    for cat in data['Modules'].values():
        for grp, mlist in cat.iteritems():
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

    # 3.0 / 3.1 additions not yet present in coriolis-data
    for k in modules.keys():
        if k.startswith('int_hullreinforcement_'):
            modules['int_guardianhullreinforcement_' + k[22:]] = modules[k]
            modules['int_metaalloyhullreinforcement_' + k[22:]] = modules[k]
            modules['int_guardianmodulereinforcement_' + k[22:]] = modules[k]
    modules['hpt_causticmissile_fixed_medium'] = {'mass': 4}
    modules['hpt_flechettelauncher_fixed_medium'] = {'mass': 4}
    modules['hpt_flechettelauncher_turret_medium'] = {'mass': 4}
    modules['hpt_guardian_plasmalauncher_fixed_medium'] = {'mass': 4}
    modules['hpt_guardian_plasmalauncher_fixed_large'] = {'mass': 8}
    modules['hpt_guardian_plasmalauncher_turret_medium'] = {'mass': 4}
    modules['hpt_guardian_plasmalauncher_turret_large'] = {'mass': 8}
    modules['hpt_guardian_shardcannon_fixed_medium'] = {'mass': 4}
    modules['hpt_guardian_shardcannon_fixed_large'] = {'mass': 8}
    modules['hpt_guardian_shardcannon_turret_medium'] = {'mass': 4}
    modules['hpt_guardian_shardcannon_turret_large'] = {'mass': 8}
    modules['hpt_plasmashockcannon_fixed_medium'] = {'mass': 4}
    modules['hpt_plasmashockcannon_fixed_large'] = {'mass': 8}	# ???
    modules['hpt_plasmashockcannon_gimbal_medium'] = {'mass': 4}
    modules['hpt_plasmashockcannon_gimbal_large'] = {'mass': 8}	# ???
    modules['hpt_plasmashockcannon_turret_medium'] = {'mass': 4}
    modules['hpt_plasmashockcannon_turret_large'] = {'mass': 8}	# ???
    modules['int_dronecontrol_decontamination_size1_class1'] = {'mass': 1.3}
    modules['int_dronecontrol_decontamination_size3_class1'] = {'mass': 2}
    modules['int_dronecontrol_decontamination_size5_class1'] = {'mass': 20}
    modules['int_dronecontrol_decontamination_size7_class1'] = {'mass': 128}
    modules['int_dronecontrol_unkvesselresearch'] = {'mass': 1.3}

    modules = OrderedDict([(k,modules[k]) for k in sorted(modules)])	# sort for easier diffing
    cPickle.dump(modules, open('modules.p', 'wb'))
