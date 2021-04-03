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
