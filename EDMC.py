#!/usr/bin/env python
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
l10n.Translations.install_dummy()

import collate
import companion
import commodity
from commodity import COMMODITY_DEFAULT
import outfitting
import loadout
import edshipyard
import shipyard
import stats
from config import appcmdname, appversion, update_feed, config
from monitor import monitor

sys.path.append(config.internal_plugin_dir)
import eddn


SERVER_RETRY = 5	# retry pause for Companion servers [s]
EXIT_SUCCESS, EXIT_SERVER, EXIT_CREDENTIALS, EXIT_VERIFICATION, EXIT_LAGGING, EXIT_SYS_ERR = range(6)

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

    if getattr(sys, 'frozen', False):
        os.environ['REQUESTS_CA_BUNDLE'] = join(config.respath, 'cacert.pem')

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
        print('%.2f%s' % (float(''.join(appversion.split('.')[:3])) / 100, latest))	# just first three digits
        sys.exit(EXIT_SUCCESS)

    if args.j:
        # Import and collate from JSON dump
        data = json.load(open(args.j))
        config.set('querytime', int(getmtime(args.j)))
    else:
        # Get state from latest Journal file
        try:
            logdir = config.get('journaldir') or config.default_journal_dir
            logfiles = sorted([x for x in os.listdir(logdir) if x.startswith('Journal') and x.endswith('.log')],
                              key=lambda x: x.split('.')[1:])
            logfile = join(logdir, logfiles[-1])
            with open(logfile, 'r') as loghandle:
                for line in loghandle:
                    try:
                        monitor.parse_entry(line)
                    except:
                        if __debug__:
                            print('Invalid journal entry "%s"' % repr(line))
        except Exception as e:
            sys.stderr.write("Can't read Journal file: %s\n" % str(e).encode('ascii', 'replace'))
            sys.exit(EXIT_SYS_ERR)

        if not monitor.cmdr:
            sys.stderr.write('Not available while E:D is at the main menu\n')
            sys.exit(EXIT_SYS_ERR)

        # Get data from Companion API
        if args.p:
            cmdrs = config.get('cmdrs') or []
            if args.p in cmdrs:
                idx = cmdrs.index(args.p)
            else:
                for idx, cmdr in enumerate(cmdrs):
                    if cmdr.lower() == args.p.lower():
                        break
                else:
                    raise companion.CredentialsError()
            companion.session.login(cmdrs[idx], monitor.is_beta)
        else:
            cmdrs = config.get('cmdrs') or []
            if monitor.cmdr not in cmdrs:
                raise companion.CredentialsError()
            companion.session.login(monitor.cmdr, monitor.is_beta)
        querytime = int(time())
        data = companion.session.station()
        config.set('querytime', querytime)

    # Validation
    if not data.get('commander') or not data['commander'].get('name','').strip():
        sys.stderr.write('Who are you?!\n')
        sys.exit(EXIT_SERVER)
    elif (not data.get('lastSystem', {}).get('name') or
          (data['commander'].get('docked') and not data.get('lastStarport', {}).get('name'))):	# Only care if docked
        sys.stderr.write('Where are you?!\n')		# Shouldn't happen
        sys.exit(EXIT_SERVER)
    elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
        sys.stderr.write('What are you flying?!\n')	# Shouldn't happen
        sys.exit(EXIT_SERVER)
    elif args.j:
        pass	# Skip further validation
    elif data['commander']['name'] != monitor.cmdr:
        sys.stderr.write('Wrong Cmdr\n')				# Companion API return doesn't match Journal
        sys.exit(EXIT_CREDENTIALS)
    elif ((data['lastSystem']['name'] != monitor.system) or
          ((data['commander']['docked'] and data['lastStarport']['name'] or None) != monitor.station) or
          (data['ship']['id'] != monitor.state['ShipID']) or
          (data['ship']['name'].lower() != monitor.state['ShipType'])):
        sys.stderr.write('Frontier server is lagging\n')
        sys.exit(EXIT_LAGGING)

    # stuff we can do when not docked
    if args.d:
        with open(args.d, 'wb') as h:
            h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))
    if args.a:
        loadout.export(data, args.a)
    if args.e:
        edshipyard.export(data, args.e)
    if args.l:
        stats.export_ships(data, args.l)
    if args.t:
        stats.export_status(data, args.t)

    if data['commander'].get('docked'):
        print('%s,%s' % (data.get('lastSystem', {}).get('name', 'Unknown'), data.get('lastStarport', {}).get('name', 'Unknown')))
    else:
        print(data.get('lastSystem', {}).get('name', 'Unknown'))

    if (args.m or args.o or args.s or args.n or args.j):
        if not data['commander'].get('docked'):
            sys.stderr.write("You're not docked at a station!\n")
            sys.exit(EXIT_SUCCESS)
        elif not data.get('lastStarport', {}).get('name'):
            sys.stderr.write("Unknown station!\n")
            sys.exit(EXIT_LAGGING)
        elif not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):	# Ignore possibly missing shipyard info
            sys.stderr.write("Station doesn't have anything!\n")
            sys.exit(EXIT_SUCCESS)
    else:
        sys.exit(EXIT_SUCCESS)

    # Finally - the data looks sane and we're docked at a station

    if args.j:
        # Collate from JSON dump
        collate.addcommodities(data)
        collate.addmodules(data)
        collate.addships(data)

    if args.m:
        if data['lastStarport'].get('commodities'):
            # Fixup anomalies in the commodity data
            fixed = companion.fixup(data)
            commodity.export(fixed, COMMODITY_DEFAULT, args.m)
        else:
            sys.stderr.write("Station doesn't have a market\n")

    if args.o:
        if data['lastStarport'].get('modules'):
            outfitting.export(data, args.o)
        else:
            sys.stderr.write("Station doesn't supply outfitting\n")

    if (args.s or args.n) and not args.j and not data['lastStarport'].get('ships') and data['lastStarport']['services'].get('shipyard'):
        # Retry for shipyard
        sleep(SERVER_RETRY)
        data2 = companion.session.station()
        if (data2['commander'].get('docked') and	# might have undocked while we were waiting for retry in which case station data is unreliable
            data2.get('lastSystem',   {}).get('name') == monitor.system and
            data2.get('lastStarport', {}).get('name') == monitor.station):
            data = data2

    if args.s:
        if data['lastStarport'].get('ships', {}).get('shipyard_list'):
            shipyard.export(data, args.s)
        elif not args.j and monitor.stationservices and 'Shipyard' in monitor.stationservices:
            sys.stderr.write("Failed to get shipyard data\n")
        else:
            sys.stderr.write("Station doesn't have a shipyard\n")

    if args.n:
        try:
            eddn_sender = eddn.EDDN(None)
            eddn_sender.export_commodities(data, monitor.is_beta)
            eddn_sender.export_outfitting(data, monitor.is_beta)
            eddn_sender.export_shipyard(data, monitor.is_beta)
        except Exception as e:
            sys.stderr.write("Failed to send data to EDDN: %s\n" % unicode(e).encode('ascii', 'replace'))

    sys.exit(EXIT_SUCCESS)

except companion.ServerError as e:
    sys.stderr.write('Server is down\n')
    sys.exit(EXIT_SERVER)
except companion.SKUError as e:
    sys.stderr.write('Server SKU problem\n')
    sys.exit(EXIT_SERVER)
except companion.CredentialsError as e:
    sys.stderr.write('Invalid Credentials\n')
    sys.exit(EXIT_CREDENTIALS)
