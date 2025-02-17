"""
Static data.

For easy reference any variable should be prefixed with the name of the file it
was either in originally, or where the primary code utilising it is.
"""

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

# Map suit symbol names to English localised names
companion_suit_type_map = {
    'TacticalSuit_Class1':      'Dominator Suit',
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

outfitting_armour_map = {
    'grade1': 'Lightweight Alloy',
    'grade2': 'Reinforced Alloy',
    'grade3': 'Military Grade Composite',
    'mirrored': 'Mirrored Surface Composite',
    'reactive': 'Reactive Surface Composite',
}


outfitting_weapon_map = {
    'advancedtorppylon':                 'Torpedo Pylon',
    'atdumbfiremissile':                 'AX Missile Rack',
    'atmulticannon':                     'AX Multi-Cannon',
    ('atmulticannon', 'v2'):             'Enhanced AX Multi-Cannon',
    ('atdumbfiremissile', 'v2'):         'Enhanced AX Missile Rack',
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
    'human_extraction':                  'Sub-Surface Extraction Missile',
    'atventdisruptorpylon':              'Guardian Nanite Torpedo Pylon',
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
    'basic':    'Utility',
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
    'hpt_multicannon_fixed_small_advanced':      'F',
    'hpt_multicannon_fixed_medium':              'E',
    'hpt_multicannon_fixed_medium_advanced':     'E',
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
    'hpt_xenoscannermk2_basic_tiny':             '?',
    'hpt_atmulticannon_gimbal_large':            'C',
    'hpt_atmulticannon_gimbal_medium':           'E',
    'hpt_human_extraction_fixed_medium':         'B',
    'hpt_atventdisruptorpylon_fixed_medium':     'I',
    'hpt_atventdisruptorpylon_fixed_large':      'I',
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
    'antiunknownshutdown':          ('Shutdown Field Neutraliser', 'F'),
    ('antiunknownshutdown', 'v2'):  ('Thargoid Pulse Neutraliser', 'E'),
    'chafflauncher':                ('Chaff Launcher', 'I'),
    'electroniccountermeasure':     ('Electronic Countermeasure', 'F'),
    'heatsinklauncher':             ('Heat Sink Launcher', 'I'),
    'plasmapointdefence':           ('Point Defence', 'I'),
    'xenoscanner':                  ('Xeno Scanner', 'E'),
    'xenoscannermk2':               ('Unknown Xeno Scanner Mk II', '?'),
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
    ('hyperdrive', 'overcharge'):   'Frame Shift Drive (SCO)',
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
    'rescue':                       'Rescue Limpet Controller',
    'mining':                       'Mining Multi Limpet Controller',
    'xeno':                         'Xeno Multi Limpet Controller',
    'operations':                   'Operations Multi Limpet Controller',
    'universal':                    'Universal Multi Limpet Controller',
    'repairer':                     'Auto Field-Maintenance Unit',
    'resourcesiphon':               'Hatch Breaker Limpet Controller',
    'shieldcellbank':               'Shield Cell Bank',
    'shieldgenerator':              'Shield Generator',
    ('shieldgenerator', 'fast'):    'Bi-Weave Shield Generator',
    ('shieldgenerator', 'strong'):  'Prismatic Shield Generator',
    'unkvesselresearch':            'Research Limpet Controller',
    'expmodulestabiliser':          'Experimental Weapon Stabiliser',
}

# Dashboard Flags constants
FlagsDocked = 1 << 0             # on a landing pad
FlagsLanded = 1 << 1             # on planet surface
FlagsLandingGearDown = 1 << 2
FlagsShieldsUp = 1 << 3
FlagsSupercruise = 1 << 4
FlagsFlightAssistOff = 1 << 5
FlagsHardpointsDeployed = 1 << 6
FlagsInWing = 1 << 7
FlagsLightsOn = 1 << 8
FlagsCargoScoopDeployed = 1 << 9
FlagsSilentRunning = 1 << 10
FlagsScoopingFuel = 1 << 11
FlagsSrvHandbrake = 1 << 12
FlagsSrvTurret = 1 << 13         # using turret view
FlagsSrvUnderShip = 1 << 14      # turret retracted
FlagsSrvDriveAssist = 1 << 15
FlagsFsdMassLocked = 1 << 16
FlagsFsdCharging = 1 << 17
FlagsFsdCooldown = 1 << 18
FlagsLowFuel = 1 << 19           # < 25%
FlagsOverHeating = 1 << 20       # > 100%, or is this 80% now ?
FlagsHasLatLong = 1 << 21
FlagsIsInDanger = 1 << 22
FlagsBeingInterdicted = 1 << 23
FlagsInMainShip = 1 << 24
FlagsInFighter = 1 << 25
FlagsInSRV = 1 << 26
FlagsAnalysisMode = 1 << 27      # Hud in Analysis mode
FlagsNightVision = 1 << 28
FlagsAverageAltitude = 1 << 29   # Altitude from Average radius
FlagsFsdJump = 1 << 30
FlagsSrvHighBeam = 1 << 31

# Status.json / Dashboard flags2
Flags2OnFoot = 1 << 0
Flags2InTaxi = 1 << 1  # (or dropship/shuttle)
Flags2InMulticrew = 1 << 2  # (ie in someone else’s ship)
Flags2OnFootInStation = 1 << 3
Flags2OnFootOnPlanet = 1 << 4
Flags2AimDownSight = 1 << 5
Flags2LowOxygen = 1 << 6
Flags2LowHealth = 1 << 7
Flags2Cold = 1 << 8
Flags2Hot = 1 << 9
Flags2VeryCold = 1 << 10
Flags2VeryHot = 1 << 11
Flags2GlideMode = 1 << 12
Flags2OnFootInHangar = 1 << 13
Flags2OnFootSocialSpace = 1 << 14
Flags2OnFootExterior = 1 << 15
Flags2BreathableAtmosphere = 1 << 16

# Dashboard GuiFocus constants
GuiFocusNoFocus = 0
GuiFocusInternalPanel = 1        # right hand side
GuiFocusExternalPanel = 2        # left hand side
GuiFocusCommsPanel = 3		     # top
GuiFocusRolePanel = 4		     # bottom
GuiFocusStationServices = 5
GuiFocusGalaxyMap = 6
GuiFocusSystemMap = 7
GuiFocusOrrery = 8
GuiFocusFSS = 9
GuiFocusSAA = 10
GuiFocusCodex = 11

ship_name_map = {
    'adder':                        'Adder',
    'anaconda':                     'Anaconda',
    'asp':                          'Asp Explorer',
    'asp_scout':                    'Asp Scout',
    'belugaliner':                  'Beluga Liner',
    'cobramkiii':                   'Cobra MkIII',
    'cobramkiv':                    'Cobra MkIV',
    'cobramkv':                     'Cobra MkV',
    'clipper':                      'Panther Clipper',
    'cutter':                       'Imperial Cutter',
    'diamondback':                  'Diamondback Scout',
    'diamondbackxl':                'Diamondback Explorer',
    'dolphin':                      'Dolphin',
    'eagle':                        'Eagle',
    'empire_courier':               'Imperial Courier',
    'empire_eagle':                 'Imperial Eagle',
    'empire_fighter':               'Imperial Fighter',
    'empire_trader':                'Imperial Clipper',
    'federation_corvette':          'Federal Corvette',
    'federation_dropship':          'Federal Dropship',
    'federation_dropship_mkii':     'Federal Assault Ship',
    'federation_gunship':           'Federal Gunship',
    'federation_fighter':           'F63 Condor',
    'ferdelance':                   'Fer-de-Lance',
    'hauler':                       'Hauler',
    'independant_trader':           'Keelback',
    'independent_fighter':          'Taipan Fighter',
    'krait_mkii':                   'Krait MkII',
    'krait_light':                  'Krait Phantom',
    'mamba':                        'Mamba',
    'mandalay':                     'Mandalay',
    'orca':                         'Orca',
    'python':                       'Python',
    'python_nx':                    'Python Mk II',
    'scout':                        'Taipan Fighter',
    'sidewinder':                   'Sidewinder',
    'testbuggy':                    'Scarab',
    'type6':                        'Type-6 Transporter',
    'type7':                        'Type-7 Transporter',
    'type8':                        'Type-8 Transporter',
    'type9':                        'Type-9 Heavy',
    'type9_military':               'Type-10 Defender',
    'typex':                        'Alliance Chieftain',
    'typex_2':                      'Alliance Crusader',
    'typex_3':                      'Alliance Challenger',
    'viper':                        'Viper MkIII',
    'viper_mkiv':                   'Viper MkIV',
    'vulture':                      'Vulture',
}

# Odyssey Suit Names
edmc_suit_shortnames = {
    'Flight Suit':            'Flight',     # EN
    'Artemis Suit':           'Artemis',    # EN
    'Dominator Suit':         'Dominator',  # EN
    'Maverick Suit':          'Maverick',   # EN

    'Flug-Anzug':             'Flug',       # DE
    'Artemis-Anzug':          'Artemis',    # DE
    'Dominator-Anzug':        'Dominator',  # DE
    'Maverick-Anzug':         'Maverick',   # DE

    'Traje de vuelo':         'de vuelo',   # ES
    'Traje Artemis':          'Artemis',    # ES
    'Traje Dominator':        'Dominator',  # ES
    'Traje Maverick':         'Maverick',   # ES

    'Combinaison de vol':     'de vol',     # FR
    'Combinaison Artemis':    'Artemis',    # FR
    'Combinaison Dominator':  'Dominator',  # FR
    'Combinaison Maverick':   'Maverick',   # FR

    'Traje voador':           'voador',     # PT-BR
    #  These are duplicates of the ES ones, but kept here for clarity
    #  'Traje Artemis':          'Artemis',    # PT-BR
    #  'Traje Dominator':        'Dominator',  # PT-BR
    #  'Traje Maverick':         'Maverick',   # PT-BR

    'Летный комбинезон':      'Летный',     # RU
    'Комбинезон Artemis':     'Artemis',    # RU
    'Комбинезон Dominator':   'Dominator',  # RU
    'Комбинезон Maverick':    'Maverick',   # RU
}

edmc_suit_symbol_localised = {
    # The key here should match what's seen in Fileheader 'language', but with
    # any in-file `\\` already unescaped to a single `\`.
    r'English\UK': {
        'flightsuit':      'Flight Suit',
        'explorationsuit': 'Artemis Suit',
        'tacticalsuit':    'Dominator Suit',
        'utilitysuit':     'Maverick Suit',
    },
    r'German\DE': {
        'flightsuit':      'Flug-Anzug',
        'explorationsuit': 'Artemis-Anzug',
        'tacticalsuit':    'Dominator-Anzug',
        'utilitysuit':     'Maverick-Anzug',
    },
    r'French\FR': {
        'flightsuit':      'Combinaison de vol',
        'explorationsuit': 'Combinaison Artemis',
        'tacticalsuit':    'Combinaison Dominator',
        'utilitysuit':     'Combinaison Maverick',
    },
    r'Portuguese\BR': {
        'flightsuit':      'Traje voador',
        'explorationsuit': 'Traje Artemis',
        'tacticalsuit':    'Traje Dominator',
        'utilitysuit':     'Traje Maverick',
    },
    r'Russian\RU': {
        'flightsuit':      'Летный комбинезон',
        'explorationsuit': 'Комбинезон Artemis',
        'tacticalsuit':    'Комбинезон Dominator',
        'utilitysuit':     'Комбинезон Maverick',
    },
    r'Spanish\ES': {
        'flightsuit':      'Traje de vuelo',
        'explorationsuit': 'Traje Artemis',
        'tacticalsuit':    'Traje Dominator',
        'utilitysuit':     'Traje Maverick',
    },
}

# WORKAROUND 2021-07-03 | 4.0.0.600 Update 5: duplicates of `fileheader` keys in `LoadGame`,
# but the GameLanguage in the latter has doubled up the `\`, so cater for either here.
# This is sourced from what the game is passed by the launcher, caveat emptor. It was mentioned that / is also
# an option
# This is only run once when this file is imported by something, no runtime cost or repeated expansions will occur
__keys = list(edmc_suit_symbol_localised.keys())
for lang in __keys:
    new_lang = lang.replace('\\', r'\\')
    new_lang_2 = lang.replace('\\', '/')

    edmc_suit_symbol_localised[new_lang] = edmc_suit_symbol_localised[lang]
    edmc_suit_symbol_localised[new_lang_2] = edmc_suit_symbol_localised[lang]


# Local webserver for debugging. See implementation in debug_webserver.py
DEBUG_WEBSERVER_HOST = '127.0.0.1'
DEBUG_WEBSERVER_PORT = 9090
