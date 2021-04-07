"""Export ship loadout in ED Shipyard plain text format."""

import os
import pathlib
import pickle
import re
import time
from collections import defaultdict
from typing import Dict, List, Union

import outfitting
import util_ships
from config import config
from edmc_data import edshipyard_slot_map as slot_map
from edmc_data import ship_name_map
from EDMCLogging import get_main_logger

logger = get_main_logger()

__Module = Dict[str, Union[str, List[str]]]

# Map API ship names to ED Shipyard names
ship_map = ship_name_map.copy()

# Ship masses
# TODO: prefer something other than pickle for this storage (dev readability, security)
ships = pickle.load(open(pathlib.Path(config.respath_path) / 'ships.p', 'rb'))


def export(data, filename=None) -> None:  # noqa: C901, CCR001
    """
    Export ship loadout in E:D Shipyard plain text format.

    :param data: CAPI data.
    :param filename: Override default file name.
    """
    def class_rating(module: __Module) -> str:
        """
        Return a string representation of the class of the given module.

        :param module: Module data dict.
        :return: Rating of the module.
        """
        mod_class = module['class']
        mod_rating = module['rating']
        mod_mount = module.get('mount')
        mod_guidance: str = module.get('guidance')  # type: ignore

        ret = f'{mod_class}{mod_rating}'
        if 'guidance' in module:  # Missiles
            if mod_mount is not None:
                mount = mod_mount[0]

            else:
                mount = 'F'

            guidance = mod_guidance[0]
            ret += f'/{mount}{guidance}'

        elif 'mount' in module:  # Hardpoints
            ret += f'/{mod_mount}'

        elif 'Cabin' in module['name']:  # Passenger cabins
            ret += f'/{module["name"][0]}'

        return ret + ' '

    querytime = config.get_int('querytime', default=int(time.time()))

    loadout = defaultdict(list)
    mass = 0.0
    fuel = 0
    cargo = 0
    fsd = None
    jumpboost = 0

    for slot in sorted(data['ship']['modules']):

        v = data['ship']['modules'][slot]
        try:
            if not v:
                continue

            module: __Module = outfitting.lookup(v['module'], ship_map)
            if not module:
                continue

            cr = class_rating(module)
            mods = v.get('modifications') or v.get('WorkInProgress_modifications') or {}
            if mods.get('OutfittingFieldType_Mass'):
                mass += float(module.get('mass', 0.0) * mods['OutfittingFieldType_Mass']['value'])

            else:
                mass += float(module.get('mass', 0.0))  # type: ignore

            # Specials
            if 'Fuel Tank' in module['name']:
                fuel += 2**int(module['class'])  # type: ignore
                name = f'{module["name"]} (Capacity: {2**int(module["class"])})'  # type: ignore

            elif 'Cargo Rack' in module['name']:
                cargo += 2**int(module['class'])  # type: ignore
                name = f'{module["name"]} (Capacity: {2**int(module["class"])})'  # type: ignore

            else:
                name = module['name']  # type: ignore

            if name == 'Frame Shift Drive':
                fsd = module  # save for range calculation

                if mods.get('OutfittingFieldType_FSDOptimalMass'):
                    fsd['optmass'] *= mods['OutfittingFieldType_FSDOptimalMass']['value']

                if mods.get('OutfittingFieldType_MaxFuelPerJump'):
                    fsd['maxfuel'] *= mods['OutfittingFieldType_MaxFuelPerJump']['value']

            jumpboost += module.get('jumpboost', 0)  # type: ignore

            for s in slot_map:
                if slot.lower().startswith(s):
                    loadout[slot_map[s]].append(cr + name)
                    break

            else:
                if slot.lower().startswith('slot'):
                    loadout[slot[-1]].append(cr + name)

                elif not slot.lower().startswith('planetaryapproachsuite'):
                    logger.debug(f'EDShipyard: Unknown slot {slot}')

        except AssertionError as e:
            logger.debug(f'EDShipyard: {e!r}')
            continue  # Silently skip unrecognized modules

        except Exception:
            if __debug__:
                raise

    # Construct description
    ship = ship_map.get(data['ship']['name'].lower(), data['ship']['name'])

    if data['ship'].get('shipName') is not None:
        _ships = f'{ship}, {data["ship"]["shipName"]}'

    else:
        _ships = ship

    string = f'[{_ships}]\n'

    slot_types = (
        'H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, 'MC', None, '9', '8',
        '7', '6', '5', '4', '3', '2', '1'
    )
    for slot in slot_types:
        if not slot:
            string += '\n'

        elif slot in loadout:
            for name in loadout[slot]:
                string += f'{slot}: {name}\n'

    string += f'---\nCargo : {cargo} T\nFuel  : {fuel} T\n'

    # Add mass and range
    assert data['ship']['name'].lower() in ship_name_map, data['ship']['name']
    assert ship_name_map[data['ship']['name'].lower()] in ships, ship_name_map[data['ship']['name'].lower()]

    try:
        mass += ships[ship_name_map[data['ship']['name'].lower()]]['hullMass']
        string += f'Mass  : {mass:.2f} T empty\n        {mass + fuel + cargo:.2f} T full\n'

        multiplier = pow(min(fuel, fsd['maxfuel']) / fsd['fuelmul'], 1.0  # type: ignore
                         / fsd['fuelpower']) * fsd['optmass']  # type: ignore

        range_unladen = multiplier / (mass + fuel) + jumpboost
        range_laden = multiplier / (mass + fuel + cargo) + jumpboost
        # As of 2021-04-07 edsy.org says text import not yet implemented, so ignore the possible issue with
        # a locale that uses comma for decimal separator.
        string += f'Range : {range_unladen:.2f} LY unladen\n        {range_laden:.2f} LY laden\n'

    except Exception:
        if __debug__:
            raise

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)

        return

    # Look for last ship of this type
    ship = util_ships.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + r'\.\d{4}-\d\d-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get_str('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(pathlib.Path(config.get_str('outdir')) / oldfiles[-1], 'rU') as h:
            if h.read() == string:
                return  # same as last time - don't write

    # Write
    timestamp = time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))
    filename = pathlib.Path(config.get_str('outdir')) / f'{ship}.{timestamp}.txt'

    with open(filename, 'wt') as h:
        h.write(string)
