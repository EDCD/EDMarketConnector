"""Monitor for new Journal files and contents of latest."""

import json
import re
import threading
from calendar import timegm
from collections import OrderedDict, defaultdict
from os import SEEK_END, SEEK_SET, listdir
from os.path import basename, expanduser, isdir, join
from sys import platform
from time import gmtime, localtime, sleep, strftime, strptime, time
from typing import TYPE_CHECKING, Any, Dict, List, MutableMapping, Optional
from typing import OrderedDict as OrderedDictT
from typing import Tuple

if TYPE_CHECKING:
    import tkinter

import util_ships
from config import config
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
    _RE_SHIP_ONFOOT = re.compile(r'^(FlightSuit|UtilitySuit_Class.)$')

    def __init__(self) -> None:
        # TODO(A_D): A bunch of these should be switched to default values (eg '' for strings) and no longer be Optional
        FileSystemEventHandler.__init__(self)  # futureproofing - not need for current version of watchdog
        self.root: 'tkinter.Tk' = None  # type: ignore # Don't use Optional[] - mypy thinks no methods
        self.currentdir: Optional[str] = None  # The actual logdir that we're monitoring
        self.logfile: Optional[str] = None
        self.observer: Optional['Observer'] = None
        self.observed = None  # a watchdog ObservedWatch, or None if polling
        self.thread: Optional[threading.Thread] = None
        self.event_queue: List = []  # For communicating journal entries back to main thread

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
        self.started: Optional[int] = None  # Timestamp of the LoadGame event
        self.on_foot: bool = False

        # Cmdr state shared with EDSM and plugins
        # If you change anything here update PLUGINS.md documentation!
        self.state: Dict = {
            'Captain':      None,  # On a crew
            'Cargo':        defaultdict(int),
            'Credits':      None,
            'FID':          None,  # Frontier Cmdr ID
            'Horizons':     None,  # Does this user have Horizons?
            'Loan':         None,
            'Raw':          defaultdict(int),
            'Manufactured': defaultdict(int),
            'Encoded':      defaultdict(int),
            'Engineers':    {},
            'Rank':         {},
            'Reputation':   {},
            'Statistics':   {},
            'Role':         None,  # Crew role - None, Idle, FireCon, FighterCon
            'Friends':      set(),  # Online friends
            'ShipID':       None,
            'ShipIdent':    None,
            'ShipName':     None,
            'ShipType':     None,
            'HullValue':    None,
            'ModulesValue': None,
            'Rebuy':        None,
            'Modules':      None,
            'CargoJSON':    None,  # The raw data from the last time cargo.json was read
            'Route':        None,  # Last plotted route from Route.json file
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

        # TODO(A_D): this is ignored for type checking due to all the different types config.get returns
        # When that is refactored, remove the magic comment
        logdir = expanduser(journal_dir)  # type: ignore # config is weird

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
                (x for x in listdir(self.currentdir) if self._RE_LOGFILE.search(x)),  # type: ignore # config is weird
                key=lambda x: x.split('.')[1:]
            )

            self.logfile = join(self.currentdir, logfiles[-1]) if logfiles else None  # type: ignore # config is weird

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
        self.on_foot = False

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
        logfile = self.logfile
        if logfile:
            loghandle = open(logfile, 'rb', 0)  # unbuffered
            if platform == 'darwin':
                fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

            for line in loghandle:
                try:
                    if b'"event":"Location"' in line:
                        logger.trace('"Location" event in the past at startup')

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

                self.event_queue.append(json.dumps(entry, separators=(', ', ':')))

            else:
                # Generate null event to update the display (with possibly out-of-date info)
                self.event_queue.append(None)
                self.live = False

        # Watchdog thread -- there is a way to get this by using self.observer.emitters and checking for an attribute:
        # watch, but that may have unforseen differences in behaviour.
        emitter = self.observed and self.observer._emitter_for_watch[self.observed]  # Note: Uses undocumented attribute

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

            if logfile != newlogfile:
                logger.info(f'New Journal File. Was "{logfile}", now "{newlogfile}"')
                logfile = newlogfile
                if loghandle:
                    loghandle.close()

                if logfile:
                    loghandle = open(logfile, 'rb', 0)  # unbuffered
                    if platform == 'darwin':
                        fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

                    log_pos = 0

            if logfile:
                loghandle.seek(0, SEEK_END)		  # required to make macOS notice log change over SMB
                loghandle.seek(log_pos, SEEK_SET)  # reset EOF flag # TODO: log_pos reported as possibly unbound
                for line in loghandle:
                    # Paranoia check to see if we're shutting down
                    if threading.current_thread() != self.thread:
                        logger.info("We're not meant to be running, exiting...")
                        return  # Terminate

                    if b'"event":"Location"' in line:
                        logger.trace('Found "Location" event, appending to event_queue')

                    self.event_queue.append(line)

                if self.event_queue:
                    if not config.shutting_down:
                        self.root.event_generate('<<JournalEvent>>', when="tail")

                log_pos = loghandle.tell()

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
                    self.event_queue.append(
                        f'{{ "timestamp":"{timestamp}", "event":"ShutDown" }}'
                    )

                    if not config.shutting_down:
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

            event_type = entry['event']
            if event_type == 'Fileheader':
                self.live = False
                self.version = entry['gameversion']
                self.is_beta = any(v in entry['gameversion'].lower() for v in ('alpha', 'beta'))

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
                self.state = {
                    'Captain':      None,
                    'Cargo':        defaultdict(int),
                    'Credits':      None,
                    'FID':          None,
                    'Horizons':     None,
                    'Loan':         None,
                    'Raw':          defaultdict(int),
                    'Manufactured': defaultdict(int),
                    'Encoded':      defaultdict(int),
                    'Engineers':    {},
                    'Rank':         {},
                    'Reputation':   {},
                    'Statistics':   {},
                    'Role':         None,
                    'Friends':      set(),
                    'ShipID':       None,
                    'ShipIdent':    None,
                    'ShipName':     None,
                    'ShipType':     None,
                    'HullValue':    None,
                    'ModulesValue': None,
                    'Rebuy':        None,
                    'Modules':      None,
                    'Route':        None,
                }
                self.on_foot = False

            elif event_type == 'Commander':
                self.live = True  # First event in 3.0

            elif event_type == 'LoadGame':
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
                self.state.update({
                    'Captain':    None,
                    'Credits':    entry['Credits'],
                    'FID':        entry.get('FID'),   # From 3.3
                    'Horizons':   entry['Horizons'],  # From 3.0
                    'Loan':       entry['Loan'],
                    'Engineers':  {},
                    'Rank':       {},
                    'Reputation': {},
                    'Statistics': {},
                    'Role':       None,
                })
                if self._RE_SHIP_ONFOOT.search(entry['Ship']):
                    self.on_foot = True

            elif event_type == 'NewCommander':
                self.cmdr = entry['Name']
                self.group = None

            elif event_type == 'SetUserShipName':
                self.state['ShipID'] = entry['ShipID']
                if 'UserShipId' in entry:  # Only present when changing the ship's ident
                    self.state['ShipIdent'] = entry['UserShipId']

                self.state['ShipName'] = entry.get('UserShipName')
                self.state['ShipType'] = self.canonicalise(entry['Ship'])

            elif event_type == 'ShipyardBuy':
                self.state['ShipID'] = None
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

            elif event_type == 'ShipyardSwap':
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

            elif (event_type == 'Loadout' and
                  'fighter' not in self.canonicalise(entry['Ship']) and
                  'buggy' not in self.canonicalise(entry['Ship'])):
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

            elif event_type == 'ModuleBuy':
                self.state['Modules'][entry['Slot']] = {
                    'Slot':     entry['Slot'],
                    'Item':     self.canonicalise(entry['BuyItem']),
                    'On':       True,
                    'Priority': 1,
                    'Health':   1.0,
                    'Value':    entry['BuyPrice'],
                }

            elif event_type == 'ModuleSell':
                self.state['Modules'].pop(entry['Slot'], None)

            elif event_type == 'ModuleSwap':
                to_item = self.state['Modules'].get(entry['ToSlot'])
                to_slot = entry['ToSlot']
                from_slot = entry['FromSlot']
                modules = self.state['Modules']
                modules[to_slot] = modules[from_slot]
                if to_item:
                    modules[from_slot] = to_item

                else:
                    modules.pop(from_slot, None)

            elif event_type == 'Undocked':
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None

            elif event_type == 'Embark':
                self.on_foot = False

            elif event_type == 'Disembark':
                self.on_foot = True

            elif event_type in ('Location', 'FSDJump', 'Docked', 'CarrierJump'):
                if event_type in ('Location', 'CarrierJump'):
                    self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None

                    if event_type == 'Location':
                        logger.trace('"Location" event')

                elif event_type == 'FSDJump':
                    self.planet = None

                if 'StarPos' in entry:
                    self.coordinates = tuple(entry['StarPos'])  # type: ignore

                elif self.system != entry['StarSystem']:
                    self.coordinates = None  # Docked event doesn't include coordinates

                self.systemaddress = entry.get('SystemAddress')

                if event_type in ('Location', 'FSDJump', 'CarrierJump'):
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
                self.stationservices = entry.get('StationServices')  # None under E:D < 2.4

            elif event_type == 'ApproachBody':
                self.planet = entry['Body']

            elif event_type in ('LeaveBody', 'SupercruiseEntry'):
                self.planet = None

            elif event_type in ('Rank', 'Promotion'):
                payload = dict(entry)
                payload.pop('event')
                payload.pop('timestamp')

                self.state['Rank'].update({k: (v, 0) for k, v in payload.items()})

            elif event_type == 'Progress':
                rank = self.state['Rank']
                for k, v in entry.items():
                    if k in rank:
                        # perhaps not taken promotion mission yet
                        rank[k] = (rank[k][0], min(v, 100))

            elif event_type in ('Reputation', 'Statistics'):
                payload = OrderedDict(entry)
                payload.pop('event')
                payload.pop('timestamp')
                self.state[event_type] = payload

            elif event_type == 'EngineerProgress':
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

            elif event_type == 'Cargo' and entry.get('Vessel') == 'Ship':
                self.state['Cargo'] = defaultdict(int)
                # From 3.3 full Cargo event (after the first one) is written to a separate file
                if 'Inventory' not in entry:
                    with open(join(self.currentdir, 'Cargo.json'), 'rb') as h:  # type: ignore
                        entry = json.load(h, object_pairs_hook=OrderedDict)  # Preserve property order because why not?
                        self.state['CargoJSON'] = entry

                clean = self.coalesce_cargo(entry['Inventory'])

                self.state['Cargo'].update({self.canonicalise(x['Name']): x['Count'] for x in clean})

            elif event_type == 'NavRoute':
                # Added in ED 3.7 - multi-hop route details in NavRoute.json
                with open(join(self.currentdir, 'NavRoute.json'), 'rb') as rf:  # type: ignore
                    try:
                        entry = json.load(rf)

                    except json.JSONDecodeError:
                        logger.exception('Failed decoding NavRoute.json', exc_info=True)

                    else:
                        self.state['NavRoute'] = entry

            elif event_type == 'ModuleInfo':
                with open(join(self.currentdir, 'ModulesInfo.json'), 'rb') as mf:  # type: ignore
                    try:
                        entry = json.load(mf)

                    except json.JSONDecodeError:
                        logger.exception('Failed decoding ModulesInfo.json', exc_info=True)

                    else:
                        self.state['ModuleInfo'] = entry

            elif event_type in ('CollectCargo', 'MarketBuy', 'BuyDrones', 'MiningRefined'):
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] += entry.get('Count', 1)

            elif event_type in ('EjectCargo', 'MarketSell', 'SellDrones'):
                commodity = self.canonicalise(entry['Type'])
                cargo = self.state['Cargo']
                cargo[commodity] -= entry.get('Count', 1)
                if cargo[commodity] <= 0:
                    cargo.pop(commodity)

            elif event_type == 'SearchAndRescue':
                for item in entry.get('Items', []):
                    commodity = self.canonicalise(item['Name'])
                    cargo = self.state['Cargo']
                    cargo[commodity] -= item.get('Count', 1)
                    if cargo[commodity] <= 0:
                        cargo.pop(commodity)

            elif event_type == 'Materials':
                for category in ('Raw', 'Manufactured', 'Encoded'):
                    self.state[category] = defaultdict(int)
                    self.state[category].update({
                        self.canonicalise(x['Name']): x['Count'] for x in entry.get(category, [])
                    })

            elif event_type == 'MaterialCollected':
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] += entry['Count']

            elif event_type in ('MaterialDiscarded', 'ScientificResearch'):
                material = self.canonicalise(entry['Name'])
                state_category = self.state[entry['Category']]
                state_category[material] -= entry['Count']
                if state_category[material] <= 0:
                    state_category.pop(material)

            elif event_type == 'Synthesis':
                for category in ('Raw', 'Manufactured', 'Encoded'):
                    for x in entry['Materials']:
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif event_type == 'MaterialTrade':
                category = self.category(entry['Paid']['Category'])
                state_category = self.state[category]
                paid = entry['Paid']
                received = entry['Received']

                state_category[paid['Material']] -= paid['Quantity']
                if state_category[paid['Material']] <= 0:
                    state_category.pop(paid['Material'])

                category = self.category(received['Category'])
                state_category[received['Material']] += received['Quantity']

            elif event_type == 'EngineerCraft' or (
                event_type == 'EngineerLegacyConvert' and not entry.get('IsPreview')
            ):

                for category in ('Raw', 'Manufactured', 'Encoded'):
                    for x in entry.get('Ingredients', []):
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

                module = self.state['Modules'][entry['Slot']]
                assert(module['Item'] == self.canonicalise(entry['Module']))
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

            elif event_type == 'MissionCompleted':
                for reward in entry.get('CommodityReward', []):
                    commodity = self.canonicalise(reward['Name'])
                    self.state['Cargo'][commodity] += reward.get('Count', 1)

                for reward in entry.get('MaterialsReward', []):
                    if 'Category' in reward:  # Category not present in E:D 3.0
                        category = self.category(reward['Category'])
                        material = self.canonicalise(reward['Name'])
                        self.state[category][material] += reward.get('Count', 1)

            elif event_type == 'EngineerContribution':
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

            elif event_type == 'TechnologyBroker':
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

            elif event_type == 'JoinACrew':
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
                self.on_foot = False

            elif event_type == 'ChangeCrewRole':
                self.state['Role'] = entry['Role']

            elif event_type == 'QuitACrew':
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
                # TODO: on_foot: Will we get an event after this to know ?

            elif event_type == 'Friends':
                if entry['Status'] in ('Online', 'Added'):
                    self.state['Friends'].add(entry['Name'])

                else:
                    self.state['Friends'].discard(entry['Name'])

            return entry

        except Exception as ex:
            logger.debug(f'Invalid journal entry:\n{line!r}\n', exc_info=ex)
            return {'event': None}

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

        if not self.event_queue:
            logger.trace('Called with no event_queue')
            return None

        else:
            entry = self.parse_entry(self.event_queue.pop(0))

            if entry['event'] == 'Location':
                logger.trace('"Location" event')

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

                if entry['event'] == 'Location':
                    logger.trace('Appending "Location" event to event_queue')

                self.event_queue.append(json.dumps(entry, separators=(', ', ':')))

            elif self.live and entry['event'] == 'Music' and entry.get('MusicTrack') == 'MainMenu':
                ts = strftime('%Y-%m-%dT%H:%M:%SZ', gmtime())
                self.event_queue.append(
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
                with open(join(config.get('outdir'), oldfiles[-1]), 'r', encoding='utf-8') as h:  # type: ignore
                    if h.read() == string:
                        return  # same as last time - don't write

            except UnicodeError:
                logger.exception("UnicodeError reading old ship loadout with utf-8 encoding, trying without...")
                try:
                    with open(join(config.get('outdir'), oldfiles[-1]), 'r') as h:  # type: ignore
                        if h.read() == string:
                            return  # same as last time - don't write

                except OSError:
                    logger.exception("OSError reading old ship loadout default encoding.")

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


# singleton
monitor = EDLogs()
