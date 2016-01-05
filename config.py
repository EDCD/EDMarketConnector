import sys
from os import getenv, makedirs, mkdir
from os.path import expanduser, dirname, isdir, join
from sys import platform


appname = 'EDMarketConnector'
applongname = 'E:D Market Connector'
appcmdname = 'EDMC'
appversion = '2.0.4.0'

update_feed = 'http://marginal.org.uk/edmarketconnector.xml'
update_interval = 47*60*60


if platform=='darwin':
    from Foundation import NSBundle, NSUserDefaults, NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSDocumentDirectory, NSLibraryDirectory, NSUserDomainMask

elif platform=='win32':
    import ctypes
    import numbers

    CSIDL_PERSONAL = 0x0005
    CSIDL_LOCAL_APPDATA = 0x001C
    CSIDL_PROFILE = 0x0028

    # _winreg that ships with Python 2 doesn't support unicode, so do this instead
    from ctypes.wintypes import *

    HKEY_CURRENT_USER       = 0x80000001
    KEY_ALL_ACCESS          = 0x000F003F
    REG_CREATED_NEW_KEY     = 0x00000001
    REG_OPENED_EXISTING_KEY = 0x00000002
    REG_SZ    = 1
    REG_DWORD = 4

    RegCreateKeyEx = ctypes.windll.advapi32.RegCreateKeyExW
    RegCreateKeyEx.restype = LONG
    RegCreateKeyEx.argtypes = [HKEY, LPCWSTR, DWORD, LPCVOID, DWORD, DWORD, LPCVOID, ctypes.POINTER(HKEY), ctypes.POINTER(DWORD)]

    RegOpenKeyEx = ctypes.windll.advapi32.RegOpenKeyExW
    RegOpenKeyEx.restype = LONG
    RegOpenKeyEx.argtypes = [HKEY, LPCWSTR, DWORD, DWORD, ctypes.POINTER(HKEY)]

    RegCloseKey = ctypes.windll.advapi32.RegCloseKey
    RegCloseKey.restype = LONG
    RegCloseKey.argtypes = [HKEY]

    RegQueryValueEx = ctypes.windll.advapi32.RegQueryValueExW
    RegQueryValueEx.restype = LONG
    RegQueryValueEx.argtypes = [HKEY, LPCWSTR, LPCVOID, ctypes.POINTER(DWORD), LPCVOID, ctypes.POINTER(DWORD)]

    RegSetValueEx = ctypes.windll.advapi32.RegSetValueExW
    RegSetValueEx.restype = LONG
    RegSetValueEx.argtypes = [HKEY, LPCWSTR, LPCVOID, DWORD, LPCVOID, DWORD]

    SHCopyKey = ctypes.windll.shlwapi.SHCopyKeyW
    SHCopyKey.restype = LONG
    SHCopyKey.argtypes = [HKEY, LPCWSTR, HKEY, DWORD]

    SHDeleteKey = ctypes.windll.shlwapi.SHDeleteKeyW
    SHDeleteKey.restype = LONG
    SHDeleteKey.argtypes = [HKEY, LPCWSTR]

elif platform=='linux2':
    import codecs
    # requires python-iniparse package - ConfigParser that ships with Python < 3.2 doesn't support unicode
    from iniparse import RawConfigParser


class Config:

    OUT_EDDN = 1
    OUT_BPC  = 2
    OUT_TD   = 4
    OUT_CSV  = 8
    OUT_SHIP_EDS = 16
    OUT_LOG_FILE  = 32
    #OUT_STAT = 64	# No longer available
    OUT_SHIP_CORIOLIS = 128
    OUT_LOG_EDSM = 256
    OUT_LOG_AUTO = 512
    EDSM_AUTOOPEN = 1024

    if platform=='darwin':

        def __init__(self):
            self.app_dir = join(NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.home = expanduser('~')

            if not getattr(sys, 'frozen', False):
                # Don't use Python's settings if interactive
                self.bundle = 'uk.org.marginal.%s' % appname.lower()
                NSBundle.mainBundle().infoDictionary()['CFBundleIdentifier'] = self.bundle
            self.bundle = NSBundle.mainBundle().bundleIdentifier()
            self.defaults = NSUserDefaults.standardUserDefaults()
            settings = self.defaults.persistentDomainForName_(self.bundle) or {}
            self.settings = dict(settings)

            # Check out_dir exists
            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

        def get(self, key):
            return self.settings.get(key)

        def getint(self, key):
            try:
                return int(self.settings.get(key, 0))	# should already be int, but check by casting
            except:
                return 0

        def set(self, key, val):
            self.settings[key] = val

        def close(self):
            self.defaults.setPersistentDomain_forName_(self.settings, self.bundle)
            self.defaults.synchronize()
            self.defaults = None

    elif platform=='win32':

        def __init__(self):

            buf = ctypes.create_unicode_buffer(MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_LOCAL_APPDATA, 0)
            self.app_dir = join(buf.value, appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)
            
            # expanduser in Python 2 on Windows doesn't handle non-ASCII - http://bugs.python.org/issue13207
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_PROFILE, 0)
            self.home = buf.value

            self.hkey = HKEY()
            disposition = DWORD()
            if RegCreateKeyEx(HKEY_CURRENT_USER, r'Software\Marginal\EDMarketConnector', 0, None, 0, KEY_ALL_ACCESS, None, ctypes.byref(self.hkey), ctypes.byref(disposition)):
                raise Exception()

            if disposition.value == REG_CREATED_NEW_KEY:

                # Migrate pre-1.3.4 registry location
                oldkey = HKEY()
                if not RegOpenKeyEx(HKEY_CURRENT_USER, r'Software\EDMarketConnector', 0, KEY_ALL_ACCESS, ctypes.byref(oldkey)):
                    SHCopyKey(oldkey, None, self.hkey, 0)
                    SHDeleteKey(oldkey, '')
                    RegCloseKey(oldkey)

                # set WinSparkle defaults - https://github.com/vslavik/winsparkle/wiki/Registry-Settings
                sparklekey = HKEY()
                if not RegCreateKeyEx(self.hkey, 'WinSparkle', 0, None, 0, KEY_ALL_ACCESS, None, ctypes.byref(sparklekey), ctypes.byref(disposition)):
                    if disposition.value == REG_CREATED_NEW_KEY:
                        buf = ctypes.create_unicode_buffer('1')
                        RegSetValueEx(sparklekey, 'CheckForUpdates', 0, 1, buf, len(buf)*2)
                        buf = ctypes.create_unicode_buffer(unicode(update_interval))
                        RegSetValueEx(sparklekey, 'UpdateInterval', 0, 1, buf, len(buf)*2)
                    RegCloseKey(sparklekey)

            if not self.get('outdir') or not isdir(self.get('outdir')):
                buf = ctypes.create_unicode_buffer(MAX_PATH)
                ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_PERSONAL, 0)
                self.set('outdir', buf.value)

        def get(self, key):
            typ  = DWORD()
            size = DWORD()
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), None, ctypes.byref(size)) or typ.value != REG_SZ:
                return None
            buf = ctypes.create_unicode_buffer(size.value / 2)
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), buf, ctypes.byref(size)):
                return None
            else:
                return buf.value

        def getint(self, key):
            typ  = DWORD()
            size = DWORD(4)
            val  = DWORD()
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), ctypes.byref(val), ctypes.byref(size)) or typ.value != REG_DWORD:
                return 0
            else:
                return val.value

        def set(self, key, val):
            if isinstance(val, basestring):
                buf = ctypes.create_unicode_buffer(val)
                RegSetValueEx(self.hkey, key, 0, REG_SZ, buf, len(buf)*2)
            elif isinstance(val, numbers.Integral):
                RegSetValueEx(self.hkey, key, 0, REG_DWORD, ctypes.byref(DWORD(val)), 4)
            else:
                raise NotImplementedError()

        def close(self):
            RegCloseKey(self.hkey)
            self.hkey = None

    elif platform=='linux2':

        def __init__(self):

            # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html
            self.app_dir = join(getenv('XDG_DATA_HOME', expanduser('~/.local/share')), appname)
            if not isdir(self.app_dir):
                makedirs(self.app_dir)

            self.home = expanduser('~')

            self.filename = join(getenv('XDG_CONFIG_HOME', expanduser('~/.config')), appname, '%s.ini' % appname)
            if not isdir(dirname(self.filename)):
                makedirs(dirname(self.filename))

            self.config = RawConfigParser()
            try:
                self.config.readfp(codecs.open(self.filename, 'r', 'utf-8'))
            except:
                self.config.add_section('config')

            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', expanduser('~'))

        def set(self, key, val):
            self.config.set('config', key, val)

        def get(self, key):
            try:
                return self.config.get('config', key)	# all values are stored as strings
            except:
                return None

        def getint(self, key):
            try:
                return int(self.config.get('config', key))	# all values are stored as strings
            except:
                return 0

        def close(self):
            h = codecs.open(self.filename, 'w', 'utf-8')
            h.write(unicode(self.config.data))
            h.close()
            self.config = None

    else:	# ???

        def __init__(self):
            raise NotImplementedError('Implement me')

# singleton
config = Config()
