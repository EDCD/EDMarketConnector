#!/usr/bin/env python3
"""
EDMC.py - Command-line interface. Requires prior setup through the GUI.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import warnings
from enum import IntEnum
from pathlib import Path
from time import sleep
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from common_utils import log_locale, SERVER_RETRY
from contextlib import suppress

# isort: off
os.environ["EDMC_NO_UI"] = "1"

# See EDMCLogging.py docs.
# workaround for https://github.com/EDCD/EDMarketConnector/issues/568
from EDMCLogging import edmclogger, logger, logging

if TYPE_CHECKING:
    from logging import TRACE  # type: ignore # noqa: F401 # needed to make mypy happy

edmclogger.set_channels_loglevel(logging.INFO)

# isort: on
import collate
import commodity
import companion
import edshipyard
from l10n import translations as tr
import loadout
import outfitting
import shipyard
import stats
from config import appcmdname, appversion, config
from monitor import monitor
from update import EDMCVersion, Updater, check_for_fdev_updates, check_for_datafile_updates

sys.path.append(config.internal_plugin_dir)
# This import must be after the sys.path.append.
# The sys.path.append has to be after `import sys` and `from config import config`
# isort: off
import eddn  # noqa: E402


# isort: on
tr.install_dummy()


class ExitCode(IntEnum):
    """List the various available exit codes."""

    SUCCESS = 0
    SERVER = 1
    CREDENTIALS = 2
    VERIFICATION = 3
    LAGGING = 4
    SYS_ERR = 5
    ARGS = 6
    JOURNAL_READ_ERR = 7
    COMMANDER_UNKNOWN = 8


# Backwards Compatibility
EXIT_SUCCESS = ExitCode.SUCCESS
EXIT_SERVER = ExitCode.SERVER
EXIT_CREDENTIALS = ExitCode.CREDENTIALS
EXIT_VERIFICATION = ExitCode.VERIFICATION
EXIT_LAGGING = ExitCode.LAGGING
EXIT_SYS_ERR = ExitCode.SYS_ERR
EXIT_ARGS = ExitCode.ARGS
EXIT_JOURNAL_READ_ERR = ExitCode.JOURNAL_READ_ERR
EXIT_COMMANDER_UNKNOWN = ExitCode.COMMANDER_UNKNOWN


def deep_get(target: companion.CAPIData, *args: str, default=None) -> Any:
    """
    Walk into a dict and return the specified deep value.

    Deprecated! Will be removed in 6.4 or later.
    Use structural pattern matching or explicit dict `.get()` chains instead.
    """
    warnings.warn(
        "deep_get is deprecated and will be removed in a future version. "
        "Use modern pattern matching (match/case) or sequential dict.get() chains instead.",
        category=DeprecationWarning,
        stacklevel=2
    )

    if not hasattr(target, 'get'):
        raise ValueError(f"Cannot call get on {target} ({type(target)})")

    current = target
    for arg in args:
        match current:
            case dict() | companion.CAPIData():
                if (res := current.get(arg)) is None:
                    return default
                current = res
            case _:
                return default

    return current


def parse_cli_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        prog=appcmdname,
        description='Prints the current system and station (if docked) to stdout and optionally writes player '
                    'status, ship locations, ship loadout and/or station data to file. '
                    'Requires prior setup through the accompanying GUI app.'
    )

    parser.add_argument('-v', '--version', help='print program version and exit', action='store_const', const=True)
    group_loglevel = parser.add_mutually_exclusive_group()
    group_loglevel.add_argument(
        '--loglevel', metavar='loglevel',
        help='Set the logging loglevel to one of: CRITICAL, ERROR, WARNING, INFO, DEBUG, TRACE'
    )
    parser.add_argument('--trace', help='Set the Debug logging loglevel to TRACE', action='store_true')
    parser.add_argument('--trace-on', action='append',
                        help='Mark the selected trace logging as active. "*" or "all" is equivalent to --trace-all')
    parser.add_argument("--trace-all", action='store_true',
                        help='Force trace level logging, with all possible --trace-on values active.')
    parser.add_argument("--trace-help", action='store_true',
                        help="Open the documentation to view all possible trace-on values")
    parser.add_argument('--refresh-all', action='store_true',
                        help='Iterate over all known CMDRs to try and refresh access tokens')
    parser.add_argument('--config', help="Define a custom config to load EDMC from")

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

    return parser.parse_args()


def handle_version_check() -> None:
    """Check for appcast updates and print version strings."""
    updater = Updater()
    newversion: EDMCVersion | None = updater.check_appcast()
    if newversion:
        # LANG: Update Available Text
        newverstr: str = tr.tl("{NEWVER} is available").format(NEWVER=newversion.title)
        print(f'{appversion()} ({newverstr})')
    else:
        print(appversion())


def _determine_log_level(args: argparse.Namespace) -> int | str | None:
    """Evaluate the correct log level with clean early-exit precedence."""
    if args.trace_all or (args.trace_on and any(x in args.trace_on for x in ('*', 'all'))):
        logger.info('Setting TRACE_ALL level debugging due to --trace-all or wildcard flag')
        return logging.TRACE_ALL  # type: ignore

    if args.trace or args.trace_on:
        logger.info('Setting TRACE level debugging due to --trace or --trace-on')
        return logging.TRACE  # type: ignore

    return args.loglevel


def configure_logging_and_env(args: argparse.Namespace) -> None:
    """Configure logger log levels, trace environments, and initial config payloads."""
    if level := _determine_log_level(args):
        if isinstance(level, int):
            logger.setLevel(level)
            edmclogger.set_channels_loglevel(level)
        else:
            edmclogger.set_channels_loglevel(level)

    # Environment Configuration updates
    if args.config:
        config.reload_from_path(args.config)

    logger.debug(f'Startup v{appversion()} : Running on Python v{sys.version}')
    logger.debug(
        f'Platform: {sys.platform}\n'
        f'argv[0]: {sys.argv[0]}\n'
        f'exec_prefix: {sys.exec_prefix}\n'
        f'executable: {sys.executable}\n'
        f'sys.path: {sys.path}'
    )

    if args.trace_on:
        import config as conf_module
        conf_module.trace_on = [x.casefold() for x in args.trace_on]
        for trace_item in conf_module.trace_on:
            logger.info(f'marked {trace_item} for TRACE')

    log_locale('Initial Locale')

    if args.trace_help:
        import webbrowser
        logger.info("Opening Trace Help Documentation")
        webbrowser.open("https://github.com/EDCD/EDMarketConnector/blob/main/docs/Available%20Traces.md")


def refresh_all_cmdrs() -> None:
    """Attempt to iterate and refresh access tokens for all known commanders."""
    logger.debug("Refreshing all known CMDRs")
    cmdrs = config.get_list('cmdrs', default=[])
    for cmdr in cmdrs:
        logger.debug(f'Attempting to use commander "{cmdr}"')
        try:
            companion.session.login(cmdr, monitor.is_beta)
            logger.debug("Succeeded!")
        except AttributeError:
            logger.debug(f"Unable to refresh CMDR {cmdr}.")


def load_json_dump(json_file_path: str) -> companion.CAPIData:
    """Load and return CAPI data from a local JSON dump file."""
    logger.debug('Import and collate from JSON dump')
    json_file = str(Path(json_file_path).resolve())
    data = None

    with suppress(UnicodeDecodeError), open(json_file, encoding='utf-8') as file_handle:
        data = json.load(file_handle)

    if data is None:
        with open(json_file, encoding='utf-8') as file_handle:
            data = json.load(file_handle)

    config.set('querytime', int(Path(json_file_path).stat().st_mtime))
    return data


def load_state_from_journal_and_capi(args: argparse.Namespace) -> companion.CAPIData:
    """Read the latest Journal state and fetch live CAPI data."""
    logger.debug('Getting state from latest journal file')
    try:
        monitor.currentdir = config.get_str('journaldir',
                                            default=config.default_journal_dir) or config.default_journal_dir
        logger.debug(f'logdir = "{monitor.currentdir}"')

        if (logfile := monitor.journal_newest_filename(monitor.currentdir)) is None:
            raise ValueError("None from monitor.journal_newest_filename")

        logger.debug(f'Using logfile "{logfile}"')
        with open(logfile, 'rb', 0) as loghandle:
            for line in loghandle:
                with suppress(Exception):
                    monitor.parse_entry(line)
                    continue
                logger.debug(f'Invalid journal entry {line!r}')

    except Exception:
        logger.exception("Can't read Journal file")
        sys.exit(ExitCode.JOURNAL_READ_ERR)

    if not monitor.cmdr:
        logger.error('Not available while E:D is at the main menu')
        sys.exit(ExitCode.COMMANDER_UNKNOWN)

    cmdrs = config.get_list('cmdrs', default=[])
    target_cmdr = args.p or monitor.cmdr
    logger.debug(f'Attempting to use commander "{target_cmdr}"' + (' from Journal File' if not args.p else ''))

    try:
        cmdr_to_use = next(c for c in cmdrs if c.lower() == target_cmdr.lower())
    except StopIteration:
        raise companion.CredentialsError() from StopIteration

    try:
        companion.session.login(cmdr_to_use, monitor.is_beta)
    except AttributeError:
        raise companion.CredentialsError() from AttributeError

    # Initiate CAPI queries
    querytime = int(datetime.now(timezone.utc).timestamp())
    companion.session.station(query_time=querytime)

    # Wait for the response
    _capi_request_timeout = 60
    try:
        capi_response = companion.session.capi_response_queue.get(block=True, timeout=_capi_request_timeout)
    except queue.Empty:
        logger.error(f'CAPI requests timed out after {_capi_request_timeout} seconds')
        sys.exit(ExitCode.SERVER)

    match capi_response:
        case companion.EDMCCAPIFailedRequest(message=msg, exception=exc):
            logger.trace_if('capi.worker', f'Failed Request: {msg}')
            if exc:
                raise exc
            raise ValueError(msg)

        case companion.EDMCCAPIResponse(capi_data=capi_data):
            logger.trace_if('capi.worker', 'Answer is not a Failure')
            config.set('querytime', querytime)
            return capi_data

        case _:
            raise ValueError(f"Response was neither CAPIFailedRequest nor EDMCAPIResponse: {type(capi_response)}")


def validate_capi_data(data: companion.CAPIData, is_json_import: bool) -> None:
    """Validate structural integrity and data lagging utilizing pattern matching."""
    # Check Commander Name
    match data:
        case {"commander": {"name": str(name)}} if name.strip():
            pass
        case _:
            logger.error("No data['commander']['name'] from CAPI")
            sys.exit(ExitCode.SERVER)

    # Check System
    match data:
        case {"lastSystem": {"name": str(sys_name)}} if sys_name.strip():
            pass
        case _:
            logger.error("No data['lastSystem']['name'] from CAPI")
            sys.exit(ExitCode.SERVER)

    # Check Docking & Starport
    match data:
        case {"commander": {"docked": True}}:
            match data:
                case {"lastStarport": {"name": str(port_name)}} if port_name.strip():
                    pass
                case _:
                    logger.error("No data['lastStarport']['name'] from CAPI (Required when docked)")
                    sys.exit(ExitCode.SERVER)
        case _:
            pass

    # Check Ship Loadout Structure
    match data:
        case {"ship": {"modules": dict() | list(), "name": str(ship_name)}} if ship_name.strip():
            pass
        case _:
            logger.error("No data['ship']['modules'] or data['ship']['name'] from CAPI")
            sys.exit(ExitCode.SERVER)

    # If importing a JSON dump, bypass lagging/journal validations
    if is_json_import:
        return

    # Match Commander exactly to Journal
    if data["commander"]["name"] != monitor.cmdr:
        raise companion.CmdrError()

    # Determine if server is lagging behind the journal
    is_docked = data["commander"].get("docked", False)
    capi_station = data.get("lastStarport", {}).get("name") if is_docked else None

    if (
            data["lastSystem"]["name"] != monitor.state['SystemName']
            or capi_station != monitor.state['StationName']
            or data["ship"]["id"] != monitor.state['ShipID']
            or data["ship"]["name"].lower() != monitor.state['ShipType']
    ):
        raise companion.ServerLagging()


def export_standard_data(data: companion.CAPIData, args: argparse.Namespace) -> None:
    """Handle all standard, non-docked specific file export operations."""
    if args.d:
        logger.debug(f'Writing raw JSON data to "{args.d}"')
        out = json.dumps(dict(data), ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': '))
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

    # Console stdout behavior based on docked state
    match data:
        case {"commander": {"docked": True}, "lastSystem": {"name": sys_name}, "lastStarport": {"name": port_name}}:
            print(f'{sys_name},{port_name}')
        case {"lastSystem": {"name": sys_name}}:
            print(f'{sys_name}')
        case _:
            print('Unknown')


def export_docked_data(data: companion.CAPIData, args: argparse.Namespace) -> None:  # noqa: C901, CCR001
    """Process market, outfitting, shipyard and EDDN exports requiring a docked state."""
    # Ensure they've requested one of the docked flags
    if not (args.m or args.o or args.s or args.n or args.j):
        return

    match data:
        case {"commander": {"docked": True}, "lastStarport": {"name": port_name}} if port_name.strip():
            pass  # Valid Docking Base
        case {"commander": {"docked": False}}:
            logger.error("Can't use -m, -o, -s, -n or -j because you're not currently docked!")
            return
        case _:
            logger.error("No data['lastStarport']['name'] from CAPI")
            sys.exit(ExitCode.LAGGING)

    # Ensure commodity or outfitting data is present in the CAPI payload
    has_commodities = bool(data["lastStarport"].get("commodities"))
    has_modules = bool(data["lastStarport"].get("modules"))
    if not (has_commodities or has_modules):
        logger.error("No commodities or outfitting (modules) in CAPI data")
        return

    if args.j:
        logger.debug('Importing data from the CAPI return...')
        collate.addcommodities(data)
        collate.addmodules(data)
        collate.addships(data)

    if args.m:
        logger.debug(f'Writing Station Commodity Market Data in CSV format to "{args.m}"')
        if has_commodities:
            fixed = companion.fixup(data)
            mkt_type = config.get_str('mkt_export_type', default='CSV')
            try:
                kind = commodity.CommodityExportKind[mkt_type]
            except KeyError:
                kind = commodity.CommodityExportKind.SEMICOLON
            commodity.export(fixed, kind, args.m)
        else:
            logger.error("Station doesn't have a market")

    if args.o:
        if has_modules:
            logger.debug(f'Writing Station Outfitting in CSV format to "{args.o}"')
            outfitting.export(data, args.o)  # type: ignore
        else:
            logger.error("Station doesn't supply outfitting")

    # Retry logic for Shipyard if missing but reported as a station service
    has_ships = bool(data["lastStarport"].get("ships"))
    has_shipyard_service = bool(data["lastStarport"].get("services", {}).get("shipyard"))

    if (args.s or args.n) and not args.j and not has_ships and has_shipyard_service:
        sleep(SERVER_RETRY)
        companion.session.station(int(datetime.now(timezone.utc).timestamp()))

        try:
            capi_response = companion.session.capi_response_queue.get(block=True, timeout=60)
        except queue.Empty:
            logger.error('CAPI requests timed out after 60 seconds (Shipyard Retry)')
            sys.exit(ExitCode.SERVER)

        if isinstance(capi_response, companion.EDMCCAPIFailedRequest):
            logger.error(f'Failed Request: {capi_response.message}')
            sys.exit(ExitCode.SERVER)

        new_data = capi_response.capi_data

        # Verify the player didn't undock or jump during the sleep cycle
        match new_data:
            case {
                "commander": {"docked": True},
                "lastSystem": {"name": sys_name},
                "lastStarport": {"name": port_name}
            } if sys_name == monitor.state['SystemName'] and port_name == monitor.state['StationName']:
                data = new_data

    if args.s:
        match data:
            case {"lastStarport": {"ships": {"shipyard_list": shipyard_list}}} if shipyard_list:
                logger.debug(f'Writing Station Shipyard in CSV format to "{args.s}"')
                shipyard.export(data, args.s)
            case _:
                if not args.j and monitor.stationservices and 'Shipyard' in monitor.stationservices:
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


def main() -> None:
    """Run the main code of the program."""
    try:
        args = parse_cli_args()

        if args.version:
            handle_version_check()
            return

        configure_logging_and_env(args)

        if args.trace_help:
            return  # Help browser launched, terminate sequence

        if args.refresh_all:
            refresh_all_cmdrs()

        if args.j:
            data = load_json_dump(args.j)
        else:
            data = load_state_from_journal_and_capi(args)

        validate_capi_data(data, is_json_import=bool(args.j))
        export_standard_data(data, args)
        export_docked_data(data, args)

    except companion.ServerConnectionError:
        logger.exception('Exception while contacting server')
        sys.exit(ExitCode.SERVER)

    except companion.ServerError:
        logger.exception('Frontier CAPI Server returned an error')
        sys.exit(ExitCode.SERVER)

    except companion.CredentialsError:
        logger.error('Frontier CAPI Server: Invalid Credentials')
        sys.exit(ExitCode.CREDENTIALS)

    except companion.ServerLagging:
        logger.error(
            'Mismatch(es) between CAPI and Journal for at least one of: '
            'StarSystem, Last Star Port, Ship ID or Ship Name/Type'
        )
        sys.exit(ExitCode.SERVER)

    except companion.CmdrError:
        logger.error(
            f'Commander "{data["commander"]["name"]}" from CAPI doesn\'t match '
            f'"{monitor.cmdr}" from Journal'
        )
        sys.exit(ExitCode.SERVER)

    except Exception:
        logger.exception('"other" exception')
        sys.exit(ExitCode.SERVER)


if __name__ == '__main__':
    try:
        check_for_fdev_updates(silent=True)
        check_for_datafile_updates(silent=True)
        main()
    except KeyboardInterrupt:
        logger.info("Ctrl+C Detected, Attempting Clean Shutdown")
    logger.debug('Exiting')
    sys.exit(ExitCode.SUCCESS)
