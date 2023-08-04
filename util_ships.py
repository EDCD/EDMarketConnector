"""Utility functions relating to ships."""
from edmc_data import ship_name_map


def ship_file_name(ship_name: str, ship_type: str) -> str:
    """Return a ship name suitable for a filename."""
    name = str(ship_name or ship_name_map.get(ship_type.lower(), ship_type)).strip()
    if name.endswith('.'):
        name = name[:-2]

    if name.lower() in ('con', 'prn', 'aux', 'nul',
                        'com0', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
                        'lpt0', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'):
        name += '_'

    return name.translate({ord(x): '_' for x in ('\0', '<', '>', ':', '"', '/', '\\', '|', '?', '*')})
