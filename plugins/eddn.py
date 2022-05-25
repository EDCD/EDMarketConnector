"""Handle exporting data to EDDN."""

# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
#
# This is an EDMC 'core' plugin.
#
# All EDMC plugins are *dynamically* loaded at run-time.
#
# We build for Windows using `py2exe`.
#
# `py2exe` can't possibly know about anything in the dynamically loaded
# core plugins.
#
# Thus you **MUST** check if any imports you add in this file are only
# referenced in this file (or only in any other core plugin), and if so...
#
#     YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN `setup.py`
#     SO AS TO ENSURE THE FILES ARE ACTUALLY PRESENT IN AN END-USER
#     INSTALLATION ON WINDOWS.
#
#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
import itertools
import json
import pathlib
import re
import sys
import tkinter as tk
from collections import OrderedDict
from os import SEEK_SET
from os.path import join
from platform import system
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, MutableMapping, Optional
from typing import OrderedDict as OrderedDictT
from typing import TextIO, Tuple, Union

import requests

import edmc_data
import killswitch
import myNotebook as nb  # noqa: N813
import plug
from companion import CAPIData, category_map
from config import applongname, appversion_nobuild, config, debug_senders, user_agent
from EDMCLogging import get_main_logger
from monitor import monitor
from myNotebook import Frame
from prefs import prefsVersion
from ttkHyperlinkLabel import HyperlinkLabel
from util import text

if sys.platform != 'win32':
    from fcntl import LOCK_EX, LOCK_NB, lockf


if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

logger = get_main_logger()


class This:
    """Holds module globals."""

    def __init__(self):
        # Track if we're on foot
        self.on_foot = False

        # Horizons ?
        self.horizons = False
        # Running under Odyssey?
        self.odyssey = False

        # Track location to add to Journal events
        self.systemaddress: Optional[str] = None
        self.coordinates: Optional[Tuple] = None
        self.body_name: Optional[str] = None
        self.body_id: Optional[int] = None
        # Track Status.json data
        self.status_body_name: Optional[str] = None

        # Avoid duplicates
        self.marketId: Optional[str] = None
        self.commodities: Optional[List[OrderedDictT[str, Any]]] = None
        self.outfitting: Optional[Tuple[bool, List[str]]] = None
        self.shipyard: Optional[Tuple[bool, List[Mapping[str, Any]]]] = None

        # For the tkinter parent window, so we can call update_idletasks()
        self.parent: tk.Tk

        # To hold EDDN class instance
        self.eddn: EDDN

        # tkinter UI bits.
        self.eddn_station: tk.IntVar
        self.eddn_station_button: nb.Checkbutton

        self.eddn_system: tk.IntVar
        self.eddn_system_button: nb.Checkbutton

        self.eddn_delay: tk.IntVar
        self.eddn_delay_button: nb.Checkbutton

        # Tracking UI
        self.ui: tk.Frame
        self.ui_j_body_name: tk.Label
        self.ui_j_body_id: tk.Label
        self.ui_s_body_name: tk.Label


this = This()


# This SKU is tagged on any module or ship that you must have Horizons for.
HORIZONS_SKU = 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'
# ELITE_HORIZONS_V_COBRA_MK_IV_1000` is for the Cobra Mk IV, but
# is also available in the base game, if you have entitlement.
# `ELITE_HORIZONS_V_GUARDIAN_FSDBOOSTER` is for the Guardian FSD Boosters,
# which you need Horizons in order to unlock, but could be on sale even in the
# base game due to entitlement.
# Thus do **NOT** use either of these in addition to the PLANETARY_LANDINGS
# one.


# TODO: a good few of these methods are static or could be classmethods. they should be created as such.

class EDDN:
    """EDDN Data export."""

    DEFAULT_URL = 'https://eddn.edcd.io:4430/upload/'
    if 'eddn' in debug_senders:
        DEFAULT_URL = f'http://{edmc_data.DEBUG_WEBSERVER_HOST}:{edmc_data.DEBUG_WEBSERVER_PORT}/eddn'

    REPLAYPERIOD = 400  # Roughly two messages per second, accounting for send delays [ms]
    REPLAYFLUSH = 20  # Update log on disk roughly every 10 seconds
    TIMEOUT = 10  # requests timeout
    MODULE_RE = re.compile(r'^Hpt_|^Int_|Armour_', re.IGNORECASE)
    CANONICALISE_RE = re.compile(r'\$(.+)_name;')
    UNKNOWN_SCHEMA_RE = re.compile(
        r"^FAIL: \[JsonValidationException\('Schema "
        r"https://eddn.edcd.io/schemas/(?P<schema_name>.+)/(?P<schema_version>[0-9]+) is unknown, "
        r"unable to validate.',\)\]$"
    )

    def __init__(self, parent: tk.Tk):
        self.parent: tk.Tk = parent
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent
        self.replayfile: Optional[TextIO] = None  # For delayed messages
        self.replaylog: List[str] = []

        if config.eddn_url is not None:
            self.eddn_url = config.eddn_url

        else:
            self.eddn_url = self.DEFAULT_URL

    def load_journal_replay(self) -> bool:
        """
        Load cached journal entries from disk.

        :return: a bool indicating success
        """
        # Try to obtain exclusive access to the journal cache
        filename = join(config.app_dir, 'replay.jsonl')
        try:
            try:
                # Try to open existing file
                self.replayfile = open(filename, 'r+', buffering=1)

            except FileNotFoundError:
                self.replayfile = open(filename, 'w+', buffering=1)  # Create file

            if sys.platform != 'win32':  # open for writing is automatically exclusive on Windows
                lockf(self.replayfile, LOCK_EX | LOCK_NB)

        except OSError:
            logger.exception('Failed opening "replay.jsonl"')
            if self.replayfile:
                self.replayfile.close()

            self.replayfile = None
            return False

        else:
            self.replaylog = [line.strip() for line in self.replayfile]
            return True

    def flush(self):
        """Flush the replay file, clearing any data currently there that is not in the replaylog list."""
        if self.replayfile is None:
            logger.error('replayfile is None!')
            return

        self.replayfile.seek(0, SEEK_SET)
        self.replayfile.truncate()
        for line in self.replaylog:
            self.replayfile.write(f'{line}\n')

        self.replayfile.flush()

    def close(self):
        """Close down the EDDN class instance."""
        logger.debug('Closing replayfile...')
        if self.replayfile:
            self.replayfile.close()

        self.replayfile = None
        logger.debug('Done.')

        logger.debug('Closing EDDN requests.Session.')
        self.session.close()

    def send(self, cmdr: str, msg: Mapping[str, Any]) -> None:
        """
        Send sends an update to EDDN.

        :param cmdr: the CMDR to use as the uploader ID.
        :param msg: the payload to send.
        """
        should_return, new_data = killswitch.check_killswitch('plugins.eddn.send', msg)
        if should_return:
            logger.warning('eddn.send has been disabled via killswitch. Returning.')
            return

        msg = new_data

        uploader_id = cmdr

        to_send: OrderedDictT[str, OrderedDict[str, Any]] = OrderedDict([
            ('$schemaRef', msg['$schemaRef']),
            ('header', OrderedDict([
                ('softwareName',    f'{applongname} [{system() if sys.platform != "darwin" else "Mac OS"}]'),
                ('softwareVersion', str(appversion_nobuild())),
                ('uploaderID',      uploader_id),
            ])),
            ('message', msg['message']),
        ])

        # About the smallest request is going to be (newlines added for brevity):
        # {"$schemaRef":"https://eddn.edcd.io/schemas/commodity/3","header":{"softwareName":"E:D Market
        # Connector Windows","softwareVersion":"5.3.0-beta4extra","uploaderID":"abcdefghijklm"},"messag
        # e":{"systemName":"delphi","stationName":"The Oracle","marketId":128782803,"timestamp":"2022-0
        # 1-26T12:00:00Z","commodities":[]}}
        #
        # Which comes to 315 bytes (including \n) and compresses to 244 bytes. So lets just compress everything

        encoded, compressed = text.gzip(json.dumps(to_send, separators=(',', ':')), max_size=0)
        headers: None | dict[str, str] = None
        if compressed:
            headers = {'Content-Encoding': 'gzip'}

        r = self.session.post(self.eddn_url, data=encoded, timeout=self.TIMEOUT, headers=headers)
        if r.status_code != requests.codes.ok:

            # Check if EDDN is still objecting to an empty commodities list
            if (
                    r.status_code == 400
                    and msg['$schemaRef'] == 'https://eddn.edcd.io/schemas/commodity/3'
                    and msg['message']['commodities'] == []
                    and r.text == "FAIL: [<ValidationError: '[] is too short'>]"
            ):
                logger.trace_if('plugin.eddn', "EDDN is still objecting to empty commodities data")
                return  # We want to silence warnings otherwise

            if r.status_code == 413:
                extra_data = {
                    'schema_ref': msg.get('$schemaRef', 'Unset $schemaRef!'),
                    'sent_data_len': str(len(encoded)),
                }

                if '/journal/' in extra_data['schema_ref']:
                    extra_data['event'] = msg.get('message', {}).get('event', 'No Event Set')

                self._log_response(r, header_msg='Got a 413 while POSTing data', **extra_data)
                return  # drop the error

            if not self.UNKNOWN_SCHEMA_RE.match(r.text):
                self._log_response(r, header_msg='Status from POST wasn\'t 200 (OK)')

        r.raise_for_status()

    def _log_response(
        self,
        response: requests.Response,
        header_msg='Failed to POST to EDDN',
        **kwargs
    ) -> None:
        """
        Log a response object with optional additional data.

        :param response: The response to log
        :param header_msg: A header message to add to the log, defaults to 'Failed to POST to EDDN'
        :param kwargs: Any other notes to add, will be added below the main data in the same format.
        """
        additional_data = "\n".join(
            f'''{name.replace('_', ' ').title():<8}:\t{value}''' for name, value in kwargs.items()
        )

        logger.debug(dedent(f'''\
        {header_msg}:
        Status  :\t{response.status_code}
        URL     :\t{response.url}
        Headers :\t{response.headers}
        Content :\t{response.text}
        ''')+additional_data)

    def sendreplay(self) -> None:  # noqa: CCR001
        """Send cached Journal lines to EDDN."""
        if not self.replayfile:
            return  # Probably closing app

        status: tk.Widget = self.parent.children['status']

        if not self.replaylog:
            status['text'] = ''
            return

        localized: str = _('Sending data to EDDN...')  # LANG: Status text shown while attempting to send data
        if len(self.replaylog) == 1:
            status['text'] = localized

        else:
            status['text'] = f'{localized.replace("...", "")} [{len(self.replaylog)}]'

        self.parent.update_idletasks()

        # Paranoia check in case this function gets chain-called.
        if not self.replaylog:
            # import traceback
            # logger.error(
            #     f'self.replaylog (type: {type(self.replaylog)}) is falsey after update_idletasks().  Traceback:\n'
            #     f'{"".join(traceback.format_list(traceback.extract_stack()))}')
            return

        try:
            cmdr, msg = json.loads(self.replaylog[0], object_pairs_hook=OrderedDict)

        except json.JSONDecodeError as e:
            # Couldn't decode - shouldn't happen!
            logger.debug(f'\n{self.replaylog[0]}\n', exc_info=e)
            # Discard and continue
            self.replaylog.pop(0)

        else:
            # TODO: Check message against *current* relevant schema so we don't try
            #       to send an old message that's now invalid.

            # Rewrite old schema name
            if msg['$schemaRef'].startswith('http://schemas.elite-markets.net/eddn/'):
                msg['$schemaRef'] = str(msg['$schemaRef']).replace(
                    'http://schemas.elite-markets.net/eddn/',
                    'https://eddn.edcd.io/schemas/'
                )

            try:
                self.send(cmdr, msg)
                self.replaylog.pop(0)
                if not len(self.replaylog) % self.REPLAYFLUSH:
                    self.flush()

            except requests.exceptions.HTTPError as e:
                if unknown_schema := self.UNKNOWN_SCHEMA_RE.match(e.response.text):
                    logger.debug(f"EDDN doesn't (yet?) know about schema: {unknown_schema['schema_name']}"
                                 f"/{unknown_schema['schema_version']}")
                    # NB: This dropping is to cater for the time when EDDN
                    #     doesn't *yet* support a new schema.
                    self.replaylog.pop(0)  # Drop the message
                    self.flush()  # Truncates the file, then writes the extant data

                elif e.response.status_code == 400:
                    # EDDN straight up says no, so drop the message
                    logger.debug(f"EDDN responded '400' to the message, dropping:\n{msg!r}")
                    self.replaylog.pop(0)  # Drop the message
                    self.flush()  # Truncates the file, then writes the extant data

                else:
                    status['text'] = self.http_error_to_log(e)

            except requests.exceptions.RequestException as e:
                logger.debug('Failed sending', exc_info=e)
                # LANG: Error while trying to send data to EDDN
                status['text'] = _("Error: Can't connect to EDDN")
                return  # stop sending

            except Exception as e:
                logger.debug('Failed sending', exc_info=e)
                status['text'] = str(e)
                return  # stop sending

        self.parent.after(self.REPLAYPERIOD, self.sendreplay)

    @staticmethod
    def http_error_to_log(exception: requests.exceptions.HTTPError) -> str:
        """Convert an exception from raise_for_status to a log message and displayed error."""
        status_code = exception.errno

        if status_code == 429:  # HTTP UPGRADE REQUIRED
            logger.warning('EDMC is sending schemas that are too old')
            # LANG: EDDN has banned this version of our client
            return _('EDDN Error: EDMC is too old for EDDN. Please update.')

        elif status_code == 400:
            # we a validation check or something else.
            logger.warning(f'EDDN Error: {status_code} -- {exception.response}')
            # LANG: EDDN returned an error that indicates something about what we sent it was wrong
            return _('EDDN Error: Validation Failed (EDMC Too Old?). See Log')

        else:
            logger.warning(f'Unknown status code from EDDN: {status_code} -- {exception.response}')
            # LANG: EDDN returned some sort of HTTP error, one we didn't expect. {STATUS} contains a number
            return _('EDDN Error: Returned {STATUS} status code').format(STATUS=status_code)

    def export_commodities(self, data: Mapping[str, Any], is_beta: bool) -> None:  # noqa: CCR001
        """
        Update EDDN with the commodities on the current (lastStarport) station.

        Once the send is complete, this.commodities is updated with the new data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param data: a dict containing the starport data
        :param is_beta: whether or not we're currently in beta mode
        """
        modules, ships = self.safe_modules_and_ships(data)
        horizons: bool = capi_is_horizons(
            data['lastStarport'].get('economies', {}),
            modules,
            ships
        )
        commodities: List[OrderedDictT[str, Any]] = []
        for commodity in data['lastStarport'].get('commodities') or []:
            # Check 'marketable' and 'not prohibited'
            if (category_map.get(commodity['categoryname'], True)
                    and not commodity.get('legality')):
                commodities.append(OrderedDict([
                    ('name',          commodity['name'].lower()),
                    ('meanPrice',     int(commodity['meanPrice'])),
                    ('buyPrice',      int(commodity['buyPrice'])),
                    ('stock',         int(commodity['stock'])),
                    ('stockBracket',  commodity['stockBracket']),
                    ('sellPrice',     int(commodity['sellPrice'])),
                    ('demand',        int(commodity['demand'])),
                    ('demandBracket', commodity['demandBracket']),
                ]))

                if commodity['statusFlags']:
                    commodities[-1]['statusFlags'] = commodity['statusFlags']

        commodities.sort(key=lambda c: c['name'])

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that, e.g.
        # EDDB can update in a timely manner.
        if this.commodities != commodities:
            message: OrderedDictT[str, Any] = OrderedDict([
                ('timestamp',   data['timestamp']),
                ('systemName',  data['lastSystem']['name']),
                ('stationName', data['lastStarport']['name']),
                ('marketId',    data['lastStarport']['id']),
                ('commodities', commodities),
                ('horizons',    horizons),
                ('odyssey',     this.odyssey),
            ])

            if 'economies' in data['lastStarport']:
                message['economies'] = sorted(
                    (x for x in (data['lastStarport']['economies'] or {}).values()), key=lambda x: x['name']
                )

            if 'prohibited' in data['lastStarport']:
                message['prohibited'] = sorted(x for x in (data['lastStarport']['prohibited'] or {}).values())

            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message':    message,
            })

        this.commodities = commodities

    def safe_modules_and_ships(self, data: Mapping[str, Any]) -> Tuple[Dict, Dict]:
        """
        Produce a sanity-checked version of ships and modules from CAPI data.

        Principally this catches where the supplied CAPI data either doesn't
        contain expected elements, or they're not of the expected type (e.g.
        a list instead of a dict).

        :param data: The raw CAPI data.
        :return: Sanity-checked data.
        """
        modules: Dict[str, Any] = data['lastStarport'].get('modules')
        if modules is None or not isinstance(modules, dict):
            if modules is None:
                logger.debug('modules was None.  FC or Damaged Station?')

            elif isinstance(modules, list):
                if len(modules) == 0:
                    logger.debug('modules is empty list. FC or Damaged Station?')

                else:
                    logger.error(f'modules is non-empty list: {modules!r}')

            else:
                logger.error(f'modules was not None, a list, or a dict! type = {type(modules)}')
            # Set a safe value
            modules = {}

        ships: Dict[str, Any] = data['lastStarport'].get('ships')
        if ships is None or not isinstance(ships, dict):
            if ships is None:
                logger.debug('ships was None')

            else:
                logger.error(f'ships was neither None nor a Dict! Type = {type(ships)}')
            # Set a safe value
            ships = {'shipyard_list': {}, 'unavailable_list': []}

        return modules, ships

    def export_outfitting(self, data: CAPIData, is_beta: bool) -> None:
        """
        Update EDDN with the current (lastStarport) station's outfitting options, if any.

        Once the send is complete, this.outfitting is updated with the given data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param data: dict containing the outfitting data
        :param is_beta: whether or not we're currently in beta mode
        """
        modules, ships = self.safe_modules_and_ships(data)

        # Horizons flag - will hit at least Int_PlanetApproachSuite other than at engineer bases ("Colony"),
        # prison or rescue Megaships, or under Pirate Attack etc
        horizons: bool = capi_is_horizons(
            data['lastStarport'].get('economies', {}),
            modules,
            ships
        )

        to_search: Iterator[Mapping[str, Any]] = filter(
            lambda m: self.MODULE_RE.search(m['name']) and m.get('sku') in (None, HORIZONS_SKU)
                                                       and m['name'] != 'Int_PlanetApproachSuite',  # noqa: E131
            modules.values()
        )

        outfitting: List[str] = sorted(
            self.MODULE_RE.sub(lambda match: match.group(0).capitalize(), mod['name'].lower()) for mod in to_search
        )

        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                    ('odyssey',     this.odyssey),
                ]),
            })

        this.outfitting = (horizons, outfitting)

    def export_shipyard(self, data: CAPIData, is_beta: bool) -> None:
        """
        Update EDDN with the current (lastStarport) station's outfitting options, if any.

        Once the send is complete, this.shipyard is updated to the new data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param data: dict containing the shipyard data
        :param is_beta: whether or not we are in beta mode
        """
        modules, ships = self.safe_modules_and_ships(data)

        horizons: bool = capi_is_horizons(
            data['lastStarport'].get('economies', {}),
            modules,
            ships
        )

        shipyard: List[Mapping[str, Any]] = sorted(
            itertools.chain(
                (ship['name'].lower() for ship in (ships['shipyard_list'] or {}).values()),
                (ship['name'].lower() for ship in ships['unavailable_list'] or {}),
            )
        )
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                    ('odyssey',     this.odyssey),
                ]),
            })

        this.shipyard = (horizons, shipyard)

    def export_journal_commodities(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        Update EDDN with Journal commodities data from the current station (lastStarport).

        As a side effect, it also updates this.commodities with the data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param cmdr: The commander to send data under
        :param is_beta: whether or not we're in beta mode
        :param entry: the journal entry containing the commodities data
        """
        items: List[Mapping[str, Any]] = entry.get('Items') or []
        commodities: List[OrderedDictT[str, Any]] = sorted((OrderedDict([
            ('name',          self.canonicalise(commodity['Name'])),
            ('meanPrice',     commodity['MeanPrice']),
            ('buyPrice',      commodity['BuyPrice']),
            ('stock',         commodity['Stock']),
            ('stockBracket',  commodity['StockBracket']),
            ('sellPrice',     commodity['SellPrice']),
            ('demand',        commodity['Demand']),
            ('demandBracket', commodity['DemandBracket']),
        ]) for commodity in items), key=lambda c: c['name'])

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that, e.g.
        # EDDB can update in a timely manner.
        if this.commodities != commodities:
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('commodities', commodities),
                    ('horizons',    this.horizons),
                    ('odyssey',     this.odyssey),
                ]),
            })

        this.commodities = commodities

    def export_journal_outfitting(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        Update EDDN with Journal oufitting data from the current station (lastStarport).

        As a side effect, it also updates this.outfitting with the data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param cmdr: The commander to send data under
        :param is_beta: Whether or not we're in beta mode
        :param entry: The relevant journal entry
        """
        modules: List[Mapping[str, Any]] = entry.get('Items', [])
        horizons: bool = entry.get('Horizons', False)
        # outfitting = sorted([self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), module['Name'])
        # for module in modules if module['Name'] != 'int_planetapproachsuite'])
        outfitting: List[str] = sorted(
            self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), mod['Name']) for mod in
            filter(lambda m: m['Name'] != 'int_planetapproachsuite', modules)
        )
        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                    ('odyssey',     entry['odyssey'])
                ]),
            })

        this.outfitting = (horizons, outfitting)

    def export_journal_shipyard(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        Update EDDN with Journal shipyard data from the current station (lastStarport).

        As a side effect, this.shipyard is updated with the data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param cmdr: the commander to send this update under
        :param is_beta: Whether or not we're in beta mode
        :param entry: the relevant journal entry
        """
        ships: List[Mapping[str, Any]] = entry.get('PriceList') or []
        horizons: bool = entry.get('Horizons', False)
        shipyard = sorted(ship['ShipType'] for ship in ships)
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                    ('odyssey',     entry['odyssey'])
                ]),
            })

        # this.shipyard = (horizons, shipyard)

    def export_journal_entry(self, cmdr: str, entry: Mapping[str, Any], msg: Mapping[str, Any]) -> None:
        """
        Update EDDN with an event from the journal.

        Additionally if other lines have been saved for retry, it may send
        those as well.

        :param cmdr: Commander name as passed in through `journal_entry()`.
        :param entry: The full journal event dictionary (due to checks in this function).
        :param msg: The EDDN message body to be sent.
        """
        if self.replayfile or self.load_journal_replay():
            # Store the entry
            self.replaylog.append(json.dumps([cmdr, msg]))
            self.replayfile.write(f'{self.replaylog[-1]}\n')  # type: ignore

            if (
                entry['event'] == 'Docked' or (entry['event'] == 'Location' and entry['Docked']) or not
                (config.get_int('output') & config.OUT_SYS_DELAY)
            ):
                self.parent.after(self.REPLAYPERIOD, self.sendreplay)  # Try to send this and previous entries

        else:
            # Can't access replay file! Send immediately.
            # LANG: Status text shown while attempting to send data
            self.parent.children['status']['text'] = _('Sending data to EDDN...')
            self.parent.update_idletasks()
            self.send(cmdr, msg)
            self.parent.children['status']['text'] = ''

    def export_journal_generic(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        Send an EDDN event on the journal schema.

        :param cmdr: the commander under which this upload is made
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/journal/1{"/test" if is_beta else ""}',
            'message': entry
        }
        this.eddn.export_journal_entry(cmdr, entry, msg)

    def entry_augment_system_data(
            self,
            entry: MutableMapping[str, Any],
            system_name: str,
            system_coordinates: list
    ) -> Union[str, MutableMapping[str, Any]]:
        """
        Augment a journal entry with necessary system data.

        :param entry: The journal entry to be augmented.
        :param system_name: Name of current star system.
        :param system_coordinates: Coordinates of current star system.
        :return: The augmented version of entry.
        """
        # If 'SystemName' or 'System' is there, it's directly from a journal event.
        # If they're not there *and* 'StarSystem' isn't either, then we add the latter.
        if 'SystemName' not in entry and 'System' not in entry and 'StarSystem' not in entry:
            if system_name is None or not isinstance(system_name, str) or system_name == '':
                # Bad assumptions if this is the case
                logger.warning(f'No system name in entry, and system_name was not set either!  entry:\n{entry!r}\n')
                return "passed-in system_name is empty, can't add System"

            else:
                entry['StarSystem'] = system_name

        if 'SystemAddress' not in entry:
            if this.systemaddress is None:
                logger.warning("this.systemaddress is None, can't add SystemAddress")
                return "this.systemaddress is None, can't add SystemAddress"

            entry['SystemAddress'] = this.systemaddress

        if 'StarPos' not in entry:
            # Prefer the passed-in, probably monitor.state version
            if system_coordinates is not None:
                entry['StarPos'] = system_coordinates

            # TODO: Deprecate in-plugin tracking
            elif this.coordinates is not None:
                entry['StarPos'] = list(this.coordinates)

            else:
                logger.warning("Neither this_coordinates or this.coordinates set, can't add StarPos")
                return 'No source for adding StarPos to EDDN message !'

        return entry

    def export_journal_fssdiscoveryscan(
            self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> Optional[str]:
        """
        Send an FSSDiscoveryScan to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of current star system
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        #######################################################################
        # Elisions
        entry = filter_localised(entry)
        entry.pop('Progress')
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssdiscoveryscan/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_navbeaconscan(
            self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> Optional[str]:
        """
        Send an NavBeaconScan to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of the current system.
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # { "timestamp":"2021-09-24T13:57:24Z", "event":"NavBeaconScan", "SystemAddress":670417626481, "NumBodies":18 }
        #######################################################################
        # Elisions
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/navbeaconscan/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_codexentry(  # noqa: CCR001
            self, cmdr: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> Optional[str]:
        """
        Send a CodexEntry to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #   "timestamp":"2021-09-26T12:29:39Z",
        #   "event":"CodexEntry",
        #   "EntryID":1400414,
        #   "Name":"$Codex_Ent_Gas_Vents_SilicateVapourGeysers_Name;",
        #   "Name_Localised":"Silicate Vapour Gas Vent",
        #   "SubCategory":"$Codex_SubCategory_Geology_and_Anomalies;",
        #   "SubCategory_Localised":"Geology and anomalies",
        #   "Category":"$Codex_Category_Biology;",
        #   "Category_Localised":"Biological and Geological",
        #   "Region":"$Codex_RegionName_18;",
        #   "Region_Localised":"Inner Orion Spur",
        #   "System":"Bestia",
        #   "SystemAddress":147916327267,
        #   "Latitude":23.197777, "Longitude":51.803349,
        #   "IsNewEntry":true,
        #   "VoucherAmount":50000
        # }
        #######################################################################
        # Elisions
        entry = filter_localised(entry)
        # Keys specific to this event
        for k in ('IsNewEntry', 'NewTraitsDiscovered'):
            if k in entry:
                del entry[k]
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # General 'system' augmentations
        ret = this.eddn.entry_augment_system_data(entry, entry['System'], system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret

        # Set BodyName if it's available from Status.json
        if this.status_body_name is None or not isinstance(this.status_body_name, str):
            logger.warning(f'this.status_body_name was not set properly:'
                           f' "{this.status_body_name}" ({type(this.status_body_name)})')

        else:
            entry['BodyName'] = this.status_body_name
            # Only set BodyID if journal BodyName matches the Status.json one.
            # This avoids binary body issues.
            if this.status_body_name == this.body_name:
                if this.body_id is not None and isinstance(this.body_id, int):
                    entry['BodyID'] = this.body_id

                else:
                    logger.warning(f'this.body_id was not set properly: "{this.body_id}" ({type(this.body_id)})')
        #######################################################################

        # Check just the top-level strings with minLength=1 in the schema
        for k in ('System', 'Name', 'Region', 'Category', 'SubCategory'):
            v = entry[k]
            if v is None or isinstance(v, str) and v == '':
                logger.warning(f'post-processing entry contains entry["{k}"] = {v} {(type(v))}')
                # We should drop this message and VERY LOUDLY inform the
                # user, in the hopes they'll open a bug report with the
                # raw Journal event that caused this.
                return 'CodexEntry had empty string, PLEASE ALERT THE EDMC DEVELOPERS'

        # Also check traits
        if 'Traits' in entry:
            for v in entry['Traits']:
                if v is None or isinstance(v, str) and v == '':
                    logger.warning(f'post-processing entry[\'Traits\'] contains {v} {(type(v))}\n{entry["Traits"]}\n')
                    return 'CodexEntry Trait had empty string, PLEASE ALERT THE EDMC DEVELOPERS'

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/codexentry/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_scanbarycentre(
            self, cmdr: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> Optional[str]:
        """
        Send a ScanBaryCentre to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #   "timestamp":"2021-09-26T11:55:03Z",
        #   "event":"ScanBaryCentre",
        #   "StarSystem":"Khruvani",
        #   "SystemAddress":13864557159793,
        #   "BodyID":21,
        #   "SemiMajorAxis":863683605194.091797,
        #   "Eccentricity":0.001446,
        #   "OrbitalInclination":-0.230714,
        #   "Periapsis":214.828581,
        #   "OrbitalPeriod":658474677.801132,
        #   "AscendingNode":21.188568,
        #   "MeanAnomaly":208.765388
        # }
        #######################################################################
        # Elisions
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        ret = this.eddn.entry_augment_system_data(entry, entry['StarSystem'], system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/scanbarycentre/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_navroute(
            self, cmdr: str, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> Optional[str]:
        """
        Send a NavRoute to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #    "timestamp":"2021-09-24T14:33:15Z",
        #    "event":"NavRoute",
        #    "Route":[
        #       {
        #         "StarSystem":"Ross 332",
        #         "SystemAddress":3657198211778,
        #         "StarPos":[-43.62500,-23.15625,-74.12500],
        #         "StarClass":"K"
        #       },
        #       {
        #          "StarSystem":"BD+44 1040",
        #          "SystemAddress":2832564490946,
        #          "StarPos":[-31.56250,1.84375,-92.37500],
        #          "StarClass":"K"
        #       },
        #       {
        #         "StarSystem":"Aonga",
        #         "SystemAddress":6680855188162,
        #         "StarPos":[-34.46875,9.53125,-90.87500],
        #         "StarClass":"M"
        #       }
        #    ]
        #  }

        # Sanity check - Ref Issue 1342
        if 'Route' not in entry:
            logger.warning(f"NavRoute didn't contain a Route array!\n{entry!r}")
            # LANG: No 'Route' found in NavRoute.json file
            return _("No 'Route' array in NavRoute.json contents")

        #######################################################################
        # Elisions
        #######################################################################
        # WORKAROUND WIP EDDN schema | 2021-10-17: This will reject with the Odyssey or Horizons flags present
        if 'odyssey' in entry:
            del entry['odyssey']

        if 'horizons' in entry:
            del entry['horizons']

        # END WORKAROUND
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # None
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/navroute/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_approachsettlement(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> Optional[str]:
        """
        Send an ApproachSettlement to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of current star system
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #   "BodyID": 32,
        #   "BodyName": "Ix 5 a a",
        #   "Latitude": 17.090912,
        #   "Longitude": 160.236679,
        #   "MarketID": 3915738368,
        #   "Name": "Arnold Defence Base",
        #   "SystemAddress": 2381282543963,
        #   "event": "ApproachSettlement",
        #   "timestamp": "2021-10-14T12:37:54Z"
        # }

        #######################################################################
        # Bugs
        #######################################################################
        # WORKAROUND 3.8.0.404 | 2022-02-18: ApproachSettlement missing coords
        # As of Horizons ("gameversion":"3.8.0.404", "build":"r280105/r0 ")
        # if you log back in (certainly a game client restart) at a
        # Planetary Port, then the ApproachSettlement event written will be
        # missing the Latitude and Longitude.
        # Ref: https://github.com/EDCD/EDMarketConnector/issues/1476
        if any(
            k not in entry for k in ('Latitude', 'Longitude')
        ):
            logger.debug(
                f'ApproachSettlement without at least one of Latitude or Longitude:\n{entry}\n'
            )
            # No need to alert the user, it will only annoy them
            return ""
        # WORKAROUND END
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # In this case should add StarSystem and StarPos
        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/approachsettlement/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_fssallbodiesfound(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> Optional[str]:
        """
        Send an FSSAllBodiesFound message to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of current star system
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #   "Count": 3,
        #   "SystemAddress": 9466778822057,
        #   "SystemName": "LP 704-74",
        #   "event": "FSSAllBodiesFound",
        #   "timestamp": "2022-02-09T18:15:14Z"
        # }
        #######################################################################
        # Augmentations
        #######################################################################
        # In this case should add StarSystem and StarPos
        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssallbodiesfound/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def export_journal_fssbodysignals(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> Optional[str]:
        """
        Send an FSSBodySignals message to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of current star system
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #   "timestamp" : "2022-03-15T13:07:51Z",
        #   "event" : "FSSBodySignals",
        #   "BodyName" : "Phroi Blou BQ-Y d1162 1 a",
        #   "BodyID" : 12,
        #   "SystemAddress" : 39935704602251,
        #   "Signals" : [
        #     {
        #       "Type" : "$SAA_SignalType_Geological;",
        #       "Type_Localised" : "Geological",
        #       "Count" : 3
        #     }
        #   ]
        # }

        #######################################################################
        # Elisions
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # In this case should add StarPos
        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssbodysignals/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.export_journal_entry(cmdr, entry, msg)
        return None

    def canonicalise(self, item: str) -> str:
        """
        Canonicalise the given commodity name.

        :param item: Name of an commodity we want the canonical name for.
        :return: The canonical name for this commodity.
        """
        match = self.CANONICALISE_RE.match(item)
        return match and match.group(1) or item


# Plugin callbacks

def plugin_start3(plugin_dir: str) -> str:
    """
    Start this plugin.

    :param plugin_dir: `str` - The full path to this plugin's directory.
    :return: `str` - Name of this plugin to use in UI.
    """
    return 'EDDN'


def plugin_app(parent: tk.Tk) -> Optional[tk.Frame]:
    """
    Set up any plugin-specific UI.

    In this case we need the tkinter parent in order to later call
    `update_idletasks()` on it.

    TODO: Re-work the whole replaylog and general sending to EDDN so this isn't
          necessary.

    :param parent: tkinter parent frame.
    :return: Optional tk.Frame, if the tracking UI is active.
    """
    this.parent = parent
    this.eddn = EDDN(parent)
    # Try to obtain exclusive lock on journal cache, even if we don't need it yet
    if not this.eddn.load_journal_replay():
        # Shouldn't happen - don't bother localizing
        this.parent.children['status']['text'] = 'Error: Is another copy of this app already running?'

    if config.eddn_tracking_ui:
        this.ui = tk.Frame(parent)

        row = this.ui.grid_size()[1]
        journal_body_name_label = tk.Label(this.ui, text="J:BodyName:")
        journal_body_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_j_body_name = tk.Label(this.ui, name='eddn_track_j_body_name', anchor=tk.W)
        this.ui_j_body_name.grid(row=row, column=1, sticky=tk.E)
        row += 1

        journal_body_id_label = tk.Label(this.ui, text="J:BodyID:")
        journal_body_id_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_j_body_id = tk.Label(this.ui, name='eddn_track_j_body_id', anchor=tk.W)
        this.ui_j_body_id.grid(row=row, column=1, sticky=tk.E)
        row += 1

        status_body_name_label = tk.Label(this.ui, text="S:BodyName:")
        status_body_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_s_body_name = tk.Label(this.ui, name='eddn_track_s_body_name', anchor=tk.W)
        this.ui_s_body_name.grid(row=row, column=1, sticky=tk.E)
        row += 1

        return this.ui

    return None


def tracking_ui_update() -> None:
    """Update the Tracking UI with current data, if required."""
    if not config.eddn_tracking_ui:
        return

    this.ui_j_body_name['text'] = '≪None≫'
    if this.body_name is not None:
        this.ui_j_body_name['text'] = this.body_name

    this.ui_j_body_id['text'] = '≪None≫'
    if this.body_id is not None:
        this.ui_j_body_id['text'] = str(this.body_id)

    this.ui_s_body_name['text'] = '≪None≫'
    if this.status_body_name is not None:
        this.ui_s_body_name['text'] = this.status_body_name

    this.ui.update_idletasks()


def plugin_prefs(parent, cmdr: str, is_beta: bool) -> Frame:
    """
    Set up Preferences pane for this plugin.

    :param parent: tkinter parent to attach to.
    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :return: The tkinter frame we created.
    """
    PADX = 10  # noqa: N806
    BUTTONX = 12  # noqa: N806 # indent Checkbuttons and Radiobuttons

    if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
        output: int = (config.OUT_MKT_EDDN | config.OUT_SYS_EDDN)  # default settings

    else:
        output = config.get_int('output')

    eddnframe = nb.Frame(parent)

    HyperlinkLabel(
        eddnframe,
        text='Elite Dangerous Data Network',
        background=nb.Label().cget('background'),
        url='https://github.com/EDSM-NET/EDDN/wiki',
        underline=True
    ).grid(padx=PADX, sticky=tk.W)  # Don't translate

    this.eddn_station = tk.IntVar(value=(output & config.OUT_MKT_EDDN) and 1)
    this.eddn_station_button = nb.Checkbutton(
        eddnframe,
        # LANG: Enable EDDN support for station data checkbox label
        text=_('Send station data to the Elite Dangerous Data Network'),
        variable=this.eddn_station,
        command=prefsvarchanged
    )  # Output setting

    this.eddn_station_button.grid(padx=BUTTONX, pady=(5, 0), sticky=tk.W)
    this.eddn_system = tk.IntVar(value=(output & config.OUT_SYS_EDDN) and 1)
    # Output setting new in E:D 2.2
    this.eddn_system_button = nb.Checkbutton(
        eddnframe,
        # LANG: Enable EDDN support for system and other scan data checkbox label
        text=_('Send system and scan data to the Elite Dangerous Data Network'),
        variable=this.eddn_system,
        command=prefsvarchanged
    )

    this.eddn_system_button.grid(padx=BUTTONX, pady=(5, 0), sticky=tk.W)
    this.eddn_delay = tk.IntVar(value=(output & config.OUT_SYS_DELAY) and 1)
    # Output setting under 'Send system and scan data to the Elite Dangerous Data Network' new in E:D 2.2
    this.eddn_delay_button = nb.Checkbutton(
        eddnframe,
        # LANG: EDDN delay sending until docked option is on, this message notes that a send was skipped due to this
        text=_('Delay sending until docked'),
        variable=this.eddn_delay
    )
    this.eddn_delay_button.grid(padx=BUTTONX, sticky=tk.W)

    return eddnframe


def prefsvarchanged(event=None) -> None:
    """
    Handle changes to EDDN Preferences.

    :param event: tkinter event ?
    """
    this.eddn_station_button['state'] = tk.NORMAL
    this.eddn_system_button['state'] = tk.NORMAL
    this.eddn_delay_button['state'] = this.eddn.replayfile and this.eddn_system.get() and tk.NORMAL or tk.DISABLED


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle when Preferences have been changed.

    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    """
    config.set(
        'output',
        (config.get_int('output')
         & (config.OUT_MKT_TD | config.OUT_MKT_CSV | config.OUT_SHIP | config.OUT_MKT_MANUAL)) +
        (this.eddn_station.get() and config.OUT_MKT_EDDN) +
        (this.eddn_system.get() and config.OUT_SYS_EDDN) +
        (this.eddn_delay.get() and config.OUT_SYS_DELAY)
    )


def plugin_stop() -> None:
    """Handle stopping this plugin."""
    logger.debug('Calling this.eddn.close()')
    this.eddn.close()
    logger.debug('Done.')


# Recursively filter '*_Localised' keys from dict
def filter_localised(d: Mapping[str, Any]) -> OrderedDictT[str, Any]:
    """
    Remove any dict keys with names ending `_Localised` from a dict.

    :param d: Dict to filter keys of.
    :return: The filtered dict.
    """
    filtered: OrderedDictT[str, Any] = OrderedDict()
    for k, v in d.items():
        if k.endswith('_Localised'):
            pass

        elif hasattr(v, 'items'):  # dict -> recurse
            filtered[k] = filter_localised(v)

        elif isinstance(v, list):  # list of dicts -> recurse
            filtered[k] = [filter_localised(x) if hasattr(x, 'items') else x for x in v]

        else:
            filtered[k] = v

    return filtered


def journal_entry(  # noqa: C901, CCR001
        cmdr: str,
        is_beta: bool,
        system: str,
        station: str,
        entry: MutableMapping[str, Any],
        state: Mapping[str, Any]
) -> Optional[str]:
    """
    Process a new Journal entry.

    :param cmdr: `str` - Name of currennt Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :param system: `str` - Name of system Cmdr is in.
    :param station: `str` - Name of station Cmdr is docked at, if applicable.
    :param entry: `dict` - The data for this Journal entry.
    :param state: `dict` - Current `monitor.state` data.
    :return: `str` - Error message, or `None` if no errors.
    """
    should_return, new_data = killswitch.check_killswitch('plugins.eddn.journal', entry)
    if should_return:
        plug.show_error(_('EDDN journal handler disabled. See Log.'))  # LANG: Killswitch disabled EDDN
        return None

    should_return, new_data = killswitch.check_killswitch(f'plugins.eddn.journal.event.{entry["event"]}', new_data)
    if should_return:
        return None

    entry = new_data
    event_name = entry['event'].lower()

    this.on_foot = state['OnFoot']

    # Note if we're under Horizons and/or Odyssey
    # The only event these are already in is `LoadGame` which isn't sent to EDDN.
    this.horizons = entry['horizons'] = state['Horizons']
    this.odyssey = entry['odyssey'] = state['Odyssey']

    # Track location
    if event_name in ('location', 'fsdjump', 'docked', 'carrierjump'):
        if event_name in ('location', 'carrierjump'):
            if entry.get('BodyType') == 'Planet':
                this.body_name = entry.get('Body')
                this.body_id = entry.get('BodyID')

            else:
                this.body_name = None

        elif event_name == 'fsdjump':
            this.body_name = None
            this.body_id = None

        if 'StarPos' in entry:
            this.coordinates = tuple(entry['StarPos'])

        elif this.systemaddress != entry.get('SystemAddress'):
            this.coordinates = None  # Docked event doesn't include coordinates

        if 'SystemAddress' not in entry:
            logger.warning(f'"location" event without SystemAddress !!!:\n{entry}\n')

        # But we'll still *use* the value, because if a 'location' event doesn't
        # have this we've still moved and now don't know where and MUST NOT
        # continue to use any old value.
        # Yes, explicitly state `None` here, so it's crystal clear.
        this.systemaddress = entry.get('SystemAddress', None)  # type: ignore

    elif event_name == 'approachbody':
        this.body_name = entry['Body']
        this.body_id = entry.get('BodyID')

    elif event_name == 'leavebody':
        # NB: **NOT** SupercruiseEntry, because we won't get a fresh
        #     ApproachBody if we don't leave Orbital Cruise and land again.
        # *This* is triggered when you go above Orbital Cruise altitude.
        # Status.json BodyName clears when the OC/Glide HUD is deactivated.
        this.body_name = None
        this.body_id = None

    elif event_name == 'music':
        if entry['MusicTrack'] == 'MainMenu':
            this.body_name = None
            this.body_id = None
            this.status_body_name = None

    # Events with their own EDDN schema
    if config.get_int('output') & config.OUT_SYS_EDDN and not state['Captain']:

        if event_name == 'fssdiscoveryscan':
            return this.eddn.export_journal_fssdiscoveryscan(cmdr, system, state['StarPos'], is_beta, entry)

        elif event_name == 'navbeaconscan':
            return this.eddn.export_journal_navbeaconscan(cmdr, system, state['StarPos'], is_beta, entry)

        elif event_name == 'codexentry':
            return this.eddn.export_journal_codexentry(cmdr, state['StarPos'], is_beta, entry)

        elif event_name == 'scanbarycentre':
            return this.eddn.export_journal_scanbarycentre(cmdr, state['StarPos'], is_beta, entry)

        elif event_name == 'navroute':
            return this.eddn.export_journal_navroute(cmdr, is_beta, entry)

        elif event_name == 'approachsettlement':
            # An `ApproachSettlement` can appear *before* `Location` if you
            # logged at one.  We won't have necessary augmentation data
            # at this point, so bail.
            if system is None:
                return ""

            return this.eddn.export_journal_approachsettlement(
                cmdr,
                system,
                state['StarPos'],
                is_beta,
                entry
            )

        # NB: If adding FSSSignalDiscovered these absolutely come in at login
        #     time **BEFORE** the `Location` event, so we won't yet know things
        #     like SystemName, or StarPos.
        #     We can either have the "now send the batch" code add such (but
        #     that has corner cases around changing systems in the meantime),
        #     drop those events, or if the schema allows, send without those
        #     augmentations.

        elif event_name == 'fssallbodiesfound':
            return this.eddn.export_journal_fssallbodiesfound(
                cmdr,
                system,
                state['StarPos'],
                is_beta,
                entry
            )
        elif event_name == 'fssbodysignals':
            return this.eddn.export_journal_fssbodysignals(
                cmdr,
                system,
                state['StarPos'],
                is_beta,
                entry
            )

    # Send journal schema events to EDDN, but not when on a crew
    if (config.get_int('output') & config.OUT_SYS_EDDN and not state['Captain'] and
        (event_name in ('location', 'fsdjump', 'docked', 'scan', 'saasignalsfound', 'carrierjump')) and
            ('StarPos' in entry or this.coordinates)):

        # strip out properties disallowed by the schema
        for thing in (
            'ActiveFine',
            'CockpitBreach',
            'BoostUsed',
            'FuelLevel',
            'FuelUsed',
            'JumpDist',
            'Latitude',
            'Longitude',
            'Wanted'
        ):
            entry.pop(thing, None)

        if 'Factions' in entry:
            # Filter faction state to comply with schema restrictions regarding personal data. `entry` is a shallow copy
            # so replace 'Factions' value rather than modify in-place.
            entry['Factions'] = [
                {
                    k: v for k, v in f.items() if k not in (
                        'HappiestSystem', 'HomeSystem', 'MyReputation', 'SquadronFaction'
                    )
                }
                for f in entry['Factions']
            ]

        # add planet to Docked event for planetary stations if known
        if event_name == 'docked' and this.body_name:
            entry['Body'] = this.body_name
            entry['BodyType'] = 'Planet'

        # add mandatory StarSystem, StarPos and SystemAddress properties to Scan events
        if 'StarSystem' not in entry:
            if not system:
                logger.warning("system is falsey, can't add StarSystem")
                return "system is falsey, can't add StarSystem"

            entry['StarSystem'] = system

        if 'StarPos' not in entry:
            if not this.coordinates:
                logger.warning("this.coordinates is falsey, can't add StarPos")
                return "this.coordinates is falsey, can't add StarPos"

            # Gazelle[TD] reported seeing a lagged Scan event with incorrect
            # augmented StarPos: <https://github.com/EDCD/EDMarketConnector/issues/961>
            if this.systemaddress is None or this.systemaddress != entry['SystemAddress']:
                logger.warning("event has no StarPos, but SystemAddress isn't current location")
                return "Wrong System! Delayed Scan event?"

            entry['StarPos'] = list(this.coordinates)

        if 'SystemAddress' not in entry:
            if not this.systemaddress:
                logger.warning("this.systemaddress is falsey, can't add SystemAddress")
                return "this.systemaddress is falsey, can't add SystemAddress"

            entry['SystemAddress'] = this.systemaddress

        try:
            this.eddn.export_journal_generic(cmdr, is_beta, filter_localised(entry))

        except requests.exceptions.RequestException as e:
            logger.debug('Failed in export_journal_entry', exc_info=e)
            return _("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

        except Exception as e:
            logger.debug('Failed in export_journal_entry', exc_info=e)
            return str(e)

    elif (config.get_int('output') & config.OUT_MKT_EDDN and not state['Captain'] and
            event_name in ('market', 'outfitting', 'shipyard')):
        # Market.json, Outfitting.json or Shipyard.json to process

        try:
            if this.marketId != entry['MarketID']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = entry['MarketID']

            journaldir = config.get_str('journaldir')
            if journaldir is None or journaldir == '':
                journaldir = config.default_journal_dir

            path = pathlib.Path(journaldir) / f'{entry["event"]}.json'

            with path.open('rb') as f:
                # Don't assume we can definitely stomp entry & event_name here
                entry_augment = json.load(f)
                event_name_augment = entry_augment['event'].lower()
                entry_augment['odyssey'] = this.odyssey

                if event_name_augment == 'market':
                    this.eddn.export_journal_commodities(cmdr, is_beta, entry_augment)

                elif event_name_augment == 'outfitting':
                    this.eddn.export_journal_outfitting(cmdr, is_beta, entry_augment)

                elif event_name_augment == 'shipyard':
                    this.eddn.export_journal_shipyard(cmdr, is_beta, entry_augment)

        except requests.exceptions.RequestException as e:
            logger.debug(f'Failed exporting {entry["event"]}', exc_info=e)
            return _("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

        except Exception as e:
            logger.debug(f'Failed exporting {entry["event"]}', exc_info=e)
            return str(e)

    tracking_ui_update()

    return None


def cmdr_data(data: CAPIData, is_beta: bool) -> Optional[str]:  # noqa: CCR001
    """
    Process new CAPI data.

    :param data: CAPI data to process.
    :param is_beta: bool - True if this is a beta version of the Game.
    :return: str - Error message, or `None` if no errors.
    """
    if (data['commander'].get('docked') or (this.on_foot and monitor.station)
            and config.get_int('output') & config.OUT_MKT_EDDN):
        try:
            if this.marketId != data['lastStarport']['id']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = data['lastStarport']['id']

            status = this.parent.children['status']
            old_status = status['text']
            if not old_status:
                status['text'] = _('Sending data to EDDN...')  # LANG: Status text shown while attempting to send data
                status.update_idletasks()

            this.eddn.export_commodities(data, is_beta)
            this.eddn.export_outfitting(data, is_beta)
            this.eddn.export_shipyard(data, is_beta)
            if not old_status:
                status['text'] = ''
                status.update_idletasks()

        except requests.RequestException as e:
            logger.debug('Failed exporting data', exc_info=e)
            return _("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

        except Exception as e:
            logger.debug('Failed exporting data', exc_info=e)
            return str(e)

    return None


MAP_STR_ANY = Mapping[str, Any]


def capi_is_horizons(economies: MAP_STR_ANY, modules: MAP_STR_ANY, ships: MAP_STR_ANY) -> bool:
    """
    Indicate if the supplied data indicates a player has Horizons access.

    This is to be used **only** for CAPI-sourced data and **MUST** be used
    for CAPI data!!!

    If the account has Horizons access then CAPI `/shipyard` will always see
    the Horizons-only modules/ships.  You can**NOT** use the Journal horizons
    flag for this!  If logged in to the base game on an account with Horizons,
    which is all of them now, CAPI `/shipyard` will *still* return all of the
    Horizons-only modules and ships.

    :param economies: Economies of where the Cmdr is docked.
    :param modules: Modules available at the docked station.
    :param ships: Ships available at the docked station.
    :return: bool - True if the Cmdr has Horizons access.
    """
    economies_colony = False
    modules_horizons = False
    ship_horizons = False

    if isinstance(economies, dict):
        economies_colony = any(economy['name'] == 'Colony' for economy in economies.values())

    else:
        logger.error(f'economies type is {type(economies)}')

    if isinstance(modules, dict):
        modules_horizons = any(module.get('sku') == HORIZONS_SKU for module in modules.values())

    else:
        logger.error(f'modules type is {type(modules)}')

    if isinstance(ships, dict):
        if ships.get('shipyard_list') is not None:
            if isinstance(ships.get('shipyard_list'), dict):
                ship_horizons = any(ship.get('sku') == HORIZONS_SKU for ship in ships['shipyard_list'].values())

            else:
                logger.debug('ships["shipyard_list"] is not dict - FC or Damaged Station?')

        else:
            logger.debug('ships["shipyard_list"] is None - FC or Damaged Station?')

    else:
        logger.error(f'ships type is {type(ships)}')

    return economies_colony or modules_horizons or ship_horizons


def dashboard_entry(cmdr: str, is_beta: bool, entry: Dict[str, Any]) -> None:
    """
    Process Status.json data to track things like current Body.

    :param cmdr: Current Commander name.
    :param is_beta: Whether non-live game version was detected.
    :param entry: The latest Status.json data.
    """
    this.status_body_name = None
    if 'BodyName' in entry:
        if not isinstance(entry['BodyName'], str):
            logger.warning(f'BodyName was present but not a string! "{entry["BodyName"]}" ({type(entry["BodyName"])})')

        else:
            this.status_body_name = entry['BodyName']

    tracking_ui_update()
