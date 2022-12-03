"""Export data for Trade Dangerous."""

import pathlib
import time
from collections import defaultdict
from operator import itemgetter
from platform import system
from sys import platform

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
        # Format described here: https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data
        h.write('#! trade.py import -\n'.encode('utf-8'))
        this_platform = 'darwin' and "Mac OS" or system_name()
        cmdr_name = data['commander']['name'].strip()
        h.write(f'# Created by {applongname} {appversion()} on {this_platform} for Cmdr {cmdr_name}.\n'.encode('utf-8'))
        h.write('#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n'.encode('utf-8'))
        system_name = data['lastSystem']['name'].strip()
        starport_name = data['lastStarport']['name'].strip()
        h.write(f'@ {system_name}/{starport_name}\n'.encode('utf-8'))

        # sort commodities by category
        bycategory = defaultdict(list)
        for commodity in data['lastStarport']['commodities']:
            bycategory[commodity['categoryname']].append(commodity)

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
        for category in sorted(bycategory):
            h.write('   + {}\n'.format(category).encode('utf-8'))
            # corrections to commodity names can change the sort order
            for commodity in sorted(bycategory[category], key=itemgetter('name')):
                h.write('      {:<23} {:7d} {:7d} {:9}{:1} {:8}{:1}  {}\n'.format(
                    commodity['name'],
                    int(commodity['sellPrice']),
                    int(commodity['buyPrice']),
                    int(commodity['demand']) if commodity['demandBracket'] else '',
                    demandbracketmap[commodity['demandBracket']],
                    int(commodity['stock']) if commodity['stockBracket'] else '',
                    stockbracketmap[commodity['stockBracket']],
                    timestamp).encode('utf-8'))

