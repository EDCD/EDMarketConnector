#!/usr/bin/python
#
# Script for building table ID->module mapping table from a dump of the Companion API output
#

import csv
import json
import os
from os.path import exists, isfile
import sys

from companion import ship_map


outfile = 'outfitting.csv'
outfitting = {}

armour_map = {
    'Grade1'   : 'Lightweight Alloy',
    'Grade2'   : 'Reinforced Alloy',
    'Grade3'   : 'Military Grade Composite',
    'Mirrored' : 'Mirrored Surface Composite',
    'Reactive' : 'Reactive Surface Composite',
}

weapon_map = {
    'AdvancedTorpPylon'              : 'Torpedo Pylon',
    'BasicMissileRack'               : 'Missile Rack',
    'BeamLaser'                      : 'Beam Laser',
    ('BeamLaser','Heat')             : 'Retributor Beam Laser',
    'Cannon'                         : 'Cannon',
    'DumbfireMissileRack'            : 'Missile Rack',
    'MineLauncher'                   : 'Mine Launcher',
    ('MineLauncher','Impulse')       : 'Pack-hound Missile Rack',
    'MiningLaser'                    : 'Mining Laser',
    ('MiningLaser','Advanced')       : 'Mining Lance Beam Laser',
    'MultiCannon'                    : 'Multi-Cannon',
    ('MultiCannon','Strong')         : 'Enforcer Cannon',
    'PlasmaAccelerator'              : 'Plasma Accelerator',
    ('PlasmaAccelerator','Advanced') : 'Advanced Plasma Accelerator',
    'PulseLaser'                     : 'Pulse Laser',
    ('PulseLaser','Disruptor')       : 'Pulse Disruptor Laser',
    'PulseLaserBurst'                : 'Burst Laser',
    ('PulseLaserBurst','Scatter')    : 'Cytoscrambler Burst Laser',
    'Railgun'                        : 'Rail Gun',
    ('Railgun','Burst')              : 'Imperial Hammer Rail Gun',
    'Slugshot'                       : 'Fragment Cannon',
    ('Slugshot','Range')             : 'Pacifier Frag-Cannon',
}

missiletype_map = {
    'AdvancedTorpPylon'   : 'Seeker',
    'BasicMissileRack'    : 'Seeker',
    'DumbfireMissileRack' : 'Dumbfire',
}

weaponmount_map = {
    'Fixed'  : 'Fixed',
    'Gimbal' : 'Gimballed',
    'Turret' : 'Turreted',
}

weaponclass_map = {
    'Tiny'   : '0',
    'Small'  : '1',
    'Medium' : '2',
    'Large'  : '3',
    'Huge'   : '4',
}

# There's no discernable pattern for weapon ratings, so here's a lookup table
weaponrating_map = {
    'Hpt_AdvancedTorpPylon_Fixed_Small': 'I',
    'Hpt_AdvancedTorpPylon_Fixed_Medium': 'I',
    'Hpt_BasicMissileRack_Fixed_Small': 'B',
    'Hpt_BasicMissileRack_Fixed_Medium': 'B',
    'Hpt_BeamLaser_Fixed_Small': 'E',
    'Hpt_BeamLaser_Fixed_Medium': 'D',
    'Hpt_BeamLaser_Fixed_Large': 'C',
    'Hpt_BeamLaser_Gimbal_Small': 'E',
    'Hpt_BeamLaser_Gimbal_Medium': 'D',
    'Hpt_BeamLaser_Gimbal_Large': 'C',
    'Hpt_BeamLaser_Turret_Small': 'F',
    'Hpt_BeamLaser_Turret_Medium': 'E',
    'Hpt_BeamLaser_Turret_Large': 'D',
    'Hpt_Cannon_Fixed_Small': 'D',
    'Hpt_Cannon_Fixed_Medium': 'D',
    'Hpt_Cannon_Fixed_Large': 'C',
    'Hpt_Cannon_Fixed_Huge': 'B',
    'Hpt_Cannon_Gimbal_Small': 'E',
    'Hpt_Cannon_Gimbal_Medium': 'D',
    'Hpt_Cannon_Gimbal_Large': 'C',
    'Hpt_Cannon_Gimbal_Huge': 'B',
    'Hpt_Cannon_Turret_Small': 'F',
    'Hpt_Cannon_Turret_Medium': 'E',
    'Hpt_Cannon_Turret_Large': 'D',
    'Hpt_DumbfireMissileRack_Fixed_Small': 'B',
    'Hpt_DumbfireMissileRack_Fixed_Medium': 'B',
    'Hpt_MineLauncher_Fixed_Small': 'I',
    'Hpt_MineLauncher_Fixed_Medium': 'I',
    'Hpt_MiningLaser_Fixed_Small': 'D',
    'Hpt_MiningLaser_Fixed_Medium': 'D',
    'Hpt_MultiCannon_Fixed_Small': 'F',
    'Hpt_MultiCannon_Fixed_Medium': 'E',
    'Hpt_MultiCannon_Gimbal_Small': 'G',
    'Hpt_MultiCannon_Gimbal_Medium': 'F',
    'Hpt_MultiCannon_Turret_Small': 'G',
    'Hpt_MultiCannon_Turret_Medium': 'F',
    'Hpt_PlasmaAccelerator_Fixed_Medium': 'C',
    'Hpt_PlasmaAccelerator_Fixed_Large': 'B',
    'Hpt_PlasmaAccelerator_Fixed_Huge': 'A',
    'Hpt_PulseLaser_Fixed_Small': 'F',
    'Hpt_PulseLaser_Fixed_Medium': 'E',
    'Hpt_PulseLaser_Fixed_Large': 'D',
    'Hpt_PulseLaser_Gimbal_Small': 'G',
    'Hpt_PulseLaser_Gimbal_Medium': 'F',
    'Hpt_PulseLaser_Gimbal_Large': 'E',
    'Hpt_PulseLaser_Turret_Small': 'G',
    'Hpt_PulseLaser_Turret_Medium': 'F',
    'Hpt_PulseLaser_Turret_Large': 'F',
    'Hpt_PulseLaserBurst_Fixed_Small': 'F',
    'Hpt_PulseLaserBurst_Fixed_Medium': 'E',
    'Hpt_PulseLaserBurst_Fixed_Large': 'D',
    'Hpt_PulseLaserBurst_Gimbal_Small': 'G',
    'Hpt_PulseLaserBurst_Gimbal_Medium': 'F',
    'Hpt_PulseLaserBurst_Gimbal_Large': 'E',
    'Hpt_PulseLaserBurst_Turret_Small': 'G',
    'Hpt_PulseLaserBurst_Turret_Medium': 'F',
    'Hpt_PulseLaserBurst_Turret_Large': 'E',
    'Hpt_Railgun_Fixed_Small': 'D',
    'Hpt_Railgun_Fixed_Medium': 'B',
    'Hpt_Slugshot_Fixed_Small': 'E',
    'Hpt_Slugshot_Fixed_Medium': 'A',
    'Hpt_Slugshot_Fixed_Large': 'C',
    'Hpt_Slugshot_Gimbal_Small': 'E',
    'Hpt_Slugshot_Gimbal_Medium': 'D',
    'Hpt_Slugshot_Gimbal_Large': 'C',
    'Hpt_Slugshot_Turret_Small': 'E',
    'Hpt_Slugshot_Turret_Medium': 'D',
    'Hpt_Slugshot_Turret_Large': 'C',
}

# Old standard weapon variants
weaponoldvariant_map = {
    'F'  : 'Focussed',
    'HI' : 'High Impact',
    'LH' : 'Low Heat',
    'OC' : 'Overcharged',
    'SS' : 'Scatter Spray',
}

utility_map = {
    'CargoScanner'             : 'Cargo Scanner',
    'ChaffLauncher'            : 'Chaff Launcher',
    'CloudScanner'             : 'Frame Shift Wake Scanner',
    'CrimeScanner'             : 'Kill Warrant Scanner',
    'ElectronicCountermeasure' : 'Electronic Countermeasure',
    'HeatSinkLauncher'         : 'Heat Sink Launcher',
    'PlasmaPointDefence'       : 'Point Defence',
    'ShieldBooster'            : 'Shield Booster',
}

rating_map = {
    '1': 'E',
    '2': 'D',
    '3': 'C',
    '4': 'B',
    '5': 'A',
}

standard_map = {
    'Armour'           : 'Bulkheads',
    'Engine'           : 'Thrusters',
    'FuelTank'         : 'Fuel Tank',
    'Hyperdrive'       : 'Frame Shift Drive',
    'LifeSupport'      : 'Life Support',
    'PowerDistributor' : 'Power Distributor',
    'Powerplant'       : 'Power Plant',
    'Sensors'          : 'Sensors',
}

stellar_map = {
    'Standard'     : ('Basic Discovery Scanner', 'E'),
    'Intermediate' : ('Intermediate Discovery Scanner', 'D'),
    'Advanced'     : ('Advanced Discovery Scanner', 'C'),
    'Tiny'         : ('Detailed Surface Scanner', 'C'),
}

internal_map = {
    'CargoRack'         : 'Cargo Rack',
    'Collection'        : 'Collector Limpet Controller',
    'FSDInterdictor'    : 'Frame Shift Drive Interdictor',
    'FuelScoop'         : 'Fuel Scoop',
    'FuelTransfer'      : 'Fuel Transfer Limpet Controller',
    'HullReinforcement' : 'Hull Reinforcement Package',
    'Prospector'        : 'Prospector Limpet Controller',
    'Refinery'          : 'Refinery',
    'Repairer'          : 'Auto Field-Maintenance Unit',
    'ResourceSiphon'    : 'Hatch Breaker Limpet Controller',
    'ShieldCellBank'    : 'Shield Cell Bank',
    'ShieldGenerator'   : 'Shield Generator',
    ('ShieldGenerator','Strong') : 'Prismatic Shield Generator',
}


# Given a module description from the Companion API returns a description of the module in the form of a
# dict { category, name, [mount], [guidance], [ship], rating, class } using the same terms found in the
# English langauge game.
# Or returns None if the module is user-specific (i.e. decal, paintjob).
# (Given the ad-hocery in this implementation a big lookup table might have been simpler and clearer).
def lookup(module):

    # if not module.get('category'): raise AssertionError('%s: Missing category' % module['id'])	# only present post 1.3, and not present in ship loadout
    if not module.get('name'): raise AssertionError('%s: Missing name' % module['id'])

    name = module['name'].split('_')
    new = {}

    # Armour - e.g. Federation_Dropship_Armour_Grade2
    if name[-2] == 'Armour':
        name = module['name'].rsplit('_', 2)	# Armour is ship-specific, and ship names can have underscores
        new['category'] = 'standard'
        new['name'] = armour_map[name[2]]
        new['ship'] = ship_map.get(name[0], name[0])
        new['class'] = '1'
        new['rating'] = 'I'

    # Skip uninteresting stuff
    elif name[0].lower() in ['decal', 'paintjob']:	# Have seen "paintjob" and "PaintJob"
        return None

    # Skip PP-specific modules in outfitting which have an sku like ELITE_SPECIFIC_V_POWER_100100
    elif module.get('category') == 'powerplay':
        return None

    # Shouldn't be listing player-specific paid stuff
    elif module.get('sku'):
        raise AssertionError('%s: Unexpected sku "%s"' % (module['id'], module['sku']))

    # Hardpoints - e.g. Hpt_Slugshot_Fixed_Medium
    elif name[0]=='Hpt' and name[1] in weapon_map:
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
            new['rating'] = weaponrating_map.get(module['name'], '?')		# no obvious rule - needs lookup table
        new['mount'] = weaponmount_map[name[2]]
        if name[1] in missiletype_map:	# e.g. Hpt_DumbfireMissileRack_Fixed_Small
            new['guidance'] = missiletype_map[name[1]]
        new['class'] = weaponclass_map[name[3]]

    # Utility - e.g. Hpt_CargoScanner_Size0_Class1
    elif name[0]=='Hpt' and name[1] in utility_map:
        new['category'] = 'utility'
        new['name'] = utility_map[len(name)>4 and (name[1],name[4]) or name[1]]
        if name[-1] in weaponclass_map:	# e.g. Hpt_PlasmaPointDefence_Turret_Tiny
            new['class'] = weaponclass_map[name[-1]]
            new['rating'] = 'I'
        else:
            if not name[2].startswith('Size') or not name[3].startswith('Class'): raise AssertionError('%s: Unknown class/rating "%s/%s"' % (module['id'], name[2], name[3]))
            new['class'] = name[2][4:]
            new['rating'] = rating_map[name[3][5:]]

    elif name[0]=='Hpt':
        raise AssertionError('%s: Unknown weapon "%s"' % (module['id'], name[1]))

    # Stellar scanners - e.g. Int_StellarBodyDiscoveryScanner_Standard
    elif name[1] in ['StellarBodyDiscoveryScanner', 'DetailedSurfaceScanner']:
        new['category'] = 'internal'
        new['name'], new['rating'] = stellar_map[name[2]]
        new['class'] = '1'

    # Docking Computer - e.g. Int_DockingComputer_Standard
    elif name[1] == 'DockingComputer' and name[2] == 'Standard':
        new['category'] = 'internal'
        new['name'] = 'Standard Docking Computer'
        new['class'] = '1'
        new['rating'] = 'E'

    # Standard & Internal
    else:
        # Reported category is not necessarily helpful. e.g. "Int_DockingComputer_Standard" has category "utility"
        if name[0] != 'Int': raise AssertionError('%s: Unknown prefix "%s"' % (module['id'], name[0]))

        if name[1] == 'DroneControl':	# e.g. Int_DroneControl_Collection_Size1_Class1
            name.pop(0)

        if name[1] in standard_map:	# e.g. Int_Engine_Size2_Class1
            new['category'] = 'standard'
            new['name'] = standard_map[len(name)>4 and (name[1],name[4]) or name[1]]
        elif name[1] in internal_map:	# e.g. Int_CargoRack_Size8_Class1
            new['category'] = 'internal'
            new['name'] = internal_map[len(name)>4 and (name[1],name[4]) or name[1]]
        else:
            raise AssertionError('%s: Unknown module "%s"' % (module['id'], name[1]))

        if not name[2].startswith('Size') or not name[3].startswith('Class'): raise AssertionError('%s: Unknown class/rating "%s/%s"' % (module['id'], name[2], name[3]))
        new['class'] = name[2][4:]
        new['rating'] = rating_map[name[3][5:]]

    # check we've filled out mandatory fields
    for thing in ['category', 'name', 'class', 'rating']:
        if not new.get('name'): raise AssertionError('%s: failed to set %s' % (module['id'], thing))

    return new


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
