"""
eddn.py - Exporting Data to EDDN.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This is an EDMC 'core' plugin.
All EDMC plugins are *dynamically* loaded at run-time.

We build for Windows using `py2exe`.
`py2exe` can't possibly know about anything in the dynamically loaded core plugins.

Thus, you **MUST** check if any imports you add in this file are only
referenced in this file (or only in any other core plugin), and if so...

    YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
    `build.py` TO ENSURE THE FILES ARE ACTUALLY PRESENT
    IN AN END-USER INSTALLATION ON WINDOWS.
"""
from __future__ import annotations

import http
import itertools
import json
import os
import pathlib
import re
import sqlite3
import tkinter as tk
from platform import system
from textwrap import dedent
from threading import Lock
from tkinter import ttk
from typing import Any, Iterator, Mapping, MutableMapping
import requests
import companion
import edmc_data
import killswitch
import plug
from companion import CAPIData, category_map
from config import applongname, appname, appversion_nobuild, config, debug_senders, user_agent
from EDMCLogging import get_main_logger
from monitor import monitor
from prefs import prefsVersion
from ttkHyperlinkLabel import HyperlinkLabel
from util import text
from l10n import translations as tr

logger = get_main_logger()


class This:
    """Holds module globals."""

    def __init__(self):
        # Game version and build
        self.game_version = ""
        self.game_build = ""
        # Commander Name
        self.cmdr_name = ""

        # Track if we're on foot
        self.on_foot = False
        # Track if we're docked
        self.docked = False

        # Horizons ?
        self.horizons = False
        # Running under Odyssey?
        self.odyssey = False

        # Track location to add to Journal events
        self.system_address: str | None = None
        self.system_name: str | None = None
        self.coordinates: tuple | None = None
        self.body_name: str | None = None
        self.body_id: int | None = None
        self.body_type: int | None = None
        self.station_name: str | None = None
        self.station_type: str | None = None
        self.station_marketid: str | None = None
        # Track Status.json data
        self.status_body_name: str | None = None

        # Avoid duplicates
        self.marketId: str | None = None
        self.commodities: list[dict[str, Any]] | None = None
        self.outfitting: tuple[bool, list[str]] | None = None
        self.shipyard: tuple[bool, list[Mapping[str, Any]]] | None = None
        self.fcmaterials_marketid: int = 0
        self.fcmaterials: list[dict[str, Any]] | None = None
        self.fcmaterials_capi_marketid: int = 0
        self.fcmaterials_capi: list[dict[str, Any]] | None = None

        # For the tkinter parent window, so we can call update_idletasks()
        self.parent: tk.Tk

        # To hold EDDN class instance
        self.eddn: EDDN

        # tkinter UI bits.
        self.eddn_station: tk.IntVar
        self.eddn_station_button: ttk.Checkbutton

        self.eddn_system: tk.IntVar
        self.eddn_system_button: ttk.Checkbutton

        self.eddn_delay: tk.IntVar
        self.eddn_delay_button: ttk.Checkbutton

        # Tracking UI
        self.ui: ttk.Frame
        self.ui_system_name: ttk.Label
        self.ui_system_address: ttk.Label
        self.ui_j_body_name: ttk.Label
        self.ui_j_body_id: ttk.Label
        self.ui_j_body_type: ttk.Label
        self.ui_s_body_name: ttk.Label
        self.ui_station_name: ttk.Label
        self.ui_station_type: ttk.Label
        self.ui_station_marketid: ttk.Label


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


class EDDNSender:
    """Handle sending of EDDN messages to the Gateway."""

    SQLITE_DB_FILENAME_V1 = 'eddn_queue-v1.db'
    # EDDN schema types that pertain to station data
    STATION_SCHEMAS = ('commodity', 'fcmaterials_capi', 'fcmaterials_journal', 'outfitting', 'shipyard')
    TIMEOUT = 10  # requests timeout
    UNKNOWN_SCHEMA_RE = re.compile(
        r"^FAIL: \[JsonValidationException\('Schema "
        r"https://eddn.edcd.io/schemas/(?P<schema_name>.+)/(?P<schema_version>[0-9]+) is unknown, "
        r"unable to validate.',\)]$"
    )

    def __init__(self, eddn: 'EDDN', eddn_endpoint: str) -> None:
        """
        Prepare the system for processing messages.

        - Ensure the sqlite3 database for EDDN replays exists and has schema.
        - Convert any legacy file into the database.
        - (Future) Handle any database migrations.

        :param eddn: Reference to the `EDDN` instance this is for.
        :param eddn_endpoint: Where messages should be sent.
        """
        self.eddn = eddn
        self.eddn_endpoint = eddn_endpoint
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent

        self.db_conn = self.sqlite_queue_v1()
        self.db = self.db_conn.cursor()

        #######################################################################
        # Queue database migration
        #######################################################################
        self.convert_legacy_file()
        #######################################################################

        self.queue_processing = Lock()
        # Initiate retry/send-now timer
        logger.trace_if(
            "plugin.eddn.send",
            f"First queue run scheduled for {self.eddn.REPLAY_STARTUP_DELAY}ms from now"
        )
        if not os.getenv("EDMC_NO_UI"):
            self.eddn.parent.after(self.eddn.REPLAY_STARTUP_DELAY, self.queue_check_and_send, True)

    def sqlite_queue_v1(self) -> sqlite3.Connection:
        """
        Initialise a v1 EDDN queue database.

        :return: sqlite3 connection
        """
        db_conn = sqlite3.connect(config.app_dir_path / self.SQLITE_DB_FILENAME_V1)
        db = db_conn.cursor()

        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created TEXT NOT NULL,
                    cmdr TEXT NOT NULL,
                    edmc_version TEXT,
                    game_version TEXT,
                    game_build TEXT,
                    message TEXT NOT NULL
                )
            """)

            db.execute("CREATE INDEX IF NOT EXISTS messages_created ON messages (created)")
            db.execute("CREATE INDEX IF NOT EXISTS messages_cmdr ON messages (cmdr)")

            logger.info("New 'eddn_queue-v1.db' created")

        except sqlite3.OperationalError as e:
            if str(e) != "table messages already exists":
                # Cleanup, as schema creation failed
                db.close()
                db_conn.close()
                raise e

        return db_conn

    def convert_legacy_file(self):
        """Convert a legacy file's contents into the sqlite3 db."""
        filename = config.app_dir_path / 'replay.jsonl'
        try:
            with open(filename, 'r+', buffering=1) as replay_file:
                logger.info("Converting legacy `replay.jsonl` to `eddn_queue-v1.db`")
                for line in replay_file:
                    cmdr, msg = json.loads(line)
                    self.add_message(cmdr, msg)

        except FileNotFoundError:
            return

        logger.info("Conversion to `eddn_queue-v1.db` complete, removing `replay.jsonl`")
        # Best effort at removing the file/contents
        with open(filename, 'w') as replay_file:
            replay_file.truncate()
        os.unlink(filename)

    def close(self) -> None:
        """Clean up any resources."""
        logger.debug('Closing db cursor.')
        if self.db:
            self.db.close()

        logger.debug('Closing db connection.')
        if self.db_conn:
            self.db_conn.close()

        logger.debug('Closing EDDN requests.Session.')
        self.session.close()

    def add_message(self, cmdr: str, msg: MutableMapping[str, Any]) -> int:
        """
        Add an EDDN message to the database.

        `msg` absolutely needs to be the **FULL** EDDN message, including all
        of `header`, `$schemaRef` and `message`.  Code handling this not being
        the case is only for loading the legacy `replay.json` file messages.

        NB: Although `cmdr` *should* be the same as `msg->header->uploaderID`
            we choose not to assume that.

        :param cmdr: Name of the Commander that created this message.
        :param msg: The full, transmission-ready, EDDN message.
        :return: ID of the successfully inserted row.
        """
        logger.trace_if("plugin.eddn.send", f"Message for {msg['$schemaRef']=}")
        # Cater for legacy replay.json messages
        if 'header' not in msg:
            msg['header'] = {
                # We have to lie and say it's *this* version, but denote that
                # it might not actually be this version.
                'softwareName': f'{applongname} [{system()}]'
                                ' (legacy replay)',
                'softwareVersion': str(appversion_nobuild()),
                'uploaderID': cmdr,
                'gameversion': '',  # Can't add what we don't know
                'gamebuild': '',  # Can't add what we don't know
            }

        created = msg['message']['timestamp']
        edmc_version = msg['header']['softwareVersion']
        game_version = msg['header'].get('gameversion', '')
        game_build = msg['header'].get('gamebuild', '')
        uploader = msg['header']['uploaderID']

        try:
            self.db.execute(
                """
                INSERT INTO messages (
                    created, cmdr, edmc_version, game_version, game_build, message
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (created, uploader, edmc_version, game_version, game_build, json.dumps(msg))
            )
            self.db_conn.commit()

        except Exception:
            logger.exception('INSERT error')
            # Can't possibly be a valid row id
            return -1

        logger.trace_if("plugin.eddn.send", f"Message for {msg['$schemaRef']=} recorded, id={self.db.lastrowid}")
        return self.db.lastrowid or -1

    def delete_message(self, row_id: int) -> None:
        """
        Delete a queued message by row id.

        :param row_id: id of message to be deleted.
        """
        logger.trace_if("plugin.eddn.send", f"Deleting message with {row_id=}")
        self.db.execute(
            """
            DELETE FROM messages WHERE id = :row_id
            """,
            {'row_id': row_id}
        )
        self.db_conn.commit()

    def send_message_by_id(self, id: int):
        """
        Transmit the message identified by the given ID.

        :param id:
        :return:
        """
        logger.trace_if("plugin.eddn.send", f"Sending message with {id=}")
        self.db.execute(
            """
            SELECT * FROM messages WHERE id = :row_id
            """,
            {'row_id': id}
        )
        row = dict(zip([c[0] for c in self.db.description], self.db.fetchone()))

        try:
            if self.send_message(row['message']):
                self.delete_message(id)
                return True

        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTPError: {str(e)}")

        return False

    def set_ui_status(self, text: str) -> None:
        """
        Set the UI status text, if applicable.

        When running as a CLI there is no such thing, so log to INFO instead.
        :param text: The status text to be set/logged.
        """
        if os.getenv('EDMC_NO_UI'):
            logger.info(text)
            return

        self.eddn.parent.nametowidget(f".{appname.lower()}.status")['text'] = text

    def send_message(self, msg: str) -> bool:
        """
        Transmit a fully-formed EDDN message to the Gateway.

        If this is called then the attempt *will* be made.  This is not where
        options to not send to EDDN, or to delay the sending until docked,
        are checked.

        It *is* however the one 'sending' place that the EDDN killswitches are checked.

        Should catch and handle all failure conditions.  A `True` return might
        mean that the message was successfully sent, *or* that this message
        should not be retried after a failure, i.e. too large.

        :param msg: Fully formed, string, message.
        :return: `True` for "now remove this message from the queue"
        """
        logger.trace_if("plugin.eddn.send", "Sending message")
        should_return: bool
        new_data: dict[str, Any]

        should_return, new_data = killswitch.check_killswitch('plugins.eddn.send', json.loads(msg))
        if should_return:
            logger.warning('eddn.send has been disabled via killswitch. Returning.')
            return False

        # Even the smallest possible message compresses somewhat, so always compress
        encoded, compressed = text.gzip(json.dumps(new_data, separators=(',', ':')), max_size=0)
        headers: dict[str, str] | None = None
        if compressed:
            headers = {'Content-Encoding': 'gzip'}

        try:
            r = self.session.post(self.eddn_endpoint, data=encoded, timeout=self.TIMEOUT, headers=headers)
            if r.status_code == requests.codes.ok:
                return True

            if r.status_code == http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                extra_data = {
                    'schema_ref': new_data.get('$schemaRef', 'Unset $schemaRef!'),
                    'sent_data_len': str(len(encoded)),
                }

                if '/journal/' in extra_data['schema_ref']:
                    extra_data['event'] = new_data.get('message', {}).get('event', 'No Event Set')

                self._log_response(r, header_msg='Got "Payload Too Large" while POSTing data', **extra_data)
                return True

            self._log_response(r, header_msg="Status from POST wasn't 200 (OK)")
            r.raise_for_status()

        except requests.exceptions.HTTPError as e:
            if unknown_schema := self.UNKNOWN_SCHEMA_RE.match(e.response.text):  # type: ignore
                logger.debug(f"EDDN doesn't (yet?) know about schema: {unknown_schema['schema_name']}"
                             f"/{unknown_schema['schema_version']}")
                # This dropping is to cater for the time period when EDDN doesn't *yet* support a new schema.
                return True

            if e.response.status_code == http.HTTPStatus.BAD_REQUEST:  # type: ignore
                # EDDN straight up says no, so drop the message
                logger.debug(f"EDDN responded '400 Bad Request' to the message, dropping:\n{msg!r}")
                return True

            # This should catch anything else, e.g. timeouts, gateway errors
            self.set_ui_status(self.http_error_to_log(e))

        except requests.exceptions.RequestException as e:
            logger.debug('Failed sending', exc_info=e)
            # LANG: Error while trying to send data to EDDN
            self.set_ui_status(tr.tl("Error: Can't connect to EDDN"))

        except Exception as e:
            logger.debug('Failed sending', exc_info=e)
            self.set_ui_status(str(e))

        return False

    def queue_check_and_send(self, reschedule: bool = False) -> None:  # noqa: CCR001
        """
        Check if we should be sending queued messages, and send if we should.

        :param reschedule: Boolean indicating if we should call `after()` again.
        """
        logger.trace_if("plugin.eddn.send", "Called")
        # Mutex in case we're already processing
        if not self.queue_processing.acquire(blocking=False):
            logger.trace_if("plugin.eddn.send", "Couldn't obtain mutex")
            if reschedule:
                logger.trace_if(
                    "plugin.eddn.send",
                    f"Next run scheduled for {self.eddn.REPLAY_PERIOD}ms from now",
                )
                self.eddn.parent.after(
                    self.eddn.REPLAY_PERIOD, self.queue_check_and_send, reschedule
                )

            else:
                logger.trace_if(
                    "plugin.eddn.send",
                    "NO next run scheduled (there should be another one already set)",
                )

            return
        logger.trace_if("plugin.eddn.send", "Obtained mutex")
        # Used to indicate if we've rescheduled at the faster rate already.
        have_rescheduled = False
        # We send either if docked or 'Delay sending until docked' not set
        if this.docked or not config.get_int('output') & config.OUT_EDDN_DELAY:
            logger.trace_if("plugin.eddn.send", "Should send")
            # We need our own cursor here, in case the semantics of
            # tk `after()` could allow this to run in the middle of other
            # database usage.
            db_cursor = self.db_conn.cursor()

            # Options:
            #  1. Process every queued message, regardless.
            #  2. Bail if we get any sort of connection error from EDDN.

            # Every queued message that is for *this* commander.  We do **NOT**
            # check if it's station/not-station, as the control of if a message
            # was even created, versus the Settings > EDDN options, is applied
            # *then*, not at time of sending.
            try:
                db_cursor.execute(
                    """
                    SELECT id FROM messages
                    ORDER BY created
                    LIMIT 1
                    """
                )

            except Exception:
                logger.exception("DB error querying queued messages")

            else:
                row = db_cursor.fetchone()
                if row:
                    row = dict(zip([c[0] for c in db_cursor.description], row))
                    if self.send_message_by_id(row['id']):
                        # If `True` was returned then we're done with this message.
                        #  `False` means "failed to send, but not because the message
                        #   is bad", i.e. an EDDN Gateway problem.  Thus, in that case
                        #   we do *NOT* schedule attempting the next message.
                        # Always re-schedule as this is only a "Don't hammer EDDN" delay
                        logger.trace_if("plugin.eddn.send", f"Next run scheduled for {self.eddn.REPLAY_DELAY}ms from "
                                                            "now")
                        self.eddn.parent.after(self.eddn.REPLAY_DELAY, self.queue_check_and_send, reschedule)
                        have_rescheduled = True

                db_cursor.close()

        else:
            logger.trace_if("plugin.eddn.send", "Should NOT send")

        self.queue_processing.release()
        logger.trace_if("plugin.eddn.send", "Mutex released")
        if reschedule and not have_rescheduled:
            # Set us up to run again per the configured period
            logger.trace_if("plugin.eddn.send", f"Next run scheduled for {self.eddn.REPLAY_PERIOD}ms from now")
            self.eddn.parent.after(self.eddn.REPLAY_PERIOD, self.queue_check_and_send, reschedule)

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

    @staticmethod
    def http_error_to_log(exception: requests.exceptions.HTTPError) -> str:
        """Convert an exception from raise_for_status to a log message and displayed error."""
        status_code = exception.errno

        if status_code == 429:  # HTTP UPGRADE REQUIRED
            logger.warning('EDMC is sending schemas that are too old')
            # LANG: EDDN has banned this version of our client
            return tr.tl('EDDN Error: EDMC is too old for EDDN. Please update.')

        if status_code == 400:
            # we a validation check or something else.
            logger.warning(f'EDDN Error: {status_code} -- {exception.response}')
            # LANG: EDDN returned an error that indicates something about what we sent it was wrong
            return tr.tl('EDDN Error: Validation Failed (EDMC Too Old?). See Log')

        logger.warning(f'Unknown status code from EDDN: {status_code} -- {exception.response}')
        # LANG: EDDN returned some sort of HTTP error, one we didn't expect. {STATUS} contains a number
        return tr.tl('EDDN Error: Returned {STATUS} status code').format(STATUS=status_code)


# TODO: a good few of these methods are static or could be classmethods. they should be created as such.
class EDDN:
    """EDDN Data export."""

    DEFAULT_URL = 'https://eddn.edcd.io:4430/upload/'
    if 'eddn' in debug_senders:
        DEFAULT_URL = f'http://{edmc_data.DEBUG_WEBSERVER_HOST}:{edmc_data.DEBUG_WEBSERVER_PORT}/eddn'

    # FIXME: Change back to `300_000`
    REPLAY_STARTUP_DELAY = 10_000  # Delay during startup before checking queue [milliseconds]
    REPLAY_PERIOD = 300_000  # How often to try (re-)sending the queue, [milliseconds]
    REPLAY_DELAY = 400  # Roughly two messages per second, accounting for send delays [milliseconds]
    REPLAYFLUSH = 20  # Update log on disk roughly every 10 seconds
    MODULE_RE = re.compile(r'^Hpt_|^Int_|Armour_', re.IGNORECASE)
    CANONICALISE_RE = re.compile(r'\$(.+)_name;')
    CAPI_LOCALISATION_RE = re.compile(r'^loc[A-Z].+')

    def __init__(self, parent: tk.Tk):
        self.parent: tk.Tk = parent

        if config.eddn_url is not None:
            self.eddn_url = config.eddn_url

        else:
            self.eddn_url = self.DEFAULT_URL

        self.sender = EDDNSender(self, self.eddn_url)

        self.fss_signals: list[Mapping[str, Any]] = []

    def close(self):
        """Close down the EDDN class instance."""
        logger.debug('Closing Sender...')
        if self.sender:
            self.sender.close()

        logger.debug('Done.')

    def export_commodities(self, data: CAPIData, is_beta: bool) -> None:  # noqa: CCR001
        """
        Update EDDN with the commodities on the current (lastStarport) station.

        Once the send is complete, this.commodities is updated with the new data.

        NB: This does *not* go through the replaylog, unlike most of the
        Journal-sourced data.  This kind of timely data is often rejected by
        listeners if 'too old' anyway, so little point.

        :param data: a dict containing the starport data
        :param is_beta: whether or not we're currently in beta mode
        """
        should_return: bool
        new_data: dict[str, Any]
        should_return, new_data = killswitch.check_killswitch('capi.request./market', {})
        if should_return:
            logger.warning("capi.request./market has been disabled by killswitch.  Returning.")
            return

        should_return, new_data = killswitch.check_killswitch('eddn.capi_export.commodities', {})
        if should_return:
            logger.warning("eddn.capi_export.commodities has been disabled by killswitch.  Returning.")
            return

        modules, ships = self.safe_modules_and_ships(data)
        horizons: bool = capi_is_horizons(
            data['lastStarport'].get('economies', {}),
            modules,
            ships
        )
        commodities: list[dict[str, Any]] = []
        for commodity in data['lastStarport'].get('commodities') or []:
            # Check 'marketable' and 'not prohibited'
            if (category_map.get(commodity['categoryname'], True)
                    and not commodity.get('legality')):
                commodities.append({
                    'name': commodity['name'].lower(),
                    'meanPrice': int(commodity['meanPrice']),
                    'buyPrice': int(commodity['buyPrice']),
                    'stock': int(commodity['stock']),
                    'stockBracket': commodity['stockBracket'],
                    'sellPrice': int(commodity['sellPrice']),
                    'demand': int(commodity['demand']),
                    'demandBracket': commodity['demandBracket'],
                })

                if commodity['statusFlags']:
                    commodities[-1]['statusFlags'] = commodity['statusFlags']

        commodities.sort(key=lambda c: c['name'])

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that
        # tools can update in a timely manner.
        if this.commodities != commodities:
            message: dict[str, Any] = {
                'timestamp': data['timestamp'],
                'systemName': data['lastSystem']['name'],
                'stationName': data['lastStarport']['name'],
                'marketId': data['lastStarport']['id'],
                'commodities': commodities,
                'horizons': horizons,
                'odyssey': this.odyssey,
            }

            if 'economies' in data['lastStarport']:
                message['economies'] = sorted(
                    (x for x in (data['lastStarport']['economies'] or {}).values()), key=lambda x: x['name']
                )

            if 'prohibited' in data['lastStarport']:
                message['prohibited'] = sorted(x for x in (data['lastStarport']['prohibited'] or {}).values())

            self.send_message(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message':    message,
                'header':     self.standard_header(
                    game_version=self.capi_gameversion_from_host_endpoint(
                        data.source_host, companion.Session.FRONTIER_CAPI_PATH_MARKET
                    ),
                    game_build=''
                ),
            })

        this.commodities = commodities

        # Send any FCMaterials.json-equivalent 'orders' as well
        self.export_capi_fcmaterials(data, is_beta, horizons)

    def safe_modules_and_ships(self, data: Mapping[str, Any]) -> tuple[dict, dict]:
        """
        Produce a sanity-checked version of ships and modules from CAPI data.

        Principally this catches where the supplied CAPI data either doesn't
        contain expected elements, or they're not of the expected type (e.g.
        a list instead of a dict).

        :param data: The raw CAPI data.
        :return: Sanity-checked data.
        """
        modules: dict[str, Any] = data['lastStarport'].get('modules')
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

        ships: dict[str, Any] = data['lastStarport'].get('ships')
        if ships is None or not isinstance(ships, dict):
            if ships is None:
                logger.debug('ships was None')

            else:
                logger.error(f'ships was neither None nor a dict! Type = {type(ships)}')
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
        should_return: bool
        new_data: dict[str, Any]
        should_return, new_data = killswitch.check_killswitch('capi.request./shipyard', {})
        if should_return:
            logger.warning("capi.request./shipyard has been disabled by killswitch.  Returning.")
            return

        should_return, new_data = killswitch.check_killswitch('eddn.capi_export.outfitting', {})
        if should_return:
            logger.warning("eddn.capi_export.outfitting has been disabled by killswitch.  Returning.")
            return

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

        outfitting: list[str] = sorted(
            self.MODULE_RE.sub(lambda match: match.group(0).capitalize(), mod['name'].lower()) for mod in to_search
        )

        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send_message(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': {
                    'timestamp': data['timestamp'],
                    'systemName': data['lastSystem']['name'],
                    'stationName': data['lastStarport']['name'],
                    'marketId': data['lastStarport']['id'],
                    'horizons': horizons,
                    'modules': outfitting,
                    'odyssey': this.odyssey,
                },
                'header': self.standard_header(
                    game_version=self.capi_gameversion_from_host_endpoint(
                        data.source_host, companion.Session.FRONTIER_CAPI_PATH_SHIPYARD
                    ),
                    game_build=''
                ),
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
        should_return: bool
        new_data: dict[str, Any]
        should_return, new_data = killswitch.check_killswitch('capi.request./shipyard', {})
        if should_return:
            logger.warning("capi.request./shipyard has been disabled by killswitch.  Returning.")
            return

        should_return, new_data = killswitch.check_killswitch('eddn.capi_export.shipyard', {})
        if should_return:
            logger.warning("eddn.capi_export.shipyard has been disabled by killswitch.  Returning.")
            return

        modules, ships = self.safe_modules_and_ships(data)

        horizons: bool = capi_is_horizons(
            data['lastStarport'].get('economies', {}),
            modules,
            ships
        )

        shipyard: list[Mapping[str, Any]] = sorted(
            itertools.chain(
                (ship['name'].lower() for ship in (ships['shipyard_list'] or {}).values()),
                (ship['name'].lower() for ship in ships['unavailable_list'] or {}),
            )
        )
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send_message(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': {
                    'timestamp': data['timestamp'],
                    'systemName': data['lastSystem']['name'],
                    'stationName': data['lastStarport']['name'],
                    'marketId': data['lastStarport']['id'],
                    'horizons': horizons,
                    'ships': shipyard,
                    'odyssey': this.odyssey,
                },
                'header': self.standard_header(
                    game_version=self.capi_gameversion_from_host_endpoint(
                        data.source_host, companion.Session.FRONTIER_CAPI_PATH_SHIPYARD
                    ),
                    game_build=''
                ),
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
        items: list[Mapping[str, Any]] = entry.get('Items') or []
        commodities: list[dict[str, Any]] = sorted(
            (
                {
                    'name': self.canonicalise(commodity['Name']),
                    'meanPrice': commodity['MeanPrice'],
                    'buyPrice': commodity['BuyPrice'],
                    'stock': commodity['Stock'],
                    'stockBracket': commodity['StockBracket'],
                    'sellPrice': commodity['SellPrice'],
                    'demand': commodity['Demand'],
                    'demandBracket': commodity['DemandBracket'],
                }
                for commodity in items
            ),
            key=lambda c: c['name']
        )

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that
        # tools can update in a timely manner.
        if this.commodities != commodities:
            message: dict[str, Any] = {  # Yes, this is a broad type hint.
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message': {
                    'timestamp': entry['timestamp'],
                    'systemName': entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketId': entry['MarketID'],
                    'commodities': commodities,
                    'horizons': this.horizons,
                    'odyssey': this.odyssey,
                    'stationType': entry['StationType'],
                }
            }

            if entry.get('CarrierDockingAccess'):
                message['message']['carrierDockingAccess'] = entry['CarrierDockingAccess']

            self.send_message(cmdr, message)

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
        modules: list[Mapping[str, Any]] = entry.get('Items', [])
        horizons: bool = entry.get('Horizons', False)
        # outfitting = sorted([self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), module['Name'])
        # for module in modules if module['Name'] != 'int_planetapproachsuite'])
        outfitting: list[str] = sorted(
            self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), mod['Name']) for mod in
            filter(lambda m: m['Name'] != 'int_planetapproachsuite', modules)
        )
        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send_message(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': {
                    'timestamp':   entry['timestamp'],
                    'systemName':  entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketId':    entry['MarketID'],
                    'horizons':    horizons,
                    'modules':     outfitting,
                    'odyssey':     entry['odyssey']
                },
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
        ships: list[Mapping[str, Any]] = entry.get('Pricelist') or []
        horizons: bool = entry.get('Horizons', False)
        shipyard = sorted(ship['ShipType'] for ship in ships)
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send_message(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': {
                    'timestamp':   entry['timestamp'],
                    'systemName':  entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketId':    entry['MarketID'],
                    'horizons':    horizons,
                    'ships':       shipyard,
                    'odyssey':     entry['odyssey']
                },
            })

        # this.shipyard = (horizons, shipyard)

    def send_message(self, cmdr: str, msg: MutableMapping[str, Any]) -> None:
        """
        Send an EDDN message.

        :param cmdr: Commander name as passed in through `journal_entry()`.
        :param msg: The EDDN message body to be sent.
        """
        # Check if the user configured messages to be sent.
        #
        #   1. If this is a 'station' data message then check config.EDDN_SEND_STATION_DATA
        #   2. Else check against config.EDDN_SEND_NON_STATION *and* config.OUT_EDDN_DELAY
        if any(f'{s}' in msg['$schemaRef'] for s in EDDNSender.STATION_SCHEMAS):
            # 'Station data'
            if config.get_int('output') & config.OUT_EDDN_SEND_STATION_DATA:
                # And user has 'station data' configured to be sent
                logger.trace_if("plugin.eddn.send", "Recording/sending 'station' message")
                if 'header' not in msg:
                    msg['header'] = self.standard_header()

                msg_id = self.sender.add_message(cmdr, msg)
                # 'Station data' is never delayed on construction of message
                self.sender.send_message_by_id(msg_id)

        elif config.get_int('output') & config.OUT_EDDN_SEND_NON_STATION:
            # Any data that isn't 'station' is configured to be sent
            logger.trace_if("plugin.eddn.send", "Recording 'non-station' message")
            if 'header' not in msg:
                msg['header'] = self.standard_header()

            msg_id = self.sender.add_message(cmdr, msg)
            if this.docked or not config.get_int('output') & config.OUT_EDDN_DELAY:
                # No delay in sending configured, so attempt immediately
                logger.trace_if("plugin.eddn.send", "Sending 'non-station' message")
                self.sender.send_message_by_id(msg_id)

    def standard_header(
        self, game_version: str | None = None, game_build: str | None = None
    ) -> MutableMapping[str, Any]:
        """
        Return the standard header for an EDDN message, given tracked state.

        NB: This should *only* be called for newly constructed messages, not
        for either a legacy message or an already queued one!

        :return: The standard header
        """
        # We want to pass `''` sometimes, so can't just use a Truthiness test
        if game_version is not None:
            gv = game_version

        else:
            gv = this.game_version

        if game_build is not None:
            gb = game_build

        else:
            gb = this.game_build

        return {
            'softwareName':    f'{applongname} [{system()}]',
            'softwareVersion': str(appversion_nobuild()),
            'uploaderID':      this.cmdr_name,
            'gameversion':     gv,
            'gamebuild':       gb,
        }

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
        this.eddn.send_message(cmdr, msg)

    def entry_augment_system_data(
            self,
            entry: MutableMapping[str, Any],
            system_name: str,
            system_coordinates: list
    ) -> str | MutableMapping[str, Any]:
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

            entry['StarSystem'] = system_name

        if 'SystemAddress' not in entry:
            if this.system_address is None:
                logger.warning("this.systemaddress is None, can't add SystemAddress")
                return "this.systemaddress is None, can't add SystemAddress"

            entry['SystemAddress'] = this.system_address

        if 'StarPos' not in entry:
            # Prefer the passed-in version
            if system_coordinates is not None:
                entry['StarPos'] = system_coordinates

            elif this.coordinates is not None:
                entry['StarPos'] = list(this.coordinates)

            else:
                logger.warning("Neither this_coordinates or this.coordinates set, can't add StarPos")
                return 'No source for adding StarPos to EDDN message !'

        return entry

    def export_journal_fssdiscoveryscan(
            self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> str | None:
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
        # In this case should add StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssdiscoveryscan/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_navbeaconscan(
            self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> str | None:
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
        # In this case should add StarSystem and StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/navbeaconscan/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_codexentry(  # noqa: CCR001
            self, cmdr: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
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
        # In this case should add StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, entry['System'], system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret

        # Set BodyName if it's available from Status.json
        if this.status_body_name is None or not isinstance(this.status_body_name, str):
            logger.warning(f'this.status_body_name was not set properly:'
                           f' "{this.status_body_name}" ({type(this.status_body_name)})')

        # this.status_body_name is available for cross-checks, so try to set
        # BodyName and ID.
        else:
            # In case Frontier add it in
            if 'BodyName' not in entry:
                entry['BodyName'] = this.status_body_name

            # Frontier are adding this in Odyssey Update 12
            if 'BodyID' not in entry:
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

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_scanbarycentre(
            self, cmdr: str, system_starpos: list, is_beta: bool, entry: Mapping[str, Any]
    ) -> str | None:
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
        # In this case should add StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, entry['StarSystem'], system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/scanbarycentre/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_navroute(
            self, cmdr: str, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
        """
        Send a NavRoute to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
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
            # This can happen if first-load of the file failed, and we're simply
            # passing through the bare Journal event, so no need to alert
            # the user.
            return None

        #######################################################################
        # Elisions
        #######################################################################
        # In case Frontier ever add any
        entry = filter_localised(entry)
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

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_fcmaterials(
        self, cmdr: str, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
        """
        Send an FCMaterials message to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        # {
        #     "timestamp":"2022-06-08T12:44:19Z",
        #     "event":"FCMaterials",
        #     "MarketID":3700710912,
        #     "CarrierName":"PSI RORSCHACH",
        #     "CarrierID":"K4X-33F",
        #     "Items":[
        #         {
        #             "id":128961533,
        #             "Name":"$encryptedmemorychip_name;",
        #             "Name_Localised":"Encrypted Memory Chip",
        #             "Price":500,
        #             "Stock":0,
        #             "Demand":5
        #         },
        #
        #         { "id":128961537,
        #             "Name":"$memorychip_name;",
        #             "Name_Localised":"Memory Chip",
        #             "Price":600,
        #             "Stock":0,
        #             "Demand":5
        #             },
        #
        #         { "id":128972290,
        #             "Name":"$campaignplans_name;",
        #             "Name_Localised":"Campaign Plans",
        #             "Price":600,
        #             "Stock":5,
        #             "Demand":0
        #         }
        #     ]
        # }
        # Abort if we're not configured to send 'station' data.
        if not config.get_int('output') & config.OUT_EDDN_SEND_STATION_DATA:
            return None

        # Sanity check
        if 'Items' not in entry:
            logger.warning(f"FCMaterials didn't contain an Items array!\n{entry!r}")
            # This can happen if first-load of the file failed, and we're simply
            # passing through the bare Journal event, so no need to alert
            # the user.
            return None

        if this.fcmaterials_marketid == entry['MarketID']:
            if this.fcmaterials == entry['Items']:
                # Same FC, no change in Stock/Demand/Prices, so don't send
                return None

        this.fcmaterials_marketid = entry['MarketID']
        this.fcmaterials = entry['Items']

        #######################################################################
        # Elisions
        #######################################################################
        # There are Name_Localised key/values in the Items array members
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # None
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fcmaterials_journal/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_capi_fcmaterials(
        self, data: CAPIData, is_beta: bool, horizons: bool
    ) -> str | None:
        """
        Send CAPI-sourced 'onfootmicroresources' data on `fcmaterials/1` schema.

        :param data: the CAPI `/market` data
        :param is_beta: whether, or not we are in beta mode
        :param horizons: whether player is in Horizons
        """
        # Sanity check
        if 'lastStarport' not in data:
            return None

        if 'orders' not in data['lastStarport']:
            return None

        if 'onfootmicroresources' not in data['lastStarport']['orders']:
            return None

        items = data['lastStarport']['orders']['onfootmicroresources']
        if this.fcmaterials_capi_marketid == data['lastStarport']['id']:
            if this.fcmaterials_capi == items:
                # Same FC, no change in orders, so don't send
                return None

        this.fcmaterials_capi_marketid = data['lastStarport']['id']
        this.fcmaterials_capi = items

        #######################################################################
        # Elisions
        #######################################################################
        # There are localised key names for the resources
        items = capi_filter_localised(items)
        #######################################################################

        #######################################################################
        # EDDN `'message'` creation, and augmentations
        #######################################################################
        entry = {
            'timestamp':   data['timestamp'],
            'event':       'FCMaterials',
            'horizons':    horizons,
            'odyssey':     this.odyssey,
            'MarketID':    data['lastStarport']['id'],
            'CarrierID':   data['lastStarport']['name'],
            'Items':       items,
        }
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fcmaterials_capi/1{"/test" if is_beta else ""}',
            'message': entry,
            'header': self.standard_header(
                game_version=self.capi_gameversion_from_host_endpoint(
                    data.source_host, companion.Session.FRONTIER_CAPI_PATH_MARKET
                ), game_build=''
            ),
        }

        this.eddn.send_message(data['commander']['name'], msg)
        return None

    def export_journal_approachsettlement(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
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
        # Elisions
        #######################################################################
        # In case Frontier ever add any
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # In this case should add SystemName and StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/approachsettlement/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_fssallbodiesfound(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
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
        # Elisions
        #######################################################################
        # In case Frontier ever add any
        entry = filter_localised(entry)
        #######################################################################

        #######################################################################
        # Augmentations
        #######################################################################
        # In this case should add StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssallbodiesfound/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_fssbodysignals(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
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
        # In this case should add SystemName and StarPos, but only if the
        # SystemAddress of where we think we are matches.
        if this.system_address is None or this.system_address != entry['SystemAddress']:
            logger.warning("SystemAddress isn't current location! Can't add augmentations!")
            return 'Wrong System! Missed jump ?'

        ret = this.eddn.entry_augment_system_data(entry, system_name, system_starpos)
        if isinstance(ret, str):
            return ret

        entry = ret
        #######################################################################

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fssbodysignals/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def enqueue_journal_fsssignaldiscovered(self, entry: MutableMapping[str, Any]) -> None:
        """
        Queue up an FSSSignalDiscovered journal event for later sending.

        :param entry: the journal entry to batch
        """
        if entry is None or entry == "":
            logger.warning(f"Supplied event was empty: {entry!r}")
            return

        logger.trace_if("plugin.eddn.fsssignaldiscovered", f"Appending FSSSignalDiscovered entry:\n"
                        f" {json.dumps(entry)}")
        self.fss_signals.append(entry)

    def export_journal_fsssignaldiscovered(
        self, cmdr: str, system_name: str, system_starpos: list, is_beta: bool, entry: MutableMapping[str, Any]
    ) -> str | None:
        """
        Send an FSSSignalDiscovered message to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param system_name: Name of current star system
        :param system_starpos: Coordinates of current star system
        :param is_beta: whether or not we are in beta mode
        :param entry: the non-FSSSignalDiscovered journal entry that triggered this batch send
        """
        logger.trace_if("plugin.eddn.fsssignaldiscovered", f"This other event is: {json.dumps(entry)}")
        #######################################################################
        # Location cross-check and augmentation setup
        #######################################################################
        # Determine if this is Horizons order or Odyssey order
        if entry['event'] in ('Location', 'FSDJump', 'CarrierJump'):
            # Odyssey order, use this new event's data for cross-check
            aug_systemaddress = entry['SystemAddress']
            aug_starsystem = entry['StarSystem']
            aug_starpos = entry['StarPos']

        else:
            # Horizons order, so use tracked data for cross-check
            if this.system_address is None or system_name is None or system_starpos is None:
                logger.error(f'Location tracking failure: {this.system_address=}, {system_name=}, {system_starpos=}')
                return 'Current location not tracked properly, started after game?'

            aug_systemaddress = this.system_address
            aug_starsystem = system_name
            aug_starpos = system_starpos

        if aug_systemaddress != self.fss_signals[0]['SystemAddress']:
            logger.warning("First signal's SystemAddress doesn't match current location: "
                           f"{self.fss_signals[0]['SystemAddress']} != {aug_systemaddress}")
            self.fss_signals = []
            return 'Wrong System! Missed jump ?'
        #######################################################################

        # Build basis of message
        msg: dict = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/fsssignaldiscovered/1{"/test" if is_beta else ""}',
            'message': {
                "event": "FSSSignalDiscovered",
                "timestamp": self.fss_signals[0]['timestamp'],
                "SystemAddress": aug_systemaddress,
                "StarSystem": aug_starsystem,
                "StarPos": aug_starpos,
                "signals": [],
            }
        }

        # Now add the signals, checking each is for the correct system, dropping
        # any that aren't, and applying necessary elisions.
        for s in self.fss_signals:
            if s['SystemAddress'] != aug_systemaddress:
                logger.warning("Signal's SystemAddress not current system, dropping: "
                               f"{s['SystemAddress']} != {aug_systemaddress}")
                continue

            # Drop Mission USS signals.
            if "USSType" in s and s["USSType"] == "$USS_Type_MissionTarget;":
                logger.trace_if("plugin.eddn.fsssignaldiscovered", "USSType is $USS_Type_MissionTarget;, dropping")
                continue

            # Remove any _Localised keys (would only be in a USS signal)
            s = filter_localised(s)

            # Remove any key/values that shouldn't be there per signal
            s.pop('event', None)
            s.pop('horizons', None)
            s.pop('odyssey', None)
            s.pop('TimeRemaining', None)
            s.pop('SystemAddress', None)

            msg['message']['signals'].append(s)

        if not msg['message']['signals']:
            # No signals passed checks, so drop them all and return
            logger.debug('No signals after checks, so sending no message')
            self.fss_signals = []
            return None

        # `horizons` and `odyssey` augmentations
        msg['message']['horizons'] = entry['horizons']
        msg['message']['odyssey'] = entry['odyssey']

        logger.trace_if("plugin.eddn.fsssignaldiscovered", f"FSSSignalDiscovered batch is {json.dumps(msg)}")

        this.eddn.send_message(cmdr, msg)
        self.fss_signals = []

        return None

    def export_journal_dockingdenied(
            self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]
    ) -> str | None:
        """
        Send a DockingDenied to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        ___
        Example:
        {
            "timestamp":"2022-06-10T10:09:41Z",
            "event":"DockingDenied",
            "Reason":"RestrictedAccess",
            "MarketID":3706117376,
            "StationName":"V7G-T1G",
            "StationType":"FleetCarrier"
        }
        """
        #######################################################################
        # Elisions
        #######################################################################
        # In case Frontier ever add any
        entry = filter_localised(entry)

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/dockingdenied/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def export_journal_dockinggranted(
            self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]
    ) -> str | None:
        """
        Send a DockingDenied to EDDN on the correct schema.

        :param cmdr: the commander under which this upload is made
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        ___
        Example:
        {
            "timestamp":"2023-10-01T14:56:34Z",
            "event":"DockingGranted",
            "LandingPad":41,
            "MarketID":3227312896,
            "StationName":"Evans Horizons",
            "StationType":"Coriolis"
        }
        """
        #######################################################################
        # Elisions
        #######################################################################
        # In case Frontier ever add any
        entry = filter_localised(entry)

        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/dockinggranted/1{"/test" if is_beta else ""}',
            'message': entry
        }

        this.eddn.send_message(cmdr, msg)
        return None

    def canonicalise(self, item: str) -> str:
        """
        Canonicalise the given commodity name.

        :param item: Name of an commodity we want the canonical name for.
        :return: The canonical name for this commodity.
        """
        match = self.CANONICALISE_RE.match(item)
        return match and match.group(1) or item

    def capi_gameversion_from_host_endpoint(self, capi_host: str | None, capi_endpoint: str) -> str:
        """
        Return the correct CAPI gameversion string for the given host/endpoint.

        :param capi_host: CAPI host used.
        :param capi_endpoint: CAPI endpoint queried.
        :return: CAPI gameversion string.
        """
        gv = ''
        #######################################################################
        # Base string
        if capi_host in (companion.SERVER_LIVE, companion.SERVER_BETA):
            gv = 'CAPI-Live-'

        elif capi_host == companion.SERVER_LEGACY:
            gv = 'CAPI-Legacy-'

        else:
            # Technically incorrect, but it will inform listeners
            logger.error(f"{capi_host=} lead to bad gameversion")
            gv = 'CAPI-UNKNOWN-'
        #######################################################################

        #######################################################################
        # endpoint
        if capi_endpoint == companion.Session.FRONTIER_CAPI_PATH_MARKET:
            gv += 'market'

        elif capi_endpoint == companion.Session.FRONTIER_CAPI_PATH_SHIPYARD:
            gv += 'shipyard'

        else:
            # Technically incorrect, but it will inform listeners
            logger.error(f"{capi_endpoint=} lead to bad gameversion")
            gv += 'UNKNOWN'
        #######################################################################

        return gv


# Plugin callbacks
def plugin_start3(plugin_dir: str) -> str:
    """
    Start this plugin.

    :param plugin_dir: `str` - The full path to this plugin's directory.
    :return: `str` - Name of this plugin to use in UI.
    """
    return 'EDDN'


def plugin_app(parent: tk.Tk) -> ttk.Frame | None:
    """
    Set up any plugin-specific UI.

    In this case we need the tkinter parent in order to later call
    `update_idletasks()` on it, or schedule things with `after()`.

    :param parent: tkinter parent frame.
    :return: Optional tk.Frame, if the tracking UI is active.
    """
    this.parent = parent
    this.eddn = EDDN(parent)

    if config.eddn_tracking_ui:
        this.ui = ttk.Frame(parent)

        row = this.ui.grid_size()[1]

        #######################################################################
        # System
        #######################################################################
        # SystemName
        system_name_label = ttk.Label(this.ui, text="J:SystemName:")
        system_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_system_name = ttk.Label(this.ui, name='eddn_track_system_name', anchor=tk.W)
        this.ui_system_name.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # SystemAddress
        system_address_label = ttk.Label(this.ui, text="J:SystemAddress:")
        system_address_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_system_address = ttk.Label(this.ui, name='eddn_track_system_address', anchor=tk.W)
        this.ui_system_address.grid(row=row, column=1, sticky=tk.E)
        row += 1
        #######################################################################

        #######################################################################
        # Body
        #######################################################################
        # Body Name from Journal
        journal_body_name_label = ttk.Label(this.ui, text="J:BodyName:")
        journal_body_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_j_body_name = ttk.Label(this.ui, name='eddn_track_j_body_name', anchor=tk.W)
        this.ui_j_body_name.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # Body ID from Journal
        journal_body_id_label = ttk.Label(this.ui, text="J:BodyID:")
        journal_body_id_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_j_body_id = ttk.Label(this.ui, name='eddn_track_j_body_id', anchor=tk.W)
        this.ui_j_body_id.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # Body Type from Journal
        journal_body_type_label = ttk.Label(this.ui, text="J:BodyType:")
        journal_body_type_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_j_body_type = ttk.Label(this.ui, name='eddn_track_j_body_type', anchor=tk.W)
        this.ui_j_body_type.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # Body Name from Status.json
        status_body_name_label = ttk.Label(this.ui, text="S:BodyName:")
        status_body_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_s_body_name = ttk.Label(this.ui, name='eddn_track_s_body_name', anchor=tk.W)
        this.ui_s_body_name.grid(row=row, column=1, sticky=tk.E)
        row += 1
        #######################################################################

        #######################################################################
        # Station
        #######################################################################
        # Name
        status_station_name_label = ttk.Label(this.ui, text="J:StationName:")
        status_station_name_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_station_name = ttk.Label(this.ui, name='eddn_track_station_name', anchor=tk.W)
        this.ui_station_name.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # Type
        status_station_type_label = ttk.Label(this.ui, text="J:StationType:")
        status_station_type_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_station_type = ttk.Label(this.ui, name='eddn_track_station_type', anchor=tk.W)
        this.ui_station_type.grid(row=row, column=1, sticky=tk.E)
        row += 1
        # MarketID
        status_station_marketid_label = ttk.Label(this.ui, text="J:StationID:")
        status_station_marketid_label.grid(row=row, column=0, sticky=tk.W)
        this.ui_station_marketid = ttk.Label(this.ui, name='eddn_track_station_id', anchor=tk.W)
        this.ui_station_marketid.grid(row=row, column=1, sticky=tk.E)
        row += 1
        #######################################################################

        return this.ui

    return None


def tracking_ui_update() -> None:
    """Update the Tracking UI with current data, if required."""
    if not config.eddn_tracking_ui:
        return

    this.ui_system_name['text'] = '≪None≫'
    if this.system_name is not None:
        this.ui_system_name['text'] = this.system_name

    this.ui_system_address['text'] = '≪None≫'
    if this.system_address is not None:
        this.ui_system_address['text'] = this.system_address

    this.ui_j_body_name['text'] = '≪None≫'
    if this.body_name is not None:
        this.ui_j_body_name['text'] = this.body_name

    this.ui_j_body_id['text'] = '≪None≫'
    if this.body_id is not None:
        this.ui_j_body_id['text'] = str(this.body_id)

    this.ui_j_body_type['text'] = '≪None≫'
    if this.body_type is not None:
        this.ui_j_body_type['text'] = str(this.body_type)

    this.ui_s_body_name['text'] = '≪None≫'
    if this.status_body_name is not None:
        this.ui_s_body_name['text'] = this.status_body_name

    this.ui_station_name['text'] = '≪None≫'
    if this.station_name is not None:
        this.ui_station_name['text'] = this.station_name

    this.ui_station_type['text'] = '≪None≫'
    if this.station_type is not None:
        this.ui_station_type['text'] = this.station_type

    this.ui_station_marketid['text'] = '≪None≫'
    if this.station_marketid is not None:
        this.ui_station_marketid['text'] = this.station_marketid

    this.ui.update_idletasks()


def plugin_prefs(parent, cmdr: str, is_beta: bool) -> ttk.Frame:
    """
    Set up Preferences pane for this plugin.

    :param parent: tkinter parent to attach to.
    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :return: The tkinter frame we created.
    """
    PADX = 10  # noqa: N806
    BUTTONX = 12  # noqa: N806 # indent Checkbuttons and Radiobuttons
    PADY = 1  # noqa: N806

    if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
        output: int = config.OUT_EDDN_SEND_STATION_DATA | config.OUT_EDDN_SEND_NON_STATION  # default settings

    else:
        output = config.get_int('output')

    eddnframe = ttk.Frame(parent)

    cur_row = 0
    HyperlinkLabel(
        eddnframe,
        text='Elite Dangerous Data Network',
        url='https://github.com/EDCD/EDDN#eddn---elite-dangerous-data-network',
        underline=True
    ).grid(row=cur_row, padx=PADX, pady=PADY, sticky=tk.W)  # Don't translate
    cur_row += 1

    this.eddn_station = tk.IntVar(value=(output & config.OUT_EDDN_SEND_STATION_DATA) and 1)
    this.eddn_station_button = ttk.Checkbutton(
        eddnframe,
        # LANG: Enable EDDN support for station data checkbox label
        text=tr.tl('Send station data to the Elite Dangerous Data Network'),
        variable=this.eddn_station,
        command=prefsvarchanged
    )  # Output setting
    this.eddn_station_button.grid(row=cur_row, padx=BUTTONX, pady=PADY, sticky=tk.W)
    cur_row += 1

    this.eddn_system = tk.IntVar(value=(output & config.OUT_EDDN_SEND_NON_STATION) and 1)
    # Output setting new in E:D 2.2
    this.eddn_system_button = ttk.Checkbutton(
        eddnframe,
        # LANG: Enable EDDN support for system and other scan data checkbox label
        text=tr.tl('Send system and scan data to the Elite Dangerous Data Network'),
        variable=this.eddn_system,
        command=prefsvarchanged
    )
    this.eddn_system_button.grid(row=cur_row, padx=BUTTONX, pady=PADY, sticky=tk.W)
    cur_row += 1

    this.eddn_delay = tk.IntVar(value=(output & config.OUT_EDDN_DELAY) and 1)
    # Output setting under 'Send system and scan data to the Elite Dangerous Data Network' new in E:D 2.2
    this.eddn_delay_button = ttk.Checkbutton(
        eddnframe,
        # LANG: EDDN delay sending until docked option is on, this message notes that a send was skipped due to this
        text=tr.tl('Delay sending until docked'),
        variable=this.eddn_delay
    )
    this.eddn_delay_button.grid(row=cur_row, padx=BUTTONX, pady=PADY, sticky=tk.W)

    return eddnframe


def prefsvarchanged(event=None) -> None:
    """
    Handle changes to EDDN Preferences.

    :param event: tkinter event ?
    """
    # These two lines are legacy and probably not even needed
    this.eddn_station_button['state'] = tk.NORMAL
    this.eddn_system_button['state'] = tk.NORMAL
    # This line will grey out the 'Delay sending ...' option if the 'Send
    #  system and scan data' option is off.
    this.eddn_delay_button['state'] = tk.NORMAL if this.eddn_system.get() else tk.DISABLED


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
        (this.eddn_station.get() and config.OUT_EDDN_SEND_STATION_DATA) +
        (this.eddn_system.get() and config.OUT_EDDN_SEND_NON_STATION) +
        (this.eddn_delay.get() and config.OUT_EDDN_DELAY)
    )


def plugin_stop() -> None:
    """Handle stopping this plugin."""
    logger.debug('Calling this.eddn.close()')
    this.eddn.close()
    logger.debug('Done.')


def filter_localised(d: Mapping[str, Any]) -> dict[str, Any]:
    """
    Recursively remove any dict keys with names ending `_Localised` from a dict.

    :param d: dict to filter keys of.
    :return: The filtered dict.
    """
    filtered: dict[str, Any] = {}
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


def capi_filter_localised(d: Mapping[str, Any]) -> dict[str, Any]:
    """
    Recursively remove any dict keys for known CAPI 'localised' names.

    :param d: dict to filter keys of.
    :return: The filtered dict.
    """
    filtered: dict[str, Any] = {}
    for k, v in d.items():
        if EDDN.CAPI_LOCALISATION_RE.search(k):
            pass

        elif hasattr(v, 'items'):  # dict -> recurse
            filtered[k] = capi_filter_localised(v)

        elif isinstance(v, list):  # list of dicts -> recurse
            filtered[k] = [capi_filter_localised(x) if hasattr(x, 'items') else x for x in v]

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
) -> str | None:
    """
    Process a new Journal entry.

    :param cmdr: `str` - Name of current Cmdr.
    :param is_beta: `bool` - True if this is a beta version of the Game.
    :param system: `str` - Name of system Cmdr is in.
    :param station: `str` - Name of station Cmdr is docked at, if applicable.
    :param entry: `dict` - The data for this Journal entry.
    :param state: `dict` - Current `monitor.state` data.
    :return: `str` - Error message, or `None` if no errors.
    """
    should_return, new_data = killswitch.check_killswitch('plugins.eddn.journal', entry)
    if should_return:
        plug.show_error(tr.tl('EDDN journal handler disabled. See Log.'))  # LANG: Killswitch disabled EDDN
        return None

    should_return, new_data = killswitch.check_killswitch(f'plugins.eddn.journal.event.{entry["event"]}', new_data)
    if should_return:
        return None

    entry = new_data
    event_name = entry['event'].lower()

    this.cmdr_name = cmdr
    this.game_version = state['GameVersion']
    this.game_build = state['GameBuild']
    this.on_foot = state['OnFoot']
    this.docked = state['IsDocked']

    # Note if we're under Horizons and/or Odyssey
    # The only event these are already in is `LoadGame` which isn't sent to EDDN.
    this.horizons = entry['horizons'] = state['Horizons']
    this.odyssey = entry['odyssey'] = state['Odyssey']

    # Simple queue: send batched FSSSignalDiscovered once a non-FSSSignalDiscovered is observed
    if event_name != 'fsssignaldiscovered' and this.eddn.fss_signals:
        # We can't return here, we still might need to otherwise process this event,
        # so errors will never be shown to the user.
        this.eddn.export_journal_fsssignaldiscovered(
            cmdr,
            system,
            state['StarPos'],
            is_beta,
            entry
        )

    # Copy some state into module-held variables because we might need it
    # outside of this function.
    this.body_name = state['Body']
    this.body_id = state['BodyID']
    this.body_type = state['BodyType']
    this.coordinates = state['StarPos']
    this.system_address = state['SystemAddress']
    this.system_name = state['SystemName']
    this.station_name = state['StationName']
    this.station_type = state['StationType']
    this.station_marketid = state['MarketID']

    if event_name == 'docked':
        # Trigger a send/retry of pending EDDN messages
        this.eddn.parent.after(this.eddn.REPLAY_DELAY, this.eddn.sender.queue_check_and_send, False)

    elif event_name == 'music':
        if entry['MusicTrack'] == 'MainMenu':
            this.status_body_name = None

    tracking_ui_update()

    # Events with their own EDDN schema
    if config.get_int('output') & config.OUT_EDDN_SEND_NON_STATION and not state['Captain']:

        if event_name == 'fssdiscoveryscan':
            return this.eddn.export_journal_fssdiscoveryscan(cmdr, system, state['StarPos'], is_beta, entry)

        if event_name == 'navbeaconscan':
            return this.eddn.export_journal_navbeaconscan(cmdr, system, state['StarPos'], is_beta, entry)

        if event_name == 'codexentry':
            return this.eddn.export_journal_codexentry(cmdr, state['StarPos'], is_beta, entry)

        if event_name == 'scanbarycentre':
            return this.eddn.export_journal_scanbarycentre(cmdr, state['StarPos'], is_beta, entry)

        if event_name == 'navroute':
            return this.eddn.export_journal_navroute(cmdr, is_beta, entry)

        if event_name == 'fcmaterials':
            return this.eddn.export_journal_fcmaterials(cmdr, is_beta, entry)

        if event_name == "dockingdenied":
            return this.eddn.export_journal_dockingdenied(cmdr, is_beta, entry)

        if event_name == "dockinggranted":
            return this.eddn.export_journal_dockinggranted(cmdr, is_beta, entry)

        if event_name == 'approachsettlement':
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

        if event_name == 'fsssignaldiscovered':
            this.eddn.enqueue_journal_fsssignaldiscovered(entry)

        if event_name == 'fssallbodiesfound':
            return this.eddn.export_journal_fssallbodiesfound(
                cmdr,
                system,
                state['StarPos'],
                is_beta,
                entry
            )

        if event_name == 'fssbodysignals':
            return this.eddn.export_journal_fssbodysignals(
                cmdr,
                system,
                state['StarPos'],
                is_beta,
                entry
            )

    # Send journal schema events to EDDN, but not when on a crew
    if (config.get_int('output') & config.OUT_EDDN_SEND_NON_STATION and not state['Captain'] and
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
        if event_name == 'docked' and state['Body'] is not None:
            if state['BodyType'] == 'Planet':
                entry['Body'] = state['Body']
                entry['BodyType'] = state['BodyType']

        # The generic journal schema is for events:
        #   Docked, FSDJump, Scan, Location, SAASignalsFound, CarrierJump
        # (Also CodexEntry, but that has its own schema and handling).
        # Journals 2021-08-23 to 2022-05-29
        #                   StarSystem  SystemAddress  StarPos
        # Docked                Y             Y           N
        # FSDJump               Y             Y           Y
        # Scan                  Y             Y           N
        # Location              Y             Y           Y
        # SAASignalsFound       N             Y           N
        # CarrierJump           Y             Y           Y

        if 'SystemAddress' not in entry:
            logger.warning(f"journal schema event({entry['event']}) doesn't contain SystemAddress when it should, "
                           "aborting")
            return "No SystemAddress in event, aborting send"

        # add mandatory StarSystem and StarPos properties to events
        if 'StarSystem' not in entry:
            if this.system_address is None or this.system_address != entry['SystemAddress']:
                logger.warning(f"event({entry['event']}) has no StarSystem, but SystemAddress isn't current location")
                return "Wrong System! Delayed Scan event?"

            if not system:
                logger.warning(f"system is falsey, can't add StarSystem to {entry['event']} event")
                return "system is falsey, can't add StarSystem"

            entry['StarSystem'] = system

        if 'StarPos' not in entry:
            if not this.coordinates:
                logger.warning(f"this.coordinates is falsey, can't add StarPos to {entry['event']} event")
                return "this.coordinates is falsey, can't add StarPos"

            # Gazelle[TD] reported seeing a lagged Scan event with incorrect
            # augmented StarPos: <https://github.com/EDCD/EDMarketConnector/issues/961>
            if this.system_address is None or this.system_address != entry['SystemAddress']:
                logger.warning(f"event({entry['event']}) has no StarPos, but SystemAddress isn't current location")
                return "Wrong System! Delayed Scan event?"

            entry['StarPos'] = list(this.coordinates)

        try:
            this.eddn.export_journal_generic(cmdr, is_beta, filter_localised(entry))

        except requests.exceptions.RequestException as e:
            logger.debug('Failed in send_message', exc_info=e)
            return tr.tl("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

        except Exception as e:
            logger.debug('Failed in export_journal_generic', exc_info=e)
            return str(e)

    elif (config.get_int('output') & config.OUT_EDDN_SEND_STATION_DATA and not state['Captain'] and
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
            return tr.tl("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

        except Exception as e:
            logger.debug(f'Failed exporting {entry["event"]}', exc_info=e)
            return str(e)

    return None


def cmdr_data_legacy(data: CAPIData, is_beta: bool) -> str | None:
    """
    Process new CAPI data for Legacy galaxy.

    Ensuring the correct EDDN `header->gameversion` is achieved by use of
    `EDDN.capi_gameversion_from_host_endpoint()` in:

        `EDDN.export_outfitting()`
        `EDDN.export_shipyard()`
        `EDDN.export_outfitting()`

    Thus we can just call through to the 'not Legacy' version of this function.
    :param data: CAPI data to process.
    :param is_beta: bool - True if this is a beta version of the Game.
    :return: str - Error message, or `None` if no errors.
    """
    return cmdr_data(data, is_beta)


def cmdr_data(data: CAPIData, is_beta: bool) -> str | None:  # noqa: CCR001
    """
    Process new CAPI data for not-Legacy galaxy (might be beta).

    :param data: CAPI data to process.
    :param is_beta: bool - True if this is a beta version of the Game.
    :return: str - Error message, or `None` if no errors.
    """
    # 'Update' can trigger CAPI queries before plugins have been fed any
    # Journal events.  So this.cmdr_name might not be set otherwise.
    if (
        not this.cmdr_name
        and data.get('commander') and (cmdr_name := data['commander'].get('name'))
    ):
        this.cmdr_name = cmdr_name

    if (data['commander'].get('docked') or (this.on_foot and monitor.state['StationName'])
            and config.get_int('output') & config.OUT_EDDN_SEND_STATION_DATA):
        try:
            if this.marketId != data['lastStarport']['id']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = data['lastStarport']['id']

            status = this.parent.nametowidget(f".{appname.lower()}.status")
            old_status = status['text']
            if not old_status:
                # LANG: Status text shown while attempting to send data
                status['text'] = tr.tl('Sending data to EDDN...')
                status.update_idletasks()

            this.eddn.export_commodities(data, is_beta)
            this.eddn.export_outfitting(data, is_beta)
            this.eddn.export_shipyard(data, is_beta)
            if not old_status:
                status['text'] = ''
                status.update_idletasks()

        except requests.RequestException as e:
            logger.debug('Failed exporting data', exc_info=e)
            return tr.tl("Error: Can't connect to EDDN")  # LANG: Error while trying to send data to EDDN

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


def dashboard_entry(cmdr: str, is_beta: bool, entry: dict[str, Any]) -> None:
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
