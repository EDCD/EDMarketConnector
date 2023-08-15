"""
coriolis-update-files.py - Build ship and module databases from https://github.com/EDCD/coriolis-data/.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This script also utilizes the file outfitting.csv. Due to how collate.py
both reads and writes to this file, a local copy in the root of the
project structure is used for this purpose. If you want to utilize the
FDevIDs/ version of the file, copy it over the local one.
"""

import json
import pickle
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

import outfitting
from edmc_data import coriolis_ship_map, ship_name_map

if __name__ == "__main__":

    def add(modules, name, attributes) -> None:
        """Add the given module to the modules dict."""
        assert (
            name not in modules or modules[name] == attributes
        ), f"{name}: {modules.get(name)} != {attributes}"
        assert name not in modules, name
        modules[name] = attributes

    # Regenerate coriolis-data distribution
    subprocess.check_call(
        "npm install",
        cwd="coriolis-data",
        shell=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    coriolis_data_file = Path("coriolis-data/dist/index.json")
    with open(coriolis_data_file) as coriolis_data_file_handle:
        data = json.load(coriolis_data_file_handle)

    # Symbolic name from in-game name
    reverse_ship_map = {v: k for k, v in ship_name_map.items()}

    bulkheads = list(outfitting.armour_map.keys())

    ships = {}
    modules = {}

    # Ship and armour masses
    for m in data["Ships"].values():
        name = coriolis_ship_map.get(
            m["properties"]["name"], str(m["properties"]["name"])
        )
        assert name in reverse_ship_map, name
        ships[name] = {"hullMass": m["properties"]["hullMass"]}
        for bulkhead in bulkheads:
            module_name = "_".join([reverse_ship_map[name], "armour", bulkhead])
            modules[module_name] = {"mass": m["bulkheads"][bulkhead]["mass"]}

    ships = OrderedDict(
        [(k, ships[k]) for k in sorted(ships)]
    )  # Sort for easier diffing
    ships_file = Path("resources/ships.json")
    with open(ships_file, "w") as ships_file_handle:
        json.dump(ships, ships_file_handle, indent=2)

    # Module masses
    for cat in data["Modules"].values():
        for grp, mlist in cat.items():
            for m in mlist:
                assert "symbol" in m, m
                key = str(m["symbol"].lower())
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
                    modules[key] = {
                        "mass": m.get("mass", 0)
                    }  # Some modules don't have mass

    # Pre 3.3 modules
    add(modules, "int_stellarbodydiscoveryscanner_standard", {"mass": 2})
    add(modules, "int_stellarbodydiscoveryscanner_intermediate", {"mass": 2})
    add(modules, "int_stellarbodydiscoveryscanner_advanced", {"mass": 2})

    # Missing
    add(modules, "hpt_multicannon_fixed_small_advanced", {"mass": 2})
    add(modules, "hpt_multicannon_fixed_medium_advanced", {"mass": 4})

    modules = OrderedDict(
        [(k, modules[k]) for k in sorted(modules)]
    )  # sort for easier diffing
    modules_file = Path("modules.p")
    with open(modules_file, "wb") as modules_file_handle:
        pickle.dump(modules, modules_file_handle)
