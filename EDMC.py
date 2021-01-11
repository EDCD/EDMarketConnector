#!/usr/bin/env python3
"""Command-line interface. Requires prior setup through the GUI."""


import argparse
import json
import locale
import os
import re
import sys
from os.path import getmtime, join
from time import sleep, time
from typing import TYPE_CHECKING, Any, Optional

# isort: off

os.environ["EDMC_NO_UI"] = "1"

# See EDMCLogging.py docs.
# workaround for https://github.com/EDCD/EDMarketConnector/issues/568
from EDMCLogging import edmclogger, logger, logging

if TYPE_CHECKING:
    from logging import trace, TRACE  # type: ignore # noqa: F401

edmclogger.set_channels_loglevel(logging.INFO)

# isort: on

import collate
import commodity
import companion
import edshipyard
import l10n
import loadout
import outfitting
import shipyard
import stats
from commodity import COMMODITY_DEFAULT
from config import appcmdname, appversion, config
from monitor import monitor
from update import EDMCVersion, Updater

sys.path.append(config.internal_plugin_dir)
# This import must be after the sys.path.append.
# The sys.path.append has to be after `import sys` and `from config import config`
# isort: off
import eddn  # noqa: E402
# isort: on


def log_locale(prefix: str) -> None:
    """Log the current state of locale settings."""
    logger.debug(f'''Locale: {prefix}
Locale LC_COLLATE: {locale.getlocale(locale.LC_COLLATE)}
Locale LC_CTYPE: {locale.getlocale(locale.LC_CTYPE)}
Locale LC_MONETARY: {locale.getlocale(locale.LC_MONETARY)}
Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}
Locale LC_TIME: {locale.getlocale(locale.LC_TIME)}'''
                 )


l10n.Translations.install_dummy()

SERVER_RETRY = 5  # retry pause for Companion servers [s]
EXIT_SUCCESS, EXIT_SERVER, EXIT_CREDENTIALS, EXIT_VERIFICATION, EXIT_LAGGING, EXIT_SYS_ERR, EXIT_ARGS = range(7)

JOURNAL_RE = re.compile(r'^Journal(Beta)?\.[0-9]{12}\.[0-9]{2}\.log$')


def versioncmp(versionstring):
    """Quick and dirty version comparison assuming "strict" numeric only version numbers."""
    return list(map(int, versionstring.split('.')))


def deep_get(target: dict, *args: str, default=None) -> Any:
    """
    Walk into a dict and return the specified deep value.

    Example usage:

        >>> thing = {'a': {'b': {'c': 'foo'} } }
        >>> deep_get(thing, ('a', 'b', 'c'), None)
        'foo'
        >>> deep_get(thing, ('a', 'b'), None)
        {'c': 'foo'}
        >>> deep_get(thing, ('a', 'd'), None)
        None

    :param target: The dict to walk into for the desired value.
    :param args: The list of keys to walk down through.
    :param default: What to return if the target has no value.
    :return: The value at the target deep key.
    """
    if not hasattr(target, 'get'):
        raise ValueError(f"Cannot call get on {target} ({type(target)})")

    current = target
    for arg in args:
        res = current.get(arg)
        if res is None:
            return default

        current = res

    return current


def main():
    """Run the main code of the program."""
    try:
        # arg parsing
        parser = argparse.ArgumentParser(
            prog=appcmdname,
            description='Prints the current system and station (if docked) to stdout and optionally writes player '
                        'status, ship locations, ship loadout and/or station data to file. '
                        'Requires prior setup through the accompanying GUI app.'
        )

        parser.add_argument('-v', '--version', help='print program version and exit', action='store_const', const=True)
        group_loglevel = parser.add_mutually_exclusive_group()
        group_loglevel.add_argument('--loglevel',
                                    metavar='loglevel',
                                    help='Set the logging loglevel to one of: '
                                         'CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE',
                                    )
        group_loglevel.add_argument('--trace',
                                    help='Set the Debug logging loglevel to TRACE',
                                    action='store_true',
                                    )
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
        parser.add_argument('-j', help=argparse.SUPPRESS)  # Import JSON dump
        args = parser.parse_args()

        if args.version:
            updater = Updater(provider='internal')
            newversion: Optional[EDMCVersion] = updater.check_appcast()
            if newversion:
                print(f'{appversion} ({newversion.title!r} is available)')
            else:
                print(appversion)

            return

        if args.trace:
            edmclogger.set_channels_loglevel(logging.TRACE)

        elif args.loglevel:
            if args.loglevel not in ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'TRACE'):
                print('loglevel must be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE', file=sys.stderr)
                sys.exit(EXIT_ARGS)
            edmclogger.set_channels_loglevel(args.loglevel)

        logger.debug(f'Startup v{appversion} : Running on Python v{sys.version}')
        logger.debug(f'''Platform: {sys.platform}
argv[0]: {sys.argv[0]}
exec_prefix: {sys.exec_prefix}
executable: {sys.executable}
sys.path: {sys.path}'''
                     )

        log_locale('Initial Locale')

        if args.j:
            logger.debug('Import and collate from JSON dump')
            # Import and collate from JSON dump
            #
            # Try twice, once with the system locale and once enforcing utf-8. If the file was made on the current
            # system, chances are its the current locale, and not utf-8. Otherwise if it was copied, its probably
            # utf8. Either way, try the system FIRST because reading something like cp1251 in UTF-8 results in garbage
            # but the reverse results in an exception.
            try:
                data = json.load(open(args.j))
            except UnicodeDecodeError:
                data = json.load(open(args.j, encoding='utf-8'))

            config.set('querytime', int(getmtime(args.j)))

        else:
            # Get state from latest Journal file
            logger.debug('Getting state from latest journal file')
            try:
                logdir = config.get_str('journaldir', default=config.default_journal_dir)
                if not logdir:
                    logdir = config.default_journal_dir

                logger.debug(f'logdir = "{logdir}"')
                logfiles = sorted((x for x in os.listdir(logdir) if JOURNAL_RE.search(x)),
                                  key=lambda x: x.split('.')[1:])

                logfile = join(logdir, logfiles[-1])

                logger.debug(f'Using logfile "{logfile}"')
                with open(logfile, 'r', encoding='utf-8') as loghandle:
                    for line in loghandle:
                        try:
                            monitor.parse_entry(line)
                        except Exception:
                            logger.debug(f'Invalid journal entry {line!r}')

            except Exception:
                logger.exception("Can't read Journal file")
                sys.exit(EXIT_SYS_ERR)

            if not monitor.cmdr:
                logger.error('Not available while E:D is at the main menu')
                sys.exit(EXIT_SYS_ERR)

            # Get data from Companion API
            if args.p:
                logger.debug(f'Attempting to use commander "{args.p}"')
                cmdrs = config.get_list('cmdrs', default=[])
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
                logger.debug(f'Attempting to use commander "{monitor.cmdr}" from Journal File')
                cmdrs = config.get_list('cmdrs', default=[])
                if monitor.cmdr not in cmdrs:
                    raise companion.CredentialsError()

                companion.session.login(monitor.cmdr, monitor.is_beta)

            querytime = int(time())
            data = companion.session.station()
            config.set('querytime', querytime)

        # Validation
        if not deep_get(data, 'commander', 'name', default='').strip():
            logger.error("No data['command']['name'] from CAPI")
            sys.exit(EXIT_SERVER)

        elif not deep_get(data, 'lastSystem', 'name') or \
                data['commander'].get('docked') and not \
                deep_get(data, 'lastStarport', 'name'):  # Only care if docked

            logger.error("No data['lastSystem']['name'] from CAPI")
            sys.exit(EXIT_SERVER)

        elif not deep_get(data, 'ship', 'modules') or not deep_get(data, 'ship', 'name', default=''):
            logger.error("No data['ship']['modules'] from CAPI")
            sys.exit(EXIT_SERVER)

        elif args.j:
            pass  # Skip further validation

        elif data['commander']['name'] != monitor.cmdr:
            logger.error(f'Commander "{data["commander"]["name"]}" from CAPI doesn\'t match "{monitor.cmdr}" from Journal')  # noqa: E501
            sys.exit(EXIT_CREDENTIALS)

        elif data['lastSystem']['name'] != monitor.system or \
                ((data['commander']['docked'] and data['lastStarport']['name'] or None) != monitor.station) or \
                data['ship']['id'] != monitor.state['ShipID'] or \
                data['ship']['name'].lower() != monitor.state['ShipType']:

            logger.error('Mismatch(es) between CAPI and Journal for at least one of: StarSystem, Last Star Port, Ship ID or Ship Name/Type')  # noqa: E501
            sys.exit(EXIT_LAGGING)

        # stuff we can do when not docked
        if args.d:
            logger.debug(f'Writing raw JSON data to "{args.d}"')
            out = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': '))
            with open(args.d, 'wb') as f:
                f.write(out.encode("utf-8"))

        if args.a:
            logger.debug(f'Writing Ship Loadout in Companion API JSON format to "{args.a}"')
            loadout.export(data, args.a)

        if args.e:
            logger.debug(f'Writing Ship Loadout in ED Shipyard plain text format to "{args.e}"')
            edshipyard.export(data, args.e)

        if args.l:
            logger.debug(f'Writing Ship Locations in CSV format to "{args.l}"')
            stats.export_ships(data, args.l)

        if args.t:
            logger.debug(f'Writing Player Status in CSV format to "{args.t}"')
            stats.export_status(data, args.t)

        if data['commander'].get('docked'):
            print(f'{deep_get(data, "lastSystem", "name", default="Unknown")},'
                  f'{deep_get(data, "lastStarport", "name", default="Unknown")}'
                  )

        else:
            print(deep_get(data, 'lastSystem', 'name', default='Unknown'))

        if (args.m or args.o or args.s or args.n or args.j):
            if not data['commander'].get('docked'):
                logger.error("Can't use -m, -o, -s, -n or -j because you're not currently docked!")
                return

            elif not deep_get(data, 'lastStarport', 'name'):
                logger.error("No data['lastStarport']['name'] from CAPI")
                sys.exit(EXIT_LAGGING)

            # Ignore possibly missing shipyard info
            elif not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):
                logger.error("No commodities or outfitting (modules) in CAPI data")
                return

        else:
            return

        # Finally - the data looks sane and we're docked at a station

        if args.j:
            logger.debug('Importing data from the CAPI return...')
            # Collate from JSON dump
            collate.addcommodities(data)
            collate.addmodules(data)
            collate.addships(data)

        if args.m:
            logger.debug(f'Writing Station Commodity Market Data in CSV format to "{args.m}"')
            if data['lastStarport'].get('commodities'):
                # Fixup anomalies in the commodity data
                fixed = companion.fixup(data)
                commodity.export(fixed, COMMODITY_DEFAULT, args.m)

            else:
                logger.error("Station doesn't have a market")

        if args.o:
            if data['lastStarport'].get('modules'):
                logger.debug(f'Writing Station Outfitting in CSV format to "{args.o}"')
                outfitting.export(data, args.o)

            else:
                logger.error("Station doesn't supply outfitting")

        if (args.s or args.n) and not args.j and not \
                data['lastStarport'].get('ships') and data['lastStarport']['services'].get('shipyard'):

            # Retry for shipyard
            sleep(SERVER_RETRY)
            new_data = companion.session.station()
            # might have undocked while we were waiting for retry in which case station data is unreliable
            if new_data['commander'].get('docked') and \
                    deep_get(new_data, 'lastSystem', 'name') == monitor.system and \
                    deep_get(new_data, 'lastStarport', 'name') == monitor.station:

                data = new_data

        if args.s:
            if deep_get(data, 'lastStarport', 'ships', 'shipyard_list'):
                logger.debug(f'Writing Station Shipyard in CSV format to "{args.s}"')
                shipyard.export(data, args.s)

            elif not args.j and monitor.stationservices and 'Shipyard' in monitor.stationservices:
                logger.error('Failed to get shipyard data')

            else:
                logger.error("Station doesn't have a shipyard")

        if args.n:
            try:
                eddn_sender = eddn.EDDN(None)
                logger.debug('Sending Market, Outfitting and Shipyard data to EDDN...')
                eddn_sender.export_commodities(data, monitor.is_beta)
                eddn_sender.export_outfitting(data, monitor.is_beta)
                eddn_sender.export_shipyard(data, monitor.is_beta)

            except Exception:
                logger.exception('Failed to send data to EDDN')

    except companion.ServerError:
        logger.error('Frontier CAPI Server returned an error')
        sys.exit(EXIT_SERVER)

    except companion.SKUError:
        logger.error('Frontier CAPI Server SKU problem')
        sys.exit(EXIT_SERVER)

    except companion.CredentialsError:
        logger.error('Frontier CAPI Server: Invalid Credentials')
        sys.exit(EXIT_CREDENTIALS)


if __name__ == '__main__':
    main()
    logger.debug('Exiting')
    sys.exit(EXIT_SUCCESS)
