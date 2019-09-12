# Export to Trade Dangerous

from os.path import join
from collections import defaultdict
import codecs
import numbers
from operator import itemgetter
from platform import system
from sys import platform
import time

from config import applongname, appversion, config

demandbracketmap = { 0: '?',
                     1: 'L',
                     2: 'M',
                     3: 'H', }
stockbracketmap =  { 0: '-',
                     1: 'L',
                     2: 'M',
                     3: 'H', }

def export(data):

    querytime = config.getint('querytime') or int(time.time())

    filename = join(config.get('outdir'), '%s.%s.%s.prices' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))

    # Format described here: https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data
    h = open(filename, 'wb')	# codecs can't automatically handle line endings, so encode manually where required
    h.write(('#! trade.py import -\n# Created by %s %s on %s%s.\n#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n@ %s/%s\n' % (applongname, appversion, platform=='darwin' and "Mac OS" or system(), not config.getint('anonymous') and ' for Cmdr '+data['commander']['name'].strip() or '', data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())).encode('utf-8'))

    # sort commodities by category
    bycategory = defaultdict(list)
    for commodity in data['lastStarport']['commodities']:
        bycategory[commodity['categoryname']].append(commodity)

    for category in sorted(bycategory):
        h.write('   + {}\n'.format(category).encode('utf-8'))
        # corrections to commodity names can change the sort order
        for commodity in sorted(bycategory[category], key=itemgetter('name')):
            #h.write('      %-23s %7d %7d %9s%c %8s%c  %s\n'.format(
            h.write('      {:<23} {:7d} {:7d} {:9}{:1} {:8}{:1}  {}\n'.format(
                commodity['name'],
                int(commodity['sellPrice']),
                int(commodity['buyPrice']),
                int(commodity['demand']) if commodity['demandBracket'] else '',
                demandbracketmap[commodity['demandBracket']],
                int(commodity['stock']) if commodity['stockBracket'] else '',
                stockbracketmap[commodity['stockBracket']],
                timestamp).encode('utf-8'))

    h.close()
