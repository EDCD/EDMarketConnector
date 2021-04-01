"""Utility functions relating to ships."""


ship_map = {
    'adder':                        'Adder',
    'anaconda':                     'Anaconda',
    'asp':                          'Asp Explorer',
    'asp_scout':                    'Asp Scout',
    'belugaliner':                  'Beluga Liner',
    'cobramkiii':                   'Cobra MkIII',
    'cobramkiv':                    'Cobra MkIV',
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
    'orca':                         'Orca',
    'python':                       'Python',
    'scout':                        'Taipan Fighter',
    'sidewinder':                   'Sidewinder',
    'testbuggy':                    'Scarab',
    'type6':                        'Type-6 Transporter',
    'type7':                        'Type-7 Transporter',
    'type9':                        'Type-9 Heavy',
    'type9_military':               'Type-10 Defender',
    'typex':                        'Alliance Chieftain',
    'typex_2':                      'Alliance Crusader',
    'typex_3':                      'Alliance Challenger',
    'viper':                        'Viper MkIII',
    'viper_mkiv':                   'Viper MkIV',
    'vulture':                      'Vulture',
}


def ship_file_name(ship_name: str, ship_type: str) -> str:
    """Return a ship name suitable for a filename."""
    name = str(ship_name or ship_map.get(ship_type.lower(), ship_type)).strip()
    if name.endswith('.'):
        name = name[:-2]

    if name.lower() in ('con', 'prn', 'aux', 'nul',
                        'com0', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
                        'lpt0', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'):
        name = name + '_'

    return name.translate({ord(x): u'_' for x in ('\0', '<', '>', ':', '"', '/', '\\', '|', '?', '*')})
