# Export ship loadout in E:D Shipyard format

from collections import defaultdict
import os
from os.path import join
import re
import time

from config import config
import outfitting
from companion import ship_map


# API slot names to E:D Shipyard slot names
slot_map = {
    'HugeHardpoint'    : 'H',
    'LargeHardpoint'   : 'L',
    'MediumHardpoint'  : 'M',
    'SmallHardpoint'   : 'S',
    'TinyHardpoint'    : 'U',
    'Armour'           : 'BH',
    'PowerPlant'       : 'RB',
    'MainEngines'      : 'TM',
    'FrameShiftDrive'  : 'FH',
    'LifeSupport'      : 'EC',
    'PowerDistributor' : 'PC',
    'Radar'            : 'SS',
    'FuelTank'         : 'FS',
}

def export(data):

    def class_rating(module):
        if 'guidance' in module:
            return module['class'] + module['rating'] + '/' + module.get('mount', 'F')[0] + module['guidance'][0] + ' '
        elif 'mount' in module:
            return module['class'] + module['rating'] + '/' + module['mount'][0] + ' '
        else:
            return module['class'] + module['rating'] + ' '

    querytime = config.getint('querytime') or int(time.time())

    ship = ship_map.get(data['ship']['name'], data['ship']['name'])

    loadout = defaultdict(list)

    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v: continue

            module = outfitting.lookup(v['module'])
            if not module: continue

            cr = class_rating(module)

            # Specials
            if module['name'] in ['Fuel Tank', 'Cargo Rack']:
                name = '%s (Capacity: %d)' % (module['name'], 2**int(module['class']))
            else:
                name = module['name']

            for s in slot_map:
                if slot.startswith(s):
                    loadout[slot_map[s]].append(cr + name)
                    break
            else:
                if slot.startswith('Slot'):
                    loadout[slot[-1]].append(cr + name)
                elif __debug__: print 'Loadout: Unknown slot %s' % slot

        except AssertionError as e:
            if __debug__: print 'Loadout: %s' % e
            continue	# Silently skip unrecognized modules
        except:
            if __debug__: raise

    # Construct description
    string = '[%s]\n' % ship
    for slot in ['H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, '9', '8', '7', '6', '5', '4', '3', '2', '1']:
        if not slot:
            string += '\n'
        elif slot in loadout:
            for name in loadout[slot]:
                string += '%s: %s\n' % (slot, name)
    string += '---\nCargo : %d T\nFuel  : %d T\n' % (data['ship']['cargo']['capacity'], data['ship']['fuel']['capacity'])

    # Look for last ship of this type
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
