"""
Static data.

For easy reference any variable should be prefixed with the name of the file it
was either in originally, or where the primary code utilising it is.
"""
from collections import OrderedDict

# Map numeric 'demand/supply brackets' to the names as shown in-game.
commodity_bracketmap = {
    0: '',
    1: 'Low',
    2: 'Med',
    3: 'High',
}

# Map values reported by the Companion interface to names displayed in-game.
# May be imported by plugins.
companion_category_map = {
    'Narcotics':      'Legal Drugs',
    'Slaves':         'Slavery',
    'Waste ':         'Waste',
    'NonMarketable':  False,  # Don't appear in the in-game market so don't report
}

# Map Coriolis's names to names displayed in the in-game shipyard.
coriolis_ship_map = {
    'Cobra Mk III': 'Cobra MkIII',
    'Cobra Mk IV':  'Cobra MkIV',
    'Krait Mk II':  'Krait MkII',
    'Viper':        'Viper MkIII',
    'Viper Mk IV':  'Viper MkIV',
}

# Map API slot names to E:D Shipyard slot names
edshipyard_slot_map = {
    'hugehardpoint':     'H',
    'largehardpoint':    'L',
    'mediumhardpoint':   'M',
    'smallhardpoint':    'S',
    'tinyhardpoint':     'U',
    'armour':            'BH',
    'powerplant':        'RB',
    'mainengines':       'TM',
    'frameshiftdrive':   'FH',
    'lifesupport':       'EC',
    'powerdistributor':  'PC',
    'radar':             'SS',
    'fueltank':          'FS',
    'military':          'MC',
}

# Map API module names to in-game names

outfitting_armour_map = OrderedDict([
    ('grade1',   'Lightweight Alloy'),
    ('grade2',   'Reinforced Alloy'),
    ('grade3',   'Military Grade Composite'),
    ('mirrored', 'Mirrored Surface Composite'),
    ('reactive', 'Reactive Surface Composite'),
])

outfitting_weapon_map = {
    'advancedtorppylon':                 'Torpedo Pylon',
    'atdumbfiremissile':                 'AX Missile Rack',
    'atmulticannon':                     'AX Multi-Cannon',
    'basicmissilerack':                  'Seeker Missile Rack',
    'beamlaser':                         'Beam Laser',
    ('beamlaser', 'heat'):               'Retributor Beam Laser',
    'cannon':                            'Cannon',
    'causticmissile':                    'Enzyme Missile Rack',
    'drunkmissilerack':                  'Pack-Hound Missile Rack',
    'dumbfiremissilerack':               'Missile Rack',
    ('dumbfiremissilerack', 'advanced'): 'Advanced Missile Rack',
    ('dumbfiremissilerack', 'lasso'):    'Rocket Propelled FSD Disruptor',
    'flakmortar':                        'Remote Release Flak Launcher',
    'flechettelauncher':                 'Remote Release Flechette Launcher',
    'guardian_gausscannon':              'Guardian Gauss Cannon',
    'guardian_plasmalauncher':           'Guardian Plasma Charger',
    'guardian_shardcannon':              'Guardian Shard Cannon',
    'minelauncher':                      'Mine Launcher',
    ('minelauncher', 'impulse'):         'Shock Mine Launcher',
    'mining_abrblstr':                   'Abrasion Blaster',
    'mining_seismchrgwarhd':             'Seismic Charge Launcher',
    'mining_subsurfdispmisle':           'Sub-Surface Displacement Missile',
    'mininglaser':                       'Mining Laser',
    ('mininglaser', 'advanced'):         'Mining Lance Beam Laser',
    'multicannon':                       'Multi-Cannon',
    ('multicannon', 'advanced'):         'Advanced Multi-Cannon',
    ('multicannon', 'strong'):           'Enforcer Cannon',
    'plasmaaccelerator':                 'Plasma Accelerator',
    ('plasmaaccelerator', 'advanced'):   'Advanced Plasma Accelerator',
    'plasmashockcannon':                 'Shock Cannon',
    'pulselaser':                        'Pulse Laser',
    ('pulselaser', 'disruptor'):         'Pulse Disruptor Laser',
    'pulselaserburst':                   'Burst Laser',
    ('pulselaserburst', 'scatter'):      'Cytoscrambler Burst Laser',
    'railgun':                           'Rail Gun',
    ('railgun', 'burst'):                'Imperial Hammer Rail Gun',
    'slugshot':                          'Fragment Cannon',
    ('slugshot', 'range'):               'Pacifier Frag-Cannon',
}

outfitting_missiletype_map = {
    'advancedtorppylon':         'Seeker',
    'atdumbfiremissile':         'Dumbfire',
    'basicmissilerack':          'Seeker',
    'causticmissile':            'Dumbfire',
    'drunkmissilerack':          'Swarm',
    'dumbfiremissilerack':       'Dumbfire',
    'mining_subsurfdispmisle':   'Seeker',
    'mining_seismchrgwarhd':     'Seeker',
}

outfitting_weaponmount_map = {
    'fixed':    'Fixed',
    'gimbal':   'Gimballed',
    'turret':   'Turreted',
}

outfitting_weaponclass_map = {
    'tiny':      '0',
    'small':     '1',
    'smallfree': '1',
    'medium':    '2',
    'large':     '3',
    'huge':      '4',
}

# There's no discernable pattern for weapon ratings, so here's a lookup table
outfitting_weaponrating_map = {
    'hpt_advancedtorppylon_fixed_small':         'I',
    'hpt_advancedtorppylon_fixed_medium':        'I',
    'hpt_advancedtorppylon_fixed_large':         'I',
    'hpt_atdumbfiremissile_fixed_medium':        'B',
    'hpt_atdumbfiremissile_fixed_large':         'A',
    'hpt_atdumbfiremissile_turret_medium':       'B',
    'hpt_atdumbfiremissile_turret_large':        'A',
    'hpt_atmulticannon_fixed_medium':            'E',
    'hpt_atmulticannon_fixed_large':             'C',
    'hpt_atmulticannon_turret_medium':           'F',
    'hpt_atmulticannon_turret_large':            'E',
    'hpt_basicmissilerack_fixed_small':          'B',
    'hpt_basicmissilerack_fixed_medium':         'B',
    'hpt_basicmissilerack_fixed_large':          'A',
    'hpt_beamlaser_fixed_small':                 'E',
    'hpt_beamlaser_fixed_medium':                'D',
    'hpt_beamlaser_fixed_large':                 'C',
    'hpt_beamlaser_fixed_huge':                  'A',
    'hpt_beamlaser_gimbal_small':                'E',
    'hpt_beamlaser_gimbal_medium':               'D',
    'hpt_beamlaser_gimbal_large':                'C',
    'hpt_beamlaser_gimbal_huge':                 'A',
    'hpt_beamlaser_turret_small':                'F',
    'hpt_beamlaser_turret_medium':               'E',
    'hpt_beamlaser_turret_large':                'D',
    'hpt_cannon_fixed_small':                    'D',
    'hpt_cannon_fixed_medium':                   'D',
    'hpt_cannon_fixed_large':                    'C',
    'hpt_cannon_fixed_huge':                     'B',
    'hpt_cannon_gimbal_small':                   'E',
    'hpt_cannon_gimbal_medium':                  'D',
    'hpt_cannon_gimbal_large':                   'C',
    'hpt_cannon_gimbal_huge':                    'B',
    'hpt_cannon_turret_small':                   'F',
    'hpt_cannon_turret_medium':                  'E',
    'hpt_cannon_turret_large':                   'D',
    'hpt_causticmissile_fixed_medium':           'B',
    'hpt_drunkmissilerack_fixed_medium':         'B',
    'hpt_dumbfiremissilerack_fixed_small':       'B',
    'hpt_dumbfiremissilerack_fixed_medium':      'B',
    'hpt_dumbfiremissilerack_fixed_large':       'A',
    'hpt_flakmortar_fixed_medium':               'B',
    'hpt_flakmortar_turret_medium':              'B',
    'hpt_flechettelauncher_fixed_medium':        'B',
    'hpt_flechettelauncher_turret_medium':       'B',
    'hpt_guardian_gausscannon_fixed_small':      'D',
    'hpt_guardian_gausscannon_fixed_medium':     'B',
    'hpt_guardian_plasmalauncher_fixed_small':   'D',
    'hpt_guardian_plasmalauncher_fixed_medium':  'B',
    'hpt_guardian_plasmalauncher_fixed_large':   'C',
    'hpt_guardian_plasmalauncher_turret_small':  'F',
    'hpt_guardian_plasmalauncher_turret_medium': 'E',
    'hpt_guardian_plasmalauncher_turret_large':  'D',
    'hpt_guardian_shardcannon_fixed_small':      'D',
    'hpt_guardian_shardcannon_fixed_medium':     'A',
    'hpt_guardian_shardcannon_fixed_large':      'C',
    'hpt_guardian_shardcannon_turret_small':     'F',
    'hpt_guardian_shardcannon_turret_medium':    'D',
    'hpt_guardian_shardcannon_turret_large':     'D',
    'hpt_minelauncher_fixed_small':              'I',
    'hpt_minelauncher_fixed_medium':             'I',
    'hpt_mining_abrblstr_fixed_small':           'D',
    'hpt_mining_abrblstr_turret_small':          'D',
    'hpt_mining_seismchrgwarhd_fixed_medium':    'B',
    'hpt_mining_seismchrgwarhd_turret_medium':   'B',
    'hpt_mining_subsurfdispmisle_fixed_small':   'B',
    'hpt_mining_subsurfdispmisle_fixed_medium':  'B',
    'hpt_mining_subsurfdispmisle_turret_small':  'B',
    'hpt_mining_subsurfdispmisle_turret_medium': 'B',
    'hpt_mininglaser_fixed_small':               'D',
    'hpt_mininglaser_fixed_medium':              'D',
    'hpt_mininglaser_turret_small':              'D',
    'hpt_mininglaser_turret_medium':             'D',
    'hpt_multicannon_fixed_small':               'F',
    'hpt_multicannon_fixed_medium':              'E',
    'hpt_multicannon_fixed_large':               'C',
    'hpt_multicannon_fixed_huge':                'A',
    'hpt_multicannon_gimbal_small':              'G',
    'hpt_multicannon_gimbal_medium':             'F',
    'hpt_multicannon_gimbal_large':              'C',
    'hpt_multicannon_gimbal_huge':               'A',
    'hpt_multicannon_turret_small':              'G',
    'hpt_multicannon_turret_medium':             'F',
    'hpt_multicannon_turret_large':              'E',
    'hpt_plasmaaccelerator_fixed_medium':        'C',
    'hpt_plasmaaccelerator_fixed_large':         'B',
    'hpt_plasmaaccelerator_fixed_huge':          'A',
    'hpt_plasmashockcannon_fixed_small':         'D',
    'hpt_plasmashockcannon_fixed_medium':        'D',
    'hpt_plasmashockcannon_fixed_large':         'C',
    'hpt_plasmashockcannon_gimbal_small':        'E',
    'hpt_plasmashockcannon_gimbal_medium':       'D',
    'hpt_plasmashockcannon_gimbal_large':        'C',
    'hpt_plasmashockcannon_turret_small':        'F',
    'hpt_plasmashockcannon_turret_medium':       'E',
    'hpt_plasmashockcannon_turret_large':        'D',
    'hpt_pulselaser_fixed_small':                'F',
    'hpt_pulselaser_fixed_smallfree':            'F',
    'hpt_pulselaser_fixed_medium':               'E',
    'hpt_pulselaser_fixed_large':                'D',
    'hpt_pulselaser_fixed_huge':                 'A',
    'hpt_pulselaser_gimbal_small':               'G',
    'hpt_pulselaser_gimbal_medium':              'F',
    'hpt_pulselaser_gimbal_large':               'E',
    'hpt_pulselaser_gimbal_huge':                'A',
    'hpt_pulselaser_turret_small':               'G',
    'hpt_pulselaser_turret_medium':              'F',
    'hpt_pulselaser_turret_large':               'F',
    'hpt_pulselaserburst_fixed_small':           'F',
    'hpt_pulselaserburst_fixed_medium':          'E',
    'hpt_pulselaserburst_fixed_large':           'D',
    'hpt_pulselaserburst_fixed_huge':            'E',
    'hpt_pulselaserburst_gimbal_small':          'G',
    'hpt_pulselaserburst_gimbal_medium':         'F',
    'hpt_pulselaserburst_gimbal_large':          'E',
    'hpt_pulselaserburst_gimbal_huge':           'E',
    'hpt_pulselaserburst_turret_small':          'G',
    'hpt_pulselaserburst_turret_medium':         'F',
    'hpt_pulselaserburst_turret_large':          'E',
    'hpt_railgun_fixed_small':                   'D',
    'hpt_railgun_fixed_medium':                  'B',
    'hpt_slugshot_fixed_small':                  'E',
    'hpt_slugshot_fixed_medium':                 'A',
    'hpt_slugshot_fixed_large':                  'C',
    'hpt_slugshot_gimbal_small':                 'E',
    'hpt_slugshot_gimbal_medium':                'D',
    'hpt_slugshot_gimbal_large':                 'C',
    'hpt_slugshot_turret_small':                 'E',
    'hpt_slugshot_turret_medium':                'D',
    'hpt_slugshot_turret_large':                 'C',
}

# Old standard weapon variants
outfitting_weaponoldvariant_map = {
    'f':    'Focussed',
    'hi':   'High Impact',
    'lh':   'Low Heat',
    'oc':   'Overcharged',
    'ss':   'Scatter Spray',
}

outfitting_countermeasure_map = {
    'antiunknownshutdown':        ('Shutdown Field Neutraliser', 'F'),
    'chafflauncher':              ('Chaff Launcher', 'I'),
    'electroniccountermeasure':   ('Electronic Countermeasure', 'F'),
    'heatsinklauncher':           ('Heat Sink Launcher', 'I'),
    'plasmapointdefence':         ('Point Defence', 'I'),
    'xenoscanner':                ('Xeno Scanner', 'E'),
}

outfitting_utility_map = {
    'cargoscanner':               'Cargo Scanner',
    'cloudscanner':               'Frame Shift Wake Scanner',
    'crimescanner':               'Kill Warrant Scanner',
    'mrascanner':                 'Pulse Wave Analyser',
    'shieldbooster':              'Shield Booster',
}

outfitting_cabin_map = {
    '0': 'Prisoner Cells',
    '1': 'Economy Class Passenger Cabin',
    '2': 'Business Class Passenger Cabin',
    '3': 'First Class Passenger Cabin',
    '4': 'Luxury Class Passenger Cabin',
    '5': 'Passenger Cabin',  # not seen
}

outfitting_rating_map = {
    '1': 'E',
    '2': 'D',
    '3': 'C',
    '4': 'B',
    '5': 'A',
}

# Ratings are weird for the following

outfitting_corrosion_rating_map = {
    '1': 'E',
    '2': 'F',
}

outfitting_planet_rating_map = {
    '1': 'H',
    '2': 'G',
}

outfitting_fighter_rating_map = {
    '1': 'D',
}

outfitting_misc_internal_map = {
    ('detailedsurfacescanner',      'tiny'):          ('Detailed Surface Scanner',       'I'),
    ('dockingcomputer',             'advanced'):      ('Advanced Docking Computer',      'E'),
    ('dockingcomputer',             'standard'):      ('Standard Docking Computer',      'E'),
    'planetapproachsuite':                            ('Planetary Approach Suite',       'I'),
    ('stellarbodydiscoveryscanner', 'standard'):      ('Basic Discovery Scanner',        'E'),
    ('stellarbodydiscoveryscanner', 'intermediate'):  ('Intermediate Discovery Scanner', 'D'),
    ('stellarbodydiscoveryscanner', 'advanced'):      ('Advanced Discovery Scanner',     'C'),
    'supercruiseassist':                              ('Supercruise Assist',             'E'),
}

outfitting_standard_map = {
    # 'armour':                     handled separately
    'engine':                       'Thrusters',
    ('engine', 'fast'):             'Enhanced Performance Thrusters',
    'fueltank':                     'Fuel Tank',
    'guardianpowerdistributor':     'Guardian Hybrid Power Distributor',
    'guardianpowerplant':           'Guardian Hybrid Power Plant',
    'hyperdrive':                   'Frame Shift Drive',
    'lifesupport':                  'Life Support',
    # 'planetapproachsuite':        handled separately
    'powerdistributor':             'Power Distributor',
    'powerplant':                   'Power Plant',
    'sensors':                      'Sensors',
}

outfitting_internal_map = {
    'buggybay':                     'Planetary Vehicle Hangar',
    'cargorack':                    'Cargo Rack',
    'collection':                   'Collector Limpet Controller',
    'corrosionproofcargorack':      'Corrosion Resistant Cargo Rack',
    'decontamination':              'Decontamination Limpet Controller',
    'fighterbay':                   'Fighter Hangar',
    'fsdinterdictor':               'Frame Shift Drive Interdictor',
    'fuelscoop':                    'Fuel Scoop',
    'fueltransfer':                 'Fuel Transfer Limpet Controller',
    'guardianfsdbooster':           'Guardian FSD Booster',
    'guardianhullreinforcement':    'Guardian Hull Reinforcement',
    'guardianmodulereinforcement':  'Guardian Module Reinforcement',
    'guardianshieldreinforcement':  'Guardian Shield Reinforcement',
    'hullreinforcement':            'Hull Reinforcement Package',
    'metaalloyhullreinforcement':   'Meta Alloy Hull Reinforcement',
    'modulereinforcement':          'Module Reinforcement Package',
    'passengercabin':               'Passenger Cabin',
    'prospector':                   'Prospector Limpet Controller',
    'refinery':                     'Refinery',
    'recon':                        'Recon Limpet Controller',
    'repair':                       'Repair Limpet Controller',
    'repairer':                     'Auto Field-Maintenance Unit',
    'resourcesiphon':               'Hatch Breaker Limpet Controller',
    'shieldcellbank':               'Shield Cell Bank',
    'shieldgenerator':              'Shield Generator',
    ('shieldgenerator', 'fast'):    'Bi-Weave Shield Generator',
    ('shieldgenerator', 'strong'):  'Prismatic Shield Generator',
    'unkvesselresearch':            'Research Limpet Controller',
}
