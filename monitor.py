"""
monitor.py - Monitor for new Journal files and contents of latest.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import json
import pathlib
import queue
import re
import sys
import threading
from calendar import timegm
from collections import defaultdict
from os import SEEK_END, SEEK_SET, listdir
from os.path import basename, expanduser, getctime, isdir, join
from time import gmtime, localtime, mktime, sleep, strftime, strptime, time
from typing import TYPE_CHECKING, Any, BinaryIO, MutableMapping
import psutil
import semantic_version
import util_ships
from config import config, appname, appversion
from edmc_data import edmc_suit_shortnames, edmc_suit_symbol_localised, ship_name_map
from EDMCLogging import get_main_logger
from edshipyard import ships

if TYPE_CHECKING:
    import tkinter


logger = get_main_logger()
STARTUP = 'journal.startup'
MAX_NAVROUTE_DISCREPANCY = 5  # Timestamp difference in seconds
MAX_FCMATERIALS_DISCREPANCY = 5  # Timestamp difference in seconds

if sys.platform == 'win32':
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    from watchdog.observers import Observer
    from watchdog.observers.api import BaseObserver

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object  # dummy
    if TYPE_CHECKING:
        # this isn't ever used, but this will make type checking happy
        from watchdog.events import FileSystemEvent
        from watchdog.observers import Observer
        from watchdog.observers.api import BaseObserver


# Journal handler
class EDLogs(FileSystemEventHandler):
    """Monitoring of Journal files."""

    # Magic with FileSystemEventHandler can confuse type checkers when they do not have access to every import
    _POLL = 1		# Polling while running is cheap, so do it often
    _INACTIVE_POLL = 10		# Polling while not running isn't as cheap, so do it less often
    _RE_CANONICALISE = re.compile(r'\$(.+)_name;')
    _RE_CATEGORY = re.compile(r'\$MICRORESOURCE_CATEGORY_(.+);')
    _RE_LOGFILE = re.compile(r'^Journal(Alpha|Beta)?\.[0-9]{2,4}(-)?[0-9]{2}(-)?[0-9]{2}(T)?[0-9]{2}[0-9]{2}[0-9]{2}'
                             r'\.[0-9]{2}\.log$')
    _RE_SHIP_ONFOOT = re.compile(r'^(FlightSuit|UtilitySuit_Class.|TacticalSuit_Class.|ExplorationSuit_Class.)$')

    def __init__(self) -> None:
        # TODO(A_D): A bunch of these should be switched to default values (eg '' for strings) and no longer be Optional
        FileSystemEventHandler.__init__(self)  # futureproofing - not need for current version of watchdog
        self.root: 'tkinter.Tk' = None  # type: ignore # Don't use Optional[] - mypy thinks no methods
        self.currentdir: str | None = None  # The actual logdir that we're monitoring
        self.logfile: str | None = None
        self.observer: BaseObserver | None = None
        self.observed = None  # a watchdog ObservedWatch, or None if polling
        self.thread: threading.Thread | None = None
        # For communicating journal entries back to main thread
        self.event_queue: queue.Queue = queue.Queue(maxsize=0)

        # On startup we might be:
        # 1) Looking at an old journal file because the game isn't running or the user has exited to the main menu.
        # 2) Looking at an empty journal (only 'Fileheader') because the user is at the main menu.
        # 3) In the middle of a 'live' game.
        # If 1 or 2 a LoadGame event will happen when the game goes live.
        # If 3 we need to inject a special 'StartUp' event since consumers won't see the LoadGame event.
        self.live = False
        # And whilst we're parsing *only to catch up on state*, we might not want to fully process some things
        self.catching_up = False

        self.game_was_running = False  # For generation of the "ShutDown" event
        self.running_process = None

        # Context for journal handling
        self.version: str | None = None
        self.version_semantic: semantic_version.Version | None = None
        self.is_beta = False
        self.mode: str | None = None
        self.group: str | None = None
        self.cmdr: str | None = None
        self.started: int | None = None  # Timestamp of the LoadGame event
        self.slef: str | None = None

        self._navroute_retries_remaining = 0
        self._last_navroute_journal_timestamp: float | None = None

        self._fcmaterials_retries_remaining = 0
        self._last_fcmaterials_journal_timestamp: float | None = None

        # For determining Live versus Legacy galaxy.
        # The assumption is gameversion will parse via `coerce()` and always
        # be >= for Live, and < for Legacy.
        self.live_galaxy_base_version = semantic_version.Version('4.0.0')

        self.__init_state()

    def __init_state(self) -> None:
        # Cmdr state shared with EDSM and plugins
        # If you change anything here update PLUGINS.md documentation!
        self.state: dict = {
            'GameLanguage':       None,  # From `Fileheader
            'GameVersion':        None,  # From `Fileheader
            'GameBuild':          None,  # From `Fileheader
            'Captain':            None,  # On a crew
            'Cargo':              defaultdict(int),
            'Credits':            None,
            'FID':                None,  # Frontier Cmdr ID
            'Horizons':           None,  # Does this user have Horizons?
            'Odyssey':            False,  # Have we detected we're running under Odyssey?
            'Loan':               None,
            'Raw':                defaultdict(int),
            'Manufactured':       defaultdict(int),
            'Encoded':            defaultdict(int),
            'Engineers':          {},
            'Rank':               {},
            'Reputation':         {},
            'Statistics':         {},
            'Role':               None,  # Crew role - None, Idle, FireCon, FighterCon
            'Friends':            set(),  # Online friends
            'ShipID':             None,
            'ShipIdent':          None,
            'ShipName':           None,
            'ShipType':           None,
            'HullValue':          None,
            'ModulesValue':       None,
            'UnladenMass':        None,
            'CargoCapacity':      None,
            'MaxJumpRange':       None,
            'FuelCapacity':       None,
            'Rebuy':              None,
            'Modules':            None,
            'CargoJSON':          None,  # The raw data from the last time cargo.json was read
            'Route':              None,  # Last plotted route from Route.json file
            'IsDocked':           False,  # Whether we think cmdr is docked
            'OnFoot':             False,  # Whether we think you're on-foot
            'Component':          defaultdict(int),      # Odyssey Components in Ship Locker
            'Item':               defaultdict(int),      # Odyssey Items in Ship Locker
            'Consumable':         defaultdict(int),      # Odyssey Consumables in Ship Locker
            'Data':               defaultdict(int),      # Odyssey Data in Ship Locker
            'BackPack':     {                      # Odyssey BackPack contents
                'Component':      defaultdict(int),    # BackPack Components
                'Consumable':     defaultdict(int),    # BackPack Consumables
                'Item':           defaultdict(int),    # BackPack Items
                'Data':           defaultdict(int),  # Backpack Data
            },
            'BackpackJSON':       None,  # Raw JSON from `Backpack.json` file, if available
            'ShipLockerJSON':     None,  # Raw JSON from the `ShipLocker.json` file, if available
            'SuitCurrent':        None,
            'Suits':              {},
            'SuitLoadoutCurrent': None,
            'SuitLoadouts':       {},
            'Taxi':               None,  # True whenever we are _in_ a taxi. ie, this is reset on Disembark etc.
            'Dropship':           None,  # Best effort as to whether or not the above taxi is a dropship.
            'StarPos':            None,  # Best effort current system's galaxy position.
            'SystemAddress':      None,
            'SystemName':         None,
            'SystemPopulation':   None,
            'Body':               None,
            'BodyID':             None,
            'BodyType':           None,
            'StationName':        None,

            'NavRoute':           None,
            'Powerplay':      {
                'Power':          None,
                'Rank':           None,
                'Merits':         None,
                'Votes':          None,
                'TimePledged':    None,
            },
        }

    def start(self, root: 'tkinter.Tk') -> bool:  # noqa: CCR001
        """
        Start journal monitoring.

        :param root: The parent Tk window.
        :return: bool - False if we couldn't access/find latest Journal file.
        """
        logger.debug('Begin...')
        self.root = root
        journal_dir = config.get_str('journaldir')

        if journal_dir == '' or journal_dir is None:
            journal_dir = config.default_journal_dir

        logdir = expanduser(journal_dir)

        if not logdir or not isdir(logdir):
            logger.error(f'Journal Directory is invalid: "{logdir}"')
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            logger.debug(f'Journal Directory changed?  Was "{self.currentdir}", now "{logdir}"')
            self.stop()

        self.currentdir = logdir

        # Latest pre-existing logfile - e.g. if E:D is already running.
        # Do this before setting up the observer in case the journal directory has gone away
        try:  # TODO: This should be replaced with something specific ONLY wrapping listdir
            self.logfile = self.journal_newest_filename(self.currentdir)

        except Exception:
            logger.exception('Failed to find latest logfile')
            self.logfile = None
            return False

        # Set up a watchdog observer.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = bool(config.get_str('journaldir')) and sys.platform != 'win32'
        if not polling and not self.observer:
            logger.debug('Not polling, no observer, starting an observer...')
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()
            logger.debug('Done')

        elif polling and self.observer:
            logger.debug('Polling, but observer, so stopping observer...')
            self.observer.stop()
            self.observer = None
            logger.debug('Done')

        if not self.observed and not polling:
            logger.debug('Not observed and not polling, setting observed...')
            self.observed = self.observer.schedule(self, self.currentdir)  # type: ignore
            logger.debug('Done')

        logger.info(f'{"Polling" if polling else "Monitoring"} Journal Folder: "{self.currentdir}"')
        logger.info(f'Start Journal File: "{self.logfile}"')

        if not self.running():
            logger.debug('Starting Journal worker thread...')
            self.thread = threading.Thread(target=self.worker, name='Journal worker')
            self.thread.daemon = True
            self.thread.start()
            logger.debug('Done')

        logger.debug('Done.')
        return True

    def journal_newest_filename(self, journals_dir) -> str | None:
        """
        Determine the newest Journal file name.

        :param journals_dir: The directory to check
        :return: The `str` form of the full path to the newest Journal file
        """
        # os.listdir(None) returns CWD's contents
        if journals_dir is None:
            return None

        journal_files = (x for x in listdir(journals_dir) if self._RE_LOGFILE.search(x))
        if journal_files:
            # Odyssey Update 11 has, e.g.    Journal.2022-03-15T152503.01.log
            # Horizons Update 11 equivalent: Journal.220315152335.01.log
            # So we can no longer use a naive sort.
            journals_dir_path = pathlib.Path(journals_dir)
            journal_files = (journals_dir_path / pathlib.Path(x) for x in journal_files)
            return str(max(journal_files, key=getctime))

        return None

    def stop(self) -> None:
        """Stop journal monitoring."""
        logger.debug('Stopping monitoring Journal')

        self.currentdir = None
        self.version = None
        self.version_semantic = None
        self.mode = None
        self.group = None
        self.cmdr = None
        self.state['SystemAddress'] = None
        self.state['SystemName'] = None
        self.state['SystemPopulation'] = None
        self.state['StarPos'] = None
        self.state['Body'] = None
        self.state['BodyID'] = None
        self.state['BodyType'] = None
        self.state['StationName'] = None
        self.state['MarketID'] = None
        self.state['StationType'] = None
        self.stationservices = None
        self.is_beta = False
        self.state['OnFoot'] = False
        self.state['IsDocked'] = False

        if self.observed:
            logger.debug('self.observed: Calling unschedule_all()')
            self.observed = None
            assert self.observer is not None, 'Observer was none but it is in use?'
            self.observer.unschedule_all()
            logger.debug('Done')

        self.thread = None  # Orphan the worker thread - will terminate at next poll

        logger.debug('Done.')

    def close(self) -> None:
        """Close journal monitoring."""
        logger.debug('Calling self.stop()...')
        self.stop()
        logger.debug('Done')

        if self.observer:
            logger.debug('Calling self.observer.stop()...')
            self.observer.stop()
            logger.debug('Done')

        if self.observer:
            logger.debug('Joining self.observer thread...')
            self.observer.join()
            self.observer = None
            logger.debug('Done')

        logger.debug('Done.')

    def running(self) -> bool:
        """
        Determine if Journal watching is active.

        :return: bool
        """
        return bool(self.thread and self.thread.is_alive())

    def on_created(self, event: 'FileSystemEvent') -> None:
        """Watchdog callback when, e.g. client (re)started."""
        if not event.is_directory and self._RE_LOGFILE.search(str(basename(event.src_path))):

            self.logfile = event.src_path  # type: ignore

    def worker(self) -> None:  # noqa: C901, CCR001
        """
        Watch latest Journal file.

        1. Keep track of the latest Journal file, switching to a new one if
          needs be.
        2. Read in lines from the latest Journal file and queue them up for
          get_entry() to process in the main thread.
        """
        # Tk isn't thread-safe in general.
        # event_generate() is the only safe way to poke the main thread from this thread:
        # https://mail.python.org/pipermail/tkinter-discuss/2013-November/003522.html

        logger.debug(f'Starting on logfile "{self.logfile}"')
        # Seek to the end of the latest log file
        log_pos = -1  # make this bound, but with something that should go bang if its misused
        logfile = self.logfile
        if logfile:
            loghandle: BinaryIO = open(logfile, 'rb', 0)  # unbuffered

            self.catching_up = True
            for line in loghandle:
                try:
                    if b'"event":"Location"' in line:
                        logger.trace_if('journal.locations', '"Location" event in the past at startup')

                    self.parse_entry(line)  # Some events are of interest even in the past

                except Exception as ex:
                    logger.debug(f'Invalid journal entry:\n{line!r}\n', exc_info=ex)

            # One-shot attempt to read in latest NavRoute, if present
            navroute_data = self._parse_navroute_file()
            if navroute_data is not None:
                # If it's NavRouteClear contents, just keep those anyway.
                self.state['NavRoute'] = navroute_data

            self.catching_up = False
            log_pos = loghandle.tell()

        else:
            loghandle = None  # type: ignore

        logger.debug('Now at end of latest file.')

        self.game_was_running = self.game_running()

        if self.live:
            if self.game_was_running:
                logger.info("Game is/was running, so synthesizing StartUp event for plugins")
                # Game is running locally
                entry = self.synthesize_startup_event()

                self.event_queue.put(json.dumps(entry, separators=(', ', ':')))

            else:
                # Generate null event to update the display (with possibly out-of-date info)
                self.event_queue.put(None)
                self.live = False

        emitter = None
        # Watchdog thread -- there is a way to get this by using self.observer.emitters and checking for an attribute:
        # watch, but that may have unforseen differences in behaviour.
        if self.observed:
            assert self.observer is not None, 'self.observer is None but also in use?'
            # Note: Uses undocumented attribute
            emitter = self.observed and self.observer._emitter_for_watch[self.observed]

        logger.debug('Entering loop...')
        while True:

            # Check whether new log file started, e.g. client (re)started.
            if emitter and emitter.is_alive():
                new_journal_file: str | None = self.logfile  # updated by on_created watchdog callback

            else:
                # Poll
                try:
                    new_journal_file = self.journal_newest_filename(self.currentdir)

                except Exception:
                    logger.exception('Failed to find latest logfile')
                    new_journal_file = None

            if logfile:
                loghandle.seek(0, SEEK_END)  # required for macOS to notice log change over SMB. TODO: Do we need this?
                loghandle.seek(log_pos, SEEK_SET)  # reset EOF flag # TODO: log_pos reported as possibly unbound
                for line in loghandle:
                    # Paranoia check to see if we're shutting down
                    if threading.current_thread() != self.thread:
                        logger.info("We're not meant to be running, exiting...")
                        return  # Terminate

                    if b'"event":"Continue"' in line:
                        for _ in range(10):
                            logger.trace_if('journal.continuation', "****")
                        logger.trace_if('journal.continuation', 'Found a Continue event, its being added to the list, '
                                        'we will finish this file up and then continue with the next')

                    self.event_queue.put(line)

                if not self.event_queue.empty():
                    if not config.shutting_down:
                        logger.trace_if('journal.queue', 'Sending <<JournalEvent>>')
                        self.root.event_generate('<<JournalEvent>>', when="tail")

                log_pos = loghandle.tell()

            if logfile != new_journal_file:
                for _ in range(10):
                    logger.trace_if('journal.file', "****")
                logger.info(f'New Journal File. Was "{logfile}", now "{new_journal_file}"')
                logfile = new_journal_file
                if loghandle:
                    loghandle.close()

                if logfile:
                    loghandle = open(logfile, 'rb', 0)  # unbuffered
                    log_pos = 0

            if self.game_was_running:
                sleep(self._POLL)
            else:
                sleep(self._INACTIVE_POLL)

            # Check whether we're still supposed to be running
            if threading.current_thread() != self.thread:
                logger.info("We're not meant to be running, exiting...")
                if loghandle:
                    loghandle.close()

                return  # Terminate

            if self.game_was_running:
                if not self.game_running():
                    logger.info('Detected exit from game, synthesising ShutDown event')
                    timestamp = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())
                    self.event_queue.put(
                        f'{{ "timestamp":"{timestamp}", "event":"ShutDown" }}'
                    )

                    if not config.shutting_down:
                        logger.trace_if('journal.queue', 'Sending <<JournalEvent>>')
                        self.root.event_generate('<<JournalEvent>>', when="tail")

                    self.game_was_running = False

            else:
                self.game_was_running = self.game_running()

    def synthesize_startup_event(self) -> dict[str, Any]:
        """
        Synthesize a 'StartUp' event to notify plugins of initial state.

        May be called, e.g. after 'catch up' loading of current latest
        journal file on startup, or when a new journal file is detected without
        the game running locally.

        :return: Synthesized event as a dict
        """
        entry: dict[str, Any] = {
            'timestamp':        strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()),
            'event':            'StartUp',
            'StarSystem':       self.state['SystemName'],
            'StarPos':          self.state['StarPos'],
            'SystemAddress':    self.state['SystemAddress'],
            'Population':       self.state['SystemPopulation'],
        }

        if self.state['Body']:
            entry['Body'] = self.state['Body']
            entry['BodyID'] = self.state['BodyID']
            entry['BodyType'] = self.state['BodyType']

        if self.state['StationName']:
            entry['Docked'] = True
            entry['MarketID'] = self.state['MarketID']
            entry['StationName'] = self.state['StationName']
            entry['StationType'] = self.state['StationType']

        else:
            entry['Docked'] = False

        return entry

    def parse_entry(self, line: bytes) -> MutableMapping[str, Any]:  # noqa: C901, CCR001
        """
        Parse a Journal JSON line.

        This augments some events, sets internal state in reaction to many and
        loads some extra files, e.g. Cargo.json, as necessary.

        :param line: bytes - The entry being parsed.  Yes, this is bytes, not str.
                             We rely on json.loads() dealing with this properly.
        :return: Dict of the processed event.
        """
        # TODO(A_D): a bunch of these can be simplified to use if itertools.product and filters
        if line is None:
            return {'event': None}  # Fake startup event

        try:
            # Preserve property order because why not?
            entry: MutableMapping[str, Any] = json.loads(line)
            assert 'timestamp' in entry, "Timestamp does not exist in the entry"

            self.__navroute_retry()

            event_type = entry['event'].lower()
            if event_type == 'fileheader':
                self.live = False

                self.cmdr = None
                self.mode = None
                self.group = None
                self.state['SystemAddress'] = None
                self.state['SystemName'] = None
                self.state['SystemPopulation'] = None
                self.state['StarPos'] = None
                self.state['Body'] = None
                self.state['BodyID'] = None
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None
                self.started = None
                self.__init_state()

                # Do this AFTER __init_state() lest our nice new state entries be None
                self.populate_version_info(entry)

            elif event_type == 'commander':
                self.live = True  # First event in 3.0
                self.cmdr = entry['Name']
                self.state['FID'] = entry['FID']
                logger.trace_if(STARTUP, f'"Commander" event, {monitor.cmdr=}, {monitor.state["FID"]=}')

            elif event_type == 'loadgame':
                # Odyssey Release Update 5 -- This contains data that doesn't match the format used in FileHeader above
                self.populate_version_info(entry, suppress=True)

                # alpha4
                # Odyssey: bool
                self.cmdr = entry['Commander']
                # 'Open', 'Solo', 'Group', or None for CQC (and Training - but no LoadGame event)
                if not entry.get('Ship') and not entry.get('GameMode') or entry.get('GameMode', '').lower() == 'cqc':
                    logger.trace_if('journal.loadgame.cqc', f'loadgame to cqc: {entry}')
                    self.mode = 'CQC'

                else:
                    self.mode = entry.get('GameMode')

                self.group = entry.get('Group')
                self.state['SystemAddress'] = None
                self.state['SystemName'] = None
                self.state['SystemPopulation'] = None
                self.state['StarPos'] = None
                self.state['Body'] = None
                self.state['BodyID'] = None
                self.state['BodyType'] = None
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None
                self.started = timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                # Don't set Ship, ShipID etc since this will reflect Fighter or SRV if starting in those
                self.state.update({
                    'Captain':              None,
                    'Credits':              entry['Credits'],
                    'FID':                  entry.get('FID'),   # From 3.3
                    'Horizons':             entry['Horizons'],  # From 3.0
                    'Odyssey':              entry.get('Odyssey', False),  # From 4.0 Odyssey
                    'Loan':                 entry['Loan'],
                    # For Odyssey, by 4.0.0.100, and at least from Horizons 3.8.0.201 the order of events changed
                    # to LoadGame being after some 'status' events.
                    # 'Engineers':          {},  # 'EngineerProgress' event now before 'LoadGame'
                    # 'Rank':               {},  # 'Rank'/'Progress' events now before 'LoadGame'
                    # 'Reputation':         {},  # 'Reputation' event now before 'LoadGame'
                    'Statistics':           {},  # Still after 'LoadGame' in 4.0.0.903
                    'Role':                 None,
                    'Taxi':                 None,
                    'Dropship':             None,
                })
                if entry.get('Ship') is not None and self._RE_SHIP_ONFOOT.search(entry['Ship']):
                    self.state['OnFoot'] = True

                logger.trace_if(STARTUP, f'"LoadGame" event, {monitor.cmdr=}, {monitor.state["FID"]=}')

            elif event_type == 'newcommander':
                self.cmdr = entry['Name']
                self.group = None

            elif event_type == 'setusershipname':
                self.state['ShipID'] = entry['ShipID']
                if 'UserShipId' in entry:  # Only present when changing the ship's ident
                    self.state['ShipIdent'] = entry['UserShipId']

                self.state['ShipName'] = entry.get('UserShipName')
                self.state['ShipType'] = self.canonicalise(entry['Ship'])

            elif event_type == 'shipyardbuy':
                self.state['ShipID'] = None
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

                self.state['Credits'] -= entry.get('ShipPrice', 0)

            elif event_type == 'shipyardswap':
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

            elif (
                event_type == 'loadout' and
                'fighter' not in self.canonicalise(entry['Ship']) and
                'buggy' not in self.canonicalise(entry['Ship'])
            ):
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = entry['ShipIdent']

                # Newly purchased ships can show a ShipName of "" initially,
                # and " " after a game restart/relog.
                # Players *can* also purposefully set " " as the name, but anyone
                # doing that gets to live with EDMC showing ShipType instead.
                if entry['ShipName'] and entry['ShipName'] not in ('', ' '):
                    self.state['ShipName'] = entry['ShipName']

                self.state['ShipType'] = self.canonicalise(entry['Ship'])
                self.state['HullValue'] = entry.get('HullValue')  # not present on exiting Outfitting
                self.state['ModulesValue'] = entry.get('ModulesValue')  # not present on exiting Outfitting
                self.state['UnladenMass'] = entry.get('UnladenMass')
                self.state['CargoCapacity'] = entry.get('CargoCapacity')
                self.state['MaxJumpRange'] = entry.get('MaxJumpRange')
                self.state["FuelCapacity"] = {name: entry.get("FuelCapacity", {}).get(name) for name in
                                              ("Main", "Reserve")}
                self.state['Rebuy'] = entry.get('Rebuy')
                # Remove spurious differences between initial Loadout event and subsequent
                self.state['Modules'] = {}
                for module in entry['Modules']:
                    module = dict(module)
                    module['Item'] = self.canonicalise(module['Item'])
                    if ('Hardpoint' in module['Slot'] and
                        not module['Slot'].startswith('TinyHardpoint') and
                            module.get('AmmoInClip') == module.get('AmmoInHopper') == 1):  # lasers
                        module.pop('AmmoInClip')
                        module.pop('AmmoInHopper')

                    self.state['Modules'][module['Slot']] = module
                # SLEF
                initial_dict: dict[str, dict[str, Any]] = {
                    "header": {"appName": appname, "appVersion": str(appversion())}
                }
                data_dict = {}
                for module in entry['Modules']:
                    if module.get('Slot') == 'FuelTank':
                        cap = module['Item'].split('size')
                        cap = cap[1].split('_')
                        cap = 2 ** int(cap[0])
                        ship = ship_name_map[entry["Ship"]]
                        fuel = {'Main': cap, 'Reserve': ships[ship]['reserveFuelCapacity']}
                        data_dict.update({"FuelCapacity": fuel})
                data_dict.update({
                    'Ship': entry["Ship"],
                    'ShipName': entry['ShipName'],
                    'ShipIdent': entry['ShipIdent'],
                    'HullValue': entry.get('HullValue'),  # type: ignore
                    'ModulesValue': entry.get('ModulesValue'),  # type: ignore
                    'Rebuy': entry['Rebuy'],
                    'MaxJumpRange': entry['MaxJumpRange'],
                    'UnladenMass': entry['UnladenMass'],
                    'CargoCapacity': entry['CargoCapacity'],
                    'Modules': entry['Modules'],
                })
                initial_dict.update({'data': data_dict})
                output = json.dumps(initial_dict, indent=4)
                self.slef = str(f"[{output}]")

            elif event_type == 'modulebuy':
                self.state['Modules'][entry['Slot']] = {
                    'Slot':     entry['Slot'],
                    'Item':     self.canonicalise(entry['BuyItem']),
                    'On':       True,
                    'Priority': 1,
                    'Health':   1.0,
                    'Value':    entry['BuyPrice'],
                }

                self.state['Credits'] -= entry.get('BuyPrice', 0)

            elif event_type == 'moduleretrieve':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'modulesell':
                self.state['Modules'].pop(entry['Slot'], None)
                self.state['Credits'] += entry.get('SellPrice', 0)

            elif event_type == 'modulesellremote':
                self.state['Credits'] += entry.get('SellPrice', 0)

            elif event_type == 'modulestore':
                self.state['Modules'].pop(entry['Slot'], None)
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'moduleswap':
                to_item = self.state['Modules'].get(entry['ToSlot'])
                to_slot = entry['ToSlot']
                from_slot = entry['FromSlot']
                modules = self.state['Modules']
                modules[to_slot] = modules[from_slot]
                if to_item:
                    modules[from_slot] = to_item

                else:
                    modules.pop(from_slot, None)

            elif event_type == 'undocked':
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None
                self.state['IsDocked'] = False

            elif event_type == 'embark':
                # This event is logged when a player (on foot) gets into a ship or SRV
                # Parameters:
                #     • SRV: true if getting into SRV, false if getting into a ship
                #     • Taxi: true when boarding a taxi transport ship
                #     • Multicrew: true when boarding another player’s vessel
                #     • ID: player’s ship ID (if players own vessel)
                #     • StarSystem
                #     • SystemAddress
                #     • Body
                #     • BodyID
                #     • OnStation: bool
                #     • OnPlanet: bool
                #     • StationName (if at a station)
                #     • StationType
                #     • MarketID
                self.state['StationName'] = None
                self.state['MarketID'] = None
                if entry.get('OnStation'):
                    self.state['StationName'] = entry.get('StationName', '')
                    self.state['MarketID'] = entry.get('MarketID', '')

                self.state['OnFoot'] = False
                self.state['Taxi'] = entry['Taxi']

                # We can't now have anything in the BackPack, it's all in the
                # ShipLocker.
                self.backpack_set_empty()

            elif event_type == 'disembark':
                # This event is logged when the player steps out of a ship or SRV
                #
                # Parameters:
                #     • SRV: true if getting out of SRV, false if getting out of a ship
                #     • Taxi: true when getting out of a taxi transport ship
                #     • Multicrew: true when getting out of another player’s vessel
                #     • ID: player’s ship ID (if players own vessel)
                #     • StarSystem
                #     • SystemAddress
                #     • Body
                #     • BodyID
                #     • OnStation: bool
                #     • OnPlanet: bool
                #     • StationName (if at a station)
                #     • StationType
                #     • MarketID

                if entry.get('OnStation', False):
                    self.state['StationName'] = entry.get('StationName', '')

                else:
                    self.state['StationName'] = None

                self.state['OnFoot'] = True
                if self.state['Taxi'] is not None and self.state['Taxi'] != entry.get('Taxi', False):
                    logger.warning('Disembarked from a taxi but we didn\'t know we were in a taxi?')

                self.state['Taxi'] = False
                self.state['Dropship'] = False

            elif event_type == 'dropshipdeploy':
                # We're definitely on-foot now
                self.state['OnFoot'] = True
                self.state['Taxi'] = False
                self.state['Dropship'] = False

            elif event_type == 'supercruiseexit':
                # For any orbital station we have no way of determining the body
                # it orbits:
                #
                #   In-ship Status.json doesn't specify this.
                #   On-foot Status.json lists the station itself as Body.
                #   Location for stations (on-foot or in-ship) has station as Body.
                #   SupercruiseExit (own ship or taxi) lists the station as the Body.
                if entry['BodyType'] == 'Station':
                    self.state['Body'] = None
                    self.state['BodyID'] = None

            elif event_type == 'docked':
                ###############################################################
                # Track: Station
                ###############################################################
                self.state['IsDocked'] = True
                self.state['StationName'] = entry.get('StationName')  # It may be None
                self.state['MarketID'] = entry.get('MarketID')  # It may be None
                self.state['StationType'] = entry.get('StationType')  # It may be None
                self.stationservices = entry.get('StationServices')  # None under E:D < 2.4

                # No need to set self.state['Taxi'] or Dropship here, if it's
                # those, the next event is a Disembark anyway
                ###############################################################

            elif event_type in ('location', 'fsdjump', 'carrierjump'):
                """
                Notes on tracking of a player's location.

                Body
                ---
                There are some caveats about tracking Body name, ID and type,
                mostly due to close-orbiting binary planets/moons.

                Presence on or near a Body is indicated in several scenarios:

                1. When the player logs in.
                2. When the player's location changes due to being docked
                  on a Fleet Carrier when it jumps.
                3. When the player flies within Orbital Cruise range of a
                  Body.

                For the first case this will always be a 'Location' event.
                If landed on a Body, or docked at a surface port then this
                will be indicated.  However, if docked at an orbital station
                the 'Body' is the name of that station, with 'BodyType' having
                'Station' as its value.

                In the second case although it *should* be a 'CarrierJump'
                event, for a while now it's actually been a 'Location' event.
                This should follow the same rules as being docked at an
                orbital station.

                For the last case there are some caveats to do with close
                orbiting binary bodies:

                1. 'ApproachBody' indicates presence near the Body in question.
                2. 'LeaveBody' indicates the player is no longer considered
                  to be near the Body.  This is specifically when no longer
                  in Orbital Cruise around the Body such that the HUD for that
                  has been switched out for the normal SuperCruise one.
                3. 'SupercruiseExit' does not indicate any change of presence
                  near a Body.
                4. 'SupercruiseEntry' *also* **DOES NOT** indicate that the
                  player is no longer near the Body.  They can easily utilise
                  Orbital Cruise to rapidly travel around the Body and then
                  land on it again **without a fresh 'ApproachBody'** event.

                  The only way to check for this is to utilise the Body (name)
                  present in `Status.json` data, as this *will* correctly
                  reflect the second Body.
                """
                ###############################################################
                # Track: Body
                ###############################################################
                if event_type in ('location', 'carrierjump'):
                    # We're not guaranteeing this is a planet, rather than a
                    # station.
                    self.state['Body'] = entry.get('Body')
                    self.state['BodyID'] = entry.get('BodyID')
                    self.state['BodyType'] = entry.get('BodyType')

                elif event_type == 'fsdjump':
                    self.state['Body'] = None
                    self.state['BodyID'] = None
                    self.state['BodyType'] = None
                ###############################################################

                ###############################################################
                # Track: IsDocked
                ###############################################################
                if event_type == 'location':
                    logger.trace_if('journal.locations', '"Location" event')
                    self.state['IsDocked'] = entry.get('Docked', False)
                ###############################################################

                ###############################################################
                # Track: Current System
                ###############################################################
                if 'StarPos' in entry:
                    # Plugins need this as well, so copy in state
                    self.state['StarPos'] = tuple(entry['StarPos'])

                else:
                    logger.warning(f"'{event_type}' event without 'StarPos' !!!:\n{entry}\n")

                if 'SystemAddress' not in entry:
                    logger.warning(f"{event_type} event without SystemAddress !!!:\n{entry}\n")

                # But we'll still *use* the value, because if a 'location' event doesn't
                # have this we've still moved and now don't know where and MUST NOT
                # continue to use any old value.
                # Yes, explicitly state `None` here, so it's crystal clear.
                self.state['SystemAddress'] = entry.get('SystemAddress', None)

                self.state['SystemPopulation'] = entry.get('Population')

                if entry['StarSystem'] == 'ProvingGround':
                    self.state['SystemName'] = 'CQC'

                else:
                    self.state['SystemName'] = entry['StarSystem']
                ###############################################################

                ###############################################################
                # Track: Current station, if applicable
                ###############################################################
                if event_type == 'fsdjump':
                    self.state['StationName'] = None
                    self.state['MarketID'] = None
                    self.state['StationType'] = None
                    self.stationservices = None

                else:
                    self.state['StationName'] = entry.get('StationName')  # It may be None
                    # If on foot in-station 'Docked' is false, but we have a
                    # 'BodyType' of 'Station', and the 'Body' is the station name
                    # NB: No MarketID
                    if entry.get('BodyType') and entry['BodyType'] == 'Station':
                        self.state['StationName'] = entry.get('Body')

                    self.state['MarketID'] = entry.get('MarketID')  # May be None
                    self.state['StationType'] = entry.get('StationType')  # May be None
                    self.stationservices = entry.get('StationServices')  # None in Odyssey for on-foot 'Location'
                ###############################################################

                ###############################################################
                # Track: Whether in a Taxi/Dropship
                ###############################################################
                self.state['Taxi'] = entry.get('Taxi', None)
                if not self.state['Taxi']:
                    self.state['Dropship'] = None
                ###############################################################

            elif event_type == 'approachbody':
                self.state['Body'] = entry['Body']
                self.state['BodyID'] = entry.get('BodyID')
                # This isn't in the event, but Journal doc for ApproachBody says:
                #   when in Supercruise, and distance from planet drops to within the 'Orbital Cruise' zone
                # Used in plugins/eddn.py for setting entry Body/BodyType
                # on 'docked' events when Planetary.
                self.state['BodyType'] = 'Planet'

            elif event_type == 'leavebody':
                # Triggered when ship goes above Orbital Cruise altitude, such
                # that a new 'ApproachBody' would get triggered if the ship
                # went back down.
                self.state['Body'] = None
                self.state['BodyID'] = None
                self.state['BodyType'] = None

            elif event_type == 'supercruiseentry':
                # We only clear Body state if the Type is Station.  This is
                # because we won't get a fresh ApproachBody if we don't leave
                # Orbital Cruise but land again.
                if self.state['BodyType'] == 'Station':
                    self.state['Body'] = None
                    self.state['BodyID'] = None
                    self.state['BodyType'] = None

                ###############################################################
                # Track: Current station, if applicable
                ###############################################################
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None
                ###############################################################

            elif event_type == 'music':
                if entry['MusicTrack'] == 'MainMenu':
                    # We'll get new Body state when the player logs back into
                    # the game.
                    self.state['Body'] = None
                    self.state['BodyID'] = None
                    self.state['BodyType'] = None

            elif event_type in ('rank', 'promotion'):
                payload = dict(entry)
                payload.pop('event')
                payload.pop('timestamp')

                self.state['Rank'].update({k: (v, 0) for k, v in payload.items()})

            elif event_type == 'progress':
                rank = self.state['Rank']
                for k, v in entry.items():
                    if k in rank:
                        # perhaps not taken promotion mission yet
                        rank[k] = (rank[k][0], min(v, 100))

            elif event_type in ('reputation', 'statistics'):
                payload = dict(entry)
                payload.pop('event')
                payload.pop('timestamp')
                # NB: We need the original casing for these keys
                self.state[entry['event']] = payload

            elif event_type == 'engineerprogress':
                # Sanity check - at least once the 'Engineer' (name) was missing from this in early
                # Odyssey 4.0.0.100.  Might only have been a server issue causing incomplete data.

                if self.event_valid_engineerprogress(entry):
                    engineers = self.state['Engineers']
                    if 'Engineers' in entry:  # Startup summary
                        self.state['Engineers'] = {
                            e['Engineer']: ((e['Rank'], e.get('RankProgress', 0)) if 'Rank' in e else e['Progress'])
                            for e in entry['Engineers']
                        }

                    else:  # Promotion
                        engineer = entry['Engineer']
                        if 'Rank' in entry:
                            engineers[engineer] = (entry['Rank'], entry.get('RankProgress', 0))

                        else:
                            engineers[engineer] = entry['Progress']

            elif event_type == 'cargo' and entry.get('Vessel') == 'Ship':
                self.state['Cargo'] = defaultdict(int)
                # From 3.3 full Cargo event (after the first one) is written to a separate file
                if 'Inventory' not in entry:
                    with open(join(self.currentdir, 'Cargo.json'), 'rb') as h:  # type: ignore
                        entry = json.load(h)
                        self.state['CargoJSON'] = entry

                clean = self.coalesce_cargo(entry['Inventory'])

                self.state['Cargo'].update({self.canonicalise(x['Name']): x['Count'] for x in clean})

            elif event_type == 'cargotransfer':
                for c in entry['Transfers']:
                    name = self.canonicalise(c['Type'])
                    if c['Direction'] == 'toship':
                        self.state['Cargo'][name] += c['Count']

                    else:
                        # So it's *from* the ship
                        self.state['Cargo'][name] -= c['Count']

            elif event_type == 'shiplocker':
                # As of 4.0.0.400 (2021-06-10)
                # "ShipLocker" will be a full list written to the journal at startup/boarding, and also
                # written to a separate shiplocker.json file - other updates will just update that file and mention it
                # has changed with an empty shiplocker event in the main journal.

                # Always attempt loading of this, but if it fails we'll hope this was
                # a startup/boarding version and thus `entry` contains
                # the data anyway.
                currentdir_path = pathlib.Path(str(self.currentdir))
                shiplocker_filename = currentdir_path / 'ShipLocker.json'
                shiplocker_max_attempts = 5
                shiplocker_fail_sleep = 0.01
                attempts = 0
                while attempts < shiplocker_max_attempts:
                    attempts += 1
                    try:
                        with open(shiplocker_filename, 'rb') as h:
                            entry = json.load(h)
                            self.state['ShipLockerJSON'] = entry
                            break

                    except FileNotFoundError:
                        logger.warning('ShipLocker event but no ShipLocker.json file')
                        sleep(shiplocker_fail_sleep)
                        pass

                    except json.JSONDecodeError as e:
                        logger.warning(f'ShipLocker.json failed to decode:\n{e!r}\n')
                        sleep(shiplocker_fail_sleep)
                        pass

                else:
                    logger.warning(f'Failed to load & decode shiplocker after {shiplocker_max_attempts} tries. '
                                   'Giving up.')

                if not all(t in entry for t in ('Components', 'Consumables', 'Data', 'Items')):
                    logger.warning('ShipLocker event is missing at least one category')

                # This event has the current totals, so drop any current data
                self.state['Component'] = defaultdict(int)
                self.state['Consumable'] = defaultdict(int)
                self.state['Item'] = defaultdict(int)
                self.state['Data'] = defaultdict(int)

                clean_components = self.coalesce_cargo(entry['Components'])
                self.state['Component'].update(
                    {self.canonicalise(x['Name']): x['Count'] for x in clean_components}
                )

                clean_consumables = self.coalesce_cargo(entry['Consumables'])
                self.state['Consumable'].update(
                    {self.canonicalise(x['Name']): x['Count'] for x in clean_consumables}
                )

                clean_items = self.coalesce_cargo(entry['Items'])
                self.state['Item'].update(
                    {self.canonicalise(x['Name']): x['Count'] for x in clean_items}
                )

                clean_data = self.coalesce_cargo(entry['Data'])
                self.state['Data'].update(
                    {self.canonicalise(x['Name']): x['Count'] for x in clean_data}
                )

            # Journal v31 implies this was removed before Odyssey launch
            elif event_type == 'backpackmaterials':
                # Last seen in a 4.0.0.102 journal file.
                logger.warning(f'We have a BackPackMaterials event, defunct since > 4.0.0.102 ?:\n{entry}\n')
                pass

            elif event_type in ('backpack', 'resupply'):
                # as of v4.0.0.600, a `resupply` event is dropped when resupplying your suit at your ship.
                # This event writes the same data as a backpack event. It will also be followed by a ShipLocker
                # but that follows normal behaviour in its handler.

                # TODO: v31 doc says this is`backpack.json` ... but Howard Chalkley
                #       said it's `Backpack.json`
                backpack_file = pathlib.Path(str(self.currentdir)) / 'Backpack.json'
                backpack_data = None

                if not backpack_file.exists():
                    logger.warning(f'Failed to find backpack.json file as it appears not to exist? {backpack_file=}')

                else:
                    backpack_data = backpack_file.read_bytes()

                parsed = None

                if backpack_data is None:
                    logger.warning('Unable to read backpack data!')

                elif len(backpack_data) == 0:
                    logger.warning('Backpack.json was empty when we read it!')

                else:
                    try:
                        parsed = json.loads(backpack_data)

                    except json.JSONDecodeError:
                        logger.exception('Unable to parse Backpack.json')

                if parsed is not None:
                    entry = parsed  # set entry so that it ends up in plugins with the right data
                    # Store in monitor.state
                    self.state['BackpackJSON'] = entry

                    # Assume this reflects the current state when written
                    self.backpack_set_empty()

                    clean_components = self.coalesce_cargo(entry['Components'])
                    self.state['BackPack']['Component'].update(
                        {self.canonicalise(x['Name']): x['Count'] for x in clean_components}
                    )

                    clean_consumables = self.coalesce_cargo(entry['Consumables'])
                    self.state['BackPack']['Consumable'].update(
                        {self.canonicalise(x['Name']): x['Count'] for x in clean_consumables}
                    )

                    clean_items = self.coalesce_cargo(entry['Items'])
                    self.state['BackPack']['Item'].update(
                        {self.canonicalise(x['Name']): x['Count'] for x in clean_items}
                    )

                    clean_data = self.coalesce_cargo(entry['Data'])
                    self.state['BackPack']['Data'].update(
                        {self.canonicalise(x['Name']): x['Count'] for x in clean_data}
                    )

            elif event_type == 'backpackchange':
                # Changes to Odyssey Backpack contents *other* than from a Transfer
                # See TransferMicroResources event for that.

                if entry.get('Added') is not None:
                    changes = 'Added'

                elif entry.get('Removed') is not None:
                    changes = 'Removed'

                else:
                    logger.warning(f'BackpackChange with neither Added nor Removed: {entry=}')
                    changes = ''

                if changes != '':
                    for c in entry[changes]:
                        category = self.category(c['Type'])
                        name = self.canonicalise(c['Name'])

                        if changes == 'Removed':
                            self.state['BackPack'][category][name] -= c['Count']

                        elif changes == 'Added':
                            self.state['BackPack'][category][name] += c['Count']

                # Paranoia check to see if anything has gone negative.
                # As of Odyssey Alpha Phase 1 Hotfix 2 keeping track of BackPack
                # materials is impossible when used/picked up anyway.
                for c in self.state['BackPack']:
                    for m in self.state['BackPack'][c]:
                        if self.state['BackPack'][c][m] < 0:
                            self.state['BackPack'][c][m] = 0

            elif event_type == 'buymicroresources':
                # From 4.0.0.400 we get an empty (see file) `ShipLocker` event,
                # so we can ignore this for inventory purposes.

                # But do record the credits balance change.
                self.state['Credits'] -= entry.get('Price', 0)

            elif event_type == 'sellmicroresources':
                # As of 4.0.0.400 we can ignore this as an empty (see file)
                # `ShipLocker` event is written for the full new inventory.

                # But still record the credits balance change.
                self.state['Credits'] += entry.get('Price', 0)

            elif event_type in ('tradeMicroResources', 'collectitems', 'dropitems', 'useconsumable'):
                # As of 4.0.0.400 we can ignore these as an empty (see file)
                # `ShipLocker` event and/or a `BackpackChange` is also written.
                pass

            # <https://forums.frontier.co.uk/threads/575010/>
            # also there's one additional journal event that was missed out from
            # this version of the docs: "SuitLoadout": # when starting on foot, or
            # when disembarking from a ship, with the same info as found in "CreateSuitLoadout"
            elif event_type == 'suitloadout':
                suit_slotid, suitloadout_slotid = self.suitloadout_store_from_event(entry)
                if not self.suit_and_loadout_setcurrent(suit_slotid, suitloadout_slotid):
                    logger.error(f"Event was: {entry}")

            elif event_type == 'switchsuitloadout':
                # 4.0.0.101
                #
                # { "timestamp":"2021-05-21T10:39:43Z", "event":"SwitchSuitLoadout",
                #   "SuitID":1700217809818876, "SuitName":"utilitysuit_class1",
                #   "SuitName_Localised":"Maverick Suit", "LoadoutID":4293000002,
                #   "LoadoutName":"K/P", "Modules":[ { "SlotName":"PrimaryWeapon1",
                #   "SuitModuleID":1700217863661544,
                #   "ModuleName":"wpn_m_assaultrifle_kinetic_fauto",
                #   "ModuleName_Localised":"Karma AR-50" },
                #   { "SlotName":"SecondaryWeapon", "SuitModuleID":1700216180036986,
                #   "ModuleName":"wpn_s_pistol_plasma_charged",
                #   "ModuleName_Localised":"Manticore Tormentor" } ] }
                #
                suitid, suitloadout_slotid = self.suitloadout_store_from_event(entry)
                if not self.suit_and_loadout_setcurrent(suitid, suitloadout_slotid):
                    logger.error(f"Event was: {entry}")

            elif event_type == 'createsuitloadout':
                # 4.0.0.101
                #
                # { "timestamp":"2021-05-21T11:13:15Z", "event":"CreateSuitLoadout", "SuitID":1700216165682989,
                # "SuitName":"tacticalsuit_class1", "SuitName_Localised":"Dominator Suit", "LoadoutID":4293000004,
                # "LoadoutName":"P/P/K", "Modules":[ { "SlotName":"PrimaryWeapon1", "SuitModuleID":1700216182854765,
                # "ModuleName":"wpn_m_assaultrifle_plasma_fauto", "ModuleName_Localised":"Manticore Oppressor" },
                # { "SlotName":"PrimaryWeapon2", "SuitModuleID":1700216190363340,
                # "ModuleName":"wpn_m_shotgun_plasma_doublebarrel", "ModuleName_Localised":"Manticore Intimidator" },
                # { "SlotName":"SecondaryWeapon", "SuitModuleID":1700217869872834,
                # "ModuleName":"wpn_s_pistol_kinetic_sauto", "ModuleName_Localised":"Karma P-15" } ] }
                #
                suitid, suitloadout_slotid = self.suitloadout_store_from_event(entry)
                # Creation doesn't mean equipping it
                #  if not self.suit_and_loadout_setcurrent(suitid, suitloadout_slotid):
                #      logger.error(f"Event was: {entry}")

            elif event_type == 'deletesuitloadout':
                # alpha4:
                # { "timestamp":"2021-04-29T10:32:27Z", "event":"DeleteSuitLoadout", "SuitID":1698365752966423,
                # "SuitName":"explorationsuit_class1", "SuitName_Localised":"Artemis Suit", "LoadoutID":4293000003,
                # "LoadoutName":"Loadout 1" }

                if self.state['SuitLoadouts']:
                    loadout_id = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
                    try:
                        self.state['SuitLoadouts'].pop(f'{loadout_id}')

                    except KeyError:
                        # This should no longer happen, as we're now handling CreateSuitLoadout properly
                        logger.debug(f"loadout slot id {loadout_id} doesn't exist, not in last CAPI pull ?")

            elif event_type == 'renamesuitloadout':
                # alpha4
                # Parameters:
                #     • SuitID
                #     • SuitName
                #     • LoadoutID
                #     • Loadoutname
                # alpha4:
                # { "timestamp":"2021-04-29T10:35:55Z", "event":"RenameSuitLoadout", "SuitID":1698365752966423,
                # "SuitName":"explorationsuit_class1", "SuitName_Localised":"Artemis Suit", "LoadoutID":4293000003,
                # "LoadoutName":"Art L/K" }
                if self.state['SuitLoadouts']:
                    loadout_id = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
                    try:
                        self.state['SuitLoadouts'][loadout_id]['name'] = entry['LoadoutName']

                    except KeyError:
                        logger.debug(f"loadout slot id {loadout_id} doesn't exist, not in last CAPI pull ?")

            elif event_type == 'buysuit':
                # alpha4 :
                # { "timestamp":"2021-04-29T09:03:37Z", "event":"BuySuit", "Name":"UtilitySuit_Class1",
                # "Name_Localised":"Maverick Suit", "Price":150000, "SuitID":1698364934364699 }
                loc_name = entry.get('Name_Localised', entry['Name'])
                self.state['Suits'][entry['SuitID']] = {
                    'name':      entry['Name'],
                    'locName':   loc_name,
                    'edmcName':  self.suit_sane_name(loc_name),
                    'id':        None,  # Is this an FDev ID for suit type ?
                    'suitId':    entry['SuitID'],
                    'mods':      entry['SuitMods'],  # Suits can (rarely) be bought with modules installed
                }

                # update credits
                if price := entry.get('Price') is None:
                    logger.error(f"BuySuit didn't contain Price: {entry}")

                else:
                    self.state['Credits'] -= price

            elif event_type == 'sellsuit':
                # Remove from known suits
                # As of Odyssey Alpha Phase 2, Hotfix 5 (4.0.0.13) this isn't possible as this event
                # doesn't contain the specific suit ID as per CAPI `suits` dict.
                # alpha4
                # This event is logged when a player sells a flight suit
                #
                # Parameters:
                #     • Name
                #     • Price
                #     • SuitID
                # alpha4:
                # { "timestamp":"2021-04-29T09:15:51Z", "event":"SellSuit", "SuitID":1698364937435505,
                # "Name":"explorationsuit_class1", "Name_Localised":"Artemis Suit", "Price":90000 }
                if self.state['Suits']:
                    try:
                        self.state['Suits'].pop(entry['SuitID'])

                    except KeyError:
                        logger.debug(f"SellSuit for a suit we didn't know about? {entry['SuitID']}")

                    # update credits total
                    if price := entry.get('Price') is None:
                        logger.error(f"SellSuit didn't contain Price: {entry}")

                    else:
                        self.state['Credits'] += price

            elif event_type == 'upgradesuit':
                # alpha4
                # This event is logged when the player upgrades their flight suit
                #
                # Parameters:
                #     • Name
                #     • SuitID
                #     • Class
                #     • Cost
                # TODO: Update self.state['Suits'] when we have an example to work from
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'loadoutequipmodule':
                # alpha4:
                # { "timestamp":"2021-04-29T11:11:13Z", "event":"LoadoutEquipModule", "LoadoutName":"Dom L/K/K",
                # "SuitID":1698364940285172, "SuitName":"tacticalsuit_class1", "SuitName_Localised":"Dominator Suit",
                # "LoadoutID":4293000001, "SlotName":"PrimaryWeapon2", "ModuleName":"wpn_m_assaultrifle_laser_fauto",
                # "ModuleName_Localised":"TK Aphelion", "SuitModuleID":1698372938719590 }
                if self.state['SuitLoadouts']:
                    loadout_id = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
                    try:
                        self.state['SuitLoadouts'][loadout_id]['slots'][entry['SlotName']] = {
                            'name':           entry['ModuleName'],
                            'locName':        entry.get('ModuleName_Localised', entry['ModuleName']),
                            'id':             None,
                            'weaponrackId':   entry['SuitModuleID'],
                            'locDescription': '',
                            'class':          entry['Class'],
                            'mods':           entry['WeaponMods']
                        }

                    except KeyError:
                        # TODO: Log the exception details too, for some clue about *which* key
                        logger.error(f"LoadoutEquipModule: {entry}")

            elif event_type == 'loadoutremovemodule':
                # alpha4 - triggers if selecting an already-equipped weapon into a different slot
                # { "timestamp":"2021-04-29T11:11:13Z", "event":"LoadoutRemoveModule", "LoadoutName":"Dom L/K/K",
                # "SuitID":1698364940285172, "SuitName":"tacticalsuit_class1", "SuitName_Localised":"Dominator Suit",
                # "LoadoutID":4293000001, "SlotName":"PrimaryWeapon1", "ModuleName":"wpn_m_assaultrifle_laser_fauto",
                # "ModuleName_Localised":"TK Aphelion", "SuitModuleID":1698372938719590 }
                if self.state['SuitLoadouts']:
                    loadout_id = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
                    try:
                        self.state['SuitLoadouts'][loadout_id]['slots'].pop(entry['SlotName'])

                    except KeyError:
                        logger.error(f"LoadoutRemoveModule: {entry}")

            elif event_type == 'buyweapon':
                # alpha4
                # { "timestamp":"2021-04-29T11:10:51Z", "event":"BuyWeapon", "Name":"Wpn_M_AssaultRifle_Laser_FAuto",
                # "Name_Localised":"TK Aphelion", "Price":125000, "SuitModuleID":1698372938719590 }
                # update credits
                if price := entry.get('Price') is None:
                    logger.error(f"BuyWeapon didn't contain Price: {entry}")

                else:
                    self.state['Credits'] -= price

            elif event_type == 'sellweapon':
                # We're not actually keeping track of all owned weapons, only those in
                # Suit Loadouts.
                # alpha4:
                # { "timestamp":"2021-04-29T10:50:34Z", "event":"SellWeapon", "Name":"wpn_m_assaultrifle_laser_fauto",
                # "Name_Localised":"TK Aphelion", "Price":75000, "SuitModuleID":1698364962722310 }

                # We need to look over all Suit Loadouts for ones that used this specific weapon
                # and update them to entirely empty that slot.
                for sl in self.state['SuitLoadouts']:
                    for w in self.state['SuitLoadouts'][sl]['slots']:
                        if self.state['SuitLoadouts'][sl]['slots'][w]['weaponrackId'] == entry['SuitModuleID']:
                            self.state['SuitLoadouts'][sl]['slots'].pop(w)
                            # We've changed the dict, so iteration breaks, but also the weapon
                            # could only possibly have been here once.
                            break

                # Update credits total
                if price := entry.get('Price') is None:
                    logger.error(f"SellWeapon didn't contain Price: {entry}")

                else:
                    self.state['Credits'] += price

            elif event_type == 'upgradeweapon':
                # We're not actually keeping track of all owned weapons, only those in
                # Suit Loadouts.
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'scanorganic':
                # Nothing of interest to our state.
                pass

            elif event_type == 'sellorganicdata':
                for bd in entry['BioData']:
                    self.state['Credits'] += bd.get('Value', 0) + bd.get('Bonus', 0)

            elif event_type == 'bookdropship':
                self.state['Credits'] -= entry.get('Cost', 0)
                self.state['Dropship'] = True
                # Technically we *might* now not be OnFoot.
                # The problem is that this event is recorded both for signing up for
                # an on-foot CZ, and when you use the Dropship to return after the
                # CZ completes.
                #
                # In the first case we're still in-station and thus still on-foot.
                #
                # In the second case we should instantly be in the Dropship and thus
                # not still on-foot, BUT it doesn't really matter as the next significant
                # event is going to be Disembark to on-foot anyway.

            elif event_type == 'booktaxi':
                self.state['Credits'] -= entry.get('Cost', 0)
                # Dont set taxi state here, as we're not IN a taxi yet. Set it on Embark

            elif event_type == 'canceldropship':
                self.state['Credits'] += entry.get('Refund', 0)
                self.state['Dropship'] = False
                self.state['Taxi'] = False

            elif event_type == 'canceltaxi':
                self.state['Credits'] += entry.get('Refund', 0)
                self.state['Taxi'] = False

            elif event_type == 'navroute' and not self.catching_up:
                # assume we've failed out the gate, then pull it back if things are fine
                self._last_navroute_journal_timestamp = mktime(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                self._navroute_retries_remaining = 11

                # Added in ED 3.7 - multi-hop route details in NavRoute.json
                # rather than duplicating this, lets just call the function
                if self.__navroute_retry():
                    entry = self.state['NavRoute']

            elif event_type == 'fcmaterials' and not self.catching_up:
                # assume we've failed out the gate, then pull it back if things are fine
                self._last_fcmaterials_journal_timestamp = mktime(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                self._fcmaterials_retries_remaining = 11

                # Added in ED 4.0.0.1300 - Fleet Carrier Materials market in FCMaterials.json
                # rather than duplicating this, lets just call the function
                if fcmaterials := self.__fcmaterials_retry():
                    entry = fcmaterials

            elif event_type == 'moduleinfo':
                with open(join(self.currentdir, 'ModulesInfo.json'), 'rb') as mf:  # type: ignore
                    try:
                        entry = json.load(mf)

                    except json.JSONDecodeError:
                        logger.exception('Failed decoding ModulesInfo.json')

                    else:
                        self.state['ModuleInfo'] = entry

            elif event_type in ('collectcargo', 'marketbuy', 'buydrones', 'miningrefined'):
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] += entry.get('Count', 1)

                if event_type == 'buydrones':
                    self.state['Credits'] -= entry.get('TotalCost', 0)

                elif event_type == 'marketbuy':
                    self.state['Credits'] -= entry.get('TotalCost', 0)

            elif event_type in ('ejectcargo', 'marketsell', 'selldrones'):
                commodity = self.canonicalise(entry['Type'])
                cargo = self.state['Cargo']
                cargo[commodity] -= entry.get('Count', 1)
                if cargo[commodity] <= 0:
                    cargo.pop(commodity)

                if event_type == 'marketsell':
                    self.state['Credits'] += entry.get('TotalSale', 0)

                elif event_type == 'selldrones':
                    self.state['Credits'] += entry.get('TotalSale', 0)

            elif event_type == 'searchandrescue':
                for item in entry.get('Items', []):
                    commodity = self.canonicalise(item['Name'])
                    cargo = self.state['Cargo']
                    cargo[commodity] -= item.get('Count', 1)
                    if cargo[commodity] <= 0:
                        cargo.pop(commodity)

            elif event_type == 'materials':
                for category in ('Raw', 'Manufactured', 'Encoded'):
                    self.state[category] = defaultdict(int)
                    self.state[category].update({
                        self.canonicalise(x['Name']): x['Count'] for x in entry.get(category, [])
                    })

            elif event_type == 'materialcollected':
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] += entry['Count']

            elif event_type in ('materialdiscarded', 'scientificresearch'):
                material = self.canonicalise(entry['Name'])
                state_category = self.state[entry['Category']]
                state_category[material] -= entry['Count']
                if state_category[material] <= 0:
                    state_category.pop(material)

            elif event_type == 'synthesis':
                for category in ('Raw', 'Manufactured', 'Encoded'):
                    for x in entry['Materials']:
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif event_type == 'materialtrade':
                category = self.category(entry['Paid']['Category'])
                state_category = self.state[category]
                paid = entry['Paid']
                received = entry['Received']

                state_category[paid['Material']] -= paid['Quantity']
                if state_category[paid['Material']] <= 0:
                    state_category.pop(paid['Material'])

                category = self.category(received['Category'])
                state_category[received['Material']] += received['Quantity']

            elif event_type == 'engineercraft' or (
                event_type == 'engineerlegacyconvert' and not entry.get('IsPreview')
            ):

                for category in ('Raw', 'Manufactured', 'Encoded'):
                    for x in entry.get('Ingredients', []):
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

                module = self.state['Modules'][entry['Slot']]
                assert module['Item'] == self.canonicalise(entry['Module'])
                module['Engineering'] = {
                    'Engineer':      entry['Engineer'],
                    'EngineerID':    entry['EngineerID'],
                    'BlueprintName': entry['BlueprintName'],
                    'BlueprintID':   entry['BlueprintID'],
                    'Level':         entry['Level'],
                    'Quality':       entry['Quality'],
                    'Modifiers':     entry['Modifiers'],
                }

                if 'ExperimentalEffect' in entry:
                    module['Engineering']['ExperimentalEffect'] = entry['ExperimentalEffect']
                    module['Engineering']['ExperimentalEffect_Localised'] = entry['ExperimentalEffect_Localised']

                else:
                    module['Engineering'].pop('ExperimentalEffect', None)
                    module['Engineering'].pop('ExperimentalEffect_Localised', None)

            elif event_type == 'missioncompleted':
                self.state['Credits'] += entry.get('Reward', 0)

                for reward in entry.get('CommodityReward', []):
                    commodity = self.canonicalise(reward['Name'])
                    self.state['Cargo'][commodity] += reward.get('Count', 1)

                for reward in entry.get('MaterialsReward', []):
                    if 'Category' in reward:  # Category not present in E:D 3.0
                        category = self.category(reward['Category'])
                        material = self.canonicalise(reward['Name'])
                        self.state[category][material] += reward.get('Count', 1)

            elif event_type == 'engineercontribution':
                commodity = self.canonicalise(entry.get('Commodity'))
                if commodity:
                    self.state['Cargo'][commodity] -= entry['Quantity']
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

                material = self.canonicalise(entry.get('Material'))
                if material:
                    for category in ('Raw', 'Manufactured', 'Encoded'):
                        if material in self.state[category]:
                            self.state[category][material] -= entry['Quantity']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif event_type == 'technologybroker':
                for thing in entry.get('Ingredients', []):  # 3.01
                    for category in ('Cargo', 'Raw', 'Manufactured', 'Encoded'):
                        item = self.canonicalise(thing['Name'])
                        if item in self.state[category]:
                            self.state[category][item] -= thing['Count']
                            if self.state[category][item] <= 0:
                                self.state[category].pop(item)

                for thing in entry.get('Commodities', []):  # 3.02
                    commodity = self.canonicalise(thing['Name'])
                    self.state['Cargo'][commodity] -= thing['Count']
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

                for thing in entry.get('Materials', []):  # 3.02
                    material = self.canonicalise(thing['Name'])
                    category = thing['Category']
                    self.state[category][material] -= thing['Count']
                    if self.state[category][material] <= 0:
                        self.state[category].pop(material)

            elif event_type == 'joinacrew':
                self.state['Captain'] = entry['Captain']
                self.state['Role'] = 'Idle'
                self.state['StarPos'] = None
                self.state['SystemName'] = None
                self.state['SystemAddress'] = None
                self.state['SystemPopulation'] = None
                self.state['StarPos'] = None
                self.state['Body'] = None
                self.state['BodyID'] = None
                self.state['BodyType'] = None
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None
                self.state['OnFoot'] = False

            elif event_type == 'changecrewrole':
                self.state['Role'] = entry['Role']

            elif event_type == 'quitacrew':
                self.state['Captain'] = None
                self.state['Role'] = None
                self.state['SystemName'] = None
                self.state['SystemAddress'] = None
                self.state['SystemPopulation'] = None
                self.state['StarPos'] = None
                self.state['Body'] = None
                self.state['BodyID'] = None
                self.state['BodyType'] = None
                self.state['StationName'] = None
                self.state['MarketID'] = None
                self.state['StationType'] = None
                self.stationservices = None

                # TODO: on_foot: Will we get an event after this to know ?

            elif event_type == 'friends':
                if entry['Status'] in ('Online', 'Added'):
                    self.state['Friends'].add(entry['Name'])

                else:
                    self.state['Friends'].discard(entry['Name'])

            # Try to keep Credits total updated
            elif event_type in ('multisellexplorationdata', 'sellexplorationdata'):
                self.state['Credits'] += entry.get('TotalEarnings', 0)

            elif event_type == 'buyexplorationdata':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'buytradedata':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'buyammo':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'communitygoalreward':
                self.state['Credits'] += entry.get('Reward', 0)

            elif event_type == 'crewhire':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'fetchremotemodule':
                self.state['Credits'] -= entry.get('TransferCost', 0)

            elif event_type == 'missionabandoned':
                # Is this paid at this point, or just a fine to pay later ?
                # self.state['Credits'] -= entry.get('Fine', 0)
                pass

            elif event_type in ('paybounties', 'payfines', 'paylegacyfines'):
                self.state['Credits'] -= entry.get('Amount', 0)

            elif event_type == 'redeemvoucher':
                self.state['Credits'] += entry.get('Amount', 0)

            elif event_type in ('refuelall', 'refuelpartial', 'repair', 'repairall', 'restockvehicle'):
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'sellshiponrebuy':
                self.state['Credits'] += entry.get('ShipPrice', 0)

            elif event_type == 'shipyardsell':
                self.state['Credits'] += entry.get('ShipPrice', 0)

            elif event_type == 'shipyardtransfer':
                self.state['Credits'] -= entry.get('TransferPrice', 0)

            elif event_type == 'powerplayfasttrack':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'powerplaysalary':
                self.state['Credits'] += entry.get('Amount', 0)

            elif event_type == 'squadroncreated':
                # v30 docs don't actually say anything about credits cost
                pass

            elif event_type == 'carrierbuy':
                self.state['Credits'] -= entry.get('Price', 0)

            elif event_type == 'carrierbanktransfer':
                if newbal := entry.get('PlayerBalance'):
                    self.state['Credits'] = newbal

            elif event_type == 'carrierdecommission':
                # v30 doc says nothing about citing the refund amount
                pass

            elif event_type == 'npccrewpaidwage':
                self.state['Credits'] -= entry.get('Amount', 0)

            elif event_type == 'resurrect':
                self.state['Credits'] -= entry.get('Cost', 0)

                # There should be a `Backpack` event as you 'come to' in the
                # new location, so no need to zero out BackPack here.

            elif event_type == 'powerplay':
                self.state['Powerplay']['Power'] = entry.get('Power', '')
                self.state['Powerplay']['Rank'] = entry.get('Rank', 0)
                self.state['Powerplay']['Merits'] = entry.get('Merits', 0)
                self.state['Powerplay']['Votes'] = entry.get('Votes', 0)
                self.state['Powerplay']['TimePledged'] = entry.get('TimePledged', 0)

            return entry

        except Exception as ex:
            logger.debug(f'Invalid journal entry:\n{line!r}\n', exc_info=ex)
            return {'event': None}

    def populate_version_info(self, entry: MutableMapping[str, str], suppress: bool = False):
        """
        Update game version information stored locally.

        :param entry: Either a Fileheader or LoadGame event
        """
        try:
            self.state['GameLanguage'] = entry['language']
            self.state['GameVersion'] = entry['gameversion']
            self.state['GameBuild'] = entry['build']
            self.version = self.state['GameVersion']

            try:
                self.version_semantic = semantic_version.Version.coerce(self.state['GameVersion'])

            except Exception:
                # Catching all Exceptions as this is *one* call, and we won't
                # get caught out by any semantic_version changes.
                self.version_semantic = None
                logger.error(f"Couldn't coerce {self.state['GameVersion']=}")
                pass

            else:
                logger.debug(f"Parsed {self.state['GameVersion']=} into {self.version_semantic=}")

            self.is_beta = any(v in self.version.lower() for v in ('alpha', 'beta'))  # type: ignore
        except KeyError:
            if not suppress:
                raise

    def backpack_set_empty(self):
        """Set the BackPack contents to be empty."""
        self.state['BackPack']['Component'] = defaultdict(int)
        self.state['BackPack']['Consumable'] = defaultdict(int)
        self.state['BackPack']['Item'] = defaultdict(int)
        self.state['BackPack']['Data'] = defaultdict(int)

    def suit_sane_name(self, name: str) -> str:
        """
        Given an input suit name return the best 'sane' name we can.

        AS of 4.0.0.102 the Journal events are fine for a Grade 1 suit, but
        anything above that has broken SuitName_Localised strings, e.g.
        $TacticalSuit_Class1_Name;

        Also, if there isn't a SuitName_Localised value at all we'll use the
        plain SuitName which can be, e.g. tacticalsuit_class3

        If the names were correct we would get 'Dominator Suit' in this instance,
        however what we want to return is, e.g. 'Dominator'.  As that's both
        sufficient for disambiguation and more succinct.

        :param name: Name that could be in any of the forms.
        :return: Our sane version of this suit's name.
        """
        # WORKAROUND 4.0.0.200 | 2021-05-27: Suit names above Grade 1 aren't localised
        #    properly by Frontier, so we do it ourselves.
        # Stage 1: Is it in `$<type>_Class<X>_Name;` form ?
        if m := re.fullmatch(r'(?i)^\$([^_]+)_Class([0-9]+)_Name;$', name):
            n, c = m.group(1, 2)
            name = n

        # Stage 2: Is it in `<type>_class<x>` form ?
        elif m := re.fullmatch(r'(?i)^([^_]+)_class([0-9]+)$', name):
            n, c = m.group(1, 2)
            name = n

        # Now turn either of those into a '<type> Suit' (modulo language) form
        if loc_lookup := edmc_suit_symbol_localised.get(self.state['GameLanguage']):
            name = loc_lookup.get(name.lower(), name)
        # WORKAROUND END

        # Finally, map that to a form without the verbose ' Suit' on the end
        name = edmc_suit_shortnames.get(name, name)

        return name

    def suitloadout_store_from_event(self, entry) -> tuple[int, int]:
        """
        Store Suit and SuitLoadout data from a journal event.

        Also use set currently in-use instances of them as being as per this
        event.

        :param entry: Journal entry - 'SwitchSuitLoadout' or 'SuitLoadout'
        :return Tuple[suit_slotid, suitloadout_slotid]: The IDs we set data for.
        """
        # This is the full ID from Frontier, it's not a sparse array slot id
        suitid = entry['SuitID']

        # Check if this looks like a suit we already have stored, so as
        # to avoid 'bad' Journal localised names.
        suit = self.state['Suits'].get(f"{suitid}", None)
        if suit is None:
            # Initial suit containing just the data that is then embedded in
            # the loadout

            # TODO: Attempt to map SuitName_Localised to something sane, if it
            #       isn't already.
            suitname = entry.get('SuitName_Localised', entry['SuitName'])
            edmc_suitname = self.suit_sane_name(suitname)
            suit = {
                'edmcName': edmc_suitname,
                'locName':  suitname,
            }

        # Overwrite with latest data, just in case, as this can be from CAPI which may or may not have had
        # all the data we wanted
        suit['suitId'] = entry['SuitID']
        suit['name'] = entry['SuitName']
        suit['mods'] = entry['SuitMods']

        suitloadout_slotid = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
        # Make the new loadout, in the CAPI format
        new_loadout = {
            'loadoutSlotId': suitloadout_slotid,
            'suit':          suit,
            'name':          entry['LoadoutName'],
            'slots':         self.suit_loadout_slots_array_to_dict(entry['Modules']),
        }
        # Assign this loadout into our state
        self.state['SuitLoadouts'][f"{suitloadout_slotid}"] = new_loadout

        # Now add in the extra fields for new_suit to be a 'full' Suit structure
        suit['id'] = suit.get('id')  # Not available in 4.0.0.100 journal event
        # Ensure the suit is in self.state['Suits']
        self.state['Suits'][f"{suitid}"] = suit

        return suitid, suitloadout_slotid

    def suit_and_loadout_setcurrent(self, suitid: int, suitloadout_slotid: int) -> bool:
        """
        Set self.state for SuitCurrent and SuitLoadoutCurrent as requested.

        If the specified slots are unknown we abort and return False, else
        return True.

        :param suitid: Numeric ID of the suit.
        :param suitloadout_slotid: Numeric ID of the slot for the suit loadout.
        :return: True if we could do this, False if not.
        """
        str_suitid = f"{suitid}"
        str_suitloadoutid = f"{suitloadout_slotid}"

        if (self.state['Suits'].get(str_suitid, False)
                and self.state['SuitLoadouts'].get(str_suitloadoutid, False)):
            self.state['SuitCurrent'] = self.state['Suits'][str_suitid]
            self.state['SuitLoadoutCurrent'] = self.state['SuitLoadouts'][str_suitloadoutid]
            return True

        logger.error(f"Tried to set a suit and suitloadout where we didn't know about both: {suitid=}, "
                     f"{str_suitloadoutid=}")
        return False

    # TODO: *This* will need refactoring and a proper validation infrastructure
    #       designed for this in the future.  This is a bandaid for a known issue.
    def event_valid_engineerprogress(self, entry) -> bool:  # noqa: CCR001
        """
        Check an `EngineerProgress` Journal event for validity.

        :param entry: Journal event dict
        :return: True if passes validation, else False.
        """
        engineers_present = 'Engineers' in entry
        progress_present = 'Progress' in entry

        if not (engineers_present or progress_present):
            logger.warning(f"EngineerProgress has neither 'Engineers' nor 'Progress': {entry=}")
            return False

        if engineers_present and progress_present:
            logger.warning(f"EngineerProgress has BOTH 'Engineers' and 'Progress': {entry=}")
            return False

        if engineers_present:
            engineers = entry['Engineers']
            # 'Engineers' version should have a list as value
            if not isinstance(engineers, list):
                logger.warning(f"EngineerProgress 'Engineers' is not a list: {entry=}")
                return False

            # It should have at least one entry?  This might still be valid ?
            if len(engineers) < 1:
                logger.warning(f"EngineerProgress 'Engineers' list is empty ?: {entry=}")
                # TODO: As this might be valid, we might want to only log
                return False

            # And that list should have all of these keys
            # For some Progress there's no Rank/RankProgress yet
            required_keys = ('Engineer', 'EngineerID', 'Rank', 'Progress', 'RankProgress')
            for e in engineers:
                missing_keys = [key for key in required_keys if key not in e]
                if any(key in ('Rank', 'RankProgress') and e.get('Progress') in ('Invited', 'Known') for key in
                       missing_keys):
                    continue

                if missing_keys:
                    logger.warning(f"Engineer entry without '{missing_keys[0]}' key: {e=} in {entry=}")
                    return False

        if progress_present:
            # Progress is only a single Engineer, so it's not an array
            # { "timestamp":"2021-05-24T17:57:52Z",
            #   "event":"EngineerProgress",
            #   "Engineer":"Felicity Farseer",
            #   "EngineerID":300100,
            #   "Progress":"Invited" }
            # For some Progress there's no Rank/RankProgress yet
            required_keys = ('Engineer', 'EngineerID', 'Rank', 'Progress', 'RankProgress')
            missing_keys = [key for key in required_keys if key not in entry]
            if any(key in ('Rank', 'RankProgress') and entry.get('Progress') in ('Invited', 'Known') for key in
                   missing_keys):
                if missing_keys:
                    logger.warning(f"Progress event without '{missing_keys[0]}' key: {entry=}")
                    return False

        return True

    def suit_loadout_id_from_loadoutid(self, journal_loadoutid: int) -> int:
        """
        Determine the CAPI-oriented numeric slot id for a Suit Loadout.

        :param journal_loadoutid: Journal `LoadoutID` integer value.
        :return:
        """
        # Observed LoadoutID in SwitchSuitLoadout events are, e.g.
        # 4293000005 for CAPI slot 5.
        # This *might* actually be "lower 6 bits", but maybe it's not.
        slotid = journal_loadoutid - 4293000000
        return slotid

    def canonicalise(self, item: str | None) -> str:
        """
        Produce canonical name for a ship module.

        Commodities, Modules and Ships can appear in different forms e.g. "$HNShockMount_Name;", "HNShockMount",
        and "hnshockmount", "$int_cargorack_size6_class1_name;" and "Int_CargoRack_Size6_Class1",
        "python" and "Python", etc.
        This returns a simple lowercased name e.g. 'hnshockmount', 'int_cargorack_size6_class1', 'python', etc

        :param item: str - 'Found' name of the item.
        :return: str - The canonical name.
        """
        if not item:
            return ''

        item = item.lower()
        match = self._RE_CANONICALISE.match(item)

        if match:
            return match.group(1)

        return item

    def category(self, item: str) -> str:
        """
        Determine the category of an item.

        :param item: str - The item in question.
        :return: str - The category for this item.
        """
        match = self._RE_CATEGORY.match(item)

        if match:
            return match.group(1).capitalize()

        return item.capitalize()

    def get_entry(self) -> MutableMapping[str, Any] | None:
        """
        Pull the next Journal event from the event_queue.

        :return: dict representing the event
        """
        if self.thread is None:
            logger.debug('Called whilst self.thread is None, returning')
            return None

        logger.trace_if('journal.queue', 'Begin')
        if self.event_queue.empty() and self.game_running():
            logger.error('event_queue is empty whilst game_running, this should not happen, returning')
            return None

        logger.trace_if('journal.queue', 'event_queue NOT empty')
        entry = self.parse_entry(self.event_queue.get_nowait())

        if entry['event'] == 'Location':
            logger.trace_if('journal.locations', '"Location" event')

        if not self.live and entry['event'] not in (None, 'Fileheader', 'ShutDown'):
            # Game not running locally, but Journal has been updated
            self.live = True
            entry = self.synthesize_startup_event()

            self.event_queue.put(json.dumps(entry, separators=(', ', ':')))

        elif self.live and entry['event'] == 'Music' and entry.get('MusicTrack') == 'MainMenu':
            ts = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())
            self.event_queue.put(
                f'{{ "timestamp":"{ts}", "event":"ShutDown" }}'
            )

        return entry

    def game_running(self) -> bool:
        """
        Determine if the game is currently running.

        :return: bool - True if the game is running.
        """
        if self.running_process:
            p = self.running_process
            try:
                with p.oneshot():
                    if p.status() not in [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING]:
                        raise psutil.NoSuchProcess(p.pid)
            except psutil.NoSuchProcess:
                # Process likely expired
                self.running_process = None
        if not self.running_process:
            try:
                edmc_process = psutil.Process()
                edmc_user = edmc_process.username()
                for proc in psutil.process_iter(['name', 'username']):
                    if 'EliteDangerous' in proc.info['name'] and proc.info['username'] == edmc_user:
                        self.running_process = proc
                        return True
            except psutil.NoSuchProcess:
                pass
            return False
        return bool(self.running_process)

    def ship(self, timestamped=True) -> MutableMapping[str, Any] | None:
        """
        Produce a subset of data for the current ship.

        Return a subset of the received data describing the current ship as a Loadout event.

        :param timestamped: bool - Whether to add a 'timestamp' member.
        :return: dict
        """
        if not self.state['Modules']:
            return None

        standard_order = (
            'ShipCockpit', 'CargoHatch', 'Armour', 'PowerPlant', 'MainEngines', 'FrameShiftDrive', 'LifeSupport',
            'PowerDistributor', 'Radar', 'FuelTank'
        )

        d: MutableMapping[str, Any] = {}
        if timestamped:
            d['timestamp'] = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())

        d['event'] = 'Loadout'
        d['Ship'] = self.state['ShipType']
        d['ShipID'] = self.state['ShipID']

        if self.state['ShipName']:
            d['ShipName'] = self.state['ShipName']

        if self.state['ShipIdent']:
            d['ShipIdent'] = self.state['ShipIdent']

        # sort modules by slot - hardpoints, standard, internal
        d['Modules'] = []

        for slot in sorted(
            self.state['Modules'],
            key=lambda x: (
                'Hardpoint' not in x,
                len(standard_order) if x not in standard_order else standard_order.index(x),
                'Slot' not in x,
                x
            )
        ):

            module = dict(self.state['Modules'][slot])
            module.pop('Health', None)
            module.pop('Value', None)
            d['Modules'].append(module)

        return d

    def export_ship(self, filename=None) -> None:  # noqa: C901, CCR001
        """
        Export ship loadout as a Loadout event.

        Writes either to the specified filename or to a formatted filename based on
        the ship name and a date+timestamp.

        :param filename: Name of file to write to, if not default.
        """
        # TODO(A_D): Some type checking has been disabled in here due to config.get getting weird outputs
        string = json.dumps(self.ship(False), ensure_ascii=False, indent=2, separators=(',', ': '))  # pretty print
        if filename:
            try:
                with open(filename, 'wt', encoding='utf-8') as h:
                    h.write(string)

            except UnicodeError:
                logger.exception("UnicodeError writing ship loadout to specified filename with utf-8 encoding"
                                 ", trying without..."
                                 )

                try:
                    with open(filename, 'wt') as h:
                        h.write(string)

                except OSError:
                    logger.exception("OSError writing ship loadout to specified filename with default encoding"
                                     ", aborting."
                                     )

            except OSError:
                logger.exception("OSError writing ship loadout to specified filename with utf-8 encoding, aborting.")

            return

        ship = util_ships.ship_file_name(self.state['ShipName'], self.state['ShipType'])
        regexp = re.compile(re.escape(ship) + r'\.\d{4}-\d\d-\d\dT\d\d\.\d\d\.\d\d\.txt')
        oldfiles = sorted((x for x in listdir(config.get_str('outdir')) if regexp.match(x)))
        if oldfiles:
            try:
                with open(join(config.get_str('outdir'), oldfiles[-1]), encoding='utf-8') as h:
                    if h.read() == string:
                        return  # same as last time - don't write

            except UnicodeError:
                logger.exception("UnicodeError reading old ship loadout with utf-8 encoding, trying without...")
                try:
                    with open(join(config.get_str('outdir'), oldfiles[-1])) as h:
                        if h.read() == string:
                            return  # same as last time - don't write

                except OSError:
                    logger.exception("OSError reading old ship loadout default encoding.")

                except ValueError:
                    # User was on $OtherEncoding, updated windows to be sane and use utf8 everywhere, thus
                    # the above open() fails, likely with a UnicodeDecodeError, which subclasses UnicodeError which
                    # subclasses ValueError, this catches ValueError _instead_ of UnicodeDecodeError just to be sure
                    # that if some other encoding error crops up we grab it too.
                    logger.exception('ValueError when reading old ship loadout default encoding')

            except OSError:
                logger.exception("OSError reading old ship loadout with default encoding")

        # Write
        ts = strftime('%Y-%m-%dT%H.%M.%S', localtime(time()))
        filename = join(config.get_str('outdir'), f'{ship}.{ts}.txt')

        try:
            with open(filename, 'wt', encoding='utf-8') as h:
                h.write(string)

        except UnicodeError:
            logger.exception("UnicodeError writing ship loadout to new filename with utf-8 encoding, trying without...")
            try:
                with open(filename, 'wt') as h:
                    h.write(string)

            except OSError:
                logger.exception("OSError writing ship loadout to new filename with default encoding, aborting.")

        except OSError:
            logger.exception("OSError writing ship loadout to new filename with utf-8 encoding, aborting.")

    def coalesce_cargo(self, raw_cargo: list[MutableMapping[str, Any]]) -> list[MutableMapping[str, Any]]:
        """
        Coalesce multiple entries of the same cargo into one.

        This exists due to the fact that a user can accept multiple missions that all require the same cargo. On the ED
        side, this is represented as multiple entries in the `Inventory` List with the same names etc. Just a differing
        MissionID. We (as in EDMC Core) dont want to support the multiple mission IDs, but DO want to have correct cargo
        counts. Thus, we reduce all existing cargo down to one total.
        >>> test = [
        ...     { "Name":"basicmedicines", "Name_Localised":"BM", "MissionID":684359162, "Count":147, "Stolen":0 },
        ...     { "Name":"survivalequipment", "Name_Localised":"SE", "MissionID":684358939, "Count":147, "Stolen":0 },
        ...     { "Name":"survivalequipment", "Name_Localised":"SE", "MissionID":684359344, "Count":36, "Stolen":0 }
        ... ]
        >>> EDLogs().coalesce_cargo(test) # doctest: +NORMALIZE_WHITESPACE
        [{'Name': 'basicmedicines', 'Name_Localised': 'BM', 'MissionID': 684359162, 'Count': 147, 'Stolen': 0},
        {'Name': 'survivalequipment', 'Name_Localised': 'SE', 'MissionID': 684358939, 'Count': 183, 'Stolen': 0}]

        :param raw_cargo: Raw cargo data (usually from Cargo.json)
        :return: Coalesced data
        """
        # self.state['Cargo'].update({self.canonicalise(x['Name']): x['Count'] for x in entry['Inventory']})
        out: list[MutableMapping[str, Any]] = []
        for inventory_item in raw_cargo:
            if not any(self.canonicalise(x['Name']) == self.canonicalise(inventory_item['Name']) for x in out):
                out.append(dict(inventory_item))
                continue

            # We've seen this before, update that count
            x = list(filter(lambda x: self.canonicalise(x['Name']) == self.canonicalise(inventory_item['Name']), out))

            if len(x) != 1:
                logger.debug(f'Unexpected number of items: {len(x)} where 1 was expected. {x}')

            x[0]['Count'] += inventory_item['Count']

        return out

    def suit_loadout_slots_array_to_dict(self, loadout: dict) -> dict:
        """
        Return a CAPI-style Suit loadout from a Journal style dict.

        :param loadout: e.g. Journal 'CreateSuitLoadout'->'Modules'.
        :return: CAPI-style dict for a suit loadout.
        """
        loadout_slots = {x['SlotName']: x for x in loadout}
        slots = {}
        for s in ('PrimaryWeapon1', 'PrimaryWeapon2', 'SecondaryWeapon'):
            if loadout_slots.get(s) is None:
                continue

            slots[s] = {
                'name':           loadout_slots[s]['ModuleName'],
                'id':             None,  # FDevID ?
                'weaponrackId':   loadout_slots[s]['SuitModuleID'],
                'locName':        loadout_slots[s].get('ModuleName_Localised', loadout_slots[s]['ModuleName']),
                'locDescription': '',
                'class':          loadout_slots[s]['Class'],
                'mods':           loadout_slots[s]['WeaponMods'],
            }

        return slots

    def _parse_navroute_file(self) -> dict[str, Any] | None:
        """Read and parse NavRoute.json."""
        if self.currentdir is None:
            raise ValueError('currentdir unset')

        try:

            with open(join(self.currentdir, 'NavRoute.json')) as f:
                raw = f.read()

        except Exception as e:
            logger.exception(f'Could not open navroute file. Bailing: {e}')
            return None

        try:
            data = json.loads(raw)

        except json.JSONDecodeError:
            logger.exception('Failed to decode NavRoute.json')
            return None

        if 'timestamp' not in data:  # quick sanity check
            return None

        return data

    def _parse_fcmaterials_file(self) -> dict[str, Any] | None:
        """Read and parse FCMaterials.json."""
        if self.currentdir is None:
            raise ValueError('currentdir unset')

        try:

            with open(join(self.currentdir, 'FCMaterials.json')) as f:
                raw = f.read()

        except Exception as e:
            logger.exception(f'Could not open FCMaterials file. Bailing: {e}')
            return None

        try:
            data = json.loads(raw)

        except json.JSONDecodeError:
            logger.exception('Failed to decode FCMaterials.json')
            return None

        if 'timestamp' not in data:  # quick sanity check
            return None

        return data

    @staticmethod
    def _parse_journal_timestamp(source: str) -> float:
        return mktime(strptime(source, '%Y-%m-%dT%H:%M:%SZ'))

    def __navroute_retry(self) -> bool:
        """Retry reading navroute files."""
        if self._navroute_retries_remaining == 0:
            return False

        logger.debug(f'Navroute read retry [{self._navroute_retries_remaining}]')
        self._navroute_retries_remaining -= 1

        if self._last_navroute_journal_timestamp is None:
            logger.critical('Asked to retry for navroute but also no set time to compare? This is a bug.')
            return False

        if (file := self._parse_navroute_file()) is None:
            logger.debug(
                'Failed to parse NavRoute.json. '
                + ('Trying again' if self._navroute_retries_remaining > 0 else 'Giving up')
            )
            return False

        # _parse_navroute_file verifies that this exists for us
        file_time = self._parse_journal_timestamp(file['timestamp'])
        if abs(file_time - self._last_navroute_journal_timestamp) > MAX_NAVROUTE_DISCREPANCY:
            logger.debug(
                f'Time discrepancy of more than {MAX_NAVROUTE_DISCREPANCY}s --'
                f' ({abs(file_time - self._last_navroute_journal_timestamp)}).'
                f' {"Trying again" if self._navroute_retries_remaining > 0 else "Giving up"}.'
            )
            return False

        # Handle it being `NavRouteClear`d already
        if file['event'].lower() == 'navrouteclear':
            logger.info('NavRoute file contained a NavRouteClear')
            # We do *NOT* copy into/clear the `self.state['NavRoute']`
        else:
            # everything is good, lets set what we need to and make sure we dont try again
            logger.info('Successfully read NavRoute file for last NavRoute event.')
            self.state['NavRoute'] = file

        self._navroute_retries_remaining = 0
        self._last_navroute_journal_timestamp = None
        return True

    def __fcmaterials_retry(self) -> dict[str, Any] | None:
        """Retry reading FCMaterials files."""
        if self._fcmaterials_retries_remaining == 0:
            return None

        logger.debug(f'FCMaterials read retry [{self._fcmaterials_retries_remaining}]')
        self._fcmaterials_retries_remaining -= 1

        if self._last_fcmaterials_journal_timestamp is None:
            logger.critical('Asked to retry for FCMaterials but also no set time to compare? This is a bug.')
            return None

        if (file := self._parse_fcmaterials_file()) is None:
            logger.debug(
                'Failed to parse FCMaterials.json. '
                + ('Trying again' if self._fcmaterials_retries_remaining > 0 else 'Giving up')
            )
            return None

        # _parse_fcmaterials_file verifies that this exists for us
        file_time = self._parse_journal_timestamp(file['timestamp'])
        if abs(file_time - self._last_fcmaterials_journal_timestamp) > MAX_FCMATERIALS_DISCREPANCY:
            logger.debug(
                f'Time discrepancy of more than {MAX_FCMATERIALS_DISCREPANCY}s --'
                f' ({abs(file_time - self._last_fcmaterials_journal_timestamp)}).'
                f' {"Trying again" if self._fcmaterials_retries_remaining > 0 else "Giving up"}.'
            )
            return None

        # everything is good, lets set what we need to and make sure we dont try again
        logger.info('Successfully read FCMaterials file for last FCMaterials event.')
        self._fcmaterials_retries_remaining = 0
        self._last_fcmaterials_journal_timestamp = None
        return file

    def is_live_galaxy(self) -> bool:
        """
        Indicate if current tracking indicates Live galaxy.

        NB: **MAY** be used by third-party plugins.

        We assume:
         1) `gameversion` remains something that semantic_verison.Version.coerce() can parse.
         2) Any Live galaxy client reports a version >= the defined base version.
         3) Any Legacy client will always report a version < that base version.
        :return: True for Live, False for Legacy or unknown.
        """
        # If we don't yet know the version we can't tell, so assume the worst
        if self.version_semantic is None:
            return False

        if self.version_semantic >= self.live_galaxy_base_version:
            return True

        return False


# singleton
monitor = EDLogs()
