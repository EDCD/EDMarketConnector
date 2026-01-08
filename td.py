"""Export data for Trade Dangerous."""

import pathlib
from datetime import datetime
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

    # parse timestamp once
    ts = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
    ts_file = ts.strftime('%Y-%m-%dT%H.%M.%S')
    ts_data = ts.strftime('%Y-%m-%d %H:%M:%S')

    system_name = data['lastSystem']['name'].strip()
    starport_name = data['lastStarport']['name'].strip()
    cmdr_name = data['commander']['name'].strip()

    data_filename = f"{system_name}.{starport_name}.{ts_file}.prices"

    with open(data_path / data_filename, 'w', encoding='utf-8', newline='\n') as h:
        h.write('#! trade.py import -\n')
        h.write(f'# Created by {applongname} {appversion()} on {system()} for Cmdr {cmdr_name}.\n')
        h.write('#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n')
        h.write(f'@ {system_name}/{starport_name}\n')

        # group by category
        by_category = defaultdict(list)
        for commodity in data['lastStarport']['commodities']:
            by_category[commodity['categoryname']].append(commodity)

        for category in sorted(by_category):
            h.write(f'   + {category}\n')
            for commodity in sorted(by_category[category], key=itemgetter('name')):
                demand_val = str(int(commodity['demand'])) if commodity['demandBracket'] else ''
                stock_val = str(int(commodity['stock'])) if commodity['stockBracket'] else ''

                h.write(
                    f"      {commodity['name']:<23}"
                    f" {int(commodity['sellPrice']):7d}"
                    f" {int(commodity['buyPrice']):7d}"
                    f" {demand_val:9}{demandbracketmap[commodity['demandBracket']]:1}"
                    f" {stock_val:8}{stockbracketmap[commodity['stockBracket']]:1}"
                    f"  {ts_data}\n"
                )
