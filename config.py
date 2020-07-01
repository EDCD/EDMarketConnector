import numbers
import sys
from os import getenv, makedirs, mkdir, pardir
from os.path import expanduser, dirname, exists, isdir, join, normpath
from sys import platform


appname = 'EDMarketConnector'
applongname = 'E:D Market Connector'
appcmdname = 'EDMC'
appversion = '3.5.1.0'
copyright = u'© 2015-2019 Jonathan Harris, 2020 EDCD'

update_feed = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml'
update_interval = 8*60*60


if platform=='darwin':
    from Foundation import NSBundle, NSUserDefaults, NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSDocumentDirectory, NSLibraryDirectory, NSUserDomainMask

elif platform=='win32':
    import ctypes
    from ctypes.wintypes import *
    import uuid

    FOLDERID_Documents    = uuid.UUID('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}')
    FOLDERID_LocalAppData = uuid.UUID('{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}')
    FOLDERID_Profile      = uuid.UUID('{5E6C858F-0E22-4760-9AFE-EA3317B67173}')
    FOLDERID_SavedGames   = uuid.UUID('{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}')

    SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [ctypes.c_char_p, DWORD, HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]

    CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
    CoTaskMemFree.argtypes = [ctypes.c_void_p]

    # winreg in Python <= 3.7.4 handles REG_MULTI_SZ incorrectly, so do this instead. https://bugs.python.org/issue32587
    HKEY_CURRENT_USER       = 0x80000001
    KEY_ALL_ACCESS          = 0x000F003F
    REG_CREATED_NEW_KEY     = 0x00000001
    REG_OPENED_EXISTING_KEY = 0x00000002
    REG_SZ    = 1
    REG_DWORD = 4
    REG_MULTI_SZ = 7

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

    RegCopyTree = ctypes.windll.advapi32.RegCopyTreeW
    RegCopyTree.restype = LONG
    RegCopyTree.argtypes = [HKEY, LPCWSTR, HKEY]

    RegDeleteKey = ctypes.windll.advapi32.RegDeleteTreeW
    RegDeleteKey.restype = LONG
    RegDeleteKey.argtypes = [HKEY, LPCWSTR]

    RegDeleteValue = ctypes.windll.advapi32.RegDeleteValueW
    RegDeleteValue.restype = LONG
    RegDeleteValue.argtypes = [HKEY, LPCWSTR]

    def KnownFolderPath(guid):
        buf = ctypes.c_wchar_p()
        if SHGetKnownFolderPath(ctypes.create_string_buffer(guid.bytes_le), 0, 0, ctypes.byref(buf)):
            return None
        retval = buf.value	# copy data
        CoTaskMemFree(buf)	# and free original
        return retval


elif platform=='linux':
    import codecs
    from configparser import RawConfigParser


class Config(object):

    OUT_MKT_EDDN      = 1
    # OUT_MKT_BPC     = 2	# No longer supported
    OUT_MKT_TD        = 4
    OUT_MKT_CSV       = 8
    OUT_SHIP          = 16
    # OUT_SHIP_EDS    = 16	# Replaced by OUT_SHIP
    # OUT_SYS_FILE    = 32	# No longer supported
    # OUT_STAT        = 64	# No longer available
    # OUT_SHIP_CORIOLIS = 128	# Replaced by OUT_SHIP
    OUT_STATION_ANY   = OUT_MKT_EDDN|OUT_MKT_TD|OUT_MKT_CSV
    # OUT_SYS_EDSM      = 256	# Now a plugin
    # OUT_SYS_AUTO    = 512	# Now always automatic
    OUT_MKT_MANUAL    = 1024
    OUT_SYS_EDDN      = 2048
    OUT_SYS_DELAY     = 4096

    if platform=='darwin':

        def __init__(self):
            self.app_dir = join(NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.plugin_dir = join(self.app_dir, 'plugins')
            if not isdir(self.plugin_dir):
                mkdir(self.plugin_dir)

            self.internal_plugin_dir = getattr(sys, 'frozen', False) and normpath(join(dirname(sys.executable), pardir, 'Library', 'plugins')) or join(dirname(__file__), 'plugins')

            self.default_journal_dir = join(NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], 'Frontier Developments', 'Elite Dangerous')

            self.home = expanduser('~')

            self.respath = getattr(sys, 'frozen', False) and normpath(join(dirname(sys.executable), pardir, 'Resources')) or dirname(__file__)

            if not getattr(sys, 'frozen', False):
                # Don't use Python's settings if interactive
                self.identifier = 'uk.org.marginal.%s' % appname.lower()
                NSBundle.mainBundle().infoDictionary()['CFBundleIdentifier'] = self.identifier
            else:
                self.identifier = NSBundle.mainBundle().bundleIdentifier()
            self.defaults = NSUserDefaults.standardUserDefaults()
            self.settings = dict(self.defaults.persistentDomainForName_(self.identifier) or {})	# make writeable

            # Check out_dir exists
            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

        def get(self, key):
            val = self.settings.get(key)
            if val is None:
                return None
            elif isinstance(val, str):
                return str(val)
            elif hasattr(val, '__iter__'):
                return list(val)	# make writeable
            else:
                return None

        def getint(self, key):
            try:
                return int(self.settings.get(key, 0))	# should already be int, but check by casting
            except:
                return 0

        def set(self, key, val):
            self.settings[key] = val

        def delete(self, key):
            self.settings.pop(key, None)

        def save(self):
            self.defaults.setPersistentDomain_forName_(self.settings, self.identifier)
            self.defaults.synchronize()

        def close(self):
            self.save()
            self.defaults = None

    elif platform=='win32':

        def __init__(self):

            self.app_dir = join(KnownFolderPath(FOLDERID_LocalAppData), appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.plugin_dir = join(self.app_dir, 'plugins')
            if not isdir(self.plugin_dir):
                mkdir(self.plugin_dir)

            self.internal_plugin_dir = join(dirname(getattr(sys, 'frozen', False) and sys.executable or __file__), u'plugins')

            # expanduser in Python 2 on Windows doesn't handle non-ASCII - http://bugs.python.org/issue13207
            self.home = KnownFolderPath(FOLDERID_Profile) or u'\\'

            journaldir = KnownFolderPath(FOLDERID_SavedGames)
            self.default_journal_dir = journaldir and join(journaldir, 'Frontier Developments', 'Elite Dangerous') or None

            self.respath = dirname(getattr(sys, 'frozen', False) and sys.executable or __file__)

            self.identifier = applongname

            self.hkey = HKEY()
            disposition = DWORD()
            if RegCreateKeyEx(HKEY_CURRENT_USER, r'Software\Marginal\EDMarketConnector', 0, None, 0, KEY_ALL_ACCESS, None, ctypes.byref(self.hkey), ctypes.byref(disposition)):
                raise Exception()

            # set WinSparkle defaults - https://github.com/vslavik/winsparkle/wiki/Registry-Settings
            sparklekey = HKEY()
            if not RegCreateKeyEx(self.hkey, 'WinSparkle', 0, None, 0, KEY_ALL_ACCESS, None, ctypes.byref(sparklekey), ctypes.byref(disposition)):
                if disposition.value == REG_CREATED_NEW_KEY:
                    buf = ctypes.create_unicode_buffer('1')
                    RegSetValueEx(sparklekey, 'CheckForUpdates', 0, 1, buf, len(buf)*2)
                    buf = ctypes.create_unicode_buffer(str(update_interval))
                    RegSetValueEx(sparklekey, 'UpdateInterval', 0, 1, buf, len(buf)*2)
                RegCloseKey(sparklekey)

            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', KnownFolderPath(FOLDERID_Documents) or self.home)

        def get(self, key):
            typ  = DWORD()
            size = DWORD()
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), None, ctypes.byref(size)) or typ.value not in [REG_SZ, REG_MULTI_SZ]:
                return None
            buf = ctypes.create_unicode_buffer(int(size.value / 2))
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), buf, ctypes.byref(size)):
                return None
            elif typ.value == REG_MULTI_SZ:
                return [x for x in ctypes.wstring_at(buf, len(buf)-2).split(u'\x00')]
            else:
                return str(buf.value)

        def getint(self, key):
            typ  = DWORD()
            size = DWORD(4)
            val  = DWORD()
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(typ), ctypes.byref(val), ctypes.byref(size)) or typ.value != REG_DWORD:
                return 0
            else:
                return val.value

        def set(self, key, val):
            if isinstance(val, str):
                buf = ctypes.create_unicode_buffer(val)
                RegSetValueEx(self.hkey, key, 0, REG_SZ, buf, len(buf)*2)
            elif isinstance(val, numbers.Integral):
                RegSetValueEx(self.hkey, key, 0, REG_DWORD, ctypes.byref(DWORD(val)), 4)
            elif hasattr(val, '__iter__'):	# iterable
                stringval = u'\x00'.join([str(x) or u' ' for x in val] + [u''])	# null terminated non-empty strings
                buf = ctypes.create_unicode_buffer(stringval)
                RegSetValueEx(self.hkey, key, 0, REG_MULTI_SZ, buf, len(buf)*2)
            else:
                raise NotImplementedError()

        def delete(self, key):
            RegDeleteValue(self.hkey, key)

        def save(self):
            pass	# Redundant since registry keys are written immediately

        def close(self):
            RegCloseKey(self.hkey)
            self.hkey = None

    elif platform=='linux':

        SECTION = 'config'

        def __init__(self):

            # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html
            self.app_dir = join(getenv('XDG_DATA_HOME', expanduser('~/.local/share')), appname)
            if not isdir(self.app_dir):
                makedirs(self.app_dir)

            self.plugin_dir = join(self.app_dir, 'plugins')
            if not isdir(self.plugin_dir):
                mkdir(self.plugin_dir)

            self.internal_plugin_dir = join(dirname(__file__), 'plugins')

            self.default_journal_dir = None

            self.home = expanduser('~')

            self.respath = dirname(__file__)

            self.identifier = 'uk.org.marginal.%s' % appname.lower()

            self.filename = join(getenv('XDG_CONFIG_HOME', expanduser('~/.config')), appname, '%s.ini' % appname)
            if not isdir(dirname(self.filename)):
                makedirs(dirname(self.filename))

            self.config = RawConfigParser(comment_prefixes = ('#',))
            try:
                with codecs.open(self.filename, 'r') as h:
                    self.config.read_file(h)
            except:
                self.config.add_section(self.SECTION)

            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', expanduser('~'))

        def get(self, key):
            try:
                val = self.config.get(self.SECTION, key)
                if u'\n' in val:	# list
                    # ConfigParser drops the last entry if blank, so we add a spurious ';' entry in set() and remove it here
                    assert val.split('\n')[-1] == ';', val.split('\n')
                    return [self._unescape(x) for x in val.split(u'\n')[:-1]]
                else:
                    return self._unescape(val)
            except:
                return None

        def getint(self, key):
            try:
                return self.config.getint(self.SECTION, key)
            except:
                return 0

        def set(self, key, val):
            if isinstance(val, bool):
                self.config.set(self.SECTION, key, val and '1' or '0')
            elif isinstance(val, str) or isinstance(val, numbers.Integral):
                self.config.set(self.SECTION, key, self._escape(val))
            elif hasattr(val, '__iter__'):	# iterable
                self.config.set(self.SECTION, key, u'\n'.join([self._escape(x) for x in val] + [u';']))
            else:
                raise NotImplementedError()

        def delete(self, key):
            self.config.remove_option(self.SECTION, key)

        def save(self):
            with codecs.open(self.filename, 'w', 'utf-8') as h:
                self.config.write(h)

        def close(self):
            self.save()
            self.config = None

        def _escape(self, val):
            return str(val).replace(u'\\', u'\\\\').replace(u'\n', u'\\n').replace(u';', u'\\;')

        def _unescape(self, val):
            chars = list(val)
            i = 0
            while i < len(chars):
                if chars[i] == '\\':
                    chars.pop(i)
                    if chars[i] == 'n':
                        chars[i] = '\n'
                i += 1
            return u''.join(chars)

    else:	# ???

        def __init__(self):
            raise NotImplementedError('Implement me')

    # Common

    def get_password(self, account):
        try:
            import keyring
            return keyring.get_password(self.identifier, account)
        except ImportError:
            return None

    def set_password(self, account, password):
        try:
            import keyring
            keyring.set_password(self.identifier, account, password)
        except ImportError:
            pass

    def delete_password(self, account):
        try:
            import keyring
            keyring.delete_password(self.identifier, account)
        except:
            pass	# don't care - silently fail

# singleton
config = Config()
