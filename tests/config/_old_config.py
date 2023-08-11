"""Old Configuration Test File"""
import numbers
import sys
import warnings
from configparser import NoOptionError
from os import getenv, makedirs, mkdir, pardir
from os.path import dirname, expanduser, isdir, join, normpath
from typing import TYPE_CHECKING, Optional, Union
from config import applongname, appname, update_interval
from EDMCLogging import get_main_logger

logger = get_main_logger()

if sys.platform == 'darwin':
    from Foundation import (  # type: ignore
        NSApplicationSupportDirectory, NSBundle, NSDocumentDirectory, NSSearchPathForDirectoriesInDomains,
        NSUserDefaults, NSUserDomainMask
    )

elif sys.platform == 'win32':
    import ctypes
    import uuid
    from ctypes.wintypes import DWORD, HANDLE, HKEY, LONG, LPCVOID, LPCWSTR
    if TYPE_CHECKING:
        import ctypes.windll  # type: ignore

    FOLDERID_Documents = uuid.UUID('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}')
    FOLDERID_LocalAppData = uuid.UUID('{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}')
    FOLDERID_Profile = uuid.UUID('{5E6C858F-0E22-4760-9AFE-EA3317B67173}')
    FOLDERID_SavedGames = uuid.UUID('{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}')

    SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [ctypes.c_char_p, DWORD, HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]

    CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
    CoTaskMemFree.argtypes = [ctypes.c_void_p]

    # winreg in Python <= 3.7.4 handles REG_MULTI_SZ incorrectly, so do this instead. https://bugs.python.org/issue32587
    HKEY_CURRENT_USER = 0x80000001
    KEY_ALL_ACCESS = 0x000F003F
    REG_CREATED_NEW_KEY = 0x00000001
    REG_OPENED_EXISTING_KEY = 0x00000002
    REG_SZ = 1
    REG_DWORD = 4
    REG_MULTI_SZ = 7

    REG_RESERVED_ALWAYS_ZERO = 0

    RegCreateKeyEx = ctypes.windll.advapi32.RegCreateKeyExW
    RegCreateKeyEx.restype = LONG
    RegCreateKeyEx.argtypes = [
        HKEY, LPCWSTR, DWORD, LPCVOID, DWORD, DWORD, LPCVOID, ctypes.POINTER(HKEY), ctypes.POINTER(DWORD)
    ]

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

    def known_folder_path(guid: uuid.UUID) -> Optional[str]:
        """Look up a Windows GUID to actual folder path name."""
        buf = ctypes.c_wchar_p()
        if SHGetKnownFolderPath(ctypes.create_string_buffer(guid.bytes_le), 0, 0, ctypes.byref(buf)):
            return None
        retval = buf.value  # copy data
        CoTaskMemFree(buf)  # and free original
        return retval

elif sys.platform == 'linux':
    import codecs
    from configparser import RawConfigParser


class OldConfig:
    """Object that holds all configuration data."""

    OUT_EDDN_SEND_STATION_DATA = 1
    # OUT_MKT_BPC = 2	# No longer supported
    OUT_MKT_TD = 4
    OUT_MKT_CSV = 8
    OUT_SHIP = 16
    # OUT_SHIP_EDS = 16	# Replaced by OUT_SHIP
    # OUT_SYS_FILE = 32	# No longer supported
    # OUT_STAT = 64	# No longer available
    # OUT_SHIP_CORIOLIS = 128	# Replaced by OUT_SHIP
    # OUT_SYS_EDSM = 256  # Now a plugin
    # OUT_SYS_AUTO = 512  # Now always automatic
    OUT_MKT_MANUAL = 1024
    OUT_EDDN_SEND_NON_STATION = 2048
    OUT_EDDN_DELAY = 4096
    OUT_STATION_ANY = OUT_EDDN_SEND_STATION_DATA | OUT_MKT_TD | OUT_MKT_CSV

    if sys.platform == 'darwin':  # noqa: C901 # It's gating *all* the functions

        def __init__(self):
            self.app_dir = join(
                NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], appname
            )
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.plugin_dir = join(self.app_dir, 'plugins')
            if not isdir(self.plugin_dir):
                mkdir(self.plugin_dir)

            if getattr(sys, 'frozen', False):
                self.internal_plugin_dir = normpath(join(dirname(sys.executable), pardir, 'Library', 'plugins'))
                self.respath = normpath(join(dirname(sys.executable), pardir, 'Resources'))
                self.identifier = NSBundle.mainBundle().bundleIdentifier()

            else:
                self.internal_plugin_dir = join(dirname(__file__), 'plugins')
                self.respath = dirname(__file__)
                # Don't use Python's settings if interactive
                self.identifier = f'uk.org.marginal.{appname.lower()}'
                NSBundle.mainBundle().infoDictionary()['CFBundleIdentifier'] = self.identifier

            self.default_journal_dir: Optional[str] = join(
                NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0],
                'Frontier Developments',
                'Elite Dangerous'
            )
            self.home = expanduser('~')

            self.defaults = NSUserDefaults.standardUserDefaults()
            self.settings = dict(self.defaults.persistentDomainForName_(self.identifier) or {})  # make writeable

            # Check out_dir exists
            if not self.get('outdir') or not isdir(str(self.get('outdir'))):
                self.set('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

        def get(self, key: str, default: Union[None, list, str] = None) -> Union[None, list, str]:
            """Look up a string configuration value."""
            val = self.settings.get(key)
            if val is None:
                return default

            if isinstance(val, str):
                return str(val)

            if isinstance(val, list):
                return list(val)  # make writeable

            return default

        def getint(self, key: str, default: int = 0) -> int:
            """Look up an integer configuration value."""
            try:
                return int(self.settings.get(key, default))  # should already be int, but check by casting

            except ValueError as e:
                logger.error(f"Failed to int({key=})", exc_info=e)
                return default

            except Exception as e:
                logger.debug('The exception type is ...', exc_info=e)
                return default

        def set(self, key: str, val: Union[int, str, list]) -> None:
            """Set value on the specified configuration key."""
            self.settings[key] = val

        def delete(self, key: str) -> None:
            """Delete the specified configuration key."""
            self.settings.pop(key, None)

        def save(self) -> None:
            """Save current configuration to disk."""
            self.defaults.setPersistentDomain_forName_(self.settings, self.identifier)
            self.defaults.synchronize()

        def close(self) -> None:
            """Close the configuration."""
            self.save()
            self.defaults = None

    elif sys.platform == 'win32':

        def __init__(self):
            self.app_dir = join(known_folder_path(FOLDERID_LocalAppData), appname)  # type: ignore # Not going to change
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.plugin_dir = join(self.app_dir, 'plugins')
            if not isdir(self.plugin_dir):
                mkdir(self.plugin_dir)

            if getattr(sys, 'frozen', False):
                self.internal_plugin_dir = join(dirname(sys.executable), 'plugins')
                self.respath = dirname(sys.executable)

            else:
                self.internal_plugin_dir = join(dirname(__file__), 'plugins')
                self.respath = dirname(__file__)

            # expanduser in Python 2 on Windows doesn't handle non-ASCII - http://bugs.python.org/issue13207
            self.home = known_folder_path(FOLDERID_Profile) or r'\\'

            journaldir = known_folder_path(FOLDERID_SavedGames)
            if journaldir:
                self.default_journal_dir: Optional[str] = join(journaldir, 'Frontier Developments', 'Elite Dangerous')

            else:
                self.default_journal_dir = None

            self.identifier = applongname
            self.hkey: Optional[ctypes.c_void_p] = HKEY()
            disposition = DWORD()
            if RegCreateKeyEx(
                    HKEY_CURRENT_USER,
                    r'Software\Marginal\EDMarketConnector',
                    0,
                    None,
                    0,
                    KEY_ALL_ACCESS,
                    None,
                    ctypes.byref(self.hkey),
                    ctypes.byref(disposition)
            ):
                raise Exception()

            # set WinSparkle defaults - https://github.com/vslavik/winsparkle/wiki/Registry-Settings
            edcdhkey = HKEY()
            if RegCreateKeyEx(
                    HKEY_CURRENT_USER,
                    r'Software\EDCD\EDMarketConnector',
                    0,
                    None,
                    0,
                    KEY_ALL_ACCESS,
                    None,
                    ctypes.byref(edcdhkey),
                    ctypes.byref(disposition)
            ):
                raise Exception()

            sparklekey = HKEY()
            if not RegCreateKeyEx(
                    edcdhkey,
                    'WinSparkle',
                    0,
                    None,
                    0,
                    KEY_ALL_ACCESS,
                    None,
                    ctypes.byref(sparklekey),
                    ctypes.byref(disposition)
            ):
                if disposition.value == REG_CREATED_NEW_KEY:
                    buf = ctypes.create_unicode_buffer('1')
                    RegSetValueEx(sparklekey, 'CheckForUpdates', 0, 1, buf, len(buf) * 2)

                buf = ctypes.create_unicode_buffer(str(update_interval))
                RegSetValueEx(sparklekey, 'UpdateInterval', 0, 1, buf, len(buf) * 2)
                RegCloseKey(sparklekey)

            if not self.get('outdir') or not isdir(self.get('outdir')):  # type: ignore # Not going to change
                self.set('outdir', known_folder_path(FOLDERID_Documents) or self.home)

        def get(self, key: str, default: Union[None, list, str] = None) -> Union[None, list, str]:
            """Look up a string configuration value."""
            key_type = DWORD()
            key_size = DWORD()
            # Only strings are handled here.
            if (
                    RegQueryValueEx(
                        self.hkey,
                        key,
                        0,
                        ctypes.byref(key_type),
                        None,
                        ctypes.byref(key_size)
                    )
                    or key_type.value not in [REG_SZ, REG_MULTI_SZ]
            ):
                return default

            buf = ctypes.create_unicode_buffer(int(key_size.value / 2))
            if RegQueryValueEx(self.hkey, key, 0, ctypes.byref(key_type), buf, ctypes.byref(key_size)):
                return default

            if key_type.value == REG_MULTI_SZ:
                return list(ctypes.wstring_at(buf, len(buf)-2).split('\x00'))

            return str(buf.value)

        def getint(self, key: str, default: int = 0) -> int:
            """Look up an integer configuration value."""
            key_type = DWORD()
            key_size = DWORD(4)
            key_val = DWORD()
            if (
                    RegQueryValueEx(
                        self.hkey,
                        key,
                        0,
                        ctypes.byref(key_type),
                        ctypes.byref(key_val),
                        ctypes.byref(key_size)
                    )
                    or key_type.value != REG_DWORD
            ):
                return default

            return key_val.value

        def set(self, key: str, val: Union[int, str, list]) -> None:
            """Set value on the specified configuration key."""
            if isinstance(val, str):
                buf = ctypes.create_unicode_buffer(val)
                RegSetValueEx(self.hkey, key, 0, REG_SZ, buf, len(buf)*2)

            elif isinstance(val, numbers.Integral):
                RegSetValueEx(self.hkey, key, 0, REG_DWORD, ctypes.byref(DWORD(val)), 4)

            elif isinstance(val, list):
                # null terminated non-empty strings
                string_val = '\x00'.join([str(x) or ' ' for x in val] + [''])
                buf = ctypes.create_unicode_buffer(string_val)
                RegSetValueEx(self.hkey, key, 0, REG_MULTI_SZ, buf, len(buf)*2)

            else:
                raise NotImplementedError()

        def delete(self, key: str) -> None:
            """Delete the specified configuration key."""
            RegDeleteValue(self.hkey, key)

        def save(self) -> None:
            """Save current configuration to disk."""
            pass  # Redundant since registry keys are written immediately

        def close(self) -> None:
            """Close the configuration."""
            RegCloseKey(self.hkey)
            self.hkey = None

    elif sys.platform == 'linux':
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
            self.default_journal_dir: Optional[str] = None
            self.home = expanduser('~')
            self.respath = dirname(__file__)
            self.identifier = f'uk.org.marginal.{appname.lower()}'

            self.filename = join(getenv('XDG_CONFIG_HOME', expanduser('~/.config')), appname, f'{appname}.ini')
            if not isdir(dirname(self.filename)):
                makedirs(dirname(self.filename))

            self.config = RawConfigParser(comment_prefixes=('#',))
            try:
                with codecs.open(self.filename) as h:
                    self.config.read_file(h)

            except Exception as e:
                logger.debug('Reading config failed, assuming we\'re making a new one...', exc_info=e)
                self.config.add_section(self.SECTION)

            if not self.get('outdir') or not isdir(self.get('outdir')):  # type: ignore # Not going to change
                self.set('outdir', expanduser('~'))

        def get(self, key: str, default: Union[None, list, str] = None) -> Union[None, list, str]:
            """Look up a string configuration value."""
            try:
                val = self.config.get(self.SECTION, key)
                if '\n' in val:  # list
                    # ConfigParser drops the last entry if blank,
                    # so we add a spurious ';' entry in set() and remove it here
                    assert val.split('\n')[-1] == ';', val.split('\n')
                    return [self._unescape(x) for x in val.split('\n')[:-1]]
                return self._unescape(val)

            except NoOptionError:
                logger.debug(f'attempted to get key {key} that does not exist')
                return default

            except Exception as e:
                logger.debug('And the exception type is...', exc_info=e)
                return default

        def getint(self, key: str, default: int = 0) -> int:
            """Look up an integer configuration value."""
            try:
                return self.config.getint(self.SECTION, key)

            except ValueError as e:
                logger.error(f"Failed to int({key=})", exc_info=e)

            except NoOptionError:
                logger.debug(f'attempted to get key {key} that does not exist')

            except Exception:
                logger.exception(f'unexpected exception while attempting to access {key}')

            return default

        def set(self, key: str, val: Union[int, str, list]) -> None:
            """Set value on the specified configuration key."""
            if isinstance(val, bool):
                self.config.set(self.SECTION, key, val and '1' or '0')  # type: ignore # Not going to change

            elif isinstance(val, (numbers.Integral, str)):
                self.config.set(self.SECTION, key, self._escape(val))  # type: ignore # Not going to change

            elif isinstance(val, list):
                self.config.set(self.SECTION, key, '\n'.join([self._escape(x) for x in val] + [';']))

            else:
                raise NotImplementedError()

        def delete(self, key: str) -> None:
            """Delete the specified configuration key."""
            self.config.remove_option(self.SECTION, key)

        def save(self) -> None:
            """Save current configuration to disk."""
            with codecs.open(self.filename, 'w', 'utf-8') as h:
                self.config.write(h)

        def close(self) -> None:
            """Close the configuration."""
            self.save()
            self.config = None

        def _escape(self, val: str) -> str:
            """Escape a string for storage."""
            return str(val).replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;')

        def _unescape(self, val: str) -> str:
            """Un-escape a string from storage."""
            chars = list(val)
            i = 0
            while i < len(chars):
                if chars[i] == '\\':
                    chars.pop(i)
                    if chars[i] == 'n':
                        chars[i] = '\n'
                i += 1
            return ''.join(chars)

    else:
        def __init__(self):
            raise NotImplementedError('Implement me')

    # Common

    def get_password(self, account: str) -> None:
        """Legacy password retrieval."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)

    def set_password(self, account: str, password: str) -> None:
        """Legacy password setting."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)

    def delete_password(self, account: str) -> None:
        """Legacy password deletion."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)


old_config = OldConfig()
