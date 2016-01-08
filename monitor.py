import atexit
import re
import threading
from os import listdir, pardir, rename, unlink
from os.path import basename, exists, isdir, isfile, join
from platform import machine
from sys import platform
from time import strptime, localtime, mktime, sleep, time
from datetime import datetime

if __debug__:
    from traceback import print_exc

if platform=='darwin':
    from AppKit import NSWorkspace
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

    WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, ctypes.POINTER(DWORD))
    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindows.argtypes = [WNDENUMPROC, LPARAM]
    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW

    @WNDENUMPROC
    def EnumWindowsProc(hwnd, lParam):
        l = GetWindowTextLength(hwnd) + 1
        buf = ctypes.create_unicode_buffer(l)
        if GetWindowText(hwnd, buf, l) and buf.value.startswith('Elite - Dangerous'):
            lParam[0] = 1
            return False	# stop enumeration
        return True

else:
    FileSystemEventHandler = object	# dummy


class EDLogs(FileSystemEventHandler):

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
        self.root = None
        self.logdir = self._logdir()
        self.logfile = None
        self.logging_enabled = self._logging_enabled
        self._restart_required = False
        self.thread = None
        self.last_event = None	# for communicating the Jump event

        if self.logdir:
            # Set up a watchog observer. This is low overhead so is left running irrespective of whether monitoring is desired.
            observer = Observer()
            observer.daemon = True
            observer.schedule(self, self.logdir)
            observer.start()
            atexit.register(observer.stop)

            # Latest pre-existing logfile - e.g. if E:D is already running. Assumes logs sort alphabetically.
            logfiles = sorted([x for x in listdir(self.logdir) if x.startswith('netLog.')])
            self.logfile = logfiles and join(self.logdir, logfiles[-1]) or None

    def enable_logging(self):
        if self.logging_enabled():
            return True
        elif self._enable_logging():
            self._restart_required = self._ED_is_running()
            return True
        else:
            return False

    def restart_required(self):
        if not self._ED_is_running():
            self._restart_required = False
        return self._restart_required

    def logging_enabled_in_file(self, appconf):
        if not isfile(appconf):
            return False

        with open(appconf, 'rU') as f:
            content = f.read().lower()
            start = content.find('<network')
            end = content.find('</network>')
            if start >= 0 and end >= 0:
                return bool(re.search('verboselogging\s*=\s*\"1\"', content[start+8:end]))
            else:
                return False

    def enable_logging_in_file(self, appconf):
        try:
            if not exists(appconf):
                with open(appconf, 'wt') as f:
                    f.write('<AppConfig>\n\t<Network\n\t\tVerboseLogging="1"\n\t>\n\t</Network>\n</AppConfig>\n')
                return True

            with open(appconf, 'rU') as f:
                content = f.read()
                f.close()
            backup = appconf[:-4] + '_backup.xml'
            if exists(backup):
                unlink(backup)
            rename(appconf, backup)

            with open(appconf, 'wt') as f:
                start = content.lower().find('<network')
                if start >= 0:
                    f.write(content[:start+8] + '\n\t\tVerboseLogging="1"' + content[start+8:])
                else:
                    start = content.lower().find("</appconfig>")
                    if start >= 0:
                        f.write(content[:start] + '\t<Network\n\t\tVerboseLogging="1"\n\t>\n\t</Network>\n' + content[start:])
                    else:
                        f.write(content)	# eh ?
                        return False

            assert self._logging_enabled()
            return self.logging_enabled_in_file(appconf)
        except:
            if __debug__: print_exc()
            return False

    def start(self, root):
        self.root = root
        if not self.logdir:
            self.stop()
            return False
        if self.running():
            return True
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
        # e.g. "{18:11:44} System:22(Gamma Doradus) Body:3 Pos:(3.69928e+07,1.13173e+09,-1.75892e+08) \r\n" or "... NormalFlight\r\n" or "... Supercruise\r\n"
        # Note that system name may contain parantheses, e.g. "Pipe (stem) Sector PI-T c3-5".
        regexp = re.compile(r'\{(.+)\} System:\d+\((.+)\) Body:')

        # Seek to the end of the latest log file
        logfile = self.logfile
        if logfile:
            loghandle = open(logfile, 'rt')
            loghandle.seek(0, 2)	# seek to EOF
        else:
            loghandle = None

        while True:
            # Check whether new log file started, e.g. client (re)started.
            newlogfile = self.logfile
            if logfile != newlogfile:
                logfile = newlogfile
                if loghandle:
                    loghandle.close()
                loghandle = open(logfile, 'rt')

            if logfile:
                system = visited = None
                loghandle.seek(0, 1)	# reset EOF flag

                for line in loghandle:
                    match = regexp.match(line)
                    if match:
                        system, visited = match.group(2), match.group(1)

                if system:
                    self._restart_required = False	# clearly logging is working
                    # Convert local time string to UTC date and time
                    visited_struct = strptime(visited, '%H:%M:%S')
                    now = localtime()
                    if now.tm_hour == 0 and visited_struct.tm_hour == 23:
                        # Crossed midnight between timestamp and poll
                        now = localtime(time()-12*60*60)	# yesterday
                    time_struct = datetime(now.tm_year, now.tm_mon, now.tm_mday, visited_struct.tm_hour, visited_struct.tm_min, visited_struct.tm_sec).timetuple()	# still local time
                    # Tk on Windows doesn't like to be called outside of an event handler, so generate an event
                    self.last_event = (mktime(time_struct), system)
                    self.root.event_generate('<<Jump>>', when="tail")

            sleep(10)	# New system gets posted to log file before hyperspace ends, so don't need to poll too often

            # Check whether we're still supposed to be running
            if threading.current_thread() != self.thread:
                return	# Terminate


    if platform=='darwin':

        def _logdir(self):
            # https://support.frontier.co.uk/kb/faq.php?id=97
            suffix = join('Frontier Developments', 'Elite Dangerous')
            paths = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)
            if len(paths) and isdir(paths[0]) and isfile(join(paths[0], suffix, 'AppNetCfg.xml')) and isdir(join(paths[0], suffix, 'Logs')):
                return join(paths[0], suffix, 'Logs')
            else:
                return None

        def _logging_enabled(self):
            return self.logdir and self.logging_enabled_in_file(join(self.logdir, pardir, 'AppConfigLocal.xml'))

        def _enable_logging(self):
            return self.logdir and self.enable_logging_in_file(join(self.logdir, pardir, 'AppConfigLocal.xml'))

        def _ED_is_running(self):
            for x in NSWorkspace.sharedWorkspace().runningApplications():
                if x.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                    return True
            else:
                return False

    elif platform=='win32':

        def _logdir(self):

            # Try locations described in https://support.elitedangerous.com/kb/faq.php?id=108, in reverse order of age
            candidates = []

            # Steam and Steam libraries
            if not RegOpenKeyEx(HKEY_CURRENT_USER, r'Software\Valve\Steam', 0, KEY_READ, ctypes.byref(key)):
                valtype = DWORD()
                valsize = DWORD()
                if not RegQueryValueEx(key, 'SteamPath', 0, ctypes.byref(valtype), None, ctypes.byref(valsize)) and valtype.value == REG_SZ:
                    buf = ctypes.create_unicode_buffer(size.value / 2)
                    if not RegQueryValueEx(key, 'SteamPath', 0, ctypes.byref(valtype), buf, ctypes.byref(valsize)):
                        steamlibs = [buf.value]
                        try:
                            # Simple-minded Valve VDF parser
                            with open(join(buf.value, 'config', 'config.vdf'), 'rU') as h:
                                for line in h:
                                    vals = line.split()
                                    if vals and vals[0].startswith('"BaseInstallFolder_'):
                                        steamlibs.append(vals[1].strip('"'))
                        except:
                            pass
                        for lib in steamlibs:
                            candidates.append(join(lib, 'steamapps', 'common', 'Elite Dangerous Horizons', 'Products'))
                            candidates.append(join(lib, 'steamapps', 'common', 'Elite Dangerous', 'Products'))
                RegCloseKey(key)

            # Next try custom installation under the Launcher
            key = HKEY()
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

        def _logging_enabled(self):
            return self.logdir and (self.logging_enabled_in_file(join(self.logdir, pardir, 'AppConfigLocal.xml')) or
                                    self.logging_enabled_in_file(join(self.logdir, pardir, 'AppConfig.xml')))

        def _enable_logging(self):
            return self.logdir and self.enable_logging_in_file(isfile(join(self.logdir, pardir, 'AppConfigLocal.xml')) and join(self.logdir, pardir, 'AppConfigLocal.xml') or join(self.logdir, pardir, 'AppConfig.xml'))

        def _ED_is_running(self):
            retval = DWORD(0)
            EnumWindows(EnumWindowsProc, ctypes.addressof(retval))
            return bool(retval)

    elif platform=='linux2':

        def _logdir(self):
            return None

        def _logging_enabled(self):
            return False

        def _enable_logging(self):
            return False

        def _ED_is_running(self):
            return False

# singleton
monitor = EDLogs()
