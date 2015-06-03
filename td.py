# Export to Trade Dangerous

from os.path import join
from collections import defaultdict
import codecs
from platform import system
from sys import platform
import time

from config import applongname, appversion, config
from companion import categorymap, commoditymap, bracketmap


def export(data):

    querytime = config.read('querytime') or int(time.time())

    filename = join(config.read('outdir'), '%s.%s.%s.prices' % (data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip(), time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime(querytime))))

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(querytime))

    # Format described here: https://bitbucket.org/kfsone/tradedangerous/wiki/Price%20Data
    h = open(filename, 'wt')	# codecs can't automatically handle line endings, so encode manually where required
    h.write(('#! trade.py import -\n# Created by %s %s on %s for Cmdr %s.\n#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n@ %s/%s\n' % (applongname, appversion, platform=='darwin' and "Mac OS" or system(), data['commander']['name'].strip(), data['lastSystem']['name'].strip(), data['lastStarport']['name'].strip())).encode('utf-8'))

    # sort commodities by category
    bycategory = defaultdict(list)
    for commodity in data['lastStarport']['commodities']:
        if commodity.get('categoryname') and commodity.get('categoryname') != 'NonMarketable':
            bycategory[categorymap.get(commodity['categoryname'], commodity['categoryname'])].append(commodity)

    for category in sorted(bycategory):
        h.write('   + %s\n' % category)
        # corrections to commodity names can change the sort order
        for commodity in sorted(bycategory[category], key=lambda x:commoditymap.get(x['name'].strip(),x['name'])):
            h.write('      %-23s %7d %7d %9s%c %8s%c  %s\n' % (
                commoditymap.get(commodity['name'].strip(), commodity['name'].strip()),
                commodity.get('sellPrice', 0),
                commodity.get('buyPrice', 0),
                int(commodity.get('demand')) if commodity.get('demandBracket') else '',
                bracketmap.get(commodity.get('demandBracket'), '?')[0],
                int(commodity.get('stock')) if commodity.get('stockBracket') else '',
                bracketmap.get(commodity.get('stockBracket'), '-')[0],
                timestamp))

    h.close()
