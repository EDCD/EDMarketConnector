# Export ship loadout in E:D Shipyard format

from collections import defaultdict
import cPickle
import os
from os.path import join
import re
import time

from config import config
import outfitting
import companion


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
}


# Ship masses
ships = cPickle.load(open(join(config.respath, 'ships.p'),  'rb'))


def export(data, filename=None):

    def class_rating(module):
        if 'guidance' in module:
            return module['class'] + module['rating'] + '/' + module.get('mount', 'F')[0] + module['guidance'][0] + ' '
        elif 'mount' in module:
            return module['class'] + module['rating'] + '/' + module['mount'][0] + ' '
        else:
            return module['class'] + module['rating'] + ' '

    querytime = config.getint('querytime') or int(time.time())

    loadout = defaultdict(list)
    mass = 0.0
    fsd = None

    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v: continue

            module = outfitting.lookup(v['module'], ship_map)
            if not module: continue

            cr = class_rating(module)
            mass += module.get('mass', 0)

            # Specials
            if module['name'] in ['Fuel Tank', 'Cargo Rack']:
                name = '%s (Capacity: %d)' % (module['name'], 2**int(module['class']))
            else:
                name = module['name']

            if name == 'Frame Shift Drive':
                fsd = module	# save for range calculation

            for s in slot_map:
                if slot.lower().startswith(s):
                    loadout[slot_map[s]].append(cr + name)
                    break
            else:
                if slot.lower().startswith('slot'):
                    loadout[slot[-1]].append(cr + name)
                elif __debug__: print 'Loadout: Unknown slot %s' % slot

        except AssertionError as e:
            if __debug__: print 'Loadout: %s' % e
            continue	# Silently skip unrecognized modules
        except:
            if __debug__: raise

    # Construct description
    string = '[%s]\n' % ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
    for slot in ['H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, '9', '8', '7', '6', '5', '4', '3', '2', '1']:
        if not slot:
            string += '\n'
        elif slot in loadout:
            for name in loadout[slot]:
                string += '%s: %s\n' % (slot, name)
    string += '---\nCargo : %d T\nFuel  : %d T\n' % (data['ship']['cargo']['capacity'], data['ship']['fuel']['main']['capacity'])

    # Add mass and range
    assert data['ship']['name'].lower() in companion.ship_map, data['ship']['name']
    assert companion.ship_map[data['ship']['name'].lower()] in ships, companion.ship_map[data['ship']['name'].lower()]
    try:
        # https://github.com/cmmcleod/coriolis/blob/master/app/js/shipyard/module-shipyard.js#L184
        mass += ships[companion.ship_map[data['ship']['name'].lower()]]['hullMass']
        string += 'Mass  : %.1f T empty\n        %.1f T full\n' % (mass, mass + data['ship']['fuel']['main']['capacity']+ data['ship']['cargo']['capacity'])
        multiplier = pow(min(data['ship']['fuel']['main']['capacity'], fsd['maxfuel']) / fsd['fuelmul'], 1.0 / fsd['fuelpower']) * fsd['optmass']
        string += 'Range : %.2f LY unladen\n        %.2f LY laden\n' % (
            multiplier / (mass + data['ship']['fuel']['main']['capacity']),
            multiplier / (mass + data['ship']['fuel']['main']['capacity'] + data['ship']['cargo']['capacity']))
    except:
        if __debug__: raise

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])	# Use in-game name
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
