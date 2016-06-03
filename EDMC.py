#!/usr/bin/python
#
# Command-line interface. Requires prior setup through the GUI.
#

import argparse
import requests
import sys
from time import time, sleep
from xml.etree import ElementTree

import l10n
l10n.Translations().install_dummy()

import companion
import commodity
from commodity import COMMODITY_DEFAULT
import outfitting
import loadout
import coriolis
import shipyard
import eddb
import stats
import prefs
from config import appcmdname, appversion, update_feed, config


EDDB = eddb.EDDB()

SERVER_RETRY = 5	# retry pause for Companion servers [s]
EXIT_SUCCESS, EXIT_SERVER, EXIT_CREDENTIALS, EXIT_VERIFICATION, EXIT_NOT_DOCKED, EXIT_SYS_ERR = range(6)

# quick and dirty version comparison assuming "strict" numeric only version numbers
def versioncmp(versionstring):
    return map(int, versionstring.split('.'))


try:
    # arg parsing
    parser = argparse.ArgumentParser(prog=appcmdname, description='Prints the current system and station (if docked) to stdout and optionally writes player status, ship locations, ship loadout and/or station data to file. Requires prior setup through the accompanying GUI app.')
    parser.add_argument('-v', '--version', help='print program version and exit', action='store_const', const=True)
    parser.add_argument('-c', metavar='FILE', help='write ship loadout to FILE in Coriolis json format')
    parser.add_argument('-e', metavar='FILE', help='write ship loadout to FILE in E:D Shipyard format')
    parser.add_argument('-l', metavar='FILE', help='write ship locations to FILE in CSV format')
    parser.add_argument('-m', metavar='FILE', help='write station commodity market data to FILE in CSV format')
    parser.add_argument('-o', metavar='FILE', help='write station outfitting data to FILE in CSV format')
    parser.add_argument('-s', metavar='FILE', help='write station shipyard data to FILE in CSV format')
    parser.add_argument('-t', metavar='FILE', help='write player status to FILE in CSV format')
    args = parser.parse_args()

    if args.version:
        latest = ''
        try:
            # Copied from update.py - probably should refactor
            r = requests.get(update_feed, timeout = 10)
            feed = ElementTree.fromstring(r.text)
            items = dict([(item.find('enclosure').attrib.get('{http://www.andymatuschak.org/xml-namespaces/sparkle}version'),
                           item.find('title').text) for item in feed.findall('channel/item')])
            lastversion = sorted(items, key=versioncmp)[-1]
            if versioncmp(lastversion) > versioncmp(appversion):

                latest = ' (%s is available)' % items[lastversion]
        except:
            pass	# Quietly suppress timeouts etc.
        print '%.2f%s' % (float(''.join(appversion.split('.')[:3])) / 100, latest)	# just first three digits
        sys.exit(EXIT_SUCCESS)

    session = companion.Session()
    session.login(config.get('username'), config.get('password'))

    querytime = int(time())
    data = session.query()
    config.set('querytime', querytime)

    # Validation
    if not data.get('commander') or not data['commander'].get('name','').strip():
        sys.stderr.write('Who are you?!\n')
        sys.exit(EXIT_SERVER)
    elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
        sys.stderr.write('Where are you?!\n')		# Shouldn't happen
        sys.exit(EXIT_SERVER)
    elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
        sys.stderr.write('What are you flying?!\n')	# Shouldn't happen
        sys.exit(EXIT_SERVER)

    # stuff we can do when not docked
    if args.c:
        coriolis.export(data, args.c)
    if args.e:
        loadout.export(data, args.e)
    if args.l:
        stats.export_ships(data, args.l)
    if args.t:
        stats.export_status(data, args.t)

    if not data['commander'].get('docked'):
        print data['lastSystem']['name']
        if (args.m or args.o or args.s):
            sys.stderr.write("You're not docked at a station!\n")
            sys.exit(EXIT_NOT_DOCKED)
        else:
            sys.exit(EXIT_SUCCESS)

    # Finally - the data looks sane and we're docked at a station
    print '%s,%s' % (data['lastSystem']['name'], data['lastStarport']['name'])
    (station_id, has_market, has_outfitting, has_shipyard) = EDDB.station(data['lastSystem']['name'], data['lastStarport']['name'])

    if station_id and not (has_market or has_outfitting or has_shipyard):
        sys.stderr.write("Station doesn't have anything!\n")
        sys.exit(EXIT_SUCCESS)
    elif not station_id and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):	# Ignore usually spurious shipyard at unknown stations
        sys.stderr.write("Station doesn't have anything!\n")
        sys.exit(EXIT_SUCCESS)

    if args.m:
        if data['lastStarport'].get('commodities'):
            # Fixup anomalies in the commodity data
            session.fixup(data['lastStarport']['commodities'])
            commodity.export(data, COMMODITY_DEFAULT, args.m)
        elif has_market:
            sys.stderr.write("Error: Can't get market data!\n")
        else:
            sys.stderr.write("Station doesn't have a market\n")

    if args.o:
        if has_outfitting or not station_id:
            outfitting.export(data, args.o)
        else:
            sys.stderr.write("Station doesn't supply outfitting\n")

    if args.s:
        if has_shipyard:
            if not data['lastStarport'].get('ships'):
                sleep(SERVER_RETRY)
                data = session.query()
            if data['lastStarport'].get('ships') and data['commander'].get('docked'):
                shipyard.export(data, args.s)
            else:
                sys.stderr.write("Couldn't retrieve shipyard info\n")
        else:
            sys.stderr.write("Station doesn't have a shipyard\n")

    sys.exit(EXIT_SUCCESS)

except companion.ServerError as e:
    sys.stderr.write('Server is down\n')
    sys.exit(EXIT_SERVER_DOWN)
except companion.CredentialsError as e:
    sys.stderr.write('Invalid Credentials\n')
    sys.exit(EXIT_CREDENTIALS)
except companion.VerificationRequired:
    sys.stderr.write('Verification Required\n')
    sys.exit(EXIT_VERIFICATION)
