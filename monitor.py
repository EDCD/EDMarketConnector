import re
import threading
from os import listdir, pardir, rename, unlink
from os.path import exists, isdir, isfile, join
from platform import machine
from sys import platform
from time import strptime, localtime, mktime, sleep, time
from datetime import datetime

if __debug__:
    from traceback import print_exc

if platform=='darwin':
    from AppKit import NSWorkspace
    from Foundation import NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSUserDomainMask
 
elif platform=='win32':
    import ctypes

    CSIDL_LOCAL_APPDATA     = 0x001C
    CSIDL_PROGRAM_FILESX86  = 0x002A

    # _winreg that ships with Python 2 doesn't support unicode, so do this instead
    from ctypes.wintypes import *

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


class EDLogs:

    def __init__(self):
        self.logdir = self._logdir()
        self.logging_enabled = self._logging_enabled
        self._restart_required = False
        self.observer = None
        self.callback = None

    def set_callback(self, callback):
        self.callback = callback

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

    def start(self):
        self.stop()
        if not self.logdir or not self.callback:
            return False
        self.observer = threading.Thread(target = self.worker, name = 'netLog worker')
        self.observer.daemon = True
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
        self.observer = None

    def worker(self):
        regexp = re.compile('{(.+)} System:[^\(]*\(([^\)]+)')

        # Seek to the end of the latest log file
        logfiles = sorted([x for x in listdir(self.logdir) if x.startswith('netLog.')])
        logfile = logfiles and logfiles[-1] or None
        if logfile:
            loghandle = open(join(self.logdir, logfile), 'rt')
            loghandle.seek(0, 2)	# seek to EOF
        else:
            loghandle = None

        while True:
            # Check whether new log file started, e.g. client restarted. Assumes logs sort alphabetically.
            logfiles = sorted([x for x in listdir(self.logdir) if x.startswith('netLog.')])
            newlogfile = logfiles and logfiles[-1] or None
            if logfile != newlogfile:
                logfile = newlogfile
                if loghandle:
                    loghandle.close()
                loghandle = open(join(self.logdir, logfile), 'rt')

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
                        now = localtime(time()-60)
                    datetime_struct = datetime(now.tm_year, now.tm_mon, now.tm_mday, visited_struct.tm_hour, visited_struct.tm_min, visited_struct.tm_sec).timetuple()	# still local time
                    self.callback(system, mktime(datetime_struct))

            sleep(10)	# New system gets posted to log file before hyperspace ends, so don't need to poll too often


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
            # First try under the Launcher
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
                                    custpath = join(valbuf.value, 'Products')
                                    if isdir(custpath):
                                        for d in listdir(custpath):
                                            if d.startswith('FORC-FDEV-D-1') and isfile(join(custpath, d, 'AppConfig.xml')) and isdir(join(custpath, d, 'Logs')):
                                                RegCloseKey(subkey)
                                                RegCloseKey(key)
                                                return join(custpath, d, 'Logs')
                        RegCloseKey(subkey)
                    i += 1
                RegCloseKey(key)

            # https://support.elitedangerous.com/kb/faq.php?id=108
            programs = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, programs, CSIDL_PROGRAM_FILESX86, 0)
            applocal = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, applocal, CSIDL_LOCAL_APPDATA, 0)
            for base in [join(programs.value, 'Steam', 'steamapps', 'common', 'Elite Dangerous', 'Products'),
                         join(programs.value, 'Frontier', 'Products'),
                         join(applocal.value, 'Frontier_Developments', 'Products')]:
                if isdir(base):
                    for d in listdir(base):
                        if d.startswith('FORC-FDEV-D-1') and isfile(join(base, d, 'AppConfig.xml')) and isdir(join(base, d, 'Logs')):
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
