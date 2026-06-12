"""Export ship loadout in ED Shipyard plain text format."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any
from config import config
from edmc_data import edshipyard_slot_map as slot_map
from edmc_data import ship_name_map
from EDMCLogging import get_main_logger
import outfitting
from update import check_for_datafile_updates
import util_ships

logger = get_main_logger()

type ModuleData = dict[str, Any]

ship_map = ship_name_map.copy()

# Ship masses
ships_file = config.app_dir_path / "ships.json"
if not ships_file.is_file():
    check_for_datafile_updates()
    ships_file = (config.app_dir_path / "ships.json")  # Probably first boot. Force update.
with open(ships_file, encoding="utf-8") as ships_file_handle:
    ships: dict[str, Any] = json.load(ships_file_handle)


def export(data: Mapping[str, Any], filename: str | pathlib.Path | None = None) -> None:  # noqa: C901, CCR001
    """Export ship loadout in E:D Shipyard plain text format.

    :param data: CAPI data.
    :param filename: Override default file name.
    """

    def class_rating(mod: ModuleData) -> str:
        """Return a string representation of the class and grading of the given module."""
        mod_class = mod.get("class", "")
        mod_rating = mod.get("rating", "")
        mod_mount = mod.get("mount")
        mod_guidance = str(mod.get("guidance", ""))

        ret = f"{mod_class}{mod_rating}"

        if "guidance" in mod:
            mount = (mod_mount[0] if isinstance(mod_mount, (list, str)) and mod_mount else "F")
            guidance = mod_guidance[0] if mod_guidance else ""
            ret += f"/{mount}{guidance}"
        elif "mount" in mod:  # Hardpoints
            ret += f"/{mod_mount}"
        elif "Cabin" in str(mod.get("name", "")):  # Passenger cabins
            name_str = str(mod.get("name", ""))
            ret += f"/{name_str[0]}" if name_str else "/"

        return f"{ret} "

    querytime = config.get_int("querytime", default=int(datetime.now(timezone.utc).timestamp()))

    loadout: dict[str, list[str]] = defaultdict(list)
    mass = 0.0
    fuel = 0
    cargo = 0
    fsd: ModuleData | None = None
    jumpboost = 0

    ship_payload = data.get("ship", {})
    modules_payload = ship_payload.get("modules", {})

    for slot in sorted(modules_payload):
        v = modules_payload[slot]
        try:
            if not v or "module" not in v:
                continue

            raw_module = outfitting.lookup(v["module"], ship_map)
            if not raw_module:
                continue

            module = dict(raw_module)

            cr = class_rating(module)
            mods = v.get("modifications") or v.get("WorkInProgress_modifications") or {}

            base_mass = float(module.get("mass", 0.0))
            if "OutfittingFieldType_Mass" in mods:
                mass += base_mass * float(mods["OutfittingFieldType_Mass"].get("value", 1.0))
            else:
                mass += base_mass

            module_name = str(module.get("name", ""))
            module_class = str(module.get("class", "0"))

            # Specials
            if "Fuel Tank" in module_name:
                capacity = 2 ** int(module_class) if module_class.isdigit() else 0
                fuel += capacity
                name = f"{module_name} (Capacity: {capacity})"
            elif "Cargo Rack" in module_name:
                capacity = 2 ** int(module_class) if module_class.isdigit() else 0
                cargo += capacity
                name = f"{module_name} (Capacity: {capacity})"
            else:
                name = module_name

            if name in ("Frame Shift Drive", "Frame Shift Drive (SCO)"):
                fsd = module  # save for range calculation
                if "OutfittingFieldType_FSDOptimalMass" in mods:
                    fsd["optmass"] = float(fsd.get("optmass", 0.0)) * float(
                        mods["OutfittingFieldType_FSDOptimalMass"].get("value", 1.0)
                    )
                if "OutfittingFieldType_MaxFuelPerJump" in mods:
                    fsd["maxfuel"] = float(fsd.get("maxfuel", 0.0)) * float(
                        mods["OutfittingFieldType_MaxFuelPerJump"].get("value", 1.0)
                    )

            jumpboost += int(module.get("jumpboost", 0))

            slot_lower = slot.lower()
            for slot_prefix, index in slot_map.items():
                if slot_lower.startswith(slot_prefix):
                    loadout[index].append(cr + name)
                    break
            else:
                if slot_lower.startswith("slot"):
                    loadout[slot[-1]].append(cr + name)
                elif not slot_lower.startswith("planetaryapproachsuite"):
                    logger.debug(f"EDShipyard: Unknown slot {slot}")

        except ValueError as e:
            logger.debug(f"EDShipyard: Parsing validation break: {e!r}")
            continue  # Silently skip unrecognized modules

    raw_ship_name = ship_payload.get("name", "")
    ship = ship_map.get(raw_ship_name.lower(), raw_ship_name)
    custom_name = ship_payload.get("shipName")

    # Construct description
    _ships = f"{ship}, {custom_name}" if custom_name is not None else ship
    string = f"[{_ships}]\n"

    slot_types = (
        'H', 'L', 'M', 'S', 'U', None, 'BH', 'RB', 'TM', 'FH', 'EC', 'PC', 'SS', 'FS', None, 'MC', None, '9', '8',
        '7', '6', '5', '4', '3', '2', '1'
    )
    for slot_key in slot_types:
        if not slot_key:
            string += "\n"
        elif slot_key in loadout:
            for name in loadout[slot_key]:
                string += f"{slot_key}: {name}\n"

    string += f"---\nCargo : {cargo} T\nFuel  : {fuel} T\n"

    # Add mass and range
    ship_lower_name = raw_ship_name.lower()
    if ship_lower_name not in ship_name_map:
        raise ValueError(f"Ship name '{raw_ship_name}' not found in ship_name_map")

    mapped_name = ship_name_map[ship_lower_name]
    if mapped_name not in ships:
        raise ValueError(
            f"Mapped ship name '{mapped_name}' not found in ships database"
        )

    try:
        mass += ships[mapped_name]["hullMass"]
        string += (
            f"Mass  : {mass:.2f} T empty\n        {mass + fuel + cargo:.2f} T full\n"
        )

        if fsd is not None:
            maxfuel = float(fsd.get("maxfuel", 0.0))
            fuelmul = float(fsd.get("fuelmul", 0.0))
            optmass = float(fsd.get("optmass", 0.0))
            fuelpower = float(fsd.get("fuelpower", 1.0))

            try:
                multiplier = (pow(min(fuel, maxfuel) / fuelmul, 1.0 / fuelpower) * optmass)
                range_unladen = multiplier / (mass + fuel) + jumpboost
                range_laden = multiplier / (mass + fuel + cargo) + jumpboost
            except (ZeroDivisionError, ValueError):
                range_unladen = range_laden = 0.0
        else:
            range_unladen = range_laden = 0.0

        string += f"Range : {range_unladen:.2f} LY unladen\n        {range_laden:.2f} LY laden\n"

    except Exception:
        if __debug__:
            raise

    if filename:
        with open(filename, "w", encoding="utf-8") as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship_filename_base = util_ships.ship_file_name(custom_name, raw_ship_name)
    regexp = re.compile(
        re.escape(ship_filename_base) + r"\.\d{4}-\d\d-\d\dT\d\d\.\d\d\.\d\d\.txt"
    )
    out_dir = pathlib.Path(config.get_str("outdir"))

    if out_dir.is_dir():
        oldfiles = sorted(
            [x for x in out_dir.iterdir() if regexp.match(x.name)],
            key=lambda p: p.name,  # Sort based on the filename string
        )
        if oldfiles:
            with oldfiles[-1].open(encoding="utf-8") as h:
                if h.read() == string:
                    return  # same as last time - don't write

    # Write
    timestamp = datetime.fromtimestamp(querytime).strftime("%Y-%m-%dT%H.%M.%S")
    final_output_path = out_dir / f"{ship_filename_base}.{timestamp}.txt"

    with open(final_output_path, "w", encoding="utf-8") as h:
        h.write(string)
