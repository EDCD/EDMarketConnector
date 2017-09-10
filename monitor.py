from collections import defaultdict, OrderedDict
import json
import re
import threading
from os import listdir, SEEK_SET, SEEK_CUR, SEEK_END
from os.path import basename, isdir, join
from sys import platform
from time import gmtime, sleep, strftime, strptime
from calendar import timegm

if __debug__:
    from traceback import print_exc

from config import config


if platform=='darwin':
    from AppKit import NSWorkspace
    from Foundation import NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSUserDomainMask
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
 
elif platform=='win32':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import ctypes

    # _winreg that ships with Python 2 doesn't support unicode, so do this instead
    from ctypes.wintypes import *

    HKEY_CURRENT_USER       = 0x80000001
    HKEY_LOCAL_MACHINE      = 0x80000002
    KEY_READ                = 0x00020019
    REG_SZ    = 1

    RegOpenKeyEx = ctypes.windll.advapi32.RegOpenKeyExW
    RegOpenKeyEx.restype = LONG
    RegOpenKeyEx.argtypes = [HKEY, LPCWSTR, DWORD, DWORD, ctypes.POINTER(HKEY)]

    RegCloseKey = ctypes.windll.advapi32.RegCloseKey
    RegCloseKey.restype = LONG
    RegCloseKey.argtypes = [HKEY]

    RegQueryValueEx = ctypes.windll.advapi32.RegQueryValueExW
    RegQueryValueEx.restype = LONG
    RegQueryValueEx.argtypes = [HKEY, LPCWSTR, LPCVOID, ctypes.POINTER(DWORD), LPCVOID, ctypes.POINTER(DWORD)]

    RegEnumKeyEx = ctypes.windll.advapi32.RegEnumKeyExW
    RegEnumKeyEx.restype = LONG
    RegEnumKeyEx.argtypes = [HKEY, DWORD, LPWSTR, ctypes.POINTER(DWORD), ctypes.POINTER(DWORD), LPWSTR, ctypes.POINTER(DWORD), ctypes.POINTER(FILETIME)]

    EnumWindows            = ctypes.windll.user32.EnumWindows
    EnumWindowsProc        = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)

    CloseHandle            = ctypes.windll.kernel32.CloseHandle

    GetWindowText          = ctypes.windll.user32.GetWindowTextW
    GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
    GetWindowTextLength    = ctypes.windll.user32.GetWindowTextLengthW

    GetProcessHandleFromHwnd = ctypes.windll.oleacc.GetProcessHandleFromHwnd

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object	# dummy


# Journal handler
class EDLogs(FileSystemEventHandler):

    _POLL = 1		# Polling is cheap, so do it often
    _RE_CANONICALISE = re.compile('\$(.+)_name;')

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
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

        # Context for journal handling
        self.version = None
        self.is_beta = False
        self.mode = None
        self.group = None
        self.cmdr = None
        self.planet = None
        self.system = None
        self.station = None
        self.stationtype = None
        self.coordinates = None
        self.started = None	# Timestamp of the LoadGame event

        # Cmdr state shared with EDSM and plugins
        self.state = {
            'Captain'      : None,	# On a crew
            'Cargo'        : defaultdict(int),
            'Credits'      : None,
            'Loan'         : None,
            'Raw'          : defaultdict(int),
            'Manufactured' : defaultdict(int),
            'Encoded'      : defaultdict(int),
            'PaintJob'     : None,
            'Rank'         : { 'Combat': None, 'Trade': None, 'Explore': None, 'Empire': None, 'Federation': None, 'CQC': None },
            'Role'         : None,	# Crew role - None, Idle, FireCon, FighterCon
            'ShipID'       : None,
            'ShipIdent'    : None,
            'ShipName'     : None,
            'ShipType'     : None,
        }

    def start(self, root):
        self.root = root
        logdir = config.get('journaldir') or config.default_journal_dir
        if not logdir or not isdir(logdir):
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            self.stop()
        self.currentdir = logdir

        # Latest pre-existing logfile - e.g. if E:D is already running. Assumes logs sort alphabetically.
        # Do this before setting up the observer in case the journal directory has gone away
        try:
            logfiles = sorted([x for x in listdir(self.currentdir) if x.startswith('Journal') and x.endswith('.log')],
                              key=lambda x: x.split('.')[1:])
            self.logfile = logfiles and join(self.currentdir, logfiles[-1]) or None
        except:
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
            print '%s Journal "%s"' % (polling and 'Polling' or 'Monitoring', self.currentdir)
            print 'Start logfile "%s"' % self.logfile

        if not self.running():
            self.thread = threading.Thread(target = self.worker, name = 'Journal worker')
            self.thread.daemon = True
            self.thread.start()

        return True

    def stop(self):
        if __debug__:
            print 'Stopping monitoring Journal'
        self.currentdir = None
        self.version = self.mode = self.group = self.cmdr = self.planet = self.system = self.station = self.stationtype = self.stationservices = self.coordinates = None
        self.is_beta = False
        if self.observed:
            self.observed = None
            self.observer.unschedule_all()
        self.thread = None	# Orphan the worker thread - will terminate at next poll

    def close(self):
        thread = self.thread
        self.stop()
        if self.observer:
            self.observer.stop()
        if thread:
            thread.join()
        if self.observer:
            self.observer.join()
            self.observer = None

    def running(self):
        return self.thread and self.thread.is_alive()

    def on_created(self, event):
        # watchdog callback, e.g. client (re)started.
        if not event.is_directory and basename(event.src_path).startswith('Journal') and basename(event.src_path).endswith('.log'):
            self.logfile = event.src_path

    def worker(self):
        # Tk isn't thread-safe in general.
        # event_generate() is the only safe way to poke the main thread from this thread:
        # https://mail.python.org/pipermail/tkinter-discuss/2013-November/003522.html

        # Seek to the end of the latest log file
        logfile = self.logfile
        if logfile:
            loghandle = open(logfile, 'r')
            for line in loghandle:
                try:
                    self.parse_entry(line)	# Some events are of interest even in the past
                except:
                    if __debug__:
                        print 'Invalid journal entry "%s"' % repr(line)
        else:
            loghandle = None

        if self.live:
            if self.game_running():
                self.event_queue.append('{ "timestamp":"%s", "event":"StartUp" }' % strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
            else:
                self.event_queue.append(None)	# Generate null event to update the display (with possibly out-of-date info)
                self.live = False

        # Watchdog thread
        emitter = self.observed and self.observer._emitter_for_watch[self.observed]	# Note: Uses undocumented attribute

        while True:

            # Check whether new log file started, e.g. client (re)started.
            if emitter and emitter.is_alive():
                newlogfile = self.logfile	# updated by on_created watchdog callback
            else:
                # Poll
                try:
                    logfiles = sorted([x for x in listdir(self.currentdir) if x.startswith('Journal') and x.endswith('.log')],
                                      key=lambda x: x.split('.')[1:])
                    newlogfile = logfiles and join(self.currentdir, logfiles[-1]) or None
                except:
                    if __debug__: print_exc()
                    newlogfile = None

            if logfile != newlogfile:
                logfile = newlogfile
                if loghandle:
                    loghandle.close()
                if logfile:
                    loghandle = open(logfile, 'r')
                if __debug__:
                    print 'New logfile "%s"' % logfile

            if logfile:
                loghandle.seek(0, SEEK_CUR)	# reset EOF flag
                for line in loghandle:
                    self.event_queue.append(line)
                if self.event_queue:
                    self.root.event_generate('<<JournalEvent>>', when="tail")

            sleep(self._POLL)

            # Check whether we're still supposed to be running
            if threading.current_thread() != self.thread:
                return	# Terminate

    def parse_entry(self, line):
        if line is None:
            return { 'event': None }	# Fake startup event

        try:
            entry = json.loads(line, object_pairs_hook=OrderedDict)	# Preserve property order because why not?
            entry['timestamp']	# we expect this to exist
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
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.started = None
                self.state = {
                    'Captain'      : None,
                    'Cargo'        : defaultdict(int),
                    'Credits'      : None,
                    'Loan'         : None,
                    'Raw'          : defaultdict(int),
                    'Manufactured' : defaultdict(int),
                    'Encoded'      : defaultdict(int),
                    'PaintJob'     : None,
                    'Rank'         : { 'Combat': None, 'Trade': None, 'Explore': None, 'Empire': None, 'Federation': None, 'CQC': None },
                    'Role'         : None,
                    'ShipID'       : None,
                    'ShipIdent'    : None,
                    'ShipName'     : None,
                    'ShipType'     : None,
                }
            elif entry['event'] == 'LoadGame':
                self.live = True
                self.cmdr = entry['Commander']
                self.mode = entry.get('GameMode')	# 'Open', 'Solo', 'Group', or None for CQC (and Training - but no LoadGame event)
                self.group = entry.get('Group')
                self.planet = None
                self.system = None
                self.station = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
                self.started = timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                self.state.update({
                    'Captain'      : None,
                    'Credits'      : entry['Credits'],
                    'Loan'         : entry['Loan'],
                    'Rank'         : { 'Combat': None, 'Trade': None, 'Explore': None, 'Empire': None, 'Federation': None, 'CQC': None },
                    'Role'         : None,
                })
            elif entry['event'] == 'NewCommander':
                self.cmdr = entry['Name']
                self.group = None
            elif entry['event'] == 'SetUserShipName':
                self.state['ShipID']    = entry['ShipID']
                if 'UserShipId' in entry:	# Only present when changing the ship's ident
                    self.state['ShipIdent'] = entry['UserShipId']
                self.state['ShipName']  = entry.get('UserShipName')
                self.state['ShipType']  = self.canonicalise(entry['Ship'])
            elif entry['event'] == 'ShipyardBuy':
                self.state['ShipID'] = None
                self.state['ShipIdent'] = None
                self.state['ShipName']  = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['PaintJob'] = None
            elif entry['event'] == 'ShipyardSwap':
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = None
                self.state['ShipName']  = None
                self.state['ShipType'] = self.canonicalise(entry['ShipType'])
                self.state['PaintJob'] = None
            elif entry['event'] == 'Loadout':	# Note: Precedes LoadGame, ShipyardNew, follows ShipyardSwap, ShipyardBuy
                self.state['ShipID'] = entry['ShipID']
                self.state['ShipIdent'] = entry['ShipIdent']
                self.state['ShipName']  = entry['ShipName']
                self.state['ShipType']  = self.canonicalise(entry['Ship'])
                # Ignore other Modules since they're missing Engineer modification details
                self.state['PaintJob'] = 'paintjob_%s_default_defaultpaintjob' % self.state['ShipType']
                for module in entry['Modules']:
                    if module.get('Slot') == 'PaintJob' and module.get('Item'):
                        self.state['PaintJob'] = self.canonicalise(module['Item'])
            elif entry['event'] in ['ModuleBuy', 'ModuleSell'] and entry['Slot'] == 'PaintJob':
                self.state['PaintJob'] = self.canonicalise(entry.get('BuyItem'))
            elif entry['event'] in ['Undocked']:
                self.station = None
                self.stationtype = None
                self.stationservices = None
            elif entry['event'] in ['Location', 'FSDJump', 'Docked']:
                if entry['event'] == 'Location':
                    self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None
                elif entry['event'] == 'FSDJump':
                    self.planet = None
                if 'StarPos' in entry:
                    self.coordinates = tuple(entry['StarPos'])
                elif self.system != entry['StarSystem']:
                    self.coordinates = None	# Docked event doesn't include coordinates
                (self.system, self.station) = (entry['StarSystem'] == 'ProvingGround' and 'CQC' or entry['StarSystem'],
                                               entry.get('StationName'))	# May be None
                self.stationtype = entry.get('StationType')	# May be None
                self.stationservices = entry.get('StationServices')	# None under E:D < 2.4
            elif entry['event'] == 'SupercruiseExit':
                self.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None
            elif entry['event'] == 'SupercruiseEntry':
                self.planet = None
            elif entry['event'] in ['Rank', 'Promotion']:
                for k,v in entry.iteritems():
                    if k in self.state['Rank']:
                        self.state['Rank'][k] = (v,0)
            elif entry['event'] == 'Progress':
                for k,v in entry.iteritems():
                    if self.state['Rank'].get(k) is not None:
                        self.state['Rank'][k] = (self.state['Rank'][k][0], min(v, 100))	# perhaps not taken promotion mission yet

            elif entry['event'] == 'Cargo':
                self.live = True	# First event in 2.3
                self.state['Cargo'] = defaultdict(int)
                self.state['Cargo'].update({ self.canonicalise(x['Name']): x['Count'] for x in entry['Inventory'] })
            elif entry['event'] in ['CollectCargo', 'MarketBuy', 'BuyDrones', 'MiningRefined']:
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] += entry.get('Count', 1)
            elif entry['event'] in ['EjectCargo', 'MarketSell', 'SellDrones']:
                commodity = self.canonicalise(entry['Type'])
                self.state['Cargo'][commodity] -= entry.get('Count', 1)
                if self.state['Cargo'][commodity] <= 0:
                    self.state['Cargo'].pop(commodity)
            elif entry['event'] == 'MissionCompleted':
                for reward in entry.get('CommodityReward', []):
                    commodity = self.canonicalise(reward['Name'])
                    self.state['Cargo'][commodity] += reward.get('Count', 1)
            elif entry['event'] == 'SearchAndRescue':
                for item in entry.get('Items', []):
                    commodity = self.canonicalise(item['Name'])
                    self.state['Cargo'][commodity] -= item.get('Count', 1)
                    if self.state['Cargo'][commodity] <= 0:
                        self.state['Cargo'].pop(commodity)

            elif entry['event'] == 'Materials':
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    self.state[category] = defaultdict(int)
                    self.state[category].update({ self.canonicalise(x['Name']): x['Count'] for x in entry.get(category, []) })
            elif entry['event'] == 'MaterialCollected':
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] += entry['Count']
            elif entry['event'] in ['MaterialDiscarded', 'ScientificResearch']:
                material = self.canonicalise(entry['Name'])
                self.state[entry['Category']][material] -= entry['Count']
                if self.state[entry['Category']][material] <= 0:
                    self.state[entry['Category']].pop(material)
            elif entry['event'] in ['EngineerCraft', 'Synthesis']:
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    for x in entry[entry['event'] == 'EngineerCraft' and 'Ingredients' or 'Materials']:
                        material = self.canonicalise(x['Name'])
                        if material in self.state[category]:
                            self.state[category][material] -= x['Count']
                            if self.state[category][material] <= 0:
                                self.state[category].pop(material)

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

            elif entry['event'] == 'JoinACrew':
                self.state['Captain'] = entry['Captain']
                self.state['Role'] = 'Idle'
                self.planet = None
                self.system = None
                self.station = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None
            elif entry['event'] == 'ChangeCrewRole':
                self.state['Role'] = entry['Role']
            elif entry['event'] == 'QuitACrew':
                self.state['Captain'] = None
                self.state['Role'] = None
                self.planet = None
                self.system = None
                self.station = None
                self.stationtype = None
                self.stationservices = None
                self.coordinates = None

            return entry
        except:
            if __debug__:
                print 'Invalid journal entry "%s"' % repr(line)
                print_exc()
            return { 'event': None }

    # Commodities, Modules and Ships can appear in different forms e.g. "$HNShockMount_Name;", "HNShockMount", and "hnshockmount",
    # "$int_cargorack_size6_class1_name;" and "Int_CargoRack_Size6_Class1", "python" and "Python", etc.
    # This returns a simple lowercased name e.g. 'hnshockmount', 'int_cargorack_size6_class1', 'python', etc
    def canonicalise(self, item):
        if not item: return ''
        item = item.lower()
        match = self._RE_CANONICALISE.match(item)
        return match and match.group(1) or item

    def get_entry(self):
        if not self.event_queue:
            return None
        else:
            entry = self.parse_entry(self.event_queue.pop(0))
            if not self.live and entry['event'] not in [None, 'Fileheader']:
                self.live = True
                self.event_queue.append('{ "timestamp":"%s", "event":"StartUp" }' % strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
            return entry

    def game_running(self):

        if platform == 'darwin':
            for app in NSWorkspace.sharedWorkspace().runningApplications():
                if app.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                    return True

        elif platform == 'win32':

            def WindowTitle(h):
                if h:
                    l = GetWindowTextLength(h) + 1
                    buf = ctypes.create_unicode_buffer(l)
                    if GetWindowText(h, buf, l):
                        return buf.value
                return None

            def callback(hWnd, lParam):
                name = WindowTitle(hWnd)
                if name and name.startswith('Elite - Dangerous'):
                    handle = GetProcessHandleFromHwnd(hWnd)
                    if handle:	# If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                        CloseHandle(handle)
                        return False	# stop enumeration
                return True

            return not EnumWindows(EnumWindowsProc(callback), 0)

        return False


# singleton
monitor = EDLogs()
