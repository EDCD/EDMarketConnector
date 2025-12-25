"""
util_ships.py - Ship Utilities.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
import os
import sys
from pathlib import Path
from edmc_data import ship_name_map


def ship_file_name(ship_name: str, ship_type: str) -> str:
    """Return a ship name suitable for a filename."""
    name = str(ship_name or ship_name_map.get(ship_type.lower(), ship_type)).strip()

    # Handle suffix using Pathlib's with_suffix method
    name = Path(name).with_suffix("").name

    # Check if the name is a reserved filename
    if sys.platform == 'win32' and os.path.isreserved(name):
        name += "_"

    return name.translate(
        {ord(x): "_" for x in ("\0", "<", ">", ":", '"', "/", "\\", "|", "?", "*")}
    )
