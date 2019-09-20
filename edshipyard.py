# Export ship loadout in E:D Shipyard plain text format

import pickle
from collections import defaultdict
import os
from os.path import join
import re
import time

from config import config
import companion
import outfitting


# Map API ship names to E:D Shipyard ship names
ship_map = dict(companion.ship_map)
ship_map['cobramkiii'] = 'Cobra Mk III'
ship_map['cobramkiv']  = 'Cobra Mk IV',
ship_map['viper']      = 'Viper'
ship_map['viper_mkiv'] = 'Viper Mk IV'


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
ships = pickle.load(open(join(config.respath, 'ships.p'),  'rb'))


# Export ship loadout in E:D Shipyard plain text format
def export(data, filename=None):

    def class_rating(module):
        if 'guidance' in module:	# Missiles
            return module['class'] + module['rating'] + '/' + module.get('mount', 'F')[0] + module['guidance'][0] + ' '
        elif 'mount' in module:		# Hardpoints
            return module['class'] + module['rating'] + '/' + module['mount'][0] + ' '
        elif 'Cabin' in module['name']:	# Passenger cabins
            return module['class'] + module['rating'] + '/' + module['name'][0] + ' '
        else:
            return module['class'] + module['rating'] + ' '

    querytime = config.getint('querytime') or int(time.time())

    loadout = defaultdict(list)
    mass = 0.0
    fuel = 0
    cargo = 0
    fsd = None
    jumpboost = 0

    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v: continue

            module = outfitting.lookup(v['module'], ship_map)
            if not module: continue

            cr = class_rating(module)
            mods = v.get('modifications') or v.get('WorkInProgress_modifications') or {}
            if mods.get('OutfittingFieldType_Mass'):
                mass += (module.get('mass', 0) * mods['OutfittingFieldType_Mass']['value'])
            else:
                mass += module.get('mass', 0)

            # Specials
            if 'Fuel Tank'in module['name']:
                fuel += 2**int(module['class'])
                name = '%s (Capacity: %d)' % (module['name'], 2**int(module['class']))
            elif 'Cargo Rack' in module['name']:
                cargo += 2**int(module['class'])
                name = '%s (Capacity: %d)' % (module['name'], 2**int(module['class']))
            else:
                name = module['name']

            if name == 'Frame Shift Drive':
                fsd = module	# save for range calculation
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
                    print('EDShipyard: Unknown slot %s' % slot)

        except AssertionError as e:
            if __debug__: print('EDShipyard: %s' % e)
            continue	# Silently skip unrecognized modules
        except:
            if __debug__: raise

    # Construct description
    ship = ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
    string = '[%s]\n' % (data['ship'].get('shipName') and ', '.join([ship, data['ship']['shipName']]) or ship)
    for slot in ['H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, 'MC', None, '9', '8', '7', '6', '5', '4', '3', '2', '1']:
        if not slot:
            string += '\n'
        elif slot in loadout:
            for name in loadout[slot]:
                string += '%s: %s\n' % (slot, name)
    string += '---\nCargo : %d T\nFuel  : %d T\n' % (cargo, fuel)

    # Add mass and range
    assert data['ship']['name'].lower() in companion.ship_map, data['ship']['name']
    assert companion.ship_map[data['ship']['name'].lower()] in ships, companion.ship_map[data['ship']['name'].lower()]
    try:
        # https://github.com/cmmcleod/coriolis/blob/master/app/js/shipyard/module-shipyard.js#L184
        mass += ships[companion.ship_map[data['ship']['name'].lower()]]['hullMass']
        string += 'Mass  : %.2f T empty\n        %.2f T full\n' % (mass, mass + fuel + cargo)
        multiplier = pow(min(fuel, fsd['maxfuel']) / fsd['fuelmul'], 1.0 / fsd['fuelpower']) * fsd['optmass']
        string += 'Range : %.2f LY unladen\n        %.2f LY laden\n' % (
            multiplier / (mass + fuel) + jumpboost,
            multiplier / (mass + fuel + cargo) + jumpboost)
    except:
        if __debug__: raise

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = companion.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + '\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return	# same as last time - don't write

    # Write
    filename = join(config.get('outdir'), '%s.%s.txt' % (ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))
    with open(filename, 'wt') as h:
        h.write(string)
