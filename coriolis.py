#!/usr/bin/python
#
# Export ship loadout in Coriolis format
#

import base64
from collections import OrderedDict
import cPickle
import json
import StringIO
import gzip

from config import config
import outfitting
import companion


# Return a URL for the current ship
def url(data, is_beta):

    string = json.dumps(companion.ship(data), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')	# most compact representation

    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)
    return (is_beta and 'https://beta.coriolis.edcd.io/import?data=' or 'https://coriolis.edcd.io/import?data=') + base64.urlsafe_b64encode(out.getvalue()).replace('=', '%3D')


#
# build ship and module databases from https://github.com/EDCD/coriolis-data/
#
if __name__ == "__main__":
    data = json.load(open('coriolis-data/dist/index.json'))

    bulkheads       = outfitting.armour_map.values()

    # Modules that have a name as well as a group
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
    specials = { v:k for k,v in fixup_map.items() }

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

    # Repair and Research Limpet Controller not yet present in coriolis-data. Same masses as Prospector.
    # (Note only seen 1E Research).
    for k in modules.keys():
        if k[0] == 'Prospector Limpet Controller':
            modules[('Repair Limpet Controller',) + k[1:]] = modules[k]
            modules[('Research Limpet Controller',) + k[1:]] = modules[k]

    # Other 2.4 additions not yet present in coriolis-data
    modules[('AX Missile Rack', None, '2', 'B')] = {'mass': 4}
    modules[('Xeno Scanner', None, '0', 'E')] = {'mass': 1.3}

    modules = OrderedDict([(k,modules[k]) for k in sorted(modules)])	# sort for easier diffing
    cPickle.dump(modules, open('modules.p', 'wb'))
