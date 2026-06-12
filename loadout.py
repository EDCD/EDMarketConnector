"""loadout.py - Export ship loadout in Companion API json format.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""

from __future__ import annotations

import json
import pathlib
import re
import companion
from datetime import datetime, timezone
from config import config
from EDMCLogging import get_main_logger
import util_ships

logger = get_main_logger()


def export(
    data: companion.CAPIData, requested_filename: str | pathlib.Path | None = None
) -> None:
    """Write Ship Loadout in Companion API JSON format.

    :param data: CAPI data containing ship loadout.
    :param requested_filename: Explicit name or Path of file to write to, or None to auto-generate.
    """
    # Pretty-Print
    string = json.dumps(
        companion.ship(data),
        cls=companion.CAPIDataEncoder,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        separators=(",", ": "),
    )

    if requested_filename:
        target_path = pathlib.Path(requested_filename)
        with open(target_path, "w", encoding="utf-8") as h:
            h.write(string)
        return

    if requested_filename == "":
        logger.error("provided requested_filename is an invalid blank string sequence.")
        return

    # Look for last ship of this type
    ship_data = data.get("ship", {})
    custom_name = ship_data.get("shipName")
    raw_ship_type = ship_data.get("name", "UnknownShip")

    ship_file_base = util_ships.ship_file_name(custom_name, raw_ship_type)

    regexp = re.compile(
        re.escape(ship_file_base) + r"\.\d{4}-\d{2}-\d{2}T\d{2}\.\d{2}\.\d{2}\.txt"
    )

    out_dir = pathlib.Path(config.get_str("outdir"))

    if out_dir.is_dir():
        oldfiles = sorted(
            [x for x in out_dir.iterdir() if regexp.match(x.name)], key=lambda p: p.name
        )

        # Deduplication
        if oldfiles:
            try:
                with open(oldfiles[-1], encoding="utf-8") as h:
                    if h.read() == string:
                        return
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Could not read historical loadout log for deduplication: {e!r}")

    querytime = config.get_int("querytime", default=int(datetime.now(timezone.utc).timestamp()))
    timestamp = datetime.fromtimestamp(querytime).strftime("%Y-%m-%dT%H.%M.%S")

    final_output_file = out_dir / f"{ship_file_base}.{timestamp}.txt"

    with open(final_output_file, "w", encoding="utf-8") as h:
        h.write(string)
