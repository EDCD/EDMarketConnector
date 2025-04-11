#!/usr/bin/env python3
"""
Collate lists of seen commodities, modules and ships from dumps of the Companion API output.

Note that currently this will only work with the output files created if you
run the main program from a working directory that has a `dump/` directory,
which causes a file to be written per CAPI query.

This script also utilise the file outfitting.csv.  As it both reads it in *and*
writes out a new copy a local copy, in the root of the project structure, is
used for this purpose.  If you want to utilise the FDevIDs/ version of the
file, copy it over the local one.
"""

import csv
import json
import os
import pathlib
import sys
from traceback import print_exc

import companion
import outfitting
from config import config
from edmc_data import companion_category_map, ship_name_map


def __make_backup(file_name: pathlib.Path, suffix: str = '.bak') -> None:
    """
    Rename the given file to $file.bak, removing any existing $file.bak. Assumes $file exists on disk.

    :param file_name: The name of the file to make a backup of
    :param suffix: The suffix to use for backup files (default '.bak')
    """
    backup_name = file_name.parent / (file_name.name + suffix)

    if pathlib.Path.is_file(backup_name):
        os.unlink(backup_name)

    os.rename(file_name, backup_name)


def addcommodities(data) -> None:  # noqa: CCR001
    """
    Keep a summary of commodities found using in-game names.

    Assumes that the commodity data has already been 'fixed up'
    :param data: - Fixed up commodity data.
    """
    if not data['lastStarport'].get('commodities'):
        return

    try:
        commodityfile = config.app_dir_path / 'FDevIDs' / 'commodity.csv'
    except FileNotFoundError:
        commodityfile = pathlib.Path('FDevIDs/commodity.csv')
    commodities = {}

    # slurp existing
    if pathlib.Path.is_file(commodityfile):
        with open(commodityfile) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                commodities[int(row['id'])] = row  # index by int for easier lookup and sorting

    size_pre = len(commodities)

    for commodity in data['lastStarport'].get('commodities'):
        key = int(commodity['id'])
        new = {
            'id':        commodity['id'],
            'symbol':    commodity['name'],
            'category':  companion_category_map.get(commodity['categoryname']) or commodity['categoryname'],
            'name':      commodity.get('locName') or 'Limpets',
        }

        old = commodities.get(key)

        if old and companion_category_map.get(commodity['categoryname'], True):
            if new['symbol'] != old['symbol'] or new['name'] != old['name']:
                raise ValueError(f'{key}: {new!r} != {old!r}')

        commodities[key] = new

    if len(commodities) <= size_pre:
        return

    if pathlib.Path.is_file(commodityfile):
        __make_backup(commodityfile)

    with open(commodityfile, 'w', newline='\n') as csvfile:
        writer = csv.DictWriter(csvfile, ['id', 'symbol', 'category', 'name'])
        writer.writeheader()

        for key in sorted(commodities):
            writer.writerow(commodities[key])

    print(f'Added {len(commodities) - size_pre} new commodities')


def addmodules(data):  # noqa: C901, CCR001
    """Keep a summary of modules found."""
    if not data['lastStarport'].get('modules'):
        return

    outfile = pathlib.Path('outfitting.csv')
    modules = {}
    fields = ('id', 'symbol', 'category', 'name', 'mount', 'guidance', 'ship', 'class', 'rating', 'entitlement')

    # slurp existing
    if pathlib.Path.is_file(outfile):
        with open(outfile) as csvfile:
            reader = csv.DictReader(csvfile, restval='')
            for row in reader:
                modules[int(row['id'])] = row  # index by int for easier lookup and sorting

    size_pre = len(modules)

    for key, module in data['lastStarport'].get('modules').items():
        # sanity check
        key = int(key)
        if key != module.get('id'):
            raise ValueError(f'id: {key} != {module["id"]}')

        try:
            new = outfitting.lookup(module, ship_name_map, True)

        except Exception:
            print(f'{module["id"]}, {module["name"]}:')
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
                        raise ValueError(f'{key}: {thing} {new.get(thing)!r}!={old.get(thing)!r}')

            modules[key] = new

    if not len(modules) > size_pre:
        return

    if pathlib.Path.is_file(outfile):
        __make_backup(outfile)

    with open(outfile, 'w', newline='\n') as csvfile:
        writer = csv.DictWriter(csvfile, fields, extrasaction='ignore')
        writer.writeheader()

        for key in sorted(modules):
            writer.writerow(modules[key])

    print(f'Added {len(modules) - size_pre} new modules')


def addships(data) -> None:  # noqa: CCR001
    """Keep a summary of ships found."""
    if not data['lastStarport'].get('ships'):
        return

    shipfile = pathlib.Path('shipyard.csv')
    ships = {}
    fields = ('id', 'symbol', 'name')

    # slurp existing
    if pathlib.Path.is_file(shipfile):
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
                        raise ValueError(f'{key}: {thing} {new.get(thing)!r} != {old.get(thing)!r}')

            ships[key] = new

    if not len(ships) > size_pre:
        return

    if pathlib.Path.is_file(shipfile):
        __make_backup(shipfile)

    with open(shipfile, 'w', newline='\n') as csvfile:
        writer = csv.DictWriter(csvfile, ['id', 'symbol', 'name'])
        writer.writeheader()

        for key in sorted(ships):
            writer.writerow(ships[key])

    print(f'Added {len(ships) - size_pre} new ships')


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
            data = data['data']

        if not data['commander'].get('docked'):
            print('Not docked!')
            continue

        if not data.get('lastStarport'):
            print('No starport!')
            continue

        addcommodities(data) if data['lastStarport'].get('commodities') else print('No market')

        addmodules(data) if data['lastStarport'].get('modules') else print('No outfitting')

        addships(data) if data['lastStarport'].get('ships') else print('No shipyard')
