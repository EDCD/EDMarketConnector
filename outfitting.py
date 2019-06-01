from collections import OrderedDict
import cPickle
from os.path import join
import time

import companion
from config import config


# Map API module names to in-game names

armour_map = OrderedDict([
    ('grade1',   'Lightweight Alloy'),
    ('grade2',   'Reinforced Alloy'),
    ('grade3',   'Military Grade Composite'),
    ('mirrored', 'Mirrored Surface Composite'),
    ('reactive', 'Reactive Surface Composite'),
])

weapon_map = {
    'advancedtorppylon'              : 'Torpedo Pylon',
    'atdumbfiremissile'              : 'AX Missile Rack',
    'atmulticannon'                  : 'AX Multi-Cannon',
    'basicmissilerack'               : 'Seeker Missile Rack',
    'beamlaser'                      : 'Beam Laser',
    ('beamlaser','heat')             : 'Retributor Beam Laser',
    'cannon'                         : 'Cannon',
    'causticmissile'                 : 'Enzyme Missile Rack',
    'drunkmissilerack'               : 'Pack-Hound Missile Rack',
    'dumbfiremissilerack'            : 'Missile Rack',
    ('dumbfiremissilerack', 'lasso') : 'Rocket Propelled FSD Disruptor',
    'flakmortar'                     : 'Remote Release Flak Launcher',
    'flechettelauncher'              : 'Remote Release Flechette Launcher',
    'guardian_gausscannon'           : 'Guardian Gauss Cannon',
    'guardian_plasmalauncher'        : 'Guardian Plasma Charger',
    'guardian_shardcannon'           : 'Guardian Shard Cannon',
    'minelauncher'                   : 'Mine Launcher',
    ('minelauncher','impulse')       : 'Shock Mine Launcher',
    'mining_abrblstr'                : 'Abrasion Blaster',
    'mining_seismchrgwarhd'          : 'Seismic Charge Launcher',
    'mining_subsurfdispmisle'        : 'Sub-Surface Displacement Missile',
    'mininglaser'                    : 'Mining Laser',
    ('mininglaser','advanced')       : 'Mining Lance Beam Laser',
    'multicannon'                    : 'Multi-Cannon',
    ('multicannon','advanced')       : 'Advanced Multi-Cannon',
    ('multicannon','strong')         : 'Enforcer Cannon',
    'plasmaaccelerator'              : 'Plasma Accelerator',
    ('plasmaaccelerator','advanced') : 'Advanced Plasma Accelerator',
    'plasmashockcannon'              : 'Shock Cannon',
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
    'atdumbfiremissile'   : 'Dumbfire',
    'basicmissilerack'    : 'Seeker',
    'causticmissile'      : 'Dumbfire',
    'drunkmissilerack'    : 'Swarm',
    'dumbfiremissilerack' : 'Dumbfire',
    'mining_subsurfdispmisle' : 'Seeker',
    'mining_seismchrgwarhd'   : 'Seeker',
}

weaponmount_map = {
    'fixed'  : 'Fixed',
    'gimbal' : 'Gimballed',
    'turret' : 'Turreted',
}

weaponclass_map = {
    'tiny'   : '0',
    'small'  : '1',
    'smallfree' : '1',
    'medium' : '2',
    'large'  : '3',
    'huge'   : '4',
}

# There's no discernable pattern for weapon ratings, so here's a lookup table
weaponrating_map = {
    'hpt_advancedtorppylon_fixed_small' : 'I',
    'hpt_advancedtorppylon_fixed_medium': 'I',
    'hpt_advancedtorppylon_fixed_large' : 'I',
    'hpt_atdumbfiremissile_fixed_medium': 'B',
    'hpt_atdumbfiremissile_fixed_large' : 'A',
    'hpt_atdumbfiremissile_turret_medium': 'B',
    'hpt_atdumbfiremissile_turret_large' : 'A',
    'hpt_atmulticannon_fixed_medium'    : 'E',
    'hpt_atmulticannon_fixed_large'     : 'C',
    'hpt_atmulticannon_turret_medium'   : 'F',
    'hpt_atmulticannon_turret_large'    : 'E',
    'hpt_basicmissilerack_fixed_small'  : 'B',
    'hpt_basicmissilerack_fixed_medium' : 'B',
    'hpt_basicmissilerack_fixed_large'  : 'A',
    'hpt_beamlaser_fixed_small'         : 'E',
    'hpt_beamlaser_fixed_medium'        : 'D',
    'hpt_beamlaser_fixed_large': 'C',
    'hpt_beamlaser_fixed_huge': 'A',
    'hpt_beamlaser_gimbal_small': 'E',
    'hpt_beamlaser_gimbal_medium': 'D',
    'hpt_beamlaser_gimbal_large': 'C',
    'hpt_beamlaser_gimbal_huge': 'A',
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
    'hpt_causticmissile_fixed_medium': 'B',
    'hpt_drunkmissilerack_fixed_medium': 'B',
    'hpt_dumbfiremissilerack_fixed_small': 'B',
    'hpt_dumbfiremissilerack_fixed_medium': 'B',
    'hpt_dumbfiremissilerack_fixed_large': 'A',
    'hpt_flakmortar_fixed_medium': 'B',
    'hpt_flakmortar_turret_medium': 'B',
    'hpt_flechettelauncher_fixed_medium': 'B',
    'hpt_flechettelauncher_turret_medium': 'B',
    'hpt_guardian_gausscannon_fixed_small': 'D',
    'hpt_guardian_gausscannon_fixed_medium': 'B',
    'hpt_guardian_plasmalauncher_fixed_small': 'D',
    'hpt_guardian_plasmalauncher_fixed_medium': 'B',
    'hpt_guardian_plasmalauncher_fixed_large': 'C',
    'hpt_guardian_plasmalauncher_turret_small': 'F',
    'hpt_guardian_plasmalauncher_turret_medium': 'E',
    'hpt_guardian_plasmalauncher_turret_large': 'D',
    'hpt_guardian_shardcannon_fixed_small': 'D',
    'hpt_guardian_shardcannon_fixed_medium': 'A',
    'hpt_guardian_shardcannon_fixed_large': 'C',
    'hpt_guardian_shardcannon_turret_small': 'F',
    'hpt_guardian_shardcannon_turret_medium': 'D',
    'hpt_guardian_shardcannon_turret_large': 'D',
    'hpt_minelauncher_fixed_small': 'I',
    'hpt_minelauncher_fixed_medium': 'I',
    'hpt_mining_abrblstr_fixed_small' : 'D',
    'hpt_mining_abrblstr_turret_small' : 'D',
    'hpt_mining_seismchrgwarhd_fixed_medium' : 'B',
    'hpt_mining_seismchrgwarhd_turret_medium' : 'B',
    'hpt_mining_subsurfdispmisle_fixed_small' : 'B',
    'hpt_mining_subsurfdispmisle_fixed_medium' : 'B',
    'hpt_mining_subsurfdispmisle_turret_small' : 'B',
    'hpt_mining_subsurfdispmisle_turret_medium' : 'B',
    'hpt_mininglaser_fixed_small': 'D',
    'hpt_mininglaser_fixed_medium': 'D',
    'hpt_mininglaser_turret_small': 'D',
    'hpt_mininglaser_turret_medium': 'D',
    'hpt_multicannon_fixed_small': 'F',
    'hpt_multicannon_fixed_medium': 'E',
    'hpt_multicannon_fixed_large': 'C',
    'hpt_multicannon_fixed_huge': 'A',
    'hpt_multicannon_gimbal_small': 'G',
    'hpt_multicannon_gimbal_medium': 'F',
    'hpt_multicannon_gimbal_large': 'C',
    'hpt_multicannon_gimbal_huge': 'A',
    'hpt_multicannon_turret_small': 'G',
    'hpt_multicannon_turret_medium': 'F',
    'hpt_multicannon_turret_large': 'E',
    'hpt_plasmaaccelerator_fixed_medium': 'C',
    'hpt_plasmaaccelerator_fixed_large': 'B',
    'hpt_plasmaaccelerator_fixed_huge': 'A',
    'hpt_plasmashockcannon_fixed_small': 'D',
    'hpt_plasmashockcannon_fixed_medium': 'D',
    'hpt_plasmashockcannon_fixed_large': 'C',
    'hpt_plasmashockcannon_gimbal_small': 'E',
    'hpt_plasmashockcannon_gimbal_medium': 'D',
    'hpt_plasmashockcannon_gimbal_large': 'C',
    'hpt_plasmashockcannon_turret_small': 'F',
    'hpt_plasmashockcannon_turret_medium': 'E',
    'hpt_plasmashockcannon_turret_large': 'D',
    'hpt_pulselaser_fixed_small': 'F',
    'hpt_pulselaser_fixed_smallfree': 'F',
    'hpt_pulselaser_fixed_medium': 'E',
    'hpt_pulselaser_fixed_large': 'D',
    'hpt_pulselaser_fixed_huge': 'A',
    'hpt_pulselaser_gimbal_small': 'G',
    'hpt_pulselaser_gimbal_medium': 'F',
    'hpt_pulselaser_gimbal_large': 'E',
    'hpt_pulselaser_gimbal_huge': 'A',
    'hpt_pulselaser_turret_small': 'G',
    'hpt_pulselaser_turret_medium': 'F',
    'hpt_pulselaser_turret_large': 'F',
    'hpt_pulselaserburst_fixed_small': 'F',
    'hpt_pulselaserburst_fixed_medium': 'E',
    'hpt_pulselaserburst_fixed_large': 'D',
    'hpt_pulselaserburst_fixed_huge': 'E',
    'hpt_pulselaserburst_gimbal_small': 'G',
    'hpt_pulselaserburst_gimbal_medium': 'F',
    'hpt_pulselaserburst_gimbal_large': 'E',
    'hpt_pulselaserburst_gimbal_huge': 'E',
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
    'antiunknownshutdown'      : ('Shutdown Field Neutraliser', 'F'),
    'chafflauncher'            : ('Chaff Launcher', 'I'),
    'electroniccountermeasure' : ('Electronic Countermeasure', 'F'),
    'heatsinklauncher'         : ('Heat Sink Launcher', 'I'),
    'plasmapointdefence'       : ('Point Defence', 'I'),
    'xenoscanner'              : ('Xeno Scanner', 'E'),
}

utility_map = {
    'cargoscanner'             : 'Cargo Scanner',
    'cloudscanner'             : 'Frame Shift Wake Scanner',
    'crimescanner'             : 'Kill Warrant Scanner',
    'mrascanner'               : 'Pulse Wave Analyser',
    'shieldbooster'            : 'Shield Booster',
}

cabin_map = {
    '0': 'Prisoner Cells',
    '1': 'Economy Class Passenger Cabin',
    '2': 'Business Class Passenger Cabin',
    '3': 'First Class Passenger Cabin',
    '4': 'Luxury Class Passenger Cabin',
    '5': 'Passenger Cabin',	# not seen
}

rating_map = {
    '1': 'E',
    '2': 'D',
    '3': 'C',
    '4': 'B',
    '5': 'A',
}

# Ratings are weird for the following

corrosion_rating_map = {
    '1': 'E',
    '2': 'F',
}

planet_rating_map = {
    '1': 'H',
    '2': 'G',
}

fighter_rating_map = {
    '1': 'D',
}

misc_internal_map = {
    ('detailedsurfacescanner',      'tiny')         : ('Detailed Surface Scanner', 'C'),
    ('dockingcomputer',             'advanced')     : ('Advanced Docking Computer', 'E'),
    ('dockingcomputer',             'standard')     : ('Standard Docking Computer', 'E'),
    'planetapproachsuite'                           : ('Planetary Approach Suite', 'I'),
    ('stellarbodydiscoveryscanner', 'standard')     : ('Basic Discovery Scanner', 'E'),
    ('stellarbodydiscoveryscanner', 'intermediate') : ('Intermediate Discovery Scanner', 'D'),
    ('stellarbodydiscoveryscanner', 'advanced')     : ('Advanced Discovery Scanner', 'C'),
    'supercruiseassist'                             : ('Supercruise Assist', 'E'),
}

standard_map = {
    # 'armour'                   : handled separately
    'engine'                     : 'Thrusters',
    ('engine','fast')            : 'Enhanced Performance Thrusters',
    'fueltank'                   : 'Fuel Tank',
    'guardianpowerdistributor'   : 'Guardian Hybrid Power Distributor',
    'guardianpowerplant'         : 'Guardian Hybrid Power Plant',
    'hyperdrive'                 : 'Frame Shift Drive',
    'lifesupport'                : 'Life Support',
    # 'planetapproachsuite'      : handled separately
    'powerdistributor'           : 'Power Distributor',
    'powerplant'                 : 'Power Plant',
    'sensors'                    : 'Sensors',
}

internal_map = {
    'buggybay'                   : 'Planetary Vehicle Hangar',
    'cargorack'                  : 'Cargo Rack',
    'collection'                 : 'Collector Limpet Controller',
    'corrosionproofcargorack'    : 'Corrosion Resistant Cargo Rack',
    'decontamination'            : 'Decontamination Limpet Controller',
    'fighterbay'                 : 'Fighter Hangar',
    'fsdinterdictor'             : 'Frame Shift Drive Interdictor',
    'fuelscoop'                  : 'Fuel Scoop',
    'fueltransfer'               : 'Fuel Transfer Limpet Controller',
    'guardianfsdbooster'         : 'Guardian FSD Booster',
    'guardianhullreinforcement'  : 'Guardian Hull Reinforcement',
    'guardianmodulereinforcement': 'Guardian Module Reinforcement',
    'guardianshieldreinforcement': 'Guardian Shield Reinforcement',
    'hullreinforcement'          : 'Hull Reinforcement Package',
    'metaalloyhullreinforcement' : 'Meta Alloy Hull Reinforcement',
    'modulereinforcement'        : 'Module Reinforcement Package',
    'passengercabin'             : 'Passenger Cabin',
    'prospector'                 : 'Prospector Limpet Controller',
    'refinery'                   : 'Refinery',
    'recon'                      : 'Recon Limpet Controller',
    'repair'                     : 'Repair Limpet Controller',
    'repairer'                   : 'Auto Field-Maintenance Unit',
    'resourcesiphon'             : 'Hatch Breaker Limpet Controller',
    'shieldcellbank'             : 'Shield Cell Bank',
    'shieldgenerator'            : 'Shield Generator',
    ('shieldgenerator','fast')   : 'Bi-Weave Shield Generator',
    ('shieldgenerator','strong') : 'Prismatic Shield Generator',
    'unkvesselresearch'          : 'Research Limpet Controller',
}


# Module mass, FSD data etc
moduledata = OrderedDict()


# Given a module description from the Companion API returns a description of the module in the form of a
# dict { category, name, [mount], [guidance], [ship], rating, class } using the same terms found in the
# English langauge game. For fitted modules, dict also includes { enabled, priority }.
# ship_map tells us what ship names to use for Armour - i.e. EDDN schema names or in-game names.
#
# Returns None if the module is user-specific (i.e. decal, paintjob, kit) or PP-specific in station outfitting.
# (Given the ad-hocery in this implementation a big lookup table might have been simpler and clearer).
def lookup(module, ship_map, entitled=False):

    # Lazily populate
    if not moduledata:
        moduledata.update(cPickle.load(open(join(config.respath, 'modules.p'),  'rb')))

    # if not module.get('category'): raise AssertionError('%s: Missing category' % module['id'])	# only present post 1.3, and not present in ship loadout
    if not module.get('name'): raise AssertionError('%s: Missing name' % module['id'])

    name = module['name'].lower().split('_')
    new = { 'id': module['id'], 'symbol': module['name'] }

    # Armour - e.g. Federation_Dropship_Armour_Grade2
    if name[-2] == 'armour':
        name = module['name'].lower().rsplit('_', 2)	# Armour is ship-specific, and ship names can have underscores
        new['category'] = 'standard'
        new['name'] = armour_map[name[2]]
        new['ship'] = ship_map[name[0]]		# Generate error on unknown ship
        new['class'] = '1'
        new['rating'] = 'I'

    # Skip uninteresting stuff - no longer present in ED 3.1 cAPI data
    elif name[0] in ['bobble', 'decal', 'nameplate', 'paintjob', 'enginecustomisation', 'weaponcustomisation'] or name[1].startswith('shipkit') :
        return None

    # Shouldn't be listing player-specific paid stuff or broker/powerplay-specific modules in outfitting, other than Horizons
    elif not entitled and module.get('sku') and module['sku'] != 'ELITE_HORIZONS_V_PLANETARY_LANDINGS':
        return None

    # Don't report Planetary Approach Suite in outfitting
    elif not entitled and name[1] == 'planetapproachsuite':
        return None

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
        new['class'] = str(name[2][4:])
        new['rating'] = rating_map[name[3][5:]]

    # Hardpoints - e.g. Hpt_Slugshot_Fixed_Medium
    elif name[0]=='hpt':
        # Hack 'Guardian' and 'Mining' prefixes
        if len(name) > 3 and name[3] in weaponmount_map:
            prefix = name.pop(1)
            name[1] = '%s_%s' % (prefix, name[1])
        if name[1] not in weapon_map:      raise AssertionError('%s: Unknown weapon "%s"'       % (module['id'], name[0]))
        if name[2] not in weaponmount_map: raise AssertionError('%s: Unknown weapon mount "%s"' % (module['id'], name[2]))
        if name[3] not in weaponclass_map: raise AssertionError('%s: Unknown weapon class "%s"' % (module['id'], name[3]))

        new['category'] = 'hardpoint'
        if len(name)>4:
            if name[4] in weaponoldvariant_map:		# Old variants e.g. Hpt_PulseLaserBurst_Turret_Large_OC
                new['name'] =  weapon_map[name[1]] + ' ' + weaponoldvariant_map[name[4]]
                new['rating'] = '?'
            elif '_'.join(name[:4]) not in weaponrating_map:
                raise AssertionError('%s: Unknown weapon rating "%s"' % (module['id'], module['name']))
            else:			# PP faction-specific weapons e.g. Hpt_Slugshot_Fixed_Large_Range
                new['name'] =  weapon_map[(name[1],name[4])]
                new['rating'] = weaponrating_map['_'.join(name[:4])]	# assumes same rating as base weapon
        elif module['name'].lower() not in weaponrating_map:
            raise AssertionError('%s: Unknown weapon rating "%s"' % (module['id'], module['name']))
        else:
            new['name'] =  weapon_map[name[1]]
            new['rating'] = weaponrating_map[module['name'].lower()]	# no obvious rule - needs lookup table
        new['mount'] = weaponmount_map[name[2]]
        if name[1] in missiletype_map:	# e.g. Hpt_DumbfireMissileRack_Fixed_Small
            new['guidance'] = missiletype_map[name[1]]
        new['class'] = weaponclass_map[name[3]]

    elif name[0]!='int':
        raise AssertionError('%s: Unknown prefix "%s"' % (module['id'], name[0]))

    # Miscellaneous Class 1 - e.g. Int_PlanetApproachSuite, Int_StellarBodyDiscoveryScanner_Advanced, Int_DockingComputer_Standard
    elif name[1] in misc_internal_map:
        new['category'] = 'internal'
        new['name'], new['rating'] = misc_internal_map[name[1]]
        new['class'] = '1'
    elif len(name) > 2 and (name[1],name[2]) in misc_internal_map:
        # Reported category is not necessarily helpful. e.g. "Int_DockingComputer_Standard" has category "utility"
        new['category'] = 'internal'
        new['name'], new['rating'] = misc_internal_map[(name[1],name[2])]
        new['class'] = '1'

    # Standard & Internal
    else:
        if name[1] == 'dronecontrol':	# e.g. Int_DroneControl_Collection_Size1_Class1
            name.pop(0)
        elif name[-1] == 'free':	# Starter Sidewinder or Freagle modules - just treat them like vanilla modules
            name.pop()

        if name[1] in standard_map:	# e.g. Int_Engine_Size2_Class1, Int_ShieldGenerator_Size8_Class5_Strong
            new['category'] = 'standard'
            new['name'] = standard_map[len(name)>4 and (name[1],name[4]) or name[1]]
        elif name[1] in internal_map:	# e.g. Int_CargoRack_Size8_Class1
            new['category'] = 'internal'
            if name[1] == 'passengercabin':
                new['name'] = cabin_map[name[3][5:]]
            else:
                new['name'] = internal_map[len(name)>4 and (name[1],name[4]) or name[1]]
        else:
            raise AssertionError('%s: Unknown module "%s"' % (module['id'], name[1]))

        if len(name) < 4 and name[1] == 'unkvesselresearch':	# Hack! No size or class.
            (new['class'], new['rating']) = ('1', 'E')
        elif len(name) < 4 and name[1] in ['guardianpowerdistributor', 'guardianpowerplant']:	# Hack! No class.
            (new['class'], new['rating']) = (str(name[2][4:]), 'A')
        elif len(name) < 4 and name[1] in ['guardianfsdbooster']:	# Hack! No class.
            (new['class'], new['rating']) = (str(name[2][4:]), 'H')
        else:
            if not name[2].startswith('size') or not name[3].startswith('class'): raise AssertionError('%s: Unknown class/rating "%s/%s"' % (module['id'], name[2], name[3]))
            new['class'] = str(name[2][4:])
            new['rating'] = (name[1]=='buggybay' and planet_rating_map or
                             name[1]=='fighterbay' and fighter_rating_map or
                             name[1]=='corrosionproofcargorack' and corrosion_rating_map or
                             rating_map)[name[3][5:]]

    # Disposition of fitted modules
    if 'on' in module and 'priority' in module:
        new['enabled'], new['priority'] = module['on'], module['priority']	# priority is zero-based

    # Entitlements
    if not module.get('sku'):
        pass
    else:
        new['entitlement'] = module['sku']

    # Extra module data
    if module['name'].endswith('_free'):
        key = module['name'][:-5].lower()	# starter modules - treated like vanilla modules
    else:
        key = module['name'].lower()
    if __debug__:
        m = moduledata.get(key, {})
        if not m:
            print 'No data for module %s' % key
        elif new['name'] == 'Frame Shift Drive':
            assert 'mass' in m and 'optmass' in m and 'maxfuel' in m and 'fuelmul' in m and 'fuelpower' in m, m
        else:
            assert 'mass' in m, m
    new.update(moduledata.get(module['name'].lower(), {}))

    # check we've filled out mandatory fields
    for thing in ['id', 'symbol', 'category', 'name', 'class', 'rating']:	# Don't consider mass etc as mandatory
        if not new.get(thing): raise AssertionError('%s: failed to set %s' % (module['id'], thing))
    if new['category'] == 'hardpoint' and not new.get('mount'):
        raise AssertionError('%s: failed to set %s' % (module['id'], 'mount'))

    return new


def export(data, filename):

    querytime = config.getint('querytime') or int(time.time())

    assert data['lastSystem'].get('name')
    assert data['lastStarport'].get('name')

    header = 'System,Station,Category,Name,Mount,Guidance,Ship,Class,Rating,FDevID,Date\n'
    rowheader = '%s,%s' % (data['lastSystem']['name'], data['lastStarport']['name'])

    h = open(filename, 'wt')
    h.write(header)
    for v in data['lastStarport'].get('modules', {}).itervalues():
        try:
            m = lookup(v, companion.ship_map)
            if m:
                h.write('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' % (rowheader, m['category'], m['name'], m.get('mount',''), m.get('guidance',''), m.get('ship',''), m['class'], m['rating'], m['id'], data['timestamp']))
        except AssertionError as e:
            if __debug__: print 'Outfitting: %s' % e	# Silently skip unrecognized modules
        except:
            if __debug__: raise
    h.close()
