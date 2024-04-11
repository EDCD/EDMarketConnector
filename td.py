"""Export data for Trade Dangerous."""

import pathlib
import sys
import time
from collections import defaultdict
from operator import itemgetter
from platform import system

from companion import CAPIData
from config import applongname, appversion, config

# These are specific to Trade Dangerous, so don't move to edmc_data.py
demandbracketmap = {0: '?',
                    1: 'L',
                    2: 'M',
                    3: 'H', }
stockbracketmap = {0: '-',
                   1: 'L',
                   2: 'M',
                   3: 'H', }


def export(data: CAPIData) -> None:
    """Export market data in TD format."""
    data_path = pathlib.Path(config.get_str('outdir'))
    timestamp = time.strftime('%Y-%m-%dT%H.%M.%S', time.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
    data_filename = f"{data['lastSystem']['name'].strip()}.{data['lastStarport']['name'].strip()}.{timestamp}.prices"

    # codecs can't automatically handle line endings, so encode manually where
    # required
    with open(data_path / data_filename, 'wb') as h:
        # Format described here: https://github.com/eyeonus/Trade-Dangerous/wiki/Price-Data
        h.write('#! trade.py import -\n'.encode('utf-8'))
        this_platform = "Mac OS" if sys.platform == 'darwin' else system()
        cmdr_name = data['commander']['name'].strip()
        h.write(
            f'# Created by {applongname} {appversion()} on {this_platform} for Cmdr {cmdr_name}.\n'.encode('utf-8')
        )
        h.write(
            '#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n'.encode('utf-8')
        )
        system_name = data['lastSystem']['name'].strip()
        starport_name = data['lastStarport']['name'].strip()
        h.write(f'@ {system_name}/{starport_name}\n'.encode('utf-8'))

        # sort commodities by category
        by_category = defaultdict(list)
        for commodity in data['lastStarport']['commodities']:
            by_category[commodity['categoryname']].append(commodity)

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
        for category in sorted(by_category):
            h.write(f'   + {format(category)}\n'.encode('utf-8'))
            # corrections to commodity names can change the sort order
            for commodity in sorted(by_category[category], key=itemgetter('name')):
                h.write(
                    f"      {commodity['name']:<23}"
                    f" {int(commodity['sellPrice']):7d}"
                    f" {int(commodity['buyPrice']):7d}"
                    f" {int(commodity['demand']) if commodity['demandBracket'] else '':9}"
                    f"{demandbracketmap[commodity['demandBracket']]:1}"
                    f" {int(commodity['stock']) if commodity['stockBracket'] else '':8}"
                    f"{stockbracketmap[commodity['stockBracket']]:1}"
                    f"  {timestamp}\n".encode('utf-8')
                )
