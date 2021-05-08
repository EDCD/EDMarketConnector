"""Monitor for new Journal files and contents of latest."""

import json
import queue
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
        self.state: Dict = {
            'Captain':            None,  # On a crew
            'Cargo':              defaultdict(int),
            'Credits':            None,
            'FID':                None,  # Frontier Cmdr ID
            'Horizons':           None,  # Does this user have Horizons?
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
            'Rebuy':              None,
            'Modules':            None,
            'CargoJSON':          None,  # The raw data from the last time cargo.json was read
            'Route':              None,  # Last plotted route from Route.json file
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
            'SuitCurrent':        None,
            'Suits':              {},
            'SuitLoadoutCurrent': None,
            'SuitLoadouts':       {},
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
        self.state['OnFoot'] = False

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

                    # if b'"event":"Location"' in line:
                    #     logger.trace('Found "Location" event, adding to event_queue')

                    self.event_queue.put(line)

                if not self.event_queue.empty():
                    if not config.shutting_down:
                        # logger.trace('Sending <<JournalEvent>>')
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
                self.__init_state()

            elif event_type == 'Commander':
                self.live = True  # First event in 3.0

            elif event_type == 'LoadGame':
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
                if entry.get('Ship') is not None and self._RE_SHIP_ONFOOT.search(entry['Ship']):
                    self.state['OnFoot'] = True

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

                self.state['Credits'] -= entry.get('ShipPrice', 0)

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

                self.state['Credits'] -= entry.get('BuyPrice', 0)

            elif event_type == 'ModuleRetrieve':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'ModuleSell':
                self.state['Modules'].pop(entry['Slot'], None)
                self.state['Credits'] += entry.get('SellPrice', 0)

            elif event_type == 'ModuleSellRemote':
                self.state['Credits'] += entry.get('SellPrice', 0)

            elif event_type == 'ModuleStore':
                self.state['Modules'].pop(entry['Slot'], None)
                self.state['Credits'] -= entry.get('Cost', 0)

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
                # This event is logged when a player (on foot) gets into a ship or SRV
                # Parameters:
                #     • SRV: true if getting into SRV, false if getting into a ship
                #     • Taxi: true when boarding a taxi transposrt ship
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

            elif event_type == 'Disembark':
                # This event is logged when the player steps out of a ship or SRV
                #
                # Parameters:
                #     • SRV: true if getting out of SRV, false if getting out of a ship
                #     • Taxi: true when getting out of a taxi transposrt ship
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

            elif event_type == 'DropshipDeploy':
                # We're definitely on-foot now
                self.state['OnFoot'] = True

            elif event_type == 'Docked':
                self.station = entry.get('StationName')  # May be None
                self.station_marketid = entry.get('MarketID')  # May be None
                self.stationtype = entry.get('StationType')  # May be None
                self.stationservices = entry.get('StationServices')  # None under E:D < 2.4

            elif event_type in ('Location', 'FSDJump', 'CarrierJump'):
                # alpha4 - any changes ?
                # Location:
                # New in Odyssey:
                #     • Taxi: bool
                #     • Multicrew: bool
                #     • InSRV: bool
                #     • OnFoot: bool
                if event_type in ('Location', 'CarrierJump'):
                    self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None

                    # if event_type == 'Location':
                    #     logger.trace('"Location" event')

                elif event_type == 'FSDJump':
                    self.planet = None

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

            elif event_type == 'CargoTransfer':
                for c in entry['Transfers']:
                    name = self.canonicalise(c['Type'])
                    if c['Direction'] == 'toship':
                        self.state['Cargo'][name] += c['Count']

                    else:
                        # So it's *from* the ship
                        self.state['Cargo'][name] -= c['Count']

            elif event_type == 'ShipLockerMaterials':
                # This event has the current totals, so drop any current data
                self.state['Component'] = defaultdict(int)
                self.state['Consumable'] = defaultdict(int)
                self.state['Item'] = defaultdict(int)
                self.state['Data'] = defaultdict(int)
                # TODO: Really we need a full BackPackMaterials event at the same time.
                #       In lieu of that, empty the backpack.  This will explicitly
                #       be wrong if Cmdr relogs at a Settlement with anything in
                #       backpack.
                #       Still no BackPackMaterials at the same time in 4.0.0.31
                self.state['BackPack']['Component'] = defaultdict(int)
                self.state['BackPack']['Consumable'] = defaultdict(int)
                self.state['BackPack']['Item'] = defaultdict(int)
                self.state['BackPack']['Data'] = defaultdict(int)

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

            elif event_type == 'BackPackMaterials':
                # alpha4 -
                # Lists the contents of the backpack, eg when disembarking from ship

                # Assume this reflects the current state when written
                self.state['BackPack']['Component'] = defaultdict(int)
                self.state['BackPack']['Consumable'] = defaultdict(int)
                self.state['BackPack']['Item'] = defaultdict(int)
                self.state['BackPack']['Data'] = defaultdict(int)

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

            elif event_type == 'BuyMicroResources':
                # Buying from a Pioneer Supplies, goes directly to ShipLocker.
                # One event per Item, not an array.
                category = self.category(entry['Category'])
                name = self.canonicalise(entry['Name'])
                self.state[category][name] += entry['Count']

                self.state['Credits'] -= entry.get('Price', 0)

            elif event_type == 'SellMicroResources':
                # Selling to a Bar Tender on-foot.
                self.state['Credits'] += entry.get('Price', 0)
                # One event per whole sale, so it's an array.
                for mr in entry['MicroResources']:
                    category = self.category(mr['Category'])
                    name = self.canonicalise(mr['Name'])
                    self.state[category][name] -= mr['Count']

            elif event_type == 'TradeMicroResources':
                # Trading some MicroResources for another at a Bar Tender
                # 'Offered' is what we traded away
                for offer in entry['Offered']:
                    category = self.category(offer['Category'])
                    name = self.canonicalise(offer['Name'])
                    self.state[category][name] -= offer['Count']

                # For a single item name received
                category = self.category(entry['Category'])
                name = self.canonicalise(entry['Received'])
                self.state[category][name] += entry['Count']

            elif event_type == 'TransferMicroResources':
                # Moving Odyssey MicroResources between ShipLocker and BackPack
                for mr in entry['Transfers']:
                    category = self.category(mr['Category'])
                    name = self.canonicalise(mr['Name'])

                    if mr['Direction'] == 'ToShipLocker':
                        self.state[category][name] += mr['Count']
                        self.state['BackPack'][category][name] -= mr['Count']

                    elif mr['Direction'] == 'ToBackpack':
                        self.state[category][name] -= mr['Count']
                        self.state['BackPack'][category][name] += mr['Count']

                    else:
                        logger.warning(f'TransferMicroResources with unexpected Direction {mr["Direction"]=}: {mr=}')

                # Paranoia check to see if anything has gone negative.
                # As of Odyssey Alpha Phase 1 Hotfix 2 keeping track of BackPack
                # materials is impossible when used/picked up anyway.
                for c in self.state['BackPack']:
                    for m in self.state['BackPack'][c]:
                        if self.state['BackPack'][c][m] < 0:
                            self.state['BackPack'][c][m] = 0

            elif event_type == 'CollectItems':
                # alpha4
                # When picking up items from the ground
                # Parameters:
                #     • Name
                #     • Type
                #     • OwnerID
                for i in self.state['BackPack'][entry['Type']]:
                    if i == entry['Name']:
                        self.state['BackPack'][entry['Type']][i] += entry['Count']

            elif event_type == 'DropItems':
                # alpha4
                # Parameters:
                #     • Name
                #     • Type
                #     • OwnerID
                #     • MissionID
                #     • Count
                for i in self.state['BackPack'][entry['Type']]:
                    if i == entry['Name']:
                        self.state['BackPack'][entry['Type']][i] -= entry['Count']
                        # Paranoia in case we lost track
                        if self.state['BackPack'][entry['Type']][i] < 0:
                            self.state['BackPack'][entry['Type']][i] = 0

            elif event_type == 'UseConsumable':
                # alpha4
                # When using an item from the player’s inventory (backpack)
                #
                # Parameters:
                #     • Name
                #     • Type
                for c in self.state['BackPack']['Consumable']:
                    if c == entry['Name']:
                        self.state['BackPack']['Consumable'][c] -= 1
                        # Paranoia in case we lost track
                        if self.state['BackPack']['Consumable'][c] < 0:
                            self.state['BackPack']['Consumable'][c] = 0

            elif event_type == 'SwitchSuitLoadout':
                loadoutid = entry['LoadoutID']
                new_slot = self.suit_loadout_id_from_loadoutid(loadoutid)
                # If this application is run with the latest Journal showing such an event then we won't
                # yet have the CAPI data, so no idea about Suits or Loadouts.
                if self.state['Suits'] and self.state['SuitLoadouts']:
                    try:
                        self.state['SuitLoadoutCurrent'] = self.state['SuitLoadouts'][f'{new_slot}']

                    except KeyError:
                        logger.debug(f"KeyError getting suit loadout after switch, bad slot: {new_slot} ({loadoutid})")
                        self.state['SuitCurrent'] = None
                        self.state['SuitLoadoutCurrent'] = None

                    else:
                        try:
                            new_suitid = self.state['SuitLoadoutCurrent']['suit']['suitId']

                        except KeyError:
                            logger.debug(f"KeyError getting switched-to suit ID from slot {new_slot} ({loadoutid})")

                        else:
                            try:
                                self.state['SuitCurrent'] = self.state['Suits'][f'{new_suitid}']

                            except KeyError:
                                logger.debug(f"KeyError getting switched-to suit from slot {new_slot} ({loadoutid}")

            elif event_type == 'CreateSuitLoadout':
                # We know we won't have data for this new one
                # Parameters:
                #     • SuitID
                #     • SuitName
                #     • LoadoutID
                #     • LoadoutName
                # alpha4:
                # { "timestamp":"2021-04-29T09:37:08Z", "event":"CreateSuitLoadout", "SuitID":1698364940285172,
                # "SuitName":"tacticalsuit_class1", "SuitName_Localised":"Dominator Suit", "LoadoutID":4293000001,
                # "LoadoutName":"Dom L/K/K", "Modules":[
                # {
                #   "SlotName":"PrimaryWeapon1",
                #   "SuitModuleID":1698364962722310,
                #   "ModuleName":"wpn_m_assaultrifle_laser_fauto",
                #   "ModuleName_Localised":"TK Aphelion"
                # },
                # { "SlotName":"PrimaryWeapon2",
                # "SuitModuleID":1698364956302993, "ModuleName":"wpn_m_assaultrifle_kinetic_fauto",
                # "ModuleName_Localised":"Karma AR-50" }, { "SlotName":"SecondaryWeapon",
                # "SuitModuleID":1698292655291850, "ModuleName":"wpn_s_pistol_kinetic_sauto",
                # "ModuleName_Localised":"Karma P-15" } ] }
                new_loadout = {
                    'loadoutSlotId': self.suit_loadout_id_from_loadoutid(entry['LoadoutID']),
                    'suit': {
                        'name': entry['SuitName'],
                        'locName': entry.get('SuitName_Localised', entry['SuitName']),
                        'suitId': entry['SuitID'],
                    },
                    'name': entry['LoadoutName'],
                    'slots': self.suit_loadout_slots_array_to_dict(entry['Modules']),
                }
                self.state['SuitLoadouts'][new_loadout['loadoutSlotId']] = new_loadout

            elif event_type == 'DeleteSuitLoadout':
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

            elif event_type == 'RenameSuitLoadout':
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

            elif event_type == 'BuySuit':
                # alpha4 :
                # { "timestamp":"2021-04-29T09:03:37Z", "event":"BuySuit", "Name":"UtilitySuit_Class1",
                # "Name_Localised":"Maverick Suit", "Price":150000, "SuitID":1698364934364699 }
                self.state['Suits'][entry['SuitID']] = {
                    'name':      entry['Name'],
                    'locName':   entry.get('Name_Localised', entry['Name']),
                    'id': None,  # Is this an FDev ID for suit type ?
                    'suitId':    entry['SuitID'],
                    'slots':     [],
                }

                # update credits
                if price := entry.get('Price') is None:
                    logger.error(f"BuySuit didn't contain Price: {entry}")

                else:
                    self.state['Credits'] -= price

            elif event_type == 'SellSuit':
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

            elif event_type == 'UpgradeSuit':
                # alpha4
                # This event is logged when the player upgrades their flight suit
                #
                # Parameters:
                #     • Name
                #     • SuitID
                #     • Class
                #     • Cost
                # Update credits total ?  It shouldn't even involve credits!
                # Actual alpha4 - need to grind mats
                # if self.state['Suits']:
                pass

            elif event_type == 'LoadoutEquipModule':
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
                        }

                    except KeyError:
                        logger.error(f"LoadoutEquipModule: {entry}")

            elif event_type == 'LoadoutRemoveModule':
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

            elif event_type == 'BuyWeapon':
                # alpha4
                # { "timestamp":"2021-04-29T11:10:51Z", "event":"BuyWeapon", "Name":"Wpn_M_AssaultRifle_Laser_FAuto",
                # "Name_Localised":"TK Aphelion", "Price":125000, "SuitModuleID":1698372938719590 }
                # update credits
                if price := entry.get('Price') is None:
                    logger.error(f"BuyWeapon didn't contain Price: {entry}")

                else:
                    self.state['Credits'] -= price

            elif event_type == 'SellWeapon':
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

            elif event_type == 'UpgradeWeapon':
                # We're not actually keeping track of all owned weapons, only those in
                # Suit Loadouts.
                # alpha4 - credits?  Shouldn't cost any!
                pass

            elif event_type == 'ScanOrganic':
                # Nothing of interest to our state.
                pass

            elif event_type == 'SellOrganicData':
                for bd in entry['BioData']:
                    self.state['Credits'] += bd.get('Value', 0) + bd.get('Bonus', 0)

            elif event_type == 'BookDropship':
                self.state['Credits'] -= entry.get('Cost', 0)
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

            elif event_type == 'BookTaxi':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'CancelDropship':
                self.state['Credits'] += entry.get('Refund', 0)

            elif event_type == 'CancelTaxi':
                self.state['Credits'] += entry.get('Refund', 0)

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

                if event_type == 'BuyDrones':
                    self.state['Credits'] -= entry.get('TotalCost', 0)

                elif event_type == 'MarketBuy':
                    self.state['Credits'] -= entry.get('TotalCost', 0)

            elif event_type in ('EjectCargo', 'MarketSell', 'SellDrones'):
                commodity = self.canonicalise(entry['Type'])
                cargo = self.state['Cargo']
                cargo[commodity] -= entry.get('Count', 1)
                if cargo[commodity] <= 0:
                    cargo.pop(commodity)

                if event_type == 'MarketSell':
                    self.state['Credits'] += entry.get('TotalSale', 0)

                elif event_type == 'SellDrones':
                    self.state['Credits'] += entry.get('TotalSale', 0)

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
                self.state['Credits'] += entry.get('Reward', 0)

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
                self.state['OnFoot'] = False

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

            # Try to keep Credits total updated
            elif event_type in ('MultiSellExplorationData', 'SellExplorationData'):
                self.state['Credits'] += entry.get('TotalEarnings', 0)

            elif event_type == 'BuyExplorationData':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'BuyTradeData':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'BuyAmmo':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'CommunityGoalReward':
                self.state['Credits'] += entry.get('Reward', 0)

            elif event_type == 'CrewHire':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'FetchRemoteModule':
                self.state['Credits'] -= entry.get('TransferCost', 0)

            elif event_type == 'MissionAbandoned':
                # Is this paid at this point, or just a fine to pay later ?
                # self.state['Credits'] -= entry.get('Fine', 0)
                pass

            elif event_type in ('PayBounties', 'PayFines', 'PayLegacyFines'):
                self.state['Credits'] -= entry.get('Amount', 0)

            elif event_type == 'RedeemVoucher':
                self.state['Credits'] += entry.get('Amount', 0)

            elif event_type in ('RefuelAll', 'RefuelPartial', 'Repair', 'RepairAll', 'RestockVehicle'):
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'SellShipOnRebuy':
                self.state['Credits'] += entry.get('ShipPrice', 0)

            elif event_type == 'ShipyardSell':
                self.state['Credits'] += entry.get('ShipPrice', 0)

            elif event_type == 'ShipyardTransfer':
                self.state['Credits'] -= entry.get('TransferPrice', 0)

            elif event_type == 'PowerplayFastTrack':
                self.state['Credits'] -= entry.get('Cost', 0)

            elif event_type == 'PowerplaySalary':
                self.state['Credits'] += entry.get('Amount', 0)

            elif event_type == 'SquadronCreated':
                # v30 docs don't actually say anything about credits cost
                pass

            elif event_type == 'CarrierBuy':
                self.state['Credits'] -= entry.get('Price', 0)

            elif event_type == 'CarrierBankTransfer':
                if (newbal := entry.get('PlayerBalance')):
                    self.state['Credits'] = newbal

            elif event_type == 'CarrierDecommission':
                # v30 doc says nothing about citing the refund amount
                pass

            elif event_type == 'NpcCrewPaidWage':
                self.state['Credits'] -= entry.get('Amount', 0)

            elif event_type == 'Resurrect':
                self.state['Credits'] -= entry.get('Cost', 0)

            return entry

        except Exception as ex:
            logger.debug(f'Invalid journal entry:\n{line!r}\n', exc_info=ex)
            return {'event': None}

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
            }

        return slots


# singleton
monitor = EDLogs()
