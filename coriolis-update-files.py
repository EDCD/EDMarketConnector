#!/usr/bin/env python3
"""coriolis-update-files.py - Build ship and module databases from coriolis-data.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.

This script also utilizes the file outfitting.csv. Due to how collate.py
both reads and writes to this file, a local copy in the root of the
project structure is used for this purpose. If you want to utilize the
FDevIDs/ version of the file, copy it over the local one.
"""

import json
import subprocess
import sys
from typing import Any

import outfitting
from edmc_data import coriolis_ship_map, ship_name_map


def add_module(modules: dict[str, Any], name: str, attributes: dict[str, Any]) -> None:
    """Add the given module to the modules dict safely."""
    if name in modules:
        if modules[name] != attributes:
            raise ValueError(f"{name}: {modules[name]} != {attributes}")
        raise ValueError(f"{name} already exists in modules")

    modules[name] = attributes


def main() -> None:  # noqa: CCR001
    """Run the Coriolis Updater."""
    try:
        # Regenerate coriolis-data distribution
        subprocess.run(
            "npm install", cwd="coriolis-data", shell=True, check=True, stdout=sys.stdout, stderr=sys.stderr,
        )
    except NotADirectoryError:
        sys.exit(
            "Coriolis-Data Directory not found! Have you set up your submodules? \n"
            "https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source#obtain-a-copy-of-the-application-source"
        )

    file_path = "coriolis-data/dist/index.json"
    with open(file_path, encoding="utf-8") as file:
        data = json.load(file)

    # Symbolic name from in-game name
    reverse_ship_map = {v: k for k, v in ship_name_map.items()}
    bulkheads = list(outfitting.armour_map)

    ships: dict[str, Any] = {}
    modules: dict[str, Any] = {}

    # Process Ship and armour masses
    for m in data["Ships"].values():
        raw_name = m["properties"]["name"]
        name = coriolis_ship_map.get(raw_name, str(raw_name))
        if name not in reverse_ship_map:
            raise ValueError(f"Unknown ship: {name}")

        ships[name] = {"hullMass": m["properties"]["hullMass"],
                       "reserveFuelCapacity": m["properties"]["reserveFuelCapacity"]}

        for i, bulkhead in enumerate(bulkheads):
            key = f"{reverse_ship_map[name]}_armour_{bulkhead}"
            modules[key] = {"mass": m["bulkheads"][i]["mass"]}

    # Native dictionary sorting optimization
    ships = dict(sorted(ships.items()))
    with open("ships.json", "w", encoding="utf-8") as ships_file:
        json.dump(ships, ships_file, indent=4)

    # Module masses
    for cat in data["Modules"].values():
        for grp, mlist in cat.items():
            for m in mlist:
                if "symbol" not in m:
                    raise ValueError(f"No symbol in {m}")

                key = m["symbol"].lower()
                if grp == "fsd":
                    modules[key] = {
                        "mass": m["mass"],
                        "optmass": m["optmass"],
                        "maxfuel": m["maxfuel"],
                        "fuelmul": m["fuelmul"],
                        "fuelpower": m["fuelpower"],
                    }
                elif grp == "gfsb":
                    modules[key] = {
                        "mass": m["mass"],
                        "jumpboost": m["jumpboost"],
                    }
                else:
                    modules[key] = {"mass": m.get("mass", 0)}  # Some modules don't have mass

    # Pre 3.3 modules
    add_module(modules, "int_stellarbodydiscoveryscanner_standard", {"mass": 2})
    add_module(modules, "int_stellarbodydiscoveryscanner_intermediate", {"mass": 2})
    add_module(modules, "int_stellarbodydiscoveryscanner_advanced", {"mass": 2})

    modules = dict(sorted(modules.items()))
    with open("modules.json", "w", encoding="utf-8") as modules_file:
        json.dump(modules, modules_file, indent=4)


if __name__ == "__main__":
    main()
