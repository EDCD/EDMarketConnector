#!/usr/bin/env python3
#
# Script for collating lists of seen commodities, modules and ships from dumps of the Companion API output
#

import csv
import json
import os
import sys
from os.path import isfile
from traceback import print_exc

import companion
import outfitting
from edmc_data import companion_category_map, ship_name_map


def __make_backup(file_name: str, suffix: str = '.bak') -> None:
    """
    Rename the given file to $file.bak, removing any existing $file.bak. Assumes $file exists on disk.

    :param file_name: The name of the file to make a backup of
    :param suffix: The suffix to use for backup files (default '.bak')
    """

    backup_name = file_name + suffix

    if isfile(backup_name):
        os.unlink(backup_name)

    os.rename(file_name, backup_name)


# keep a summary of commodities found using in-game names
# Assumes that the commodity data has already been 'fixed up'
def addcommodities(data):
    if not data['lastStarport'].get('commodities'):
        return

    commodityfile = 'commodity.csv'
    commodities = {}

    # slurp existing
    if isfile(commodityfile):
        with open(commodityfile) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                commodities[int(row['id'])] = row  # index by int for easier lookup and sorting

    size_pre = len(commodities)

    for commodity in data['lastStarport'].get('commodities'):
        key = int(commodity['id'])
        new = {
            'id'       : commodity['id'],
            'symbol'   : commodity['name'],
            'category' : companion_category_map.get(commodity['categoryname']) or commodity['categoryname'],
            'name'     : commodity.get('locName') or 'Limpets',
        }

        old = commodities.get(key)

        if old and companion_category_map.get(commodity['categoryname'], True):
            if new['symbol'] != old['symbol'] or new['name'] != old['name']:
                raise ValueError('{}: {!r} != {!r}'.format(key, new, old))

        commodities[key] = new

    if not len(commodities) > size_pre:
        return

    if isfile(commodityfile):
        __make_backup(commodityfile)

    with open(commodityfile, 'w', newline='\n') as csvfile:
        writer = csv.DictWriter(csvfile, ['id', 'symbol', 'category', 'name'])
        writer.writeheader()

        for key in sorted(commodities):
            writer.writerow(commodities[key])

    print('Added {} new commodities'.format(len(commodities) - size_pre))


# keep a summary of modules found
def addmodules(data):
    if not data['lastStarport'].get('modules'):
        return

    outfile = 'outfitting.csv'
    modules = {}
    fields = ('id', 'symbol', 'category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating', 'entitlement')

    # slurp existing
    if isfile(outfile):
        with open(outfile) as csvfile:
            reader = csv.DictReader(csvfile, restval='')
            for row in reader:
                modules[int(row['id'])] = row  # index by int for easier lookup and sorting

    size_pre = len(modules)

    for key, module in data['lastStarport'].get('modules').items():
        # sanity check
        key = int(key)
        if key != module.get('id'):
            raise ValueError('id: {} != {}'.format(key, module['id']))

        try:
            new = outfitting.lookup(module, ship_name_map, True)

        except Exception:
            print('{}, {}:'.format(module['id'], module['name']))
            print_exc(0)
            new = None

        if new:
            old = modules.get(key)
            if old:
                # check consistency with existing data
                for thing in fields:
                    if not old.get(thing) and new.get(thing):
                        size_pre -= 1

                    elif str(new.get(thing, '')) != old.get(thing):
                        raise ValueError('{}: {} {!r}!={!r}'.format(key, thing, new.get(thing), old.get(thing)))

            modules[key] = new

    if not len(modules) > size_pre:
        return

    if isfile(outfile):
        __make_backup(outfile)

    with open(outfile, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fields, extrasaction='ignore')
        writer.writeheader()

        for key in sorted(modules):
            writer.writerow(modules[key])

    print('Added {} new modules'.format(len(modules) - size_pre))


# keep a summary of ships found
def addships(data):
    if not data['lastStarport'].get('ships'):
        return

    shipfile = 'shipyard.csv'
    ships = {}
    fields = ('id', 'symbol', 'name')

    # slurp existing
    if isfile(shipfile):
        with open(shipfile) as csvfile:
            reader = csv.DictReader(csvfile, restval='')
            for row in reader:
                ships[int(row['id'])] = row  # index by int for easier lookup and sorting

    size_pre = len(ships)

    data_ships = data['lastStarport']['ships']
    for ship in tuple(data_ships.get('shipyard_list', {}).values()) + data_ships.get('unavailable_list'):
        # sanity check
        key = int(ship['id'])
        new = {'id': key, 'symbol': ship['name'], 'name': ship_name_map.get(ship['name'].lower())}
        if new:
            old = ships.get(key)
            if old:
                # check consistency with existing data
                for thing in fields:
                    if not old.get(thing) and new.get(thing):
                        ships[key] = new
                        size_pre -= 1

                    elif str(new.get(thing, '')) != old.get(thing):
                        raise ValueError('{}: {} {!r} != {!r}'.format(key, thing, new.get(thing), old.get(thing)))

            ships[key] = new

    if not len(ships) > size_pre:
        return

    if isfile(shipfile):
        __make_backup(shipfile)

    with open(shipfile, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, ['id', 'symbol', 'name'])
        writer.writeheader()

        for key in sorted(ships):
            writer.writerow(ships[key])

    print('Added {} new ships'.format(len(ships) - size_pre))


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print('Usage: collate.py [dump.json]')
        sys.exit()

    # read from dumped json file(s)
    session = companion.Session()
    for file_name in sys.argv[1:]:
        data = None
        with open(file_name) as f:
            print(file_name)
            data = json.load(f)

        if not data['commander'].get('docked'):
            print('Not docked!')
            continue

        elif not data.get('lastStarport'):
            print('No starport!')
            continue

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
