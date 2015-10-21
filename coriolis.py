# Export ship loadout in Coriolis format

from collections import OrderedDict
import json
import os
from os.path import join
import re
import time

from config import config
import outfitting
import companion


slot_map = {
    'hugehardpoint'    : 'hardpoints',
    'largehardpoint'   : 'hardpoints',
    'mediumhardpoint'  : 'hardpoints',
    'smallhardpoint'   : 'hardpoints',
    'tinyhardpoint'    : 'utility',
    'armour'           : 'standard',
    'powerplant'       : 'standard',
    'mainengines'      : 'standard',
    'frameshiftdrive'  : 'standard',
    'lifesupport'      : 'standard',
    'powerdistributor' : 'standard',
    'radar'            : 'standard',
    'fueltank'         : 'standard',
    'slot'             : 'internal',
}

# Map draft E:D Shipyard & EDDN outfitting to Coriolis
# https://raw.githubusercontent.com/jamesremuscat/EDDN/master/schemas/outfitting-v1.0-draft.json
# http://cdn.coriolis.io/schemas/ship-loadout/2.json

ship_map = dict(companion.ship_map)
ship_map['asp'] = 'Asp Explorer'

standard_map = OrderedDict([	# in output order
    ('Armour',            'bulkheads'),
    (None,                'cargoHatch'),	# not available in the Companion API data
    ('Power Plant',       'powerPlant'),
    ('Thrusters',         'thrusters'),
    ('Frame Shift Drive', 'frameShiftDrive'),
    ('Life Support',      'lifeSupport'),
    ('Power Distributor', 'powerDistributor'),
    ('Sensors',           'sensors'),
    ('Fuel Tank',         'fuelTank'),
])

weaponmount_map = {
    'Fixed'     : 'Fixed',
    'Gimballed' : 'Gimballed',
    'Turreted'  : 'Turret',
}


# Modules that have a name as well as a group
bulkheads       = outfitting.armour_map.values()
scanners        = [x[0] for x in outfitting.misc_internal_map.values()]
countermeasures = [x[0] for x in outfitting.countermeasure_map.values()]
fixup_map = {
    'Advanced Plasma Accelerator'   : ('Plasma Accelerator', 'Advanced Plasma Accelerator'),
    'Cytoscrambler Burst Laser'     : ('Burst Laser', 'Cytoscrambler'),
    'Enforcer Cannon'               : ('Multi-cannon', 'Enforcer'),
    'Imperial Hammer Rail Gun'      : ('Rail Gun', 'Imperial Hammer'),
    'Impulse Mine Launcher'         : ('Mine Launcher', 'Impulse'),
    'Mining Lance Beam Laser'       : ('Mining Laser', 'Mining Lance'),
    'Multi-Cannon'                  : ('Multi-cannon', None),
    'Pacifier Frag-Cannon'          : ('Fragment Cannon', 'Pacifier'),
    'Pack-Hound Missile Rack'       : ('Missile Rack', 'Pack-Hound'),
    'Pulse Disruptor Laser'         : ('Pulse Laser', 'Distruptor'),	# Note sp
    'Standard Docking Computer'     : ('Docking Computer', 'Standard Docking Computer'),
}


def export(data):

    querytime = config.getint('querytime') or int(time.time())

    ship = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])

    loadout = OrderedDict([	# Mimic Coriolis export ordering
        ('$schema',    'http://cdn.coriolis.io/schemas/ship-loadout/2.json#'),
        ('name',       ship_map.get(data['ship']['name'].lower(), data['ship']['name'])),
        ('ship',       ship_map.get(data['ship']['name'].lower(), data['ship']['name'])),
        ('components', OrderedDict([
            ('standard',   OrderedDict([(x,None) for x in standard_map.values()])),
            ('hardpoints', []),
            ('utility',    []),
            ('internal',   []),
        ])),
    ])
    maxpri = 0

    # Correct module ordering relies on the fact that "Slots" in the data  are correctly ordered alphabetically.
    # Correct hardpoint ordering additionally relies on the fact that "Huge" < "Large" < "Medium" < "Small"
    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            for s in slot_map:
                if slot.lower().startswith(s):
                    category = slot_map[s]
                    break
            else:
                # Uninteresting slot - e.g. DecalX or PaintJob
                if __debug__ and not slot.lower().startswith('decal') and not slot.lower().startswith('paintjob'):
                    print 'Coriolis: Unknown slot %s' % slot
                continue

            if not v:
                # Need to add nulls for empty slots. Assumes that standard slots can't be empty.
                loadout['components'][category].append(None)
                continue

            module = outfitting.lookup(v['module'])
            if not module:
                raise AssertionError('Unknown module %s' % v)	# Shouldn't happen

            thing = OrderedDict([
                ('class',int(module['class'])),
                ('rating',   module['rating']),
                ('enabled',  module['enabled']),
                ('priority', module['priority']+1),	# make 1-based
            ])
            maxpri = max(maxpri, thing['priority'])

            if category == 'standard':
                # Standard items are indexed by "group" rather than containing a "group" member
                if module['name'] in bulkheads:
                    loadout['components'][category]['bulkheads'] = module['name']	# Bulkheads are just strings
                else:
                    loadout['components'][category][standard_map[module['name']]] = thing
            else:
                # All other items have a "group" member, some also have a "name"
                if module['name'] in fixup_map:
                    thing['group'], name = fixup_map[module['name']]
                    if name: thing['name'] = name
                elif module['name'] in scanners:
                    thing['group'] = 'Scanner'
                    thing['name'] = module['name']
                elif module['name'] in countermeasures:
                    thing['group'] = 'Countermeasure'
                    thing['name'] = module['name']
                else:
                    thing['group'] = module['name']

                if 'mount' in module:
                    thing['mount'] = weaponmount_map[module['mount']]
                if 'guidance' in module:
                    thing['missile'] = module['guidance'][0]	# not mentioned in schema

                loadout['components'][category].append(thing)

        except AssertionError as e:
            # Silently skip unrecognized modules
            if __debug__: print 'Coriolis: %s' % e
            if category != 'standard':
                loadout['components'][category].append(None)
        except:
            if __debug__: raise

    # Cargo Hatch status is not available in the data - fake something up
    loadout['components']['standard']['cargoHatch'] = OrderedDict([
        ('enabled',  True),
        ('priority', maxpri),
    ])

    # Construct description
    string = json.dumps(loadout, indent=2)

    # Look for last ship of this type
    regexp = re.compile(re.escape(ship) + '\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.json')
    oldfiles = sorted([x for x in os.listdir(config.get('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return	# same as last time - don't write

    # Write
    filename = join(config.get('outdir'), '%s.%s.json' % (ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))
    with open(filename, 'wt') as h:
        h.write(string)
