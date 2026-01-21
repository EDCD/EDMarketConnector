"""Export ship loadout in ED Shipyard plain text format."""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
from collections import defaultdict
from typing import Union
from update import check_for_datafile_updates
import outfitting
import util_ships
from config import config
from edmc_data import edshipyard_slot_map as slot_map
from edmc_data import ship_name_map
from EDMCLogging import get_main_logger

logger = get_main_logger()

__Module = dict[str, Union[str, list[str]]]  # Have to keep old-style here for compatibility

# Map API ship names to ED Shipyard names
ship_map = ship_name_map.copy()

# Ship masses
ships_file = config.app_dir_path / "ships.json"
if not ships_file.is_file():
    check_for_datafile_updates()
    ships_file = config.app_dir_path / "ships.json"  # Probably first boot. Force update.
with open(ships_file, encoding="utf-8") as ships_file_handle:
    ships = json.load(ships_file_handle)


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
        mod_guidance: str = str(module.get('guidance'))

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

            module: __Module | None = outfitting.lookup(v['module'], ship_map)
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

            if name in ['Frame Shift Drive', 'Frame Shift Drive (SCO)']:
                fsd = module  # save for range calculation

                if mods.get('OutfittingFieldType_FSDOptimalMass'):
                    fsd['optmass'] *= mods['OutfittingFieldType_FSDOptimalMass']['value']

                if mods.get('OutfittingFieldType_MaxFuelPerJump'):
                    fsd['maxfuel'] *= mods['OutfittingFieldType_MaxFuelPerJump']['value']

            jumpboost += module.get('jumpboost', 0)  # type: ignore

            for slot_prefix, index in slot_map.items():
                if slot.lower().startswith(slot_prefix):
                    loadout[index].append(cr + name)
                    break

            else:
                if slot.lower().startswith('slot'):
                    loadout[slot[-1]].append(cr + name)
                elif not slot.lower().startswith('planetaryapproachsuite'):
                    logger.debug(f'EDShipyard: Unknown slot {slot}')

        except ValueError as e:
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
    ship_name = data['ship']['name'].lower()
    if ship_name not in ship_name_map:
        raise ValueError(f"Ship name '{data['ship']['name']}' not found in ship_name_map")
    if ship_name_map[ship_name] not in ships:
        raise ValueError(f"Mapped ship name '{ship_name_map[ship_name]}' not found in ships")

    try:
        mass += ships[ship_name_map[data['ship']['name'].lower()]]['hullMass']
        string += f'Mass  : {mass:.2f} T empty\n        {mass + fuel + cargo:.2f} T full\n'
        maxfuel = fsd.get('maxfuel', 0)  # type: ignore
        fuelmul = fsd.get('fuelmul', 0)  # type: ignore

        try:
            multiplier = pow(min(fuel, maxfuel) / fuelmul, 1.0 / fsd['fuelpower']) * fsd['optmass']  # type: ignore
            range_unladen = multiplier / (mass + fuel) + jumpboost
            range_laden = multiplier / (mass + fuel + cargo) + jumpboost
            # As of 2021-04-07 edsy.org says text import not yet implemented, so ignore the possible issue with
            # a locale that uses comma for decimal separator.
        except ZeroDivisionError:
            range_unladen = range_laden = 0.0
        string += (f'Range : {range_unladen:.2f} LY unladen\n'
                   f'        {range_laden:.2f} LY laden\n')

    except Exception:
        if __debug__:
            raise

    if filename:
        with open(filename, 'w') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = util_ships.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + r'\.\d{4}-\d\d-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get_str('outdir')) if regexp.match(x)])
    if oldfiles:
        with (pathlib.Path(config.get_str('outdir')) / oldfiles[-1]).open() as h:
            if h.read() == string:
                return  # same as last time - don't write

    # Write
    timestamp = time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))
    filename = pathlib.Path(config.get_str('outdir')) / f'{ship}.{timestamp}.txt'

    with open(filename, 'w') as h:
        h.write(string)
