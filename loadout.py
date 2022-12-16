"""Export ship loadout in Companion API json format."""

import json
import os
import pathlib
import re
import time
from os.path import join
from typing import Optional

import companion
import util_ships
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()


def export(data: companion.CAPIData, requested_filename: Optional[str] = None) -> None:
    """
    Write Ship Loadout in Companion API JSON format.

    :param data: CAPI data containing ship loadout.
    :param requested_filename: Name of file to write to.
    """
    string = json.dumps(
        companion.ship(data), cls=companion.CAPIDataEncoder,
        ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')
    )  # pretty print

    if requested_filename is not None and requested_filename:
        with open(requested_filename, 'wt') as h:
            h.write(string)
        return

    elif not requested_filename:
        logger.error(f"{requested_filename=} is not valid")
        return

    # Look for last ship of this type
    ship = util_ships.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + r'\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get_str('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get_str('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return  # same as last time - don't write

    query_time = config.get_int('querytime', default=int(time.time()))

    # Write

    with open(
        pathlib.Path(config.get_str('outdir')) / pathlib.Path(
            ship + '.' + time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(query_time)) + '.txt'
        ),
        'wt'
    ) as h:
        h.write(string)
