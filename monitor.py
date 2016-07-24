import atexit
import re
import threading
from os import listdir, pardir, rename, unlink
from os.path import basename, exists, isdir, isfile, join
from platform import machine
import sys
from sys import platform
from time import strptime, localtime, mktime, sleep, time
from datetime import datetime

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
    FileSystemEventHandler = object	# dummy


class EDLogs(FileSystemEventHandler):

    _POLL = 5		# New system gets posted to log file before hyperspace ends, so don't need to poll too often

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
        self.root = None
        self.logdir = self._logdir()
        self.logfile = None
        self.observer = None
        self.thread = None
        self.callbacks = { 'Jump': None, 'Dock': None }
        self.last_event = None	# for communicating the Jump event

    def set_callback(self, name, callback):
        if name in self.callbacks:
            self.callbacks[name] = callback

    def start(self, root):
        self.root = root
        if not self.logdir:
            self.stop()
            return False
        if self.running():
            return True

        self.root.bind_all('<<MonitorJump>>', self.jump)	# user-generated
        self.root.bind_all('<<MonitorDock>>', self.dock)	# user-generated

        # Set up a watchog observer. This is low overhead so is left running irrespective of whether monitoring is desired.
        if not self.observer:
            if __debug__:
                print 'Monitoring "%s"' % self.logdir
            elif getattr(sys, 'frozen', False):
                sys.stderr.write('Monitoring "%s"\n' % self.logdir)
                sys.stderr.flush()	# Required for line to show up immediately on Windows

            self.observer = Observer()
            self.observer.daemon = True
            self.observer.schedule(self, self.logdir)
            self.observer.start()
            atexit.register(self.observer.stop)

            # Latest pre-existing logfile - e.g. if E:D is already running. Assumes logs sort alphabetically.
            logfiles = sorted([x for x in listdir(self.logdir) if x.startswith('netLog.')])
            self.logfile = logfiles and join(self.logdir, logfiles[-1]) or None

        self.thread = threading.Thread(target = self.worker, name = 'netLog worker')
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop(self):
        self.thread = None	# Orphan the worker thread
        self.last_event = None

    def running(self):
        return self.thread and self.thread.is_alive()

    def on_created(self, event):
        # watchdog callback, e.g. client (re)started.
        if not event.is_directory and basename(event.src_path).startswith('netLog.'):
            self.logfile = event.src_path

    def worker(self):
        # Tk isn't thread-safe in general.
        # event_generate() is the only safe way to poke the main thread from this thread:
        # https://mail.python.org/pipermail/tkinter-discuss/2013-November/003522.html

        # e.g.:
        #   "{18:00:41} System:"Shinrarta Dezhra" StarPos:(55.719,17.594,27.156)ly  NormalFlight\r\n"
        # or with verboseLogging:
        #   "{17:20:18} System:"Shinrarta Dezhra" StarPos:(55.719,17.594,27.156)ly Body:69 RelPos:(0.334918,1.20754,1.23625)km NormalFlight\r\n"
        # or:
        #   "... Supercruise\r\n"
        # Note that system name may contain parantheses, e.g. "Pipe (stem) Sector PI-T c3-5".
        regexp = re.compile(r'\{(.+)\} System:"(.+)" StarPos:\((.+),(.+),(.+)\)ly.* (\S+)')	# (localtime, system, x, y, z, context)

        # e.g.:
        #   "{14:42:11} GetSafeUniversalAddress Station Count 1 moved 0 Docked Not Landed\r\n"
        # or:
        #   "... Undocked Landed\r\n"
        # Don't use the simpler "Commander Put ..." message since its more likely to be delayed.
        dockre = re.compile(r'\{(.+)\} GetSafeUniversalAddress Station Count \d+ moved \d+ (\S+) ([^\r\n]+)')	# (localtime, docked_status, landed_status)

        docked = False	# Whether we're docked
        updated = False	# Whether we've sent an update since we docked

        # Seek to the end of the latest log file
        logfile = self.logfile
        if logfile:
            loghandle = open(logfile, 'rt')
            loghandle.seek(0, 2)	# seek to EOF
        else:
            loghandle = None

        while True:

            if docked and not updated and not config.getint('output') & config.OUT_MANUAL:
                self.root.event_generate('<<MonitorDock>>', when="tail")
                updated = True
                if __debug__:
                    print "%s :\t%s %s" % ('Updated', docked and " docked" or "!docked", updated and " updated" or "!updated")

            # Check whether new log file started, e.g. client (re)started.
            newlogfile = self.logfile
            if logfile != newlogfile:
                logfile = newlogfile
                if loghandle:
                    loghandle.close()
                loghandle = open(logfile, 'rt')

            if logfile:
                system = visited = coordinates = None
                loghandle.seek(0, 1)	# reset EOF flag

                for line in loghandle:
                    match = regexp.match(line)
                    if match:
                        (visited, system, x, y, z, context) = match.groups()
                        if system == 'ProvingGround':
                            system = 'CQC'
                        coordinates = (float(x), float(y), float(z))
                    else:
                        match = dockre.match(line)
                        if match:
                            if match.group(2) == 'Undocked':
                                docked = updated = False
                            elif match.group(2) == 'Docked':
                                docked = True
                                # do nothing now in case the API server is lagging, but update on next poll
                            if __debug__:
                                print "%s :\t%s %s" % (match.group(2), docked and " docked" or "!docked", updated and " updated" or "!updated")

                if system and not docked and config.getint('output') & config.OUT_LOG_AUTO:
                    # Convert local time string to UTC date and time
                    visited_struct = strptime(visited, '%H:%M:%S')
                    now = localtime()
                    if now.tm_hour == 0 and visited_struct.tm_hour == 23:
                        # Crossed midnight between timestamp and poll
                        now = localtime(time()-12*60*60)	# yesterday
                    time_struct = datetime(now.tm_year, now.tm_mon, now.tm_mday, visited_struct.tm_hour, visited_struct.tm_min, visited_struct.tm_sec).timetuple()	# still local time
                    self.last_event = (mktime(time_struct), system, coordinates)
                    self.root.event_generate('<<MonitorJump>>', when="tail")

            sleep(self._POLL)

            # Check whether we're still supposed to be running
            if threading.current_thread() != self.thread:
                return	# Terminate

    def jump(self, event):
        # Called from Tkinter's main loop
        if self.callbacks['Jump'] and self.last_event:
            self.callbacks['Jump'](event, *self.last_event)

    def dock(self, event):
        # Called from Tkinter's main loop
        if self.callbacks['Dock']:
            self.callbacks['Dock'](event)


    if platform=='darwin':

        def _logdir(self):
            # https://support.frontier.co.uk/kb/faq.php?id=97
            suffix = join('Frontier Developments', 'Elite Dangerous')
            paths = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)
            if len(paths) and isdir(paths[0]) and isfile(join(paths[0], suffix, 'AppNetCfg.xml')) and isdir(join(paths[0], suffix, 'Logs')):
                return join(paths[0], suffix, 'Logs')
            else:
                return None

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
                            if d.startswith(game) and isfile(join(base, d, 'AppConfig.xml')) and isdir(join(base, d, 'Logs')):
                                return join(base, d, 'Logs')

            return None

    elif platform=='linux2':

        def _logdir(self):
            return None

# singleton
monitor = EDLogs()
