#!/usr/bin/python
#
# Script for building table ID->module mapping table from a dump of the Companion API output
#

import csv
import json
import os
from os.path import exists, isfile
import sys
import time

from shipyard import ship_map
from config import config


outfile = 'outfitting.csv'
outfitting = {}

armour_map = {
    'grade1'   : 'Lightweight Alloy',
    'grade2'   : 'Reinforced Alloy',
    'grade3'   : 'Military Grade Composite',
    'mirrored' : 'Mirrored Surface Composite',
    'reactive' : 'Reactive Surface Composite',
}

weapon_map = {
    'advancedtorppylon'              : 'Torpedo Pylon',
    'basicmissilerack'               : 'Missile Rack',
    'beamlaser'                      : 'Beam Laser',
    ('beamlaser','heat')             : 'Retributor Beam Laser',
    'cannon'                         : 'Cannon',
    'drunkmissilerack'               : 'Pack-Hound Missile Rack',
    'dumbfiremissilerack'            : 'Missile Rack',
    'minelauncher'                   : 'Mine Launcher',
    ('minelauncher','impulse')       : 'Impulse Mine Launcher',	# Not seen in game?
    'mininglaser'                    : 'Mining Laser',
    ('mininglaser','advanced')       : 'Mining Lance Beam Laser',
    'multicannon'                    : 'Multi-Cannon',
    ('multicannon','strong')         : 'Enforcer Cannon',
    'plasmaaccelerator'              : 'Plasma Accelerator',
    ('plasmaaccelerator','advanced') : 'Advanced Plasma Accelerator',
    'pulselaser'                     : 'Pulse Laser',
    ('pulselaser','disruptor')       : 'Pulse Disruptor Laser',
    'pulselaserburst'                : 'Burst Laser',
    ('pulselaserburst','scatter')    : 'Cytoscrambler Burst Laser',
    'railgun'                        : 'Rail Gun',
    ('railgun','burst')              : 'Imperial Hammer Rail Gun',
    'slugshot'                       : 'Fragment Cannon',
    ('slugshot','range')             : 'Pacifier Frag-Cannon',
}

missiletype_map = {
    'advancedtorppylon'   : 'Seeker',
    'basicmissilerack'    : 'Seeker',
    'drunkmissilerack'    : 'Swarm',
    'dumbfiremissilerack' : 'Dumbfire',
}

weaponmount_map = {
    'fixed'  : 'Fixed',
    'gimbal' : 'Gimballed',
    'turret' : 'Turreted',
}

weaponclass_map = {
    'tiny'   : '0',
    'small'  : '1',
    'medium' : '2',
    'large'  : '3',
    'huge'   : '4',
}

# There's no discernable pattern for weapon ratings, so here's a lookup table
weaponrating_map = {
    'hpt_advancedtorppylon_fixed_small' : 'I',
    'hpt_advancedtorppylon_fixed_medium': 'I',
    'hpt_basicmissilerack_fixed_small'  : 'B',
    'hpt_basicmissilerack_fixed_medium' : 'B',
    'hpt_beamlaser_fixed_small'         : 'E',
    'hpt_beamlaser_fixed_medium'        : 'D',
    'hpt_beamlaser_fixed_large': 'C',
    'hpt_beamlaser_gimbal_small': 'E',
    'hpt_beamlaser_gimbal_medium': 'D',
    'hpt_beamlaser_gimbal_large': 'C',
    'hpt_beamlaser_turret_small': 'F',
    'hpt_beamlaser_turret_medium': 'E',
    'hpt_beamlaser_turret_large': 'D',
    'hpt_cannon_fixed_small': 'D',
    'hpt_cannon_fixed_medium': 'D',
    'hpt_cannon_fixed_large': 'C',
    'hpt_cannon_fixed_huge': 'B',
    'hpt_cannon_gimbal_small': 'E',
    'hpt_cannon_gimbal_medium': 'D',
    'hpt_cannon_gimbal_large': 'C',
    'hpt_cannon_gimbal_huge': 'B',
    'hpt_cannon_turret_small': 'F',
    'hpt_cannon_turret_medium': 'E',
    'hpt_cannon_turret_large': 'D',
    'hpt_drunkmissilerack_fixed_medium': 'B',
    'hpt_dumbfiremissilerack_fixed_small': 'B',
    'hpt_dumbfiremissilerack_fixed_medium': 'B',
    'hpt_minelauncher_fixed_small': 'I',
    'hpt_minelauncher_fixed_medium': 'I',
    'hpt_mininglaser_fixed_small': 'D',
    'hpt_mininglaser_fixed_medium': 'D',
    'hpt_multicannon_fixed_small': 'F',
    'hpt_multicannon_fixed_medium': 'E',
    'hpt_multicannon_gimbal_small': 'G',
    'hpt_multicannon_gimbal_medium': 'F',
    'hpt_multicannon_turret_small': 'G',
    'hpt_multicannon_turret_medium': 'F',
    'hpt_plasmaaccelerator_fixed_medium': 'C',
    'hpt_plasmaaccelerator_fixed_large': 'B',
    'hpt_plasmaaccelerator_fixed_huge': 'A',
    'hpt_pulselaser_fixed_small': 'F',
    'hpt_pulselaser_fixed_medium': 'E',
    'hpt_pulselaser_fixed_large': 'D',
    'hpt_pulselaser_gimbal_small': 'G',
    'hpt_pulselaser_gimbal_medium': 'F',
    'hpt_pulselaser_gimbal_large': 'E',
    'hpt_pulselaser_turret_small': 'G',
    'hpt_pulselaser_turret_medium': 'F',
    'hpt_pulselaser_turret_large': 'F',
    'hpt_pulselaserburst_fixed_small': 'F',
    'hpt_pulselaserburst_fixed_medium': 'E',
    'hpt_pulselaserburst_fixed_large': 'D',
    'hpt_pulselaserburst_gimbal_small': 'G',
    'hpt_pulselaserburst_gimbal_medium': 'F',
    'hpt_pulselaserburst_gimbal_large': 'E',
    'hpt_pulselaserburst_turret_small': 'G',
    'hpt_pulselaserburst_turret_medium': 'F',
    'hpt_pulselaserburst_turret_large': 'E',
    'hpt_railgun_fixed_small': 'D',
    'hpt_railgun_fixed_medium': 'B',
    'hpt_slugshot_fixed_small': 'E',
    'hpt_slugshot_fixed_medium': 'A',
    'hpt_slugshot_fixed_large': 'C',
    'hpt_slugshot_gimbal_small': 'E',
    'hpt_slugshot_gimbal_medium': 'D',
    'hpt_slugshot_gimbal_large': 'C',
    'hpt_slugshot_turret_small': 'E',
    'hpt_slugshot_turret_medium': 'D',
    'hpt_slugshot_turret_large': 'C',
}

# Old standard weapon variants
weaponoldvariant_map = {
    'f'  : 'Focussed',
    'hi' : 'High Impact',
    'lh' : 'Low Heat',
    'oc' : 'Overcharged',
    'ss' : 'Scatter Spray',
}

countermeasure_map = {
    'chafflauncher'            : ('Chaff Launcher', 'I'),
    'electroniccountermeasure' : ('Electronic Countermeasure', 'F'),
    'heatsinklauncher'         : ('Heat Sink Launcher', 'I'),
    'plasmapointdefence'       : ('Point Defence', 'I'),
}

utility_map = {
    'cargoscanner'             : 'Cargo Scanner',
    'cloudscanner'             : 'Frame Shift Wake Scanner',
    'crimescanner'             : 'Kill Warrant Scanner',
    'shieldbooster'            : 'Shield Booster',
}

rating_map = {
    '1': 'E',
    '2': 'D',
    '3': 'C',
    '4': 'B',
    '5': 'A',
}

misc_internal_map = {
    ('detailedsurfacescanner',      'tiny')         : ('Detailed Surface Scanner', 'C'),
    ('dockingcomputer',             'standard')     : ('Standard Docking Computer', 'E'),
    ('stellarbodydiscoveryscanner', 'standard')     : ('Basic Discovery Scanner', 'E'),
    ('stellarbodydiscoveryscanner', 'intermediate') : ('Intermediate Discovery Scanner', 'D'),
    ('stellarbodydiscoveryscanner', 'advanced')     : ('Advanced Discovery Scanner', 'C'),
}

standard_map = {
    # 'armour'         : handled separately
    'engine'           : 'Thrusters',
    'fueltank'         : 'Fuel Tank',
    'hyperdrive'       : 'Frame Shift Drive',
    'lifesupport'      : 'Life Support',
    'powerdistributor' : 'Power Distributor',
    'powerplant'       : 'Power Plant',
    'sensors'          : 'Sensors',
}

internal_map = {
    'cargorack'         : 'Cargo Rack',
    'collection'        : 'Collector Limpet Controller',
    'fsdinterdictor'    : 'Frame Shift Drive Interdictor',
    'fuelscoop'         : 'Fuel Scoop',
    'fueltransfer'      : 'Fuel Transfer Limpet Controller',
    'hullreinforcement' : 'Hull Reinforcement Package',
    'prospector'        : 'Prospector Limpet Controller',
    'refinery'          : 'Refinery',
    'repairer'          : 'Auto Field-Maintenance Unit',
    'resourcesiphon'    : 'Hatch Breaker Limpet Controller',
    'shieldcellbank'    : 'Shield Cell Bank',
    'shieldgenerator'   : 'Shield Generator',
    ('shieldgenerator','strong') : 'Prismatic Shield Generator',
}


# Given a module description from the Companion API returns a description of the module in the form of a
# dict { category, name, [mount], [guidance], [ship], rating, class } using the same terms found in the
# English langauge game. For fitted modules, dict also includes { enabled, priority }.
# Or returns None if the module is user-specific (i.e. decal, paintjob).
# (Given the ad-hocery in this implementation a big lookup table might have been simpler and clearer).
def lookup(module):

    # if not module.get('category'): raise AssertionError('%s: Missing category' % module['id'])	# only present post 1.3, and not present in ship loadout
    if not module.get('name'): raise AssertionError('%s: Missing name' % module['id'])

    name = module['name'].lower().split('_')
    new = {}

    # Armour - e.g. Federation_Dropship_Armour_Grade2
    if name[-2] == 'armour':
        name = module['name'].lower().rsplit('_', 2)	# Armour is ship-specific, and ship names can have underscores
        new['category'] = 'standard'
        new['name'] = armour_map[name[2]]
        new['ship'] = ship_map[name[0]]		# Generate error on unknown ship
        new['class'] = '1'
        new['rating'] = 'I'

    # Skip uninteresting stuff
    elif name[0] in ['decal', 'paintjob']:
        return None

    # Skip PP-specific modules in outfitting which have an sku like ELITE_SPECIFIC_V_POWER_100100
    elif 'category' in module and module['category'].lower() == 'powerplay':
        return None

    # Shouldn't be listing player-specific paid stuff
    elif module.get('sku'):
        raise AssertionError('%s: Unexpected sku "%s"' % (module['id'], module['sku']))

    # Hardpoints - e.g. Hpt_Slugshot_Fixed_Medium
    elif name[0]=='hpt' and name[1] in weapon_map:
        if name[2] not in weaponmount_map: raise AssertionError('%s: Unknown weapon mount "%s"' % (module['id'], name[2]))
        if name[3] not in weaponclass_map: raise AssertionError('%s: Unknown weapon class "%s"' % (module['id'], name[3]))
        new['category'] = 'hardpoint'
        if len(name)>4:
            if name[4] in weaponoldvariant_map:		# Old variants e.g. Hpt_PulseLaserBurst_Turret_Large_OC
                new['name'] =  weapon_map[name[1]] + ' ' + weaponoldvariant_map[name[4]]
                new['rating'] = '?'
            else:			# PP faction-specific weapons e.g. Hpt_Slugshot_Fixed_Large_Range
                new['name'] =  weapon_map[(name[1],name[4])]
                new['rating'] = weaponrating_map.get(('_').join(name[:4]), '?')	# assumes same rating as base weapon
        else:
            new['name'] =  weapon_map[name[1]]
            new['rating'] = weaponrating_map.get(module['name'].lower(), '?')		# no obvious rule - needs lookup table
        new['mount'] = weaponmount_map[name[2]]
        if name[1] in missiletype_map:	# e.g. Hpt_DumbfireMissileRack_Fixed_Small
            new['guidance'] = missiletype_map[name[1]]
        new['class'] = weaponclass_map[name[3]]

    # Countermeasures - e.g. Hpt_PlasmaPointDefence_Turret_Tiny
    elif name[0]=='hpt' and name[1] in countermeasure_map:
        new['category'] = 'utility'
        new['name'], new['rating'] = countermeasure_map[len(name)>4 and (name[1],name[4]) or name[1]]
        new['class'] = weaponclass_map[name[-1]]

    # Utility - e.g. Hpt_CargoScanner_Size0_Class1
    elif name[0]=='hpt' and name[1] in utility_map:
        new['category'] = 'utility'
        new['name'] = utility_map[len(name)>4 and (name[1],name[4]) or name[1]]
        if not name[2].startswith('size') or not name[3].startswith('class'): raise AssertionError('%s: Unknown class/rating "%s/%s"' % (module['id'], name[2], name[3]))
        new['class'] = name[2][4:]
        new['rating'] = rating_map[name[3][5:]]

    elif name[0]=='hpt':
        raise AssertionError('%s: Unknown weapon "%s"' % (module['id'], name[1]))

    elif name[0]!='int':
        raise AssertionError('%s: Unknown prefix "%s"' % (module['id'], name[0]))

    # Miscellaneous Class 1 - e.g. Int_StellarBodyDiscoveryScanner_Advanced, Int_DockingComputer_Standard
    elif (name[1],name[2]) in misc_internal_map:
        # Reported category is not necessarily helpful. e.g. "Int_DockingComputer_Standard" has category "utility"
        new['category'] = 'internal'
        new['name'], new['rating'] = misc_internal_map[(name[1],name[2])]
        new['class'] = '1'

    # Standard & Internal
    else:
        if name[1] == 'dronecontrol':	# e.g. Int_DroneControl_Collection_Size1_Class1
            name.pop(0)

        if name[1] in standard_map:	# e.g. Int_Engine_Size2_Class1, Int_ShieldGenerator_Size8_Class5_Strong
            new['category'] = 'standard'
            new['name'] = standard_map[len(name)>4 and (name[1],name[4]) or name[1]]
        elif name[1] in internal_map:	# e.g. Int_CargoRack_Size8_Class1
            new['category'] = 'internal'
            new['name'] = internal_map[len(name)>4 and (name[1],name[4]) or name[1]]
        else:
            raise AssertionError('%s: Unknown module "%s"' % (module['id'], name[1]))

        if not name[2].startswith('size') or not name[3].startswith('class'): raise AssertionError('%s: Unknown class/rating "%s/%s"' % (module['id'], name[2], name[3]))
        new['class'] = name[2][4:]
        new['rating'] = rating_map[name[3][5:]]

    # Disposition of fitted modules
    if 'on' in module and 'priority' in module:
        new['enabled'], new['priority'] = module['on'], module['priority']	# priority is zero-based

    # check we've filled out mandatory fields
    for thing in ['category', 'name', 'class', 'rating']:
        if not new.get(thing): raise AssertionError('%s: failed to set %s' % (module['id'], thing))
    if new['category'] == 'hardpoint' and not new.get('mount'):
        raise AssertionError('%s: failed to set %s' % (module['id'], 'mount'))

    return new


def export(data, filename):

    querytime = config.getint('querytime') or int(time.time())

    assert data['lastSystem'].get('name')
    assert data['lastStarport'].get('name')

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(querytime))
    header = 'System,Station,Category,Name,Mount,Guidance,Ship,Class,Rating,Date\n'
    rowheader = '%s,%s' % (data['lastSystem']['name'], data['lastStarport']['name'])

    h = open(filename, 'wt')
    h.write(header)
    for v in data['lastStarport'].get('modules', {}).itervalues():
        try:
            m = lookup(v)
            if m:
                h.write('%s,%s,%s,%s,%s,%s,%s,%s,%s\n' % (rowheader, m['category'], m['name'], m.get('mount',''), m.get('guidance',''), m.get('ship',''), m['class'], m['rating'], timestamp))
        except AssertionError as e:
            if __debug__: print 'Outfitting: %s' % e	# Silently skip unrecognized modules
        except:
            if __debug__: raise
    h.close()


# add all the modules
def addmodules(data):
    if not data.get('lastStarport'):
        print 'No Starport!'
        return
    elif not data['lastStarport'].get('modules'):
        print 'No outfitting here'
        return

    # read into outfitting
    if isfile(outfile):
        with open(outfile) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                key = int(row.pop('id'))	# index by int for easier lookup and sorting
                outfitting[key] = row
    size_pre = len(outfitting)

    for key,module in data['lastStarport'].get('modules').iteritems():
        # sanity check
        if int(key) != module.get('id'): raise AssertionError('id: %s!=%s' % (key, module['id']))
        new = lookup(module)
        if new:
            old = outfitting.get(int(key))
            if old:
                # check consistency with existing data
                for thing in ['category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating']:
                    if new.get(thing,'') != old.get(thing): raise AssertionError('%s: %s "%s"!="%s"' % (key, thing, new.get(thing), old.get(thing)))
            else:
                outfitting[int(key)] = new

    if len(outfitting) > size_pre:

        if isfile(outfile):
            if isfile(outfile+'.bak'):
                os.unlink(outfile+'.bak')
            os.rename(outfile, outfile+'.bak')

        with open(outfile, 'wb') as csvfile:
            writer = csv.DictWriter(csvfile, ['id', 'category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating'])
            writer.writeheader()
            for key in sorted(outfitting):
                row = outfitting[key]
                row['id'] = key
                writer.writerow(row)

        print 'Added %d new modules' % (len(outfitting) - size_pre)

    else:
        print

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print 'Usage: outfitting.py [dump.json]'
    else:
        # read from dumped json file(s)
        for f in sys.argv[1:]:
            with open(f) as h:
                print f,
                addmodules(json.loads(h.read()))
