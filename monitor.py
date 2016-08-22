import atexit
from collections import OrderedDict
import json
import re
import threading
from os import listdir, pardir, rename, unlink, SEEK_SET, SEEK_CUR, SEEK_END
from os.path import basename, exists, isdir, isfile, join
from platform import machine
import sys
from sys import platform
from time import sleep

if __debug__:
    from traceback import print_exc

from config import config


if platform=='darwin':
    from Foundation import NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSUserDomainMask
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
 
elif platform=='win32':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import ctypes

    CSIDL_LOCAL_APPDATA     = 0x001C
    CSIDL_PROGRAM_FILESX86  = 0x002A

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

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object	# dummy


class EDLogs(FileSystemEventHandler):

    _POLL = 5		# New system gets posted to log file before hyperspace ends, so don't need to poll too often

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
        self.root = None
        self.logdir = self._logdir()	# E:D client's default Logs directory, or None if not found
        self.currentdir = None		# The actual logdir that we're monitoring
        self.logfile = None
        self.observer = None
        self.observed = None		# a watchdog ObservedWatch, or None if polling
        self.thread = None
        self.event_queue = []		# For communicating journal entries back to main thread

        # Context for journal handling
        self.version = None
        self.is_beta = False
        self.mode = None
        self.cmdr = None
        self.system = None
        self.station = None
        self.coordinates = None

    def set_callback(self, name, callback):
        if name in self.callbacks:
            self.callbacks[name] = callback

    def start(self, root):
        self.root = root
        logdir = config.get('logdir') or self.logdir
        if not self.is_valid_logdir(logdir):
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            self.stop()
        self.currentdir = logdir

        # Set up a watchog observer. This is low overhead so is left running irrespective of whether monitoring is desired.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = bool(config.get('logdir')) and platform != 'win32'
        if not polling and not self.observer:
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()
            atexit.register(self.observer.stop)

        if not self.observed and not polling:
            self.observed = self.observer.schedule(self, self.currentdir)

        # Latest pre-existing logfile - e.g. if E:D is already running. Assumes logs sort alphabetically.
        try:
            logfiles = sorted([x for x in listdir(self.currentdir) if x.startswith('Journal.')])
            self.logfile = logfiles and join(self.currentdir, logfiles[-1]) or None
        except:
            self.logfile = None

        if __debug__:
            print '%s "%s"' % (polling and 'Polling' or 'Monitoring', self.currentdir)
            print 'Start logfile "%s"' % self.logfile

        if not self.running():
            self.thread = threading.Thread(target = self.worker, name = 'Journal worker')
            self.thread.daemon = True
            self.thread.start()

        return True

    def stop(self):
        if __debug__:
            print 'Stopping monitoring'
        self.currentdir = None
        self.version = self.mode = self.cmdr = self.system = self.station = self.coordinates = None
        self.is_beta = False
        if self.observed:
            self.observed = None
            self.observer.unschedule_all()
        self.thread = None	# Orphan the worker thread - will terminate at next poll

    def running(self):
        return self.thread and self.thread.is_alive()

    def on_created(self, event):
        # watchdog callback, e.g. client (re)started.
        if not event.is_directory and basename(event.src_path).startswith('Journal.'):
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

        # Watchdog thread
        emitter = self.observed and self.observer._emitter_for_watch[self.observed]	# Note: Uses undocumented attribute

        while True:

            # Check whether new log file started, e.g. client (re)started.
            if emitter and emitter.is_alive():
                newlogfile = self.logfile	# updated by on_created watchdog callback
            else:
                # Poll
                try:
                    logfiles = sorted([x for x in listdir(self.currentdir) if x.startswith('Journal.')])
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
        try:
            entry = json.loads(line, object_pairs_hook=OrderedDict)	# Preserve property order because why not?
            entry['timestamp']	# we expect this to exist
            if entry['event'] == 'Fileheader':	# XXX or 'fileheader' ?
                self.version = entry['gameversion']
                self.is_beta = 'beta' in entry['gameversion'].lower()
            elif entry['event'] == 'LoadGame':
                self.cmdr = entry['Commander']
                self.mode = entry['GameMode']
            elif entry['event'] == 'NewCommander':
                self.cmdr = entry['Name']
            elif entry['event'] in ['Undocked']:
                self.station = None
                self.coordinates = None
            elif entry['event'] in ['Location', 'FSDJump', 'Docked']:
                if 'StarPos' in entry:
                    self.coordinates = tuple(entry['StarPos'])
                elif self.system != entry['StarSystem']:
                    self.coordinates = None	# Docked event doesn't include coordinates
                self.system = entry['StarSystem'] == 'ProvingGround' and 'CQC' or entry['StarSystem']
                self.station = entry.get('StationName')	# May be None
            return entry
        except:
            if __debug__:
                print 'Invalid journal entry "%s"' % repr(line)
            return { 'event': None }

    def get_entry(self):
        if not self.event_queue:
            return None
        else:
            return self.parse_entry(self.event_queue.pop(0))

    def is_valid_logdir(self, path):
        return self._is_valid_logdir(path)


    if platform=='darwin':

        def _logdir(self):
            # https://support.frontier.co.uk/kb/faq.php?id=97
            paths = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)
            if len(paths) and self._is_valid_logdir(join(paths[0], 'Frontier Developments', 'Elite Dangerous', 'Logs')):
                return join(paths[0], 'Frontier Developments', 'Elite Dangerous', 'Logs')
            else:
                return None

        def _is_valid_logdir(self, path):
            # Apple's SMB implementation is too flaky so assume target machine is OSX
            return path and isdir(path) and isfile(join(path, pardir, 'AppNetCfg.xml'))


    elif platform=='win32':

        def _logdir(self):

            # Try locations described in https://support.elitedangerous.com/kb/faq.php?id=108, in reverse order of age
            candidates = []

            # Steam and Steam libraries
            key = HKEY()
            if not RegOpenKeyEx(HKEY_CURRENT_USER, r'Software\Valve\Steam', 0, KEY_READ, ctypes.byref(key)):
                valtype = DWORD()
                valsize = DWORD()
                if not RegQueryValueEx(key, 'SteamPath', 0, ctypes.byref(valtype), None, ctypes.byref(valsize)) and valtype.value == REG_SZ:
                    buf = ctypes.create_unicode_buffer(valsize.value / 2)
                    if not RegQueryValueEx(key, 'SteamPath', 0, ctypes.byref(valtype), buf, ctypes.byref(valsize)):
                        steampath = buf.value.replace('/', '\\')	# For some reason uses POSIX seperators
                        steamlibs = [steampath]
                        try:
                            # Simple-minded Valve VDF parser
                            with open(join(steampath, 'config', 'config.vdf'), 'rU') as h:
                                for line in h:
                                    vals = line.split()
                                    if vals and vals[0].startswith('"BaseInstallFolder_'):
                                        steamlibs.append(vals[1].strip('"').replace('\\\\', '\\'))
                        except:
                            pass
                        for lib in steamlibs:
                            candidates.append(join(lib, 'steamapps', 'common', 'Elite Dangerous', 'Products'))
                RegCloseKey(key)

            # Next try custom installation under the Launcher
            if not RegOpenKeyEx(HKEY_LOCAL_MACHINE,
                                machine().endswith('64') and
                                r'SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall' or	# Assumes that the launcher is a 32bit process
                                r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                                0, KEY_READ, ctypes.byref(key)):
                buf = ctypes.create_unicode_buffer(MAX_PATH)
                i = 0
                while True:
                    size = DWORD(MAX_PATH)
                    if RegEnumKeyEx(key, i, buf, ctypes.byref(size), None, None, None, None):
                        break

                    subkey = HKEY()
                    if not RegOpenKeyEx(key, buf, 0, KEY_READ, ctypes.byref(subkey)):
                        valtype = DWORD()
                        valsize = DWORD((len('Frontier Developments')+1)*2)
                        valbuf = ctypes.create_unicode_buffer(valsize.value / 2)
                        if not RegQueryValueEx(subkey, 'Publisher', 0, ctypes.byref(valtype), valbuf, ctypes.byref(valsize)) and valtype.value == REG_SZ and valbuf.value == 'Frontier Developments':
                            if not RegQueryValueEx(subkey, 'InstallLocation', 0, ctypes.byref(valtype), None, ctypes.byref(valsize)) and valtype.value == REG_SZ:
                                valbuf = ctypes.create_unicode_buffer(valsize.value / 2)
                                if not RegQueryValueEx(subkey, 'InstallLocation', 0, ctypes.byref(valtype), valbuf, ctypes.byref(valsize)):
                                    candidates.append(join(valbuf.value, 'Products'))
                        RegCloseKey(subkey)
                    i += 1
                RegCloseKey(key)

            # Standard non-Steam locations
            programs = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, programs, CSIDL_PROGRAM_FILESX86, 0)
            candidates.append(join(programs.value, 'Frontier', 'Products')),

            applocal = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, applocal, CSIDL_LOCAL_APPDATA, 0)
            candidates.append(join(applocal.value, 'Frontier_Developments', 'Products'))

            for game in ['elite-dangerous-64', 'FORC-FDEV-D-1']:	# Look for Horizons in all candidate places first
                for base in candidates:
                    if isdir(base):
                        for d in listdir(base):
                            if d.startswith(game) and self._is_valid_logdir(join(base, d, 'Logs')):
                                return join(base, d, 'Logs')

            return None

        def _is_valid_logdir(self, path):
            # Assume target machine is Windows
            return path and isdir(path) and isfile(join(path, pardir, 'AppConfig.xml'))


    elif platform=='linux2':

        def _logdir(self):
            return None

        def _is_valid_logdir(self, path):
            # Assume target machine is Windows
            return path and isdir(path) and isfile(join(path, pardir, 'AppConfig.xml'))


# singleton
monitor = EDLogs()
