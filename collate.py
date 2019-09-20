#!/usr/bin/env python
#
# Script for collating lists of seen commodities, modules and ships from dumps of the Companion API output
#

import csv
import json
import os
from os.path import exists, isfile
import sys
from traceback import print_exc

import companion
import outfitting


# keep a summary of commodities found using in-game names
# Assumes that the commodity data has already been 'fixed up'
def addcommodities(data):

    if not data['lastStarport'].get('commodities'): return

    commodityfile = 'commodity.csv'
    commodities = {}

    # slurp existing
    if isfile(commodityfile):
        with open(commodityfile) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                commodities[int(row['id'])] = row	# index by int for easier lookup and sorting
    size_pre = len(commodities)

    for commodity in data['lastStarport'].get('commodities'):
        key = int(commodity['id'])
        new = {
            'id'       : commodity['id'],
            'symbol'   : commodity['name'],
            'category' : companion.category_map.get(commodity['categoryname']) or commodity['categoryname'],
            'name'     : commodity.get('locName') or 'Limpets',
        }
        old = commodities.get(key)
        if old and companion.category_map.get(commodity['categoryname'], True):
            if new['symbol'] != old['symbol'] or new['name'] != old['name']:
                raise AssertionError('%s: "%s"!="%s"' % (key, new, old))
        commodities[key] = new

    if len(commodities) > size_pre:

        if isfile(commodityfile):
            if isfile(commodityfile+'.bak'):
                os.unlink(commodityfile+'.bak')
            os.rename(commodityfile, commodityfile+'.bak')

        with open(commodityfile, 'wb') as csvfile:
            writer = csv.DictWriter(csvfile, ['id', 'symbol', 'category', 'name'])
            writer.writeheader()
            for key in sorted(commodities):
                writer.writerow(commodities[key])

        print('Added %d new commodities' % (len(commodities) - size_pre))

# keep a summary of modules found
def addmodules(data):

    if not data['lastStarport'].get('modules'): return

    outfile = 'outfitting.csv'
    modules = {}
    fields = ['id', 'symbol', 'category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating', 'entitlement']

    # slurp existing
    if isfile(outfile):
        with open(outfile) as csvfile:
            reader = csv.DictReader(csvfile, restval='')
            for row in reader:
                modules[int(row['id'])] = row	# index by int for easier lookup and sorting
    size_pre = len(modules)

    for key,module in data['lastStarport'].get('modules').items():
        # sanity check
        if int(key) != module.get('id'): raise AssertionError('id: %s!=%s' % (key, module['id']))
        try:
            new = outfitting.lookup(module, companion.ship_map, True)
        except:
            print('%d, %s:' % (module['id'], module['name']))
            print_exc(0)
            new = None
        if new:
            old = modules.get(int(key))
            if old:
                # check consistency with existing data
                for thing in fields:
                    if not old.get(thing) and new.get(thing):
                        size_pre -= 1
                    elif str(new.get(thing,'')) != old.get(thing):
                        raise AssertionError('%s: %s "%s"!="%s"' % (key, thing, new.get(thing), old.get(thing)))
            modules[int(key)] = new

    if len(modules) > size_pre:

        if isfile(outfile):
            if isfile(outfile+'.bak'):
                os.unlink(outfile+'.bak')
            os.rename(outfile, outfile+'.bak')

        with open(outfile, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fields, extrasaction='ignore')
            writer.writeheader()
            for key in sorted(modules):
                writer.writerow(modules[key])

        print('Added %d new modules' % (len(modules) - size_pre))

# keep a summary of ships found
def addships(data):

    if not data['lastStarport'].get('ships'): return

    shipfile = 'shipyard.csv'
    ships = {}
    fields = ['id', 'symbol', 'name']

    # slurp existing
    if isfile(shipfile):
        with open(shipfile) as csvfile:
            reader = csv.DictReader(csvfile, restval='')
            for row in reader:
                ships[int(row['id'])] = row	# index by int for easier lookup and sorting
    size_pre = len(ships)

    for ship in list((data['lastStarport']['ships'].get('shipyard_list') or {}).values()) + data['lastStarport']['ships'].get('unavailable_list'):
        # sanity check
        key = ship['id']
        new = { 'id': int(key), 'symbol': ship['name'], 'name': companion.ship_map.get(ship['name'].lower()) }
        if new:
            old = ships.get(int(key))
            if old:
                # check consistency with existing data
                for thing in fields:
                    if not old.get(thing) and new.get(thing):
                        ships[int(key)] = new
                        size_pre -= 1
                    elif str(new.get(thing,'')) != old.get(thing):
                        raise AssertionError('%s: %s "%s"!="%s"' % (key, thing, new.get(thing), old.get(thing)))
            ships[int(key)] = new

    if len(ships) > size_pre:

        if isfile(shipfile):
            if isfile(shipfile+'.bak'):
                os.unlink(shipfile+'.bak')
            os.rename(shipfile, shipfile+'.bak')

        with open(shipfile, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, ['id', 'symbol', 'name'])
            writer.writeheader()
            for key in sorted(ships):
                writer.writerow(ships[key])

        print('Added %d new ships' % (len(ships) - size_pre))


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print('Usage: collate.py [dump.json]')
    else:
        # read from dumped json file(s)
        session = companion.Session()
        for f in sys.argv[1:]:
            with open(f) as h:
                print(f)
                data = json.load(h)
                if not data['commander'].get('docked'):
                    print('Not docked!')
                elif not data.get('lastStarport'):
                    print('No starport!')
                else:
                    if data['lastStarport'].get('commodities'):
                        addcommodities(data)
                    else:
                        print('No market')
                    if data['lastStarport'].get('modules'):
                        addmodules(data)
                    else:
                        print('No outfitting')
                    if data['lastStarport'].get('ships'):
                        addships(data)
                    else:
                        print('No shipyard')
