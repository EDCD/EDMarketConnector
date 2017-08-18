#!/usr/bin/python2
#
# Command-line interface. Requires prior setup through the GUI.
#

import argparse
import json
import requests
import sys
import os
from os.path import dirname, getmtime, join
from time import time, sleep
from xml.etree import ElementTree

import l10n
l10n.Translations().install_dummy()

import collate
import companion
import commodity
from commodity import COMMODITY_DEFAULT
import outfitting
import loadout
import edshipyard
import shipyard
import eddn
import stats
import prefs
from config import appcmdname, appversion, update_feed, config


SERVER_RETRY = 5	# retry pause for Companion servers [s]
EXIT_SUCCESS, EXIT_SERVER, EXIT_CREDENTIALS, EXIT_VERIFICATION, EXIT_NOT_DOCKED, EXIT_SYS_ERR = range(6)

# quick and dirty version comparison assuming "strict" numeric only version numbers
def versioncmp(versionstring):
    return map(int, versionstring.split('.'))


try:
    # arg parsing
    parser = argparse.ArgumentParser(prog=appcmdname, description='Prints the current system and station (if docked) to stdout and optionally writes player status, ship locations, ship loadout and/or station data to file. Requires prior setup through the accompanying GUI app.')
    parser.add_argument('-v', '--version', help='print program version and exit', action='store_const', const=True)
    parser.add_argument('-a', metavar='FILE', help='write ship loadout to FILE in Companion API json format')
    parser.add_argument('-e', metavar='FILE', help='write ship loadout to FILE in E:D Shipyard plain text format')
    parser.add_argument('-l', metavar='FILE', help='write ship locations to FILE in CSV format')
    parser.add_argument('-m', metavar='FILE', help='write station commodity market data to FILE in CSV format')
    parser.add_argument('-o', metavar='FILE', help='write station outfitting data to FILE in CSV format')
    parser.add_argument('-s', metavar='FILE', help='write station shipyard data to FILE in CSV format')
    parser.add_argument('-t', metavar='FILE', help='write player status to FILE in CSV format')
    parser.add_argument('-d', metavar='FILE', help='write raw JSON data to FILE')
    parser.add_argument('-n', action='store_true', help='send data to EDDN')
    parser.add_argument('-p', metavar='CMDR', help='Returns data from the specified player account')
    parser.add_argument('-j', help=argparse.SUPPRESS)	# Import JSON dump
    args = parser.parse_args()

    if args.version:
        latest = ''
        try:
            if sys.platform=='win32' and getattr(sys, 'frozen', False):
                os.environ['REQUESTS_CA_BUNDLE'] = join(dirname(sys.executable), 'cacert.pem')
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

    if args.j:
        # Import and collate from JSON dump
        data = json.load(open(args.j))
        config.set('querytime', getmtime(args.j))
    else:
        session = companion.Session()
        if args.p:
            cmdrs = config.get('cmdrs') or []
            if args.p in cmdrs:
                idx = cmdrs.index(args.p)
            else:
                for idx, cmdr in enumerate(cmdrs):
                    if cmdr.lower() == args.p.lower():
                        break
                else:
                    raise companion.CredentialsError
            username = config.get('fdev_usernames')[idx]
            session.login(username, config.get_password(username))
        elif config.get('cmdrs'):
            username = config.get('fdev_usernames')[0]
            session.login(username, config.get_password(username))
        else:	# <= 2.25 not yet migrated
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
    if args.d:
        with open(args.d, 'wt') as h:
            h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))
    if args.a:
        loadout.export(data, args.a)
    if args.e:
        edshipyard.export(data, args.e)
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

    if (args.m or args.o or args.s) and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):	# Ignore possibly missing shipyard info
        sys.stderr.write("Station doesn't have anything!\n")
        sys.exit(EXIT_SUCCESS)

    # Fixup anomalies in the commodity data
    fixed = companion.fixup(data)

    if args.j:
        # Collate from JSON dump
        collate.addcommodities(fixed)
        collate.addmodules(fixed)
        collate.addships(fixed)

    if args.m:
        if data['lastStarport'].get('commodities'):
            commodity.export(fixed, COMMODITY_DEFAULT, args.m)
        else:
            sys.stderr.write("Station doesn't have a market\n")

    if args.o:
        if data['lastStarport'].get('modules'):
            outfitting.export(data, args.o)
        else:
            sys.stderr.write("Station doesn't supply outfitting\n")

    if args.s:
        if not data['lastStarport'].get('ships') and not args.j:
            sleep(SERVER_RETRY)
            data = session.query()
        if data['lastStarport'].get('ships'):
            shipyard.export(data, args.s)
        else:
            sys.stderr.write("Station doesn't have a shipyard\n")

    if args.n:
        try:
            eddn_sender = eddn.EDDN(None)
            eddn_sender.export_commodities(data, False)
            eddn_sender.export_outfitting(data, False)
            eddn_sender.export_shipyard(data, False)
        except Exception as e:
            sys.stderr.write("Failed to send data to EDDN: %s\n" % unicode(e).encode('ascii', 'replace'))

    sys.exit(EXIT_SUCCESS)

except companion.ServerError as e:
    sys.stderr.write('Server is down\n')
    sys.exit(EXIT_SERVER)
except companion.CredentialsError as e:
    sys.stderr.write('Invalid Credentials\n')
    sys.exit(EXIT_CREDENTIALS)
except companion.VerificationRequired:
    sys.stderr.write('Verification Required\n')
    sys.exit(EXIT_VERIFICATION)
