# Export ship loadout in E:D Shipyard format

import base64
from collections import defaultdict
import json
import os
from os.path import join
import re
import StringIO
import time
import gzip

import companion

from config import config


def export(data, filename=None):

    string = json.dumps(companion.ship(data), ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': '))	# pretty print

    if filename:
        with open(filename, 'wt') as h:
            h.write(string)
        return

    # Look for last ship of this type
    ship = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])	# Use in-game name
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


# Return a URL for the current ship
def url(data):

    string = json.dumps(companion.ship(data), ensure_ascii=False, sort_keys=True, separators=(',', ':'))	# most compact representation

    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)
    return 'http://www.edshipyard.com/#/I=' + base64.urlsafe_b64encode(out.getvalue())
