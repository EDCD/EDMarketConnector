# Export ship loadout in E:D Shipyard plain text format

import pickle
from collections import defaultdict
import os
from os.path import join
import re
import time

from config import config
import outfitting
import util_ships

from typing import Dict, Union, List
__Module = Dict[str, Union[str, List[str]]]

# Map API ship names to E:D Shipyard ship names
ship_map = util_ships.ship_map.copy()

ship_map.update(
    {
        'cobramkiii': 'Cobra Mk III',
        'cobramkiv' : 'Cobra Mk IV',
        'viper'     : 'Viper',
        'viper_mkiv': 'Viper Mk IV',
    }
)


# Map API slot names to E:D Shipyard slot names
slot_map = {
    'hugehardpoint'    : 'H',
    'largehardpoint'   : 'L',
    'mediumhardpoint'  : 'M',
    'smallhardpoint'   : 'S',
    'tinyhardpoint'    : 'U',
    'armour'           : 'BH',
    'powerplant'       : 'RB',
    'mainengines'      : 'TM',
    'frameshiftdrive'  : 'FH',
    'lifesupport'      : 'EC',
    'powerdistributor' : 'PC',
    'radar'            : 'SS',
    'fueltank'         : 'FS',
    'military'         : 'MC',
}


# Ship masses
# TODO: prefer something other than pickle for this storage (dev readability, security)
ships = pickle.load(open(join(config.respath_path, 'ships.p'), 'rb'))


# Export ship loadout in E:D Shipyard plain text format
def export(data, filename=None):
    def class_rating(module: __Module):
        mod_class = module['class']
        mod_rating = module['rating']
        mod_mount = module.get('mount')
        mod_guidance = module.get('guidance')

        ret = '{mod_class}{rating}'.format(mod_class=mod_class, rating=mod_rating)
        if 'guidance' in module:  # Missiles
            ret += "/{mount}{guidance}".format(
                mount=mod_mount[0] if mod_mount is not None else 'F',
                guidance=mod_guidance[0],
            )

        elif 'mount' in module:  # Hardpoints
            ret += "/{mount}".format(mount=mod_mount)

        elif 'Cabin' in module['name']:  # Passenger cabins
            ret += "/{name}".format(name=module['name'][0])

        return ret + ' '

    querytime = config.get_int('querytime', default=int(time.time()))

    loadout = defaultdict(list)
    mass = 0.0
    fuel = 0
    cargo = 0
    fsd = None
    jumpboost = 0

    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v:
                continue

            module: __Module = outfitting.lookup(v['module'], ship_map)
            if not module:
                continue

            cr = class_rating(module)
            mods = v.get('modifications') or v.get('WorkInProgress_modifications') or {}
            if mods.get('OutfittingFieldType_Mass'):
                mass += (module.get('mass', 0) * mods['OutfittingFieldType_Mass']['value'])

            else:
                mass += module.get('mass', 0)

            # Specials
            if 'Fuel Tank' in module['name']:
                fuel += 2**int(module['class'])
                name = '{} (Capacity: {})'.format(module['name'], 2**int(module['class']))

            elif 'Cargo Rack' in module['name']:
                cargo += 2**int(module['class'])
                name = '{} (Capacity: {})'.format(module['name'], 2**int(module['class']))

            else:
                name = module['name']

            if name == 'Frame Shift Drive':
                fsd = module  # save for range calculation

                if mods.get('OutfittingFieldType_FSDOptimalMass'):
                    fsd['optmass'] *= mods['OutfittingFieldType_FSDOptimalMass']['value']

                if mods.get('OutfittingFieldType_MaxFuelPerJump'):
                    fsd['maxfuel'] *= mods['OutfittingFieldType_MaxFuelPerJump']['value']

            jumpboost += module.get('jumpboost', 0)

            for s in slot_map:
                if slot.lower().startswith(s):
                    loadout[slot_map[s]].append(cr + name)
                    break

            else:
                if slot.lower().startswith('slot'):
                    loadout[slot[-1]].append(cr + name)

                elif __debug__ and not slot.lower().startswith('planetaryapproachsuite'):
                    print('EDShipyard: Unknown slot {}'.format(slot))

        except AssertionError as e:
            if __debug__:
                print('EDShipyard: {}'.format(e))

            continue  # Silently skip unrecognized modules

        except Exception:
            if __debug__:
                raise

    # Construct description
    ship = ship_map.get(data['ship']['name'].lower(), data['ship']['name'])

    if data['ship'].get('shipName') is not None:
        _ships = '{}, {}'.format(ship, data['ship']['shipName'])
    else:
        _ships = ship

    string = '[{}]\n'.format(_ships)

    SLOT_TYPES = (
        'H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, 'MC', None, '9', '8',
        '7', '6', '5', '4', '3', '2', '1'
    )
    for slot in SLOT_TYPES:
        if not slot:
            string += '\n'

        elif slot in loadout:
            for name in loadout[slot]:
                string += '{}: {}\n'.format(slot, name)

    string += '---\nCargo : {} T\nFuel  : {} T\n'.format(cargo, fuel)

    # Add mass and range
    assert data['ship']['name'].lower() in util_ships.ship_map, data['ship']['name']
    assert util_ships.ship_map[data['ship']['name'].lower()] in ships, util_ships.ship_map[data['ship']['name'].lower()]

    try:
        mass += ships[util_ships.ship_map[data['ship']['name'].lower()]]['hullMass']
        string += 'Mass  : {:.2f} T empty\n        {:.2f} T full\n'.format(mass, mass + fuel + cargo)

        multiplier = pow(min(fuel, fsd['maxfuel']) / fsd['fuelmul'], 1.0 / fsd['fuelpower']) * fsd['optmass']

        string += 'Range : {:.2f} LY unladen\n        {:.2f} LY laden\n'.format(
            multiplier / (mass + fuel) + jumpboost,
            multiplier / (mass + fuel + cargo) + jumpboost
        )

    except Exception:
        if __debug__:
            raise

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)

        return

    # Look for last ship of this type
    ship = util_ships.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + r'\.\d{4}-\d\d-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get_str('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get_str('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return  # same as last time - don't write

    # Write
    filename = join(config.get_str('outdir'), '{}.{}.txt'.format(
        ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime)))
    )

    with open(filename, 'wt') as h:
        h.write(string)
