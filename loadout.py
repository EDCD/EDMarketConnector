# Export ship loadout in Companion API json format

import json
import os
from os.path import join
import re
import time

from config import config
import companion
import util_ships


def export(data, filename=None):

    string = json.dumps(
        companion.ship(data),
        cls=companion.CAPIDataEncoder,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        separators=(",", ": "),
    )  # pretty print

    if filename:
        with open(filename, "wt") as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = util_ships.ship_file_name(data["ship"].get("shipName"), data["ship"]["name"])
    regexp = re.compile(
        re.escape(ship) + "\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt"
    )
    oldfiles = sorted(
        [x for x in os.listdir(config.get_str("outdir")) if regexp.match(x)]
    )
    if oldfiles:
        with open(join(config.get_str("outdir"), oldfiles[-1]), "rU") as h:
            if h.read() == string:
                return  # same as last time - don't write

    querytime = config.get_int("querytime", default=int(time.time()))

    # Write
    #
    #  When this is refactored into multi-line CHECK IT WORKS, avoiding the
    #  brainfart we had with dangling commas in commodity.py:export() !!!
    #
    filename = join(
        config.get_str("outdir"),
        "%s.%s.txt"
        % (ship, time.strftime("%Y-%m-%dT%H.%M.%S", time.localtime(querytime))),
    )
    #
    #  When this is refactored into multi-line CHECK IT WORKS, avoiding the
    #  brainfart we had with dangling commas in commodity.py:export() !!!
    #
    with open(filename, "wt") as h:
        h.write(string)
