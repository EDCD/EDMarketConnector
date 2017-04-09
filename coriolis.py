#!/usr/bin/python
#
# Export ship loadout in Coriolis format
#

import base64
from collections import OrderedDict
import cPickle
import json
import os
from os.path import join
import re
import StringIO
import time
import gzip

from config import config
import outfitting
import companion


# Map API slot names to Coriolis categories
# http://cdn.coriolis.io/schemas/ship-loadout/2.json

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
    'military'         : 'internal',
    'slot'             : 'internal',
}


# Map API ship names to Coriolis names
ship_map = dict(companion.ship_map)
ship_map['cobramkiii'] = 'Cobra Mk III'
ship_map['cobramkiv']  = 'Cobra Mk IV',
ship_map['viper']      = 'Viper'
ship_map['viper_mkiv'] = 'Viper Mk IV'


# Map EDDN outfitting schema / in-game names to Coriolis names
# https://raw.githubusercontent.com/jamesremuscat/EDDN/master/schemas/outfitting-v1.0.json

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
fixup_map = {}
fixup_map.update({ x[0] : ('Scanner', x[0]) for x in outfitting.misc_internal_map.values() })
fixup_map.update({ x[0] : ('Countermeasure', x[0]) for x in outfitting.countermeasure_map.values() })
fixup_map.update({
    'Advanced Plasma Accelerator'   : ('Plasma Accelerator', 'Advanced Plasma Accelerator'),
    'Corrosion Resistant Cargo Rack': ('Cargo Rack', 'Corrosion Resistant'),
    'Cytoscrambler Burst Laser'     : ('Burst Laser', 'Cytoscrambler'),
    'Enforcer Cannon'               : ('Multi-cannon', 'Enforcer'),
    'Enhanced Performance Thrusters': ('Thrusters', 'Enhanced Performance'),
    'Imperial Hammer Rail Gun'      : ('Rail Gun', 'Imperial Hammer'),
    'Luxury Class Passenger Cabin'  : ('Luxury Passenger Cabin', None),
    'Mining Lance Beam Laser'       : ('Mining Laser', 'Mining Lance'),
    'Multi-Cannon'                  : ('Multi-cannon', None),
    'Pacifier Frag-Cannon'          : ('Fragment Cannon', 'Pacifier'),
    'Pack-Hound Missile Rack'       : ('Missile Rack', 'Pack-Hound'),
    'Pulse Disruptor Laser'         : ('Pulse Laser', 'Disruptor'),
    'Retributor Beam Laser'         : ('Beam Laser', 'Retributor'),
    'Rocket Propelled FSD Disruptor': ('Missile Rack', 'Rocket Propelled FSD Disruptor'),
    'Shock Mine Launcher'           : ('Mine Launcher', 'Shock Mine Launcher'),
    'Standard Docking Computer'     : ('Docking Computer', 'Standard Docking Computer'),
})


# Ship masses
ships = cPickle.load(open(join(config.respath, 'ships.p'),  'rb'))


def export(data, filename=None):

    querytime = config.getint('querytime') or int(time.time())

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
    mass = 0.0
    fsd = None

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
                if __debug__:
                    for skip in ['bobble', 'decal', 'paintjob', 'planetaryapproachsuite', 'enginecolour', 'shipkit', 'weaponcolour']:
                        if slot.lower().startswith(skip):
                            break
                    else:
                        print 'Coriolis: Unknown slot %s' % slot
                continue

            if not v:
                # Need to add nulls for empty slots. Assumes that standard slots can't be empty.
                loadout['components'][category].append(None)
                continue

            module = outfitting.lookup(v['module'], ship_map)
            if not module:
                raise AssertionError('Unknown module %s' % v)	# Shouldn't happen
            mass += module.get('mass', 0)

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
                    if module['name'] == 'Frame Shift Drive':
                        fsd = module	# save for range calculation
            else:
                # All other items have a "group" member, some also have a "name"
                if module['name'] in fixup_map:
                    thing['group'], name = fixup_map[module['name']]
                    if name: thing['name'] = name
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

    # Add mass and range
    assert data['ship']['name'].lower() in companion.ship_map, data['ship']['name']
    assert companion.ship_map[data['ship']['name'].lower()] in ships, companion.ship_map[data['ship']['name'].lower()]
    try:
        # https://github.com/cmmcleod/coriolis/blob/master/app/js/shipyard/module-shipyard.js#L184
        hullMass = ships[companion.ship_map[data['ship']['name'].lower()]]['hullMass']
        mass += hullMass
        multiplier = pow(min(data['ship']['fuel']['main']['capacity'], fsd['maxfuel']) / fsd['fuelmul'], 1.0 / fsd['fuelpower']) * fsd['optmass']

        loadout['stats'] = OrderedDict([
            ('hullMass',      hullMass),
            ('fuelCapacity',  data['ship']['fuel']['main']['capacity']),
            ('cargoCapacity', data['ship']['cargo']['capacity']),
            ('ladenMass',     mass + data['ship']['fuel']['main']['capacity'] + data['ship']['cargo']['capacity']),
            ('unladenMass',   mass),
            ('unladenRange',  round(multiplier / (mass + min(data['ship']['fuel']['main']['capacity'], fsd['maxfuel'])), 2)),	# fuel for one jump
            ('fullTankRange', round(multiplier / (mass + data['ship']['fuel']['main']['capacity']), 2)),
            ('ladenRange',    round(multiplier / (mass + data['ship']['fuel']['main']['capacity'] + data['ship']['cargo']['capacity']), 2)),
        ])
    except:
        if __debug__: raise

    # Construct description
    string = json.dumps(loadout, indent=2, separators=(',', ': '))

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])	# Use in-game name
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


# Return a URL for the current ship
def url(data):

    string = json.dumps(companion.ship(data), ensure_ascii=False, sort_keys=True, separators=(',', ':'))	# most compact representation

    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)
    return 'https://coriolis.edcd.io/import?data=' + base64.urlsafe_b64encode(out.getvalue()).replace('=', '%3D')


#
# build ship and module databases from https://github.com/cmmcleod/coriolis-data
#
if __name__ == "__main__":
    import json
    data = json.load(open('coriolis-data/dist/index.json'))

    # Map Coriolis's names to names displayed in the in-game shipyard
    coriolis_ship_map = {
        'Cobra Mk III' : 'Cobra MkIII',
        'Cobra Mk IV'  : 'Cobra MkIV',
        'Viper'        : 'Viper MkIII',
        'Viper Mk IV'  : 'Viper MkIV',
    }

    # From https://github.com/EDCD/coriolis/blob/master/src/app/shipyard/Constants.js
    ModuleGroupToName = {
        # Standard
        'pp'  : 'Power Plant',
        't'   : 'Thrusters',
        'fsd' : 'Frame Shift Drive',
        'ls'  : 'Life Support',
        'pd'  : 'Power Distributor',
        's'   : 'Sensors',
        'ft'  : 'Fuel Tank',
        'pas' : 'Planetary Approach Suite',

        # Internal
        'fs'  : 'Fuel Scoop',
        'sc'  : 'Scanner',
        'ss'  : 'Detailed Surface Scanner',
        'am'  : 'Auto Field-Maintenance Unit',
        'bsg' : 'Bi-Weave Shield Generator',
        'cr'  : 'Cargo Rack',
        'fh'  : 'Fighter Hangar',
        'fi'  : 'Frame Shift Drive Interdictor',
        'hb'  : 'Hatch Breaker Limpet Controller',
        'hr'  : 'Hull Reinforcement Package',
        'rf'  : 'Refinery',
        'scb' : 'Shield Cell Bank',
        'sg'  : 'Shield Generator',
        'pv'  : 'Planetary Vehicle Hangar',
        'psg' : 'Prismatic Shield Generator',
        'dc'  : 'Docking Computer',
        'fx'  : 'Fuel Transfer Limpet Controller',
        'mrp' : 'Module Reinforcement Package',
        'pc'  : 'Prospector Limpet Controller',
        'pce' : 'Economy Class Passenger Cabin',
        'pci' : 'Business Class Passenger Cabin',
        'pcm' : 'First Class Passenger Cabin',
        'pcq' : 'Luxury Passenger Cabin',
        'cc'  : 'Collector Limpet Controller',

        # Hard Points
        'bl'  : 'Beam Laser',
        'ul'  : 'Burst Laser',
        'c'   : 'Cannon',
        'ch'  : 'Chaff Launcher',
        'cs'  : 'Cargo Scanner',
        'cm'  : 'Countermeasure',
        'ec'  : 'Electronic Countermeasure',
        'fc'  : 'Fragment Cannon',
        'hs'  : 'Heat Sink Launcher',
        'ws'  : 'Frame Shift Wake Scanner',
        'kw'  : 'Kill Warrant Scanner',
        'nl'  : 'Mine Launcher',
        'ml'  : 'Mining Laser',
        'mr'  : 'Missile Rack',
        'pa'  : 'Plasma Accelerator',
        'po'  : 'Point Defence',
        'mc'  : 'Multi-cannon',
        'pl'  : 'Pulse Laser',
        'rg'  : 'Rail Gun',
        'sb'  : 'Shield Booster',
        'tp'  : 'Torpedo Pylon'
    };

    specials = { v:k for k,v in fixup_map.items() }

    ships = {}
    modules = {}

    # Ship and armour masses
    for m in data['Ships'].values():
        name = coriolis_ship_map.get(m['properties']['name'], str(m['properties']['name']))
        ships[name] = { 'hullMass' : m['properties']['hullMass'] }
        for i in range(len(bulkheads)):
            modules[(bulkheads[i], name, '1', 'I')] = { 'mass': m['bulkheads'][i]['mass'] }

    ships = OrderedDict([(k,ships[k]) for k in sorted(ships)])	# sort for easier diffing
    cPickle.dump(ships, open('ships.p', 'wb'))

    # Module masses
    for cat in data['Modules'].values():
        for grp, mlist in cat.iteritems():
            for m in mlist:
                key = (specials.get((ModuleGroupToName[grp], m.get('name'))) or ModuleGroupToName[grp],
                       None,
                       str(m['class']),
                       str(m['rating']))
                if key in modules:
                    # Test our assumption that mount and guidance don't affect mass
                    assert modules[key]['mass'] == m.get('mass', 0), '%s !=\n%s' % (key, m)
                elif grp == 'fsd':
                    modules[key] = {
                        'mass'      : m['mass'],
                        'optmass'   : m['optmass'],
                        'maxfuel'   : m['maxfuel'],
                        'fuelmul'   : m['fuelmul'],
                        'fuelpower' : m['fuelpower'],
                    }
                else:
                    modules[key] = { 'mass': m.get('mass', 0) }	# Some modules don't have mass

    modules = OrderedDict([(k,modules[k]) for k in sorted(modules)])	# sort for easier diffing
    cPickle.dump(modules, open('modules.p', 'wb'))
