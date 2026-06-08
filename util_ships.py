"""
util_ships.py - Ship Utilities.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from edmc_data import ship_name_map

# Character mapping dictionary for illegal filesystem characters
_ILLEGAL_CHAR_MAP = {ord(x): "_" for x in ("\0", "<", ">", ":", '"', "/", "\\", "|", "?", "*")}


def ship_file_name(ship_name: str, ship_type: str) -> str:
    """Return a ship name suitable for a filename."""
    name = str(ship_name or ship_name_map.get(ship_type.lower(), ship_type)).strip()

    # Handle suffix using Pathlib's with_suffix method
    path_obj = Path(name).with_suffix("")
    clean_name = path_obj.name

    # Check if the name is a reserved filename
    if sys.platform == 'win32' and os.path.isreserved(name):
        clean_name += "_"

    return clean_name.translate(_ILLEGAL_CHAR_MAP)
