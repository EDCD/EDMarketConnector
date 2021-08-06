"""Monitor for new Journal files and contents of latest."""

import json
import pathlib
import queue
import re
import threading
from calendar import timegm
from collections import OrderedDict, defaultdict
from os import SEEK_END, SEEK_SET, listdir
from os.path import basename, expanduser, isdir, join
from sys import platform
from time import gmtime, localtime, sleep, strftime, strptime, time
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, List, Literal, MutableMapping, Optional
from typing import OrderedDict as OrderedDictT
from typing import Tuple, Union, cast

from monitor_state_dict import (
    ModuleDict, ModuleEngineering, MonitorStateDict, NavRouteDict, OdysseyWeapon, SuitDict, SuitLoadoutDict
)

# spell-checker: words loadoutid slotid fdev fid relog onfoot fsdjump cheaty suitid fauto sauto intimidator navroute
# spell-checker: words quitacrew joinacrew sellshiponrebuy npccrewpaidwage

if TYPE_CHECKING:
    import tkinter

import util_ships
from config import config, trace_on
from edmc_data import edmc_suit_shortnames, edmc_suit_symbol_localised
from EDMCLogging import get_main_logger

logger = get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

if platform == 'darwin':
    from fcntl import fcntl

    from AppKit import NSWorkspace
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    F_GLOBAL_NOCACHE = 55

elif platform == 'win32':
    import ctypes
    from ctypes.wintypes import BOOL, HWND, LPARAM, LPWSTR

    from watchdog.events import FileCreatedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

    CloseHandle = ctypes.windll.kernel32.CloseHandle

    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW

    GetProcessHandleFromHwnd = ctypes.windll.oleacc.GetProcessHandleFromHwnd

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object  # dummy


# Journal handler
class EDLogs(FileSystemEventHandler):  # type: ignore # See below
    """Monitoring of Journal files."""

    # Magic with FileSystemEventHandler can confuse type checkers when they do not have access to every import

    _POLL = 1		# Polling is cheap, so do it often
    _RE_CANONICALISE = re.compile(r'\$(.+)_name;')
    _RE_CATEGORY = re.compile(r'\$MICRORESOURCE_CATEGORY_(.+);')
    _RE_LOGFILE = re.compile(r'^Journal(Alpha|Beta)?\.[0-9]{12}\.[0-9]{2}\.log$')
    _RE_SHIP_ONFOOT = re.compile(r'^(FlightSuit|UtilitySuit_Class.|TacticalSuit_Class.|ExplorationSuit_Class.)$')

    def __init__(self) -> None:
        # TODO(A_D): A bunch of these should be switched to default values (eg '' for strings) and no longer be Optional
        FileSystemEventHandler.__init__(self)  # futureproofing - not need for current version of watchdog
        self.root: 'tkinter.Tk' = None  # type: ignore # Don't use Optional[] - mypy thinks no methods
        self.currentdir: Optional[str] = None  # The actual logdir that we're monitoring
        self.logfile: Optional[str] = None
        self.observer: Optional['Observer'] = None
        self.observed = None  # a watchdog ObservedWatch, or None if polling
        self.thread: Optional[threading.Thread] = None
        # For communicating journal entries back to main thread
        self.event_queue: queue.Queue = queue.Queue(maxsize=0)

        # On startup we might be:
        # 1) Looking at an old journal file because the game isn't running or the user has exited to the main menu.
        # 2) Looking at an empty journal (only 'Fileheader') because the user is at the main menu.
        # 3) In the middle of a 'live' game.
        # If 1 or 2 a LoadGame event will happen when the game goes live.
        # If 3 we need to inject a special 'StartUp' event since consumers won't see the LoadGame event.
        self.live = False

        self.game_was_running = False  # For generation of the "ShutDown" event

        # Context for journal handling
        self.version: Optional[str] = None
        self.is_beta = False
        self.mode: Optional[str] = None
        self.group: Optional[str] = None
        self.cmdr: Optional[str] = None
        self.planet: Optional[str] = None
        self.system: Optional[str] = None
        self.station: Optional[str] = None
        self.station_marketid: Optional[int] = None
        self.stationtype: Optional[str] = None
        self.coordinates: Optional[Tuple[float, float, float]] = None
        self.systemaddress: Optional[int] = None
        self.systempopulation: Optional[int] = None
        self.started: Optional[int] = None  # Timestamp of the LoadGame event

        self.__init_state()

    def __init_state(self) -> None:
        # Cmdr state shared with EDSM and plugins
        # If you change anything here update PLUGINS.md documentation!
        self.state: MonitorStateDict = {
            'GameLanguage':       '',  # From `Fileheader
            'GameVersion':        '',  # From `Fileheader
            'GameBuild':          '',  # From `Fileheader
            'Captain':            None,  # On a crew
            'Cargo':              defaultdict(int),
            'Credits':            0-1,  # HACK: https://github.com/PyCQA/pycodestyle/issues/1008
            'FID':                '',  # Frontier Cmdr ID
            'Horizons':           False,  # Does this user have Horizons?
            'Odyssey':            False,  # Have we detected we're running under Odyssey?
            'Loan':               0,
            'Raw':                defaultdict(int),
            'Manufactured':       defaultdict(int),
            'Encoded':            defaultdict(int),
            'Engineers':          {},
            'Rank':               {},
            'Reputation':         {},
            'Statistics':         {},
            'Role':               None,  # Crew role - None, Idle, FireCon, FighterCon
            'Friends':            set(),  # Online friends
            'ShipID':             0-1,  # HACK: https://github.com/PyCQA/pycodestyle/issues/1008
            'ShipIdent':          '',
            'ShipName':           '',
            'ShipType':           '',
            'HullValue':          0,
            'ModulesValue':       0,
            'Rebuy':              0,
            'Modules':            {},
            'CargoJSON':          {},  # The raw data from the last time cargo.json was read
            'NavRoute':           NavRouteDict(timestamp='', route=[]),  # Last plotted route from Route.json file
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
            'BackpackJSON':       {},  # Raw JSON from `Backpack.json` file, if available
            'ShipLockerJSON':     {},  # Raw JSON from the `ShipLocker.json` file, if available
            'SuitCurrent':        None,
            'Suits':              {},
            'SuitLoadoutCurrent': None,
            'SuitLoadouts':       {},
            'Taxi':               False,  # True whenever we are _in_ a taxi. ie, this is reset on Disembark etc.
            'Dropship':           False,  # Best effort as to whether or not the above taxi is a dropship.
            'Body':               '',
            'BodyType':           '',
            'ModuleInfo':         {},
        }

    def start(self, root: 'tkinter.Tk') -> bool:  # noqa: CCR001
        """
        Start journal monitoring.

        :param root: The parent Tk window.
        :return: bool - False if we couldn't access/find latest Journal file.
        """
        logger.debug('Begin...')
        self.root = root  # type: ignore
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

        # Latest pre-existing logfile - e.g. if E:D is already running. Assumes logs sort alphabetically.
        # Do this before setting up the observer in case the journal directory has gone away
        try:  # TODO: This should be replaced with something specific ONLY wrapping listdir
            logfiles = sorted(
                (x for x in listdir(self.currentdir) if self._RE_LOGFILE.search(x)),
                key=lambda x: x.split('.')[1:]
            )

            self.logfile = join(self.currentdir, logfiles[-1]) if logfiles else None

        except Exception:
            logger.exception('Failed to find latest logfile')
            self.logfile = None
            return False

        # Set up a watchdog observer.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = bool(config.get_str('journaldir')) and platform != 'win32'
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

    def stop(self) -> None:
        """Stop journal monitoring."""
        logger.debug('Stopping monitoring Journal')

        self.currentdir = None
        self.version = None
        self.mode = None
        self.group = None
        self.cmdr = None
        self.planet = None
        self.system = None
        self.station = None
        self.station_marketid = None
        self.stationtype = None
        self.stationservices = None
        self.coordinates = None
        self.systemaddress = None
        self.is_beta = False
        self.state['OnFoot'] = False
        self.state['Body'] = ''
        self.state['BodyType'] = ''

        if self.observed:
            logger.debug('self.observed: Calling unschedule_all()')
            self.observed = None
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

    def on_created(self, event: 'FileCreatedEvent') -> None:
        """Watchdog callback when, e.g. client (re)started."""
        if not event.is_directory and self._RE_LOGFILE.search(basename(event.src_path)):

            self.logfile = event.src_path

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
            if platform == 'darwin':
                fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

            for line in loghandle:
                try:
                    # if b'"event":"Location"' in line:
                    #     logger.trace('"Location" event in the past at startup')

                    self.parse_entry(line)  # Some events are of interest even in the past

                except Exception as ex:
                    logger.debug(f'Invalid journal entry:\n{line!r}\n', exc_info=ex)

            log_pos = loghandle.tell()

        else:
            loghandle = None  # type: ignore

        logger.debug('Now at end of latest file.')

        self.game_was_running = self.game_running()

        if self.live:
            if self.game_was_running:
                # Game is running locally
                entry: OrderedDictT[str, Any] = OrderedDict([
                    ('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())),
                    ('event', 'StartUp'),
                    ('StarSystem', self.system),
                    ('StarPos', self.coordinates),
                    ('SystemAddress', self.systemaddress),
                    ('Population', self.systempopulation),
                ])

                if self.planet:
                    entry['Body'] = self.planet

                entry['Docked'] = bool(self.station)

                if self.station:
                    entry['StationName'] = self.station
                    entry['StationType'] = self.stationtype
                    entry['MarketID'] = self.station_marketid

                self.event_queue.put(json.dumps(entry, separators=(', ', ':')))

            else:
                # Generate null event to update the display (with possibly out-of-date info)
                self.event_queue.put(None)
                self.live = False

        # Watchdog thread -- there is a way to get this by using self.observer.emitters and checking for an attribute:
        # watch, but that may have unforseen differences in behaviour.
        # Note: Uses undocumented attribute
        emitter = self.observed and self.observer._emitter_for_watch[self.observed]  # type: ignore

        logger.debug('Entering loop...')
        while True:

            # Check whether new log file started, e.g. client (re)started.
            if emitter and emitter.is_alive():
                newlogfile = self.logfile  # updated by on_created watchdog callback
            else:
                # Poll
                try:
                    logfiles = sorted(
                        (x for x in listdir(self.currentdir) if self._RE_LOGFILE.search(x)),
                        key=lambda x: x.split('.')[1:]
                    )

                    newlogfile = join(self.currentdir, logfiles[-1]) if logfiles else None  # type: ignore

                except Exception:
                    logger.exception('Failed to find latest logfile')
                    newlogfile = None

            if logfile:
                loghandle.seek(0, SEEK_END)		  # required to make macOS notice log change over SMB
                loghandle.seek(log_pos, SEEK_SET)  # reset EOF flag # TODO: log_pos reported as possibly unbound
                for line in loghandle:
                    # Paranoia check to see if we're shutting down
                    if threading.current_thread() != self.thread:
                        logger.info("We're not meant to be running, exiting...")
                        return  # Terminate

                    if b'"event":"Continue"' in line:
                        for _ in range(10):
                            logger.trace("****")
                        logger.trace('Found a Continue event, its being added to the list, we will finish this file up'
                                     ' and then continue with the next')

                    self.event_queue.put(line)

                if not self.event_queue.empty():
                    if not config.shutting_down:
                        # logger.trace('Sending <<JournalEvent>>')
                        self.root.event_generate('<<JournalEvent>>', when="tail")

                log_pos = loghandle.tell()

            if logfile != newlogfile:
                for _ in range(10):
                    logger.trace("****")
                logger.info(f'New Journal File. Was "{logfile}", now "{newlogfile}"')
                logfile = newlogfile
                if loghandle:
                    loghandle.close()

                if logfile:
                    loghandle = open(logfile, 'rb', 0)  # unbuffered
                    if platform == 'darwin':
                        fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

                    log_pos = 0

            sleep(self._POLL)

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
                        # logger.trace('Sending <<JournalEvent>>')
                        self.root.event_generate('<<JournalEvent>>', when="tail")

                    self.game_was_running = False

            else:
                self.game_was_running = self.game_running()

        logger.debug('Done.')

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
            entry: MutableMapping[str, Any] = json.loads(line, object_pairs_hook=OrderedDict)
            entry['timestamp']  # we expect this to exist # TODO: replace with assert? or an if key in check

            event_type = entry['event'].lower()
            if event_type == 'fileheader':
                self.live = False

                self.cmdr = None
                self.mode = None
                self.group = None
                self.planet = None
                self.system = None
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.systemaddress = None
                self.started = None
                self.__init_state()

                # Do this AFTER __init_state() lest our nice new state entries be None
                self.populate_version_info(entry)

            elif event_type == 'commander':
                self.live = True  # First event in 3.0
                self.cmdr = entry['Name']
                self.state['FID'] = entry['FID']
                if 'startup' in trace_on:
                    logger.trace(f'"Commander" event, {monitor.cmdr=}, {monitor.state["FID"]=}')

            elif event_type == 'loadgame':
                # Odyssey Release Update 5 -- This contains data that doesn't match the format used in FileHeader above
                self.populate_version_info(entry, suppress=True)

                # alpha4
                # Odyssey: bool
                self.cmdr = entry['Commander']
                # 'Open', 'Solo', 'Group', or None for CQC (and Training - but no LoadGame event)
                self.mode = entry.get('GameMode')
                self.group = entry.get('Group')
                self.planet = None
                self.system = None
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.systemaddress = None
                self.started = timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                # Don't set Ship, ShipID etc since this will reflect Fighter or SRV if starting in those

                # Cant use update() without the entire thing, do stuff manually here
                self.state['Captain'] = None
                self.state['Credits'] = entry['Credits']
                self.state['FID'] = entry.get('FID', '')   # From 3.3
                self.state['Horizons'] = entry['Horizons']  # From 3.0
                self.state['Odyssey'] = entry.get('Odyssey', False)  # From 4.0 Odyssey
                self.state['Loan'] = entry['Loan']
                self.state['Engineers'] = {}
                self.state['Rank'] = {}
                self.state['Reputation'] = {}
                self.state['Statistics'] = {}
                self.state['Role'] = None
                self.state['Taxi'] = False
                self.state['Dropship'] = False
                self.state['Body'] = ''
                self.state['BodyType'] = ''

                if entry.get('Ship') is not None and self._RE_SHIP_ONFOOT.search(entry['Ship']):
                    self.state['OnFoot'] = True

                if 'startup' in trace_on:
                    logger.trace(f'"LoadGame" event, {monitor.cmdr=}, {monitor.state["FID"]=}')

            elif event_type == 'newcommander':
                self.cmdr = entry['Name']
                self.group = None

            elif event_type == 'setusershipname':
                self.state['ShipID'] = entry['ShipID']
                if 'UserShipId' in entry:  # Only present when changing the ship's ident
                    self.state['ShipIdent'] = entry['UserShipId']

                self.state['ShipName'] = entry.get('UserShipName', '')
                self.state['ShipType'] = self.canonicalise(entry['Ship'])

            elif event_type == 'shipyardbuy':
                self.state['ShipID'] = -1
                self.state['ShipIdent'] = ''
                self.state['ShipName'] = ''
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = 0
                self.state['ModulesValue'] = 0
                self.state['Rebuy'] = 0
                self.state['Modules'] = {}

                self.state['Credits'] -= entry.get('ShipPrice', 0)

            elif event_type == 'shipyardswap':
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = ''
                self.state['ShipName'] = ''
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = 0
                self.state['ModulesValue'] = 0
                self.state['Rebuy'] = 0
                self.state['Modules'] = {}

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
                self.state['HullValue'] = entry.get('HullValue', 0)  # not present on exiting Outfitting
                self.state['ModulesValue'] = entry.get('ModulesValue', 0)  # not present on exiting Outfitting
                self.state['Rebuy'] = entry.get('Rebuy', 0)
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

            elif event_type == 'modulebuy':
                new_module: ModuleDict = {
                    'Slot':     entry['Slot'],
                    'Item':     self.canonicalise(entry['BuyItem']),
                    'On':       True,
                    'Priority': 1,
                    'Health':   1.0,
                    'Value':    entry['BuyPrice'],
                }
                self.state['Modules'][entry['Slot']] = new_module

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
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None

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
                self.station = None
                if entry.get('OnStation'):
                    self.station = entry.get('StationName', '')

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
                    self.station = entry.get('StationName', '')

                else:
                    self.station = None

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

            elif event_type == 'docked':
                self.station = entry.get('StationName')  # May be None
                self.station_marketid = entry.get('MarketID')  # May be None
                self.stationtype = entry.get('StationType')  # May be None
                self.stationservices = entry.get('StationServices')  # None under E:D < 2.4

                # No need to set self.state['Taxi'] or Dropship here, if its those, the next event is a Disembark anyway

            elif event_type in ('location', 'fsdjump', 'carrierjump'):
                # alpha4 - any changes ?
                # Location:
                # New in Odyssey:
                #     • Taxi: bool
                #     • Multicrew: bool
                #     • InSRV: bool
                #     • OnFoot: bool
                if event_type in ('location', 'carrierjump'):
                    self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None
                    self.state['Body'] = entry.get('Body', '')
                    self.state['BodyType'] = entry.get('BodyType', '')

                    # if event_type == 'location':
                    #     logger.trace('"Location" event')

                elif event_type == 'fsdjump':
                    self.planet = None
                    self.state['Body'] = ''
                    self.state['BodyType'] = ''

                if 'StarPos' in entry:
                    self.coordinates = tuple(entry['StarPos'])  # type: ignore

                self.systemaddress = entry.get('SystemAddress')

                self.systempopulation = entry.get('Population')

                self.system = 'CQC' if entry['StarSystem'] == 'ProvingGround' else entry['StarSystem']

                self.station = entry.get('StationName')  # May be None
                # If on foot in-station 'Docked' is false, but we have a
                # 'BodyType' of 'Station', and the 'Body' is the station name
                # NB: No MarketID
                if entry.get('BodyType') and entry['BodyType'] == 'Station':
                    self.station = entry.get('Body')

                self.station_marketid = entry.get('MarketID')  # May be None
                self.stationtype = entry.get('StationType')  # May be None
                self.stationservices = entry.get('StationServices')  # None in Odyssey for on-foot 'Location'

                self.state['Taxi'] = entry.get('Taxi', False)
                if not self.state['Taxi']:
                    self.state['Dropship'] = False

            elif event_type == 'approachbody':
                self.planet = entry['Body']
                self.state['Body'] = entry['Body']
                self.state['BodyType'] = 'Planet'  # Best guess. Journal says always planet.

            elif event_type in ('leavebody', 'supercruiseentry'):
                self.planet = None
                self.state['Body'] = ''
                self.state['BodyType'] = ''

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
                payload = OrderedDict(entry)
                payload.pop('event')
                payload.pop('timestamp')
                # NB: We need the original casing for these keys
                self.state[entry['event']] = payload  # type: ignore # Non-literal, but the options are ensured above

            elif event_type == 'engineerprogress':
                # Sanity check - at least once the 'Engineer' (name) was missing from this in early
                # Odyssey 4.0.0.100.  Might only have been a server issue causing incomplete data.

                if self.event_valid_engineerprogress(entry):
                    engineers = self.state['Engineers']
                    if 'Engineers' in entry:  # Startup summary
                        to_set: Dict[str, Union[str, Tuple[int, int]]] = {
                            e['Engineer']: ((e['Rank'], e.get('RankProgress', 0)) if 'Rank' in e else e['Progress'])
                            for e in entry['Engineers']
                        }
                        self.state['Engineers'] = to_set

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
                # "ShipLocker" will be a full list written to the journal at startup/boarding/disembarking, and also
                # written to a separate shiplocker.json file - other updates will just update that file and mention it
                # has changed with an empty shiplocker event in the main journal.

                # Always attempt loading of this.
                # Confirmed filename for 4.0.0.400
                try:
                    currentdir_path = pathlib.Path(str(self.currentdir))
                    with open(currentdir_path / 'ShipLocker.json', 'rb') as h:  # type: ignore
                        entry = json.load(h, object_pairs_hook=OrderedDict)
                        self.state['ShipLockerJSON'] = entry

                except FileNotFoundError:
                    logger.warning('ShipLocker event but no ShipLocker.json file')
                    pass

                except json.JSONDecodeError as e:
                    logger.warning(f'ShipLocker.json failed to decode:\n{e!r}\n')
                    pass

                if not all(t in entry for t in ('Components', 'Consumables', 'Data', 'Items')):
                    logger.trace('ShipLocker event is an empty one (missing at least one data type)')

                # This event has the current totals, so drop any current data
                self.state['Component'] = defaultdict(int)
                self.state['Consumable'] = defaultdict(int)
                self.state['Item'] = defaultdict(int)
                self.state['Data'] = defaultdict(int)

                # 4.0.0.400 - No longer zeroing out the BackPack in this event,
                # as we should now always get either `Backpack` event/file or
                # `BackpackChange` as needed.

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
                        if TYPE_CHECKING:
                            # Cheaty "its fine I promise" for TypedDict
                            category = cast(Literal['Component', 'Data', 'Consumable', 'Item'], category)

                        if changes == 'Removed':
                            self.state['BackPack'][category][name] -= c['Count']

                        elif changes == 'Added':
                            self.state['BackPack'][category][name] += c['Count']

                # Paranoia check to see if anything has gone negative.
                # As of Odyssey Alpha Phase 1 Hotfix 2 keeping track of BackPack
                # materials is impossible when used/picked up anyway.
                for c in self.state['BackPack']:
                    for m in self.state['BackPack'][c]:  # type: ignore # c and m are dynamic but "safe"
                        if self.state['BackPack'][c][m] < 0:  # type: ignore # c and m are dynamic but "safe"
                            self.state['BackPack'][c][m] = 0  # type: ignore # c and m are dynamic but "safe"

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
                        self.state['SuitLoadouts'].pop(loadout_id)

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
                to_set_suit: SuitDict = {
                    'name':      entry['Name'],
                    'locName':   loc_name,
                    'edmcName':  self.suit_sane_name(loc_name),
                    'id':        None,  # Is this an FDev ID for suit type ?
                    'suitId':    entry['SuitID'],
                    'mods':      entry['SuitMods'],  # Suits can (rarely) be bought with modules installed
                }
                self.state['Suits'][entry['SuitID']] = to_set_suit

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
                        w_to_set: OdysseyWeapon = {
                            'name':           entry['ModuleName'],
                            'locName':        entry.get('ModuleName_Localised', entry['ModuleName']),
                            'id':             None,
                            'weaponrackId':   entry['SuitModuleID'],
                            'locDescription': '',
                            'class':          entry['Class'],
                            'mods':           entry['WeaponMods'],
                        }

                        self.state['SuitLoadouts'][loadout_id]['slots'][entry['SlotName']] = w_to_set

                    except KeyError:
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

            elif event_type == 'navroute':
                # Added in ED 3.7 - multi-hop route details in NavRoute.json
                with open(join(self.currentdir, 'NavRoute.json'), 'rb') as rf:  # type: ignore
                    try:
                        nv_entry: NavRouteDict = json.load(rf)

                    except json.JSONDecodeError:
                        logger.exception('Failed decoding NavRoute.json', exc_info=True)

                    else:
                        self.state['NavRoute'] = nv_entry
                        entry = cast(dict, nv_entry)

            elif event_type == 'moduleinfo':
                with open(join(self.currentdir, 'ModulesInfo.json'), 'rb') as mf:  # type: ignore
                    try:
                        m_entry = json.load(mf)

                    except json.JSONDecodeError:
                        logger.exception('Failed decoding ModulesInfo.json', exc_info=True)

                    else:
                        self.state['ModuleInfo'] = m_entry

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
                    category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
                    self.state[category] = defaultdict(int)
                    self.state[category].update({
                        self.canonicalise(x['Name']): x['Count'] for x in entry.get(category, [])
                    })

            elif event_type == 'materialcollected':
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] += entry['Count']  # type: ignore

            elif event_type in ('materialdiscarded', 'scientificresearch'):
                material = self.canonicalise(entry['Name'])
                state_category = self.state[entry['Category']]  # type: ignore
                state_category[material] -= entry['Count']
                if state_category[material] <= 0:
                    state_category.pop(material)

            elif event_type == 'synthesis':
                for category in ('Raw', 'Manufactured', 'Encoded'):
                    category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
                    for x in entry['Materials']:
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif event_type == 'materialtrade':
                category = self.category(entry['Paid']['Category'])
                state_category = self.state[category]  # type: ignore
                paid = entry['Paid']
                received = entry['Received']

                state_category[paid['Material']] -= paid['Quantity']
                if state_category[paid['Material']] <= 0:
                    state_category.pop(paid['Material'])

                category = self.category(received['Category'])
                state_category[received['Material']] += received['Quantity']

            elif event_type == 'EngineerCraft' or (
                event_type == 'engineerlegacyconvert' and not entry.get('IsPreview')
            ):

                for category in ('Raw', 'Manufactured', 'Encoded'):
                    category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
                    for x in entry.get('Ingredients', []):
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

                module = self.state['Modules'][entry['Slot']]
                assert(module['Item'] == self.canonicalise(entry['Module']))
                to_set_me: ModuleEngineering = {
                    'Engineer':      entry['Engineer'],
                    'EngineerID':    entry['EngineerID'],
                    'BlueprintName': entry['BlueprintName'],
                    'BlueprintID':   entry['BlueprintID'],
                    'Level':         entry['Level'],
                    'Quality':       entry['Quality'],
                    'Modifiers':     entry['Modifiers'],
                }

                module['Engineering'] = to_set_me

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
                        self.state[category][material] += reward.get('Count', 1)  # type: ignore

            elif event_type == 'engineercontribution':
                commodity = self.canonicalise(entry.get('Commodity'))
                if commodity:
                    self.state['Cargo'][commodity] -= entry['Quantity']
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

                material = self.canonicalise(entry.get('Material'))
                if material:
                    for category in ('Raw', 'Manufactured', 'Encoded'):
                        category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
                        if material in self.state[category]:
                            self.state[category][material] -= entry['Quantity']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif event_type == 'technologybroker':
                for thing in entry.get('Ingredients', []):  # 3.01
                    for category in ('Cargo', 'Raw', 'Manufactured', 'Encoded'):
                        category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
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
                    category = cast(Literal['Raw', 'Manufactured', 'Encoded'], category)
                    self.state[category][material] -= thing['Count']
                    if self.state[category][material] <= 0:
                        self.state[category].pop(material)

            elif event_type == 'joinacrew':
                self.state['Captain'] = entry['Captain']
                self.state['Role'] = 'Idle'
                self.planet = None
                self.system = None
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.systemaddress = None
                self.state['OnFoot'] = False

                self.state['Body'] = ''
                self.state['BodyType'] = ''

            elif event_type == 'changecrewrole':
                self.state['Role'] = entry['Role']

            elif event_type == 'quitacrew':
                self.state['Captain'] = None
                self.state['Role'] = None
                self.planet = None
                self.system = None
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.systemaddress = None

                self.state['Body'] = ''
                self.state['BodyType'] = ''
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
                if (new_bal := entry.get('PlayerBalance')):
                    self.state['Credits'] = new_bal

            elif event_type == 'carrierdecommission':
                # v30 doc says nothing about citing the refund amount
                pass

            elif event_type == 'npccrewpaidwage':
                self.state['Credits'] -= entry.get('Amount', 0)

            elif event_type == 'resurrect':
                self.state['Credits'] -= entry.get('Cost', 0)

                # There should be a `Backpack` event as you 'come to' in the
                # new location, so no need to zero out BackPack here.

            # HACK (not game related / 2021-06-2): self.planet is moved into a more general self.state['Body'].
            # This exists to help plugins doing what they SHOULDN'T BE cope. It will be removed at some point.
            if self.state['Body'] is None or self.state['BodyType'] == 'Planet':
                self.planet = self.state['Body']

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
            self.is_beta = any(v in self.version.lower() for v in ('alpha', 'beta'))
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

    def suitloadout_store_from_event(self, entry) -> Tuple[int, int]:
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
        suit: Optional[SuitDict] = self.state['Suits'].get(suitid, None)
        if suit is None:
            # Initial suit containing just the data that is then embedded in
            # the loadout

            # TODO: Attempt to map SuitName_Localised to something sane, if it
            #       isn't already.
            suitname = entry.get('SuitName_Localised', entry['SuitName'])
            edmc_suitname = self.suit_sane_name(suitname)
            suit = {
                'edmcName':     edmc_suitname,
                'locName':      suitname,
                'suitId':       0-1,
                'id':           None,
                'name':         entry['SuitName'],
                'mods':         entry['SuitMods']
            }

        # Overwrite with latest data, just in case, as this can be from CAPI which may or may not have had
        # all the data we wanted
        suit['suitId'] = entry['SuitID']
        suit['name'] = entry['SuitName']
        suit['mods'] = entry['SuitMods']

        suitloadout_slotid = self.suit_loadout_id_from_loadoutid(entry['LoadoutID'])
        # Make the new loadout, in the CAPI format
        new_loadout: SuitLoadoutDict = {
            'loadoutSlotId': suitloadout_slotid,
            'suit':          suit,
            'name':          entry['LoadoutName'],
            'slots':         self.suit_loadout_slots_array_to_dict(entry['Modules']),
        }

        # Assign this loadout into our state
        self.state['SuitLoadouts'][suitloadout_slotid] = new_loadout

        # Now add in the extra fields for new_suit to be a 'full' Suit structure
        suit['id'] = suit.get('id')  # Not available in 4.0.0.100 journal event
        # Ensure the suit is in self.state['Suits']
        self.state['Suits'][suitid] = suit

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
        if suitid in self.state['Suits'] and suitloadout_slotid in self.state['SuitLoadouts']:
            self.state['SuitCurrent'] = self.state['Suits'][suitid]
            self.state['SuitLoadoutCurrent'] = self.state['SuitLoadouts'][suitloadout_slotid]
            return True

        logger.error(f"Tried to set a suit and suitloadout where we didn't know about both: {suitid=}, "
                     f"{suitloadout_slotid=}")

        return False

    # TODO: *This* will need refactoring and a proper validation infrastructure
    #       designed for this in the future.  This is a bandaid for a known issue.
    def event_valid_engineerprogress(self, entry) -> bool:  # noqa: CCR001 C901
        """
        Check an `EngineerProgress` Journal event for validity.

        :param entry: Journal event dict
        :return: True if passes validation, else False.
        """
        # The event should have at least one of these
        if 'Engineers' not in entry and 'Progress' not in entry:
            logger.warning(f"EngineerProgress has neither 'Engineers' nor 'Progress': {entry=}")
            return False

        # But not both of them
        if 'Engineers' in entry and 'Progress' in entry:
            logger.warning(f"EngineerProgress has BOTH 'Engineers' and 'Progress': {entry=}")
            return False

        if 'Engineers' in entry:
            # 'Engineers' version should have a list as value
            if not isinstance(entry['Engineers'], list):
                logger.warning(f"EngineerProgress 'Engineers' is not a list: {entry=}")
                return False

            # It should have at least one entry?  This might still be valid ?
            if len(entry['Engineers']) < 1:
                logger.warning(f"EngineerProgress 'Engineers' list is empty ?: {entry=}")
                # TODO: As this might be valid, we might want to only log
                return False

            # And that list should have all of these keys
            for e in entry['Engineers']:
                for f in ('Engineer', 'EngineerID', 'Rank', 'Progress', 'RankProgress'):
                    if f not in e:
                        # For some Progress there's no Rank/RankProgress yet
                        if f in ('Rank', 'RankProgress'):
                            if (progress := e.get('Progress', None)) is not None:
                                if progress in ('Invited', 'Known'):
                                    continue

                        logger.warning(f"Engineer entry without '{f}' key: {e=} in {entry=}")
                        return False

        if 'Progress' in entry:
            # Progress is only a single Engineer, so it's not an array
            # { "timestamp":"2021-05-24T17:57:52Z",
            #   "event":"EngineerProgress",
            #   "Engineer":"Felicity Farseer",
            #   "EngineerID":300100,
            #   "Progress":"Invited" }
            for f in ('Engineer', 'EngineerID', 'Rank', 'Progress', 'RankProgress'):
                if f not in entry:
                    # For some Progress there's no Rank/RankProgress yet
                    if f in ('Rank', 'RankProgress'):
                        if (progress := entry.get('Progress', None)) is not None:
                            if progress in ('Invited', 'Known'):
                                continue

                    logger.warning(f"Progress event without '{f}' key: {entry=}")
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

    def canonicalise(self, item: Optional[str]) -> str:
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

    def get_entry(self) -> Optional[MutableMapping[str, Any]]:
        """
        Pull the next Journal event from the event_queue.

        :return: dict representing the event
        """
        if self.thread is None:
            logger.debug('Called whilst self.thread is None, returning')
            return None

        # logger.trace('Begin')
        if self.event_queue.empty() and self.game_running():
            logger.error('event_queue is empty whilst game_running, this should not happen, returning')
            return None

        # logger.trace('event_queue NOT empty')
        entry = self.parse_entry(self.event_queue.get_nowait())

        # if entry['event'] == 'Location':
        #     logger.trace('"Location" event')

        if not self.live and entry['event'] not in (None, 'Fileheader'):
            # Game not running locally, but Journal has been updated
            self.live = True
            if self.station:
                entry = OrderedDict([
                    ('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())),
                    ('event', 'StartUp'),
                    ('Docked', True),
                    ('MarketID', self.station_marketid),
                    ('StationName', self.station),
                    ('StationType', self.stationtype),
                    ('StarSystem', self.system),
                    ('StarPos', self.coordinates),
                    ('SystemAddress', self.systemaddress),
                ])

            else:
                entry = OrderedDict([
                    ('timestamp', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())),
                    ('event', 'StartUp'),
                    ('Docked', False),
                    ('StarSystem', self.system),
                    ('StarPos', self.coordinates),
                    ('SystemAddress', self.systemaddress),
                ])

            # if entry['event'] == 'Location':
            #     logger.trace('Appending "Location" event to event_queue')

            self.event_queue.put(json.dumps(entry, separators=(', ', ':')))

        elif self.live and entry['event'] == 'Music' and entry.get('MusicTrack') == 'MainMenu':
            ts = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())
            self.event_queue.put(
                f'{{ "timestamp":"{ts}", "event":"ShutDown" }}'
            )

        return entry

    def game_running(self) -> bool:  # noqa: CCR001
        """
        Determine if the game is currently running.

        TODO: Implement on Linux

        :return: bool - True if the game is running.
        """
        if platform == 'darwin':
            for app in NSWorkspace.sharedWorkspace().runningApplications():
                if app.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                    return True

        elif platform == 'win32':
            def WindowTitle(h):  # noqa: N802 # type: ignore
                if h:
                    length = GetWindowTextLength(h) + 1
                    buf = ctypes.create_unicode_buffer(length)
                    if GetWindowText(h, buf, length):
                        return buf.value
                return None

            def callback(hWnd, lParam):  # noqa: N803
                name = WindowTitle(hWnd)
                if name and name.startswith('Elite - Dangerous'):
                    handle = GetProcessHandleFromHwnd(hWnd)
                    if handle:  # If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                        CloseHandle(handle)
                        return False  # stop enumeration

                return True

            return not EnumWindows(EnumWindowsProc(callback), 0)

        return False

    def ship(self, timestamped=True) -> Optional[MutableMapping[str, Any]]:
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

        d: MutableMapping[str, Any] = OrderedDict()
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
        regexp = re.compile(re.escape(ship) + r'\.\d{4}\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt')
        oldfiles = sorted((x for x in listdir(config.get_str('outdir')) if regexp.match(x)))  # type: ignore
        if oldfiles:
            try:
                with open(join(config.get_str('outdir'), oldfiles[-1]), 'r', encoding='utf-8') as h:  # type: ignore
                    if h.read() == string:
                        return  # same as last time - don't write

            except UnicodeError:
                logger.exception("UnicodeError reading old ship loadout with utf-8 encoding, trying without...")
                try:
                    with open(join(config.get_str('outdir'), oldfiles[-1]), 'r') as h:  # type: ignore
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
        filename = join(  # type: ignore
            config.get_str('outdir'), f'{ship}.{ts}.txt'
        )

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

    def coalesce_cargo(self, raw_cargo: List[MutableMapping[str, Any]]) -> List[MutableMapping[str, Any]]:
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
        out: List[MutableMapping[str, Any]] = []
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


# singleton
monitor = EDLogs()
