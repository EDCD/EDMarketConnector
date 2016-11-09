# Export ship loadout in E:D Shipyard format

import base64
from collections import defaultdict
import json
import os
from os.path import join
import re
import StringIO
import time
import urllib2
import gzip

import companion

from config import config


# Return a description of the current ship as a JSON object
def description(data):

    # Add a leaf to a dictionary, creating empty dictionaries along the branch if necessary
    def addleaf(data, to, props):

        # special handling for completely empty trees
        p = props[0]
        if p in data and not data[p]:
            to[p] = data[p]
            return

        # Does the leaf exist ?
        tail = data
        for p in props:
            if not hasattr(data, 'get') or p not in tail:
                return
            else:
                tail = tail[p]

        for p in props[:-1]:
            if not hasattr(data, 'get') or p not in data:
                return
            elif p not in to:
                to[p] = {}
            elif not hasattr(to, 'get'):
                return	# intermediate is not a dictionary - inconsistency!
            data = data[p]
            to = to[p]
        p = props[-1]
        to[p] = data[p]

    querytime = config.getint('querytime') or int(time.time())

    # subset of "ship" that's not noisy
    ship = {}
    for props in [
            ('alive',),
            ('cargo', 'capacity'),
            ('free',),
            ('fuel', 'main', 'capacity'),
            ('fuel', 'reserve', 'capacity'),
            ('fuel', 'superchargedFSD'),
            ('id',),
            ('name',),
            ('value', 'hull'),
            ('value', 'modules'),
            ('value', 'unloaned'),
    ]: addleaf(data['ship'], ship, props)

    ship['modules'] = {}
    for slot in data['ship'].get('modules', {}):
        for prop in ['free', 'id', 'modifiers', 'name', 'on', 'priority', 'recipeLevel', 'recipeName', 'recipeValue', 'unloaned', 'value']:
            addleaf(data['ship']['modules'], ship['modules'], (slot, 'module', prop))

    return ship


def export(data, filename=None):

    string = json.dumps(description(data), ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': '))	# pretty print

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

    # Write
    filename = join(config.get('outdir'), '%s.%s.txt' % (ship, time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))
    with open(filename, 'wt') as h:
        h.write(string)


# Return a URL for the current ship
def url(data):

    string = json.dumps(description(data), ensure_ascii=False, sort_keys=True, separators=(',', ':'))	# most compact representation

    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)
    return 'http://www.edshipyard.com/#/I=' + urllib2.quote(base64.standard_b64encode(out.getvalue()), safe='')

