# Export ship loadout in Companion API json format

import json
import os
from os.path import join
import re
import time

from config import config
import companion


def export(data, filename=None):

    string = json.dumps(companion.ship(data), ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': '))	# pretty print

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = companion.ship_file_name(data['ship'].get('shipName'), data['ship']['name'])
    regexp = re.compile(re.escape(ship) + '\.\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt')
    oldfiles = sorted([x for x in os.listdir(config.get('outdir')) if regexp.match(x)])
    if oldfiles:
        with open(join(config.get('outdir'), oldfiles[-1]), 'rU') as h:
            if h.read() == string:
                return	# same as last time - don't write

    querytime = config.getint('querytime') or int(time.time())

    # Write
    filename = join(config.get('outdir'), '%s.%s.txt' % (ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))
    with open(filename, 'wt') as h:
        h.write(string)
