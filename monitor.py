from collections import defaultdict, OrderedDict
import json
import re
import threading
from operator import itemgetter
from os import listdir, SEEK_SET, SEEK_END
from os.path import basename, expanduser, isdir, join
from sys import platform
from time import gmtime, localtime, sleep, strftime, strptime, time
from calendar import timegm

if __debug__:
    from traceback import print_exc

from config import config
from companion import ship_file_name


if platform == 'darwin':
    from AppKit import NSWorkspace
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    from fcntl import fcntl
    F_GLOBAL_NOCACHE = 55

elif platform == 'win32':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import ctypes
    from ctypes.wintypes import BOOL, HWND, LPARAM, LPWSTR

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
class EDLogs(FileSystemEventHandler):

    _POLL = 1		# Polling is cheap, so do it often
    _RE_CANONICALISE = re.compile(r'\$(.+)_name;')
    _RE_CATEGORY = re.compile(r'\$MICRORESOURCE_CATEGORY_(.+);')
    _RE_LOGFILE = re.compile(r'^Journal(Beta)?\.[0-9]{12}\.[0-9]{2}\.log$')

    def __init__(self):
        FileSystemEventHandler.__init__(self)  # futureproofing - not need for current version of watchdog
        self.root = None
        self.currentdir = None		# The actual logdir that we're monitoring
        self.logfile = None
        self.observer = None
        self.observed = None		# a watchdog ObservedWatch, or None if polling
        self.thread = None
        self.event_queue = []		# For communicating journal entries back to main thread

        # On startup we might be:
        # 1) Looking at an old journal file because the game isn't running or the user has exited to the main menu.
        # 2) Looking at an empty journal (only 'Fileheader') because the user is at the main menu.
        # 3) In the middle of a 'live' game.
        # If 1 or 2 a LoadGame event will happen when the game goes live.
        # If 3 we need to inject a special 'StartUp' event since consumers won't see the LoadGame event.
        self.live = False

        self.game_was_running = False  # For generation the "ShutDown" event

        # Context for journal handling
        self.version = None
        self.is_beta = False
        self.mode = None
        self.group = None
        self.cmdr = None
        self.planet = None
        self.system = None
        self.station = None
        self.station_marketid = None
        self.stationtype = None
        self.coordinates = None
        self.systemaddress = None
        self.started = None  # Timestamp of the LoadGame event

        # Cmdr state shared with EDSM and plugins
        # If you change anything here update PLUGINS.md documentation!
        self.state = {
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
        }

    def start(self, root):
        self.root = root
        logdir = expanduser(config.get('journaldir') or config.default_journal_dir)  # type: ignore # config is weird

        if not logdir or not isdir(logdir):  # type: ignore # config does weird things in its get
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
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
            self.logfile = None
            return False

        # Set up a watchdog observer.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = bool(config.get('journaldir')) and platform != 'win32'
        if not polling and not self.observer:
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()

        elif polling and self.observer:
            self.observer.stop()
            self.observer = None

        if not self.observed and not polling:
            self.observed = self.observer.schedule(self, self.currentdir)

        if __debug__:
            print('{} Journal {!r}'.format('Polling' if polling else 'Monitoring', self.currentdir))
            print('Start logfile {!r}'.format(self.logfile))

        if not self.running():
            self.thread = threading.Thread(target=self.worker, name='Journal worker')
            self.thread.daemon = True
            self.thread.start()

        return True

    def stop(self):
        if __debug__:
            print('Stopping monitoring Journal')

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
        if self.observed:
            self.observed = None
            self.observer.unschedule_all()

        self.thread = None  # Orphan the worker thread - will terminate at next poll

    def close(self):
        self.stop()
        if self.observer:
            self.observer.stop()

        if self.observer:
            self.observer.join()
            self.observer = None

    def running(self):
        return self.thread and self.thread.is_alive()

    def on_created(self, event):
        # watchdog callback, e.g. client (re)started.
        if not event.is_directory and self._RE_LOGFILE.search(basename(event.src_path)):

            self.logfile = event.src_path

    def worker(self):
        # Tk isn't thread-safe in general.
        # event_generate() is the only safe way to poke the main thread from this thread:
        # https://mail.python.org/pipermail/tkinter-discuss/2013-November/003522.html

        # Seek to the end of the latest log file
        logfile = self.logfile
        if logfile:
            loghandle = open(logfile, 'rb', 0)  # unbuffered
            if platform == 'darwin':
                fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

            for line in loghandle:
                try:
                    self.parse_entry(line)  # Some events are of interest even in the past

                except Exception:
                    if __debug__:
                        print('Invalid journal entry {!r}'.format(line))

            log_pos = loghandle.tell()

        else:
            loghandle = None

        self.game_was_running = self.game_running()

        if self.live:
            if self.game_was_running:
                # Game is running locally
                entry = OrderedDict([
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

        # Watchdog thread
        emitter = self.observed and self.observer._emitter_for_watch[self.observed]  # Note: Uses undocumented attribute

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

                    newlogfile = join(self.currentdir, logfiles[-1]) if logfiles else None

                except Exception:
                    if __debug__:
                        print_exc()

                    newlogfile = None

            if logfile != newlogfile:
                logfile = newlogfile
                if loghandle:
                    loghandle.close()

                if logfile:
                    loghandle = open(logfile, 'rb', 0)  # unbuffered
                    if platform == 'darwin':
                        fcntl(loghandle, F_GLOBAL_NOCACHE, -1)  # required to avoid corruption on macOS over SMB

                    log_pos = 0

                if __debug__:
                    print('New logfile {!r}'.format(logfile))

            if logfile:
                loghandle.seek(0, SEEK_END)		  # required to make macOS notice log change over SMB
                loghandle.seek(log_pos, SEEK_SET)  # reset EOF flag # TODO: log_pos reported as possibly unbound
                for line in loghandle:
                    self.event_queue.append(line)

                if self.event_queue:
                    self.root.event_generate('<<JournalEvent>>', when="tail")

                log_pos = loghandle.tell()

            sleep(self._POLL)

            # Check whether we're still supposed to be running
            if threading.current_thread() != self.thread:
                return  # Terminate

            if self.game_was_running:
                if not self.game_running():
                    self.event_queue.append(
                        '{{ "timestamp":"{}", "event":"ShutDown" }}'.format(strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
                    )

                    self.root.event_generate('<<JournalEvent>>', when="tail")
                    self.game_was_running = False

            else:
                self.game_was_running = self.game_running()

    def parse_entry(self, line):
        if line is None:
            return {'event': None}  # Fake startup event

        try:
            entry = json.loads(line, object_pairs_hook=OrderedDict)  # Preserve property order because why not?
            entry['timestamp']  # we expect this to exist
            if entry['event'] == 'Fileheader':
                self.live = False
                self.version = entry['gameversion']
                self.is_beta = 'beta' in entry['gameversion'].lower()
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
                }

            elif entry['event'] == 'Commander':
                self.live = True  # First event in 3.0

            elif entry['event'] == 'LoadGame':
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
                    'Captain': None,
                    'Credits': entry['Credits'],
                    'FID': entry.get('FID'),   # From 3.3
                    'Horizons': entry['Horizons'],  # From 3.0
                    'Loan': entry['Loan'],
                    'Engineers': {},
                    'Rank': {},
                    'Reputation': {},
                    'Statistics': {},
                    'Role': None,
                })

            elif entry['event'] == 'NewCommander':
                self.cmdr = entry['Name']
                self.group = None

            elif entry['event'] == 'SetUserShipName':
                self.state['ShipID'] = entry['ShipID']
                if 'UserShipId' in entry:  # Only present when changing the ship's ident
                    self.state['ShipIdent'] = entry['UserShipId']

                self.state['ShipName'] = entry.get('UserShipName')
                self.state['ShipType'] = self.canonicalise(entry['Ship'])

            elif entry['event'] == 'ShipyardBuy':
                self.state['ShipID'] = None
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

            elif entry['event'] == 'ShipyardSwap':
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = None
                self.state['ShipName'] = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['HullValue'] = None
                self.state['ModulesValue'] = None
                self.state['Rebuy'] = None
                self.state['Modules'] = None

            elif (entry['event'] == 'Loadout' and
                  'fighter' not in self.canonicalise(entry['Ship']) and
                  'buggy' not in self.canonicalise(entry['Ship'])):
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = entry['ShipIdent']

                # Newly purchased ships can show a ShipName of "" initially,
                # and " " after a game restart/relog.
                # Players *can* also purposefully set " " as the name, but anyone
                # doing that gets to live with EDMC showing ShipType instead.
                if entry['ShipName'] and entry['ShipName'] not in ('', ' '):
                    self.state['ShipName']  = entry['ShipName']

                self.state['ShipType'] = self.canonicalise(entry['Ship'])
                self.state['HullValue'] = entry.get('HullValue')  # not present on exiting Outfitting
                self.state['ModulesValue'] = entry.get('ModulesValue')  #   "
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

            elif entry['event'] == 'ModuleBuy':
                self.state['Modules'][entry['Slot']] = {
                    'Slot': entry['Slot'],
                    'Item': self.canonicalise(entry['BuyItem']),
                    'On': True,
                    'Priority': 1,
                    'Health': 1.0,
                    'Value': entry['BuyPrice'],
                }

            elif entry['event'] == 'ModuleSell':
                self.state['Modules'].pop(entry['Slot'], None)

            elif entry['event'] == 'ModuleSwap':
                to_item = self.state['Modules'].get(entry['ToSlot'])
                self.state['Modules'][entry['ToSlot']] = self.state['Modules'][entry['FromSlot']]
                if to_item:
                    self.state['Modules'][entry['FromSlot']] = to_item

                else:
                    self.state['Modules'].pop(entry['FromSlot'], None)

            elif entry['event'] in ['Undocked']:
                self.station = None
                self.station_marketid = None
                self.stationtype = None
                self.stationservices = None

            elif entry['event'] in ['Location', 'FSDJump', 'Docked', 'CarrierJump']:
                if entry['event'] in ('Location', 'CarrierJump'):
                    self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None

                elif entry['event'] == 'FSDJump':
                    self.planet = None

                if 'StarPos' in entry:
                    self.coordinates = tuple(entry['StarPos'])

                elif self.system != entry['StarSystem']:
                    self.coordinates = None  # Docked event doesn't include coordinates

                self.systemaddress = entry.get('SystemAddress')

                if entry['event'] in ['Location', 'FSDJump', 'CarrierJump']:
                    self.systempopulation = entry.get('Population')

                self.system = 'CQC' if entry['StarSystem'] == 'ProvingGround' else entry['StarSystem']
                self.station = entry.get('StationName')  # May be None
                self.station_marketid = entry.get('MarketID')  # May be None
                self.stationtype = entry.get('StationType')  # May be None
                self.stationservices = entry.get('StationServices')  # None under E:D < 2.4

            elif entry['event'] == 'ApproachBody':
                self.planet = entry['Body']

            elif entry['event'] in ['LeaveBody', 'SupercruiseEntry']:
                self.planet = None

            elif entry['event'] in ['Rank', 'Promotion']:
                payload = dict(entry)
                payload.pop('event')
                payload.pop('timestamp')

                self.state['Rank'].update({k: (v, 0) for k, v in payload.items()})

            elif entry['event'] == 'Progress':
                for k, v in entry.items():
                    if k in self.state['Rank']:
                        # perhaps not taken promotion mission yet
                        self.state['Rank'][k] = (self.state['Rank'][k][0], min(v, 100))

            elif entry['event'] in ['Reputation', 'Statistics']:
                payload = OrderedDict(entry)
                payload.pop('event')
                payload.pop('timestamp')
                self.state[entry['event']] = payload

            elif entry['event'] == 'EngineerProgress':
                if 'Engineers' in entry:  # Startup summary
                    self.state['Engineers'] = {
                        e['Engineer']: (e['Rank'], e.get('RankProgress', 0))
                        if 'Rank' in e else e['Progress'] for e in entry['Engineers']
                    }

                else:  # Promotion
                    if 'Rank' in entry:
                        self.state['Engineers'][entry['Engineer']] = (entry['Rank'], entry.get('RankProgress', 0))

                    else:
                        self.state['Engineers'][entry['Engineer']] = entry['Progress']

            elif entry['event'] == 'Cargo' and entry.get('Vessel') == 'Ship':
                self.state['Cargo'] = defaultdict(int)
                # From 3.3 full Cargo event (after the first one) is written to a separate file
                if 'Inventory' not in entry:
                    with open(join(self.currentdir, 'Cargo.json'), 'rb') as h:
                        entry = json.load(h, object_pairs_hook=OrderedDict)  # Preserve property order because why not?

                self.state['Cargo'].update({self.canonicalise(x['Name']): x['Count'] for x in entry['Inventory']})

            elif entry['event'] in ['CollectCargo', 'MarketBuy', 'BuyDrones', 'MiningRefined']:
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] += entry.get('Count', 1)

            elif entry['event'] in ['EjectCargo', 'MarketSell', 'SellDrones']:
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] -= entry.get('Count', 1)
                if self.state['Cargo'][commodity] <= 0:
                    self.state['Cargo'].pop(commodity)

            elif entry['event'] == 'SearchAndRescue':
                for item in entry.get('Items', []):
                    commodity = self.canonicalise(item['Name'])
                    self.state['Cargo'][commodity] -= item.get('Count', 1)
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

            elif entry['event'] == 'Materials':
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    self.state[category] = defaultdict(int)
                    self.state[category].update({
                        self.canonicalise(x['Name']): x['Count'] for x in entry.get(category, [])
                    })

            elif entry['event'] == 'MaterialCollected':
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] += entry['Count']

            elif entry['event'] in ['MaterialDiscarded', 'ScientificResearch']:
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] -= entry['Count']
                if self.state[entry['Category']][material] <= 0:
                    self.state[entry['Category']].pop(material)

            elif entry['event'] == 'Synthesis':
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    for x in entry['Materials']:
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif entry['event'] == 'MaterialTrade':
                category = self.category(entry['Paid']['Category'])
                self.state[category][entry['Paid']['Material']] -= entry['Paid']['Quantity']
                if self.state[category][entry['Paid']['Material']] <= 0:
                    self.state[category].pop(entry['Paid']['Material'])

                category = self.category(entry['Received']['Category'])
                self.state[category][entry['Received']['Material']] += entry['Received']['Quantity']

            elif entry['event'] == 'EngineerCraft' or (
                entry['event'] == 'EngineerLegacyConvert' and not entry.get('IsPreview')
            ):

                for category in ['Raw', 'Manufactured', 'Encoded']:
                    for x in entry.get('Ingredients', []):
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

                module = self.state['Modules'][entry['Slot']]
                assert(module['Item'] == self.canonicalise(entry['Module']))
                module['Engineering'] = {
                    'Engineer': entry['Engineer'],
                    'EngineerID': entry['EngineerID'],
                    'BlueprintName': entry['BlueprintName'],
                    'BlueprintID': entry['BlueprintID'],
                    'Level': entry['Level'],
                    'Quality': entry['Quality'],
                    'Modifiers': entry['Modifiers'],
                }

                if 'ExperimentalEffect' in entry:
                    module['Engineering']['ExperimentalEffect'] = entry['ExperimentalEffect']
                    module['Engineering']['ExperimentalEffect_Localised'] = entry['ExperimentalEffect_Localised']

                else:
                    module['Engineering'].pop('ExperimentalEffect', None)
                    module['Engineering'].pop('ExperimentalEffect_Localised', None)

            elif entry['event'] == 'MissionCompleted':
                for reward in entry.get('CommodityReward', []):
                    commodity = self.canonicalise(reward['Name'])
                    self.state['Cargo'][commodity] += reward.get('Count', 1)

                for reward in entry.get('MaterialsReward', []):
                    if 'Category' in reward:  # Category not present in E:D 3.0
                        category = self.category(reward['Category'])
                        material = self.canonicalise(reward['Name'])
                        self.state[category][material] += reward.get('Count', 1)

            elif entry['event'] == 'EngineerContribution':
                commodity = self.canonicalise(entry.get('Commodity'))
                if commodity:
                    self.state['Cargo'][commodity] -= entry['Quantity']
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

                material = self.canonicalise(entry.get('Material'))
                if material:
                    for category in ['Raw', 'Manufactured', 'Encoded']:
                        if material in self.state[category]:
                            self.state[category][material] -= entry['Quantity']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

            elif entry['event'] == 'TechnologyBroker':
                for thing in entry.get('Ingredients', []):  # 3.01
                    for category in ['Cargo', 'Raw', 'Manufactured', 'Encoded']:
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

            elif entry['event'] == 'JoinACrew':
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

            elif entry['event'] == 'ChangeCrewRole':
                self.state['Role'] = entry['Role']

            elif entry['event'] == 'QuitACrew':
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

            elif entry['event'] == 'Friends':
                if entry['Status'] in ['Online', 'Added']:
                    self.state['Friends'].add(entry['Name'])

                else:
                    self.state['Friends'].discard(entry['Name'])

            return entry
        except Exception:
            if __debug__:
                print('Invalid journal entry {!r}'.format(line))
                print_exc()

            return {'event': None}

    # Commodities, Modules and Ships can appear in different forms e.g. "$HNShockMount_Name;", "HNShockMount",
    # and "hnshockmount", "$int_cargorack_size6_class1_name;" and "Int_CargoRack_Size6_Class1",
    # "python" and "Python", etc.
    # This returns a simple lowercased name e.g. 'hnshockmount', 'int_cargorack_size6_class1', 'python', etc
    def canonicalise(self, item: str):
        if not item:
            return ''

        item = item.lower()
        match = self._RE_CANONICALISE.match(item)

        if match:
            return match.group(1)

        return item

    def category(self, item: str):
        match = self._RE_CATEGORY.match(item)

        if match:
            return match.group(1).capitalize()

        return item.capitalize()

    def get_entry(self):
        if not self.event_queue:
            return None

        else:
            entry = self.parse_entry(self.event_queue.pop(0))
            if not self.live and entry['event'] not in [None, 'Fileheader']:
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

                self.event_queue.append(json.dumps(entry, separators=(', ', ':')))

            elif self.live and entry['event'] == 'Music' and entry.get('MusicTrack') == 'MainMenu':
                self.event_queue.append(
                    '{{ "timestamp":"{}", "event":"ShutDown" }}'.format(strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
                )

            return entry

    def game_running(self):
        if platform == 'darwin':
            for app in NSWorkspace.sharedWorkspace().runningApplications():
                if app.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                    return True

        elif platform == 'win32':
            def WindowTitle(h):
                if h:
                    length = GetWindowTextLength(h) + 1
                    buf = ctypes.create_unicode_buffer(length)
                    if GetWindowText(h, buf, length):
                        return buf.value
                return None

            def callback(hWnd, lParam):
                name = WindowTitle(hWnd)
                if name and name.startswith('Elite - Dangerous'):
                    handle = GetProcessHandleFromHwnd(hWnd)
                    if handle:  # If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                        CloseHandle(handle)
                        return False  # stop enumeration

                return True

            return not EnumWindows(EnumWindowsProc(callback), 0)

        return False

    # Return a subset of the received data describing the current ship as a Loadout event
    def ship(self, timestamped=True):
        if not self.state['Modules']:
            return None

        standard_order = (
            'ShipCockpit', 'CargoHatch', 'Armour', 'PowerPlant', 'MainEngines', 'FrameShiftDrive', 'LifeSupport',
            'PowerDistributor', 'Radar', 'FuelTank'
        )

        d = OrderedDict()
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

    # Export ship loadout as a Loadout event
    def export_ship(self, filename=None):
        string = json.dumps(self.ship(False), ensure_ascii=False, indent=2, separators=(',', ': '))  # pretty print
        if filename:
            with open(filename, 'wt') as h:
                h.write(string)

            return

        ship = ship_file_name(self.state['ShipName'], self.state['ShipType'])
        regexp = re.compile(re.escape(ship) + r'\.\d{4}\-\d\d\-\d\dT\d\d\.\d\d\.\d\d\.txt')
        oldfiles = sorted((x for x in listdir(config.get('outdir')) if regexp.match(x)))
        if oldfiles:
            with open(join(config.get('outdir'), oldfiles[-1]), 'rU') as h:
                if h.read() == string:
                    return  # same as last time - don't write

        # Write
        filename = join(
            config.get('outdir'), '{}.{}.txt'.format(ship, strftime('%Y-%m-%dT%H.%M.%S', localtime(time())))
        )

        with open(filename, 'wt') as h:
            h.write(string)


# singleton
monitor = EDLogs()
