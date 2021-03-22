"""
Code dealing with the configuration of the program.

On Windows this uses the Registry to store values in a flat manner.
Linux uses a file, but for commonality it's still a flat data structure.
"""

# spell-checker: words HKEY FOLDERID wchar wstring edcdhkey

import abc
import contextlib
import functools
import logging
import os
import pathlib
import sys
import traceback
import warnings
from abc import abstractmethod
from sys import platform
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, TypeVar, Union

import semantic_version

from constants import applongname, appname

# Any of these may be imported by plugins
appcmdname = 'EDMC'
# appversion **MUST** follow Semantic Versioning rules:
# <https://semver.org/#semantic-versioning-specification-semver>
# Major.Minor.Patch(-prerelease)(+buildmetadata)
appversion = '5.0.0-beta1'  # -rc1+a872b5f'
# For some things we want appversion without (possible) +build metadata
appversion_nobuild = str(semantic_version.Version(appversion).truncate('prerelease'))
copyright = '© 2015-2019 Jonathan Harris, 2020 EDCD'

update_feed = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml'
update_interval = 8*60*60

# This must be done here in order to avoid an import cycle with EDMCLogging.
# Other code should use EDMCLogging.get_main_logger
if os.getenv("EDMC_NO_UI"):
    logger = logging.getLogger(appcmdname)

else:
    logger = logging.getLogger(appname)

if platform == 'darwin':
    from Foundation import (  # type: ignore
        NSApplicationSupportDirectory, NSBundle, NSDocumentDirectory, NSSearchPathForDirectoriesInDomains,
        NSUserDefaults, NSUserDomainMask
    )

elif platform == 'win32':
    import ctypes
    import uuid
    import winreg
    from ctypes.wintypes import DWORD, HANDLE
    if TYPE_CHECKING:
        import ctypes.windll  # type: ignore

    REG_RESERVED_ALWAYS_ZERO = 0

    # This is the only way to do this from python without external deps (which do this anyway).
    FOLDERID_Documents = uuid.UUID('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}')
    FOLDERID_LocalAppData = uuid.UUID('{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}')
    FOLDERID_Profile = uuid.UUID('{5E6C858F-0E22-4760-9AFE-EA3317B67173}')
    FOLDERID_SavedGames = uuid.UUID('{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}')

    SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
    SHGetKnownFolderPath.argtypes = [ctypes.c_char_p, DWORD, HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]

    CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
    CoTaskMemFree.argtypes = [ctypes.c_void_p]

    def known_folder_path(guid: uuid.UUID) -> Optional[str]:
        """Look up a Windows GUID to actual folder path name."""
        buf = ctypes.c_wchar_p()
        if SHGetKnownFolderPath(ctypes.create_string_buffer(guid.bytes_le), 0, 0, ctypes.byref(buf)):
            return None
        retval = buf.value  # copy data
        CoTaskMemFree(buf)  # and free original
        return retval

elif platform == 'linux':
    from configparser import ConfigParser


_T = TypeVar('_T')


class AbstractConfig(abc.ABC):
    """Abstract root class of all platform specific Config implementations."""

    OUT_MKT_EDDN = 1
    # OUT_MKT_BPC = 2	# No longer supported
    OUT_MKT_TD = 4
    OUT_MKT_CSV = 8
    OUT_SHIP = 16
    # OUT_SHIP_EDS = 16	# Replaced by OUT_SHIP
    # OUT_SYS_FILE = 32	# No longer supported
    # OUT_STAT = 64	# No longer available
    # OUT_SHIP_CORIOLIS = 128	# Replaced by OUT_SHIP
    OUT_STATION_ANY = OUT_MKT_EDDN | OUT_MKT_TD | OUT_MKT_CSV
    # OUT_SYS_EDSM = 256  # Now a plugin
    # OUT_SYS_AUTO = 512  # Now always automatic
    OUT_MKT_MANUAL = 1024
    OUT_SYS_EDDN = 2048
    OUT_SYS_DELAY = 4096

    app_dir_path: pathlib.Path
    plugin_dir_path: pathlib.Path
    internal_plugin_dir_path: pathlib.Path
    respath_path: pathlib.Path
    home_path: pathlib.Path
    default_journal_dir_path: pathlib.Path

    identifier: str

    __in_shutdown = False  # Is the application currently shutting down ?
    __auth_force_localserver = False  # Should we use localhost for auth callback ?

    def __init__(self) -> None:
        self.home_path = pathlib.Path.home()

    def set_shutdown(self):
        self.__in_shutdown = True

    @property
    def shutting_down(self) -> bool:
        return self.__in_shutdown

    def set_auth_force_localserver(self):
        self.__auth_force_localserver = True

    @property
    def auth_force_localserver(self) -> bool:
        return self.__auth_force_localserver

    @property
    def app_dir(self) -> str:
        """Return a string version of app_dir."""
        return str(self.app_dir_path)

    @property
    def plugin_dir(self) -> str:
        """Return a string version of plugin_dir."""
        return str(self.plugin_dir_path)

    @property
    def internal_plugin_dir(self) -> str:
        """Return a string version of internal_plugin_dir."""
        return str(self.internal_plugin_dir_path)

    @property
    def respath(self) -> str:
        """Return a string version of respath."""
        return str(self.respath_path)

    @property
    def home(self) -> str:
        """Return a string version of home."""
        return str(self.home_path)

    @property
    def default_journal_dir(self) -> str:
        """Return a string version of default_journal_dir."""
        return str(self.default_journal_dir_path)

    @staticmethod
    def _suppress_call(
        func: Callable[..., _T], exceptions: Union[Type[BaseException], List[Type[BaseException]]] = Exception,
        *args: Any, **kwargs: Any
    ) -> Optional[_T]:
        if exceptions is None:
            exceptions = [Exception]

        if not isinstance(exceptions, list):
            exceptions = [exceptions]

        with contextlib.suppress(*exceptions):  # type: ignore # it works fine, mypy
            return func(*args, **kwargs)

        return None

    def get(self, key: str, default: Union[list, str, bool, int] = None) -> Union[list, str, bool, int]:
        """
        Get the requested key, or a default.

        :param key: the key to get
        :param default: the default to return if the key does not exist, defaults to None
        :raises OSError: on windows, if a registry error occurs.
        :return: the data or the default
        """
        warnings.warn(DeprecationWarning('get is Deprecated. use the specific getter for your type'))
        logger.debug('Attempt to use Deprecated get() method\n' + ''.join(traceback.format_stack()))

        if (l := self._suppress_call(self.get_list, ValueError, key, default=None)) is not None:
            return l

        elif (s := self._suppress_call(self.get_str, ValueError, key, default=None)) is not None:
            return s

        elif (b := self._suppress_call(self.get_bool, ValueError, key, default=None)) is not None:
            return b

        elif (i := self._suppress_call(self.get_int, ValueError, key, default=None)) is not None:
            return i

        return default  # type: ignore

    @abstractmethod
    def get_list(self, key: str, *, default: list = None) -> list:
        """
        Get the list referred to by the given key if it exists, or the default.

        :param key: The key to search for
        :param default: Default to return if the key does not exist, defaults to None
        :raises ValueError: If an internal error occurs getting or converting a value
        :raises OSError: on windows, if a registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    @abstractmethod
    def get_str(self, key: str, *, default: str = None) -> str:
        """
        Get the string referred to by the given key if it exists, or the default.

        :param key: The key to search for
        :param default: Default to return if the key does not exist, defaults to None
        :raises ValueError: If an internal error occurs getting or converting a value
        :raises OSError: on windows, if a registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    @abstractmethod
    def get_bool(self, key: str, *, default: bool = None) -> bool:
        """
        Get the bool referred to by the given key if it exists, or the default.

        :param key: The key to search for
        :param default: Default to return if the key does not exist, defaults to None
        :raises ValueError: If an internal error occurs getting or converting a value
        :raises OSError: on windows, if a registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    def getint(self, key: str, *, default: int = 0) -> int:
        """
        Getint is a Deprecated getter method.

        See get_int for its replacement.
        :raises OSError: on windows, if a registry error occurs.
        """
        warnings.warn(DeprecationWarning('getint is Deprecated. Use get_int instead'))
        logger.debug('Attempt to use Deprecated get_int() method\n' + ''.join(traceback.format_stack()))

        return self.get_int(key, default=default)

    @abstractmethod
    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Get the int referred to by key if it exists in the config.

        For legacy reasons, the default is 0 and not None.

        :param key: The key to search for
        :param default: Default to return if the key does not exist, defaults to 0
        :raises ValueError: if the internal representation of this key cannot be converted to an int
        :raises OSError: on windows, if a registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, val: Union[int, str, List[str], bool]) -> None:
        """Set the given key to the given data."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        :param key: The key to delete
        :raises OSError: on windows, if a registry error occurs.
        """
        raise NotImplementedError

    @abstractmethod
    def save(self) -> None:
        """
        Save the current configuration.

        :raises OSError: on windows, if a registry error occurs.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close this config and release any associated resources."""
        raise NotImplementedError

    def get_password(self, account: str) -> None:
        """Legacy password retrieval."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)

    def set_password(self, account: str, password: str) -> None:
        """Legacy password setting."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)

    def delete_password(self, account: str) -> None:
        """Legacy password deletion."""
        warnings.warn("password subsystem is no longer supported", DeprecationWarning)


class WinConfig(AbstractConfig):
    """Implementation of AbstractConfig for windows."""

    def __init__(self, do_winsparkle=True) -> None:
        self.app_dir_path = pathlib.Path(str(known_folder_path(FOLDERID_LocalAppData))) / appname
        self.app_dir_path.mkdir(exist_ok=True)

        self.plugin_dir_path = self.app_dir_path / 'plugins'
        self.plugin_dir_path.mkdir(exist_ok=True)

        if getattr(sys, 'frozen', False):
            self.respath_path = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir_path = self.respath_path / 'plugins'

        else:
            self.respath_path = pathlib.Path(__file__).parent
            self.internal_plugin_dir_path = self.respath_path / 'plugins'

        self.home_path = pathlib.Path.home()

        journal_dir_str = known_folder_path(FOLDERID_SavedGames)
        journaldir = pathlib.Path(journal_dir_str) if journal_dir_str is not None else None
        self.default_journal_dir_path = None  # type: ignore
        if journaldir is not None:
            self.default_journal_dir_path = journaldir / 'Frontier Developments' / 'Elite Dangerous'

        create_key_defaults = functools.partial(
            winreg.CreateKeyEx,
            key=winreg.HKEY_CURRENT_USER,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )

        try:
            self.__reg_handle: winreg.HKEYType = create_key_defaults(
                sub_key=r'Software\Marginal\EDMarketConnector'
            )
            if do_winsparkle:
                self.__setup_winsparkle()

        except OSError:
            logger.exception('could not create required registry keys')
            raise

        self.identifier = applongname
        if (outdir_str := self.get_str('outdir')) is None or not pathlib.Path(outdir_str).is_dir():
            docs = known_folder_path(FOLDERID_Documents)
            self.set('outdir',  docs if docs is not None else self.home)

    def __setup_winsparkle(self):
        create_key_defaults = functools.partial(
            winreg.CreateKeyEx,
            key=winreg.HKEY_CURRENT_USER,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )
        try:
            edcd_handle: winreg.HKEYType = create_key_defaults(sub_key=r'Software\EDCD\EDMarketConnector')
            winsparkle_reg: winreg.HKEYType = winreg.CreateKeyEx(
                edcd_handle, sub_key='WinSparkle', access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY
            )

        except OSError:
            logger.exception('could not open winsparkle handle')
            raise

        # set WinSparkle defaults - https://github.com/vslavik/winsparkle/wiki/Registry-Settings
        winreg.SetValueEx(
            winsparkle_reg, 'UpdateInterval', REG_RESERVED_ALWAYS_ZERO, winreg.REG_SZ, str(update_interval)
        )

        try:
            winreg.QueryValueEx(winsparkle_reg, 'CheckForUpdates')

        except FileNotFoundError:
            # Key doesn't exist, set it to a default
            winreg.SetValueEx(winsparkle_reg, 'CheckForUpdates', REG_RESERVED_ALWAYS_ZERO, winreg.REG_SZ, '1')

        winsparkle_reg.Close()
        edcd_handle.Close()

    def __get_regentry(self, key: str) -> Union[None, list, str, int]:
        """Access the registry for the raw entry."""
        try:
            value, _type = winreg.QueryValueEx(self.__reg_handle, key)
        except FileNotFoundError:
            # Key doesn't exist
            return None

        # The type returned is actually as we'd expect for each of these. The casts are here for type checkers and
        # For programmers who want to actually know what is going on
        if _type == winreg.REG_SZ:
            return str(value)

        elif _type == winreg.REG_DWORD:
            return int(value)

        elif _type == winreg.REG_MULTI_SZ:
            return list(value)

        else:
            logger.warning(f'registry key {key=} returned unknown type {_type=} {value=}')
            return None

    def get_str(self, key: str, *, default: str = None) -> str:
        """
        Return the string represented by the key, or the default if it does not exist.

        :param key: the key to access
        :param default: the default to return when the key does not exist, defaults to None
        :raises ValueError: when the key is not a string type
        :return: the requested data, or the default
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, str):
            raise ValueError(f'Data from registry is not a string: {type(res)=} {res=}')

        return res

    def get_list(self, key: str, *, default: list = None) -> list:
        """
        Return the list found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to None
        :raises ValueError: When the data at the given key is not a list
        :return: the requested data or the default
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, list):
            raise ValueError(f'Data from registry is not a list: {type(res)=} {res}')

        return res

    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to 0
        :raises ValueError: If the data returned is of an unexpected type
        :return: the data requested or the default
        """
        res = self.__get_regentry(key)
        if res is None:
            return default

        if not isinstance(res, int):
            raise ValueError(f'Data from registry is not an int: {type(res)=} {res}')

        return res

    def get_bool(self, key: str, *, default: bool = None) -> bool:
        """
        Return the bool found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when key does not exist, defaults to None
        :raises ValueError: If the data returned is of an unexpected type
        :return: The data requested or the default
        """
        res = self.get_int(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        return bool(res)

    def set(self, key: str, val: Union[int, str, List[str], bool]) -> None:
        """
        Set sets the given key to the given value.

        :param key: The key to set the value to
        :param val: The value to set the key
        :raises ValueError: On an invalid type
        :raises OSError: On any internal failure to the registry
        """
        reg_type = None
        if isinstance(val, str):
            reg_type = winreg.REG_SZ
            winreg.SetValueEx(self.__reg_handle, key, REG_RESERVED_ALWAYS_ZERO, winreg.REG_SZ, val)

        elif isinstance(val, int):  # The original code checked for numbers.Integral, I dont think that is needed.
            reg_type = winreg.REG_DWORD

        elif isinstance(val, list):
            reg_type = winreg.REG_MULTI_SZ

        elif isinstance(val, bool):
            reg_type = winreg.REG_DWORD
            val = int(val)

        else:
            raise ValueError(f'Unexpected type for value {type(val)=}')

        # Its complaining about the list, it works, tested on windows, ignored.
        winreg.SetValueEx(self.__reg_handle, key, REG_RESERVED_ALWAYS_ZERO, reg_type, val)  # type: ignore

    def delete(self, key: str, *, suppress=False) -> None:
        try:
            winreg.DeleteValue(self.__reg_handle, key)
        except OSError:
            if suppress:
                return

            raise

    def save(self) -> None:
        """Save the configuration."""
        # Not required as reg keys are flushed on write
        pass

    def close(self):
        """Close the config file."""
        self.__reg_handle.Close()


class MacConfig(AbstractConfig):
    """MacConfig is the implementation of AbstractConfig for Darwin based OSes."""

    def __init__(self) -> None:
        super().__init__()
        support_path = pathlib.Path(
            NSSearchPathForDirectoriesInDomains(
                NSApplicationSupportDirectory, NSUserDomainMask, True
            )[0]
        )

        self.app_dir_path = support_path / appname
        self.app_dir_path.mkdir(exist_ok=True)

        self.plugin_dir_path = self.app_dir_path / 'plugins'
        self.plugin_dir_path.mkdir(exist_ok=True)

        # Bundle IDs identify a singled app though out a system

        if getattr(sys, 'frozen', False):
            exe_dir = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir_path = exe_dir.parent / 'Library' / 'plugins'
            self.respath_path = exe_dir.parent / 'Resources'
            self.identifier = NSBundle.mainBundle().bundleIdentifier()

        else:
            file_dir = pathlib.Path(__file__).parent
            self.internal_plugin_dir_path = file_dir / 'plugins'
            self.respath_path = file_dir

            self.identifier = f'uk.org.marginal.{appname.lower()}'
            NSBundle.mainBundle().infoDictionary()['CFBundleIdentifier'] = self.identifier

        self.default_journal_dir_path = support_path / 'Frontier Developments' / 'Elite Dangerous'
        self._defaults = NSUserDefaults.standardUserDefaults()
        self._settings: Dict[str, Union[int, str, list]] = dict(
            self._defaults.persistentDomainForName_(self.identifier) or {}
        )  # make writeable

        if (out_dir := self.get_str('out_dir')) is None or not pathlib.Path(out_dir).exists():
            self.set('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

    def __raw_get(self, key: str) -> Union[None, list, str, int]:
        res = self._settings.get(key)
        if isinstance(res, list):
            return list(res)

        return res

    def get_str(self, key: str, *, default: str = None) -> str:
        """
        Return the string represented by the key, or the default if it does not exist.

        :param key: the key to access
        :param default: the default to return when the key does not exist, defaults to None
        :raises ValueError: when the key is not a string type
        :return: the requested data, or the default
        """
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, str):
            raise ValueError(f'unexpected data returned from __raw_get: {type(res)=} {res}')

        return res

    def get_list(self, key: str, *, default: list = None) -> list:
        """
        Return the list found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to None
        :raises ValueError: When the data at the given key is not a list
        :return: the requested data or the default
        """
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, list):
            raise ValueError(f'__raw_get returned unexpected type {type(res)=} {res!r}')

        return res

    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to 0
        :raises ValueError: If the data returned is of an unexpected type
        :return: the data requested or the default
        """
        res = self.__raw_get(key)
        if res is None:
            return default

        elif not isinstance(res, (str, int)):
            raise ValueError(f'__raw_get returned unexpected type {type(res)=} {res!r}')

        try:
            return int(res)

        except ValueError as e:
            logger.error(f'__raw_get returned {res!r} which cannot be parsed to an int: {e}')
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

    def get_bool(self, key: str, *, default: bool = None) -> bool:
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, bool):
            raise ValueError(f'__raw_get returned unexpected type {type(res)=} {res!r}')

        return res

    def set(self, key: str, val: Union[int, str, List[str], bool]) -> None:
        """
        Set sets the given key to the given value.

        :param key: The key to set the value to
        :param val: The value to set the key
        """
        self._settings[key] = val

    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        :param key: the key to delete
        """
        del self._settings[key]

    def save(self) -> None:
        """Save the configuration."""
        self._defaults.setPersistentDomain_forName_(self._settings, self.identifier)
        self._defaults.synchronize()

    def close(self) -> None:
        """Close the configuration."""
        self.save()
        self._defaults = None


class LinuxConfig(AbstractConfig):
    """Linux implementation of AbstractConfig."""

    SECTION = 'config'
    # TODO: I dislike this, would rather use a sane config file format. But here we are.
    __unescape_lut = {'\\': '\\', 'n': '\n', ';': ';', 'r': '\r', '#': '#'}
    __escape_lut = {'\\': '\\', '\n': 'n', ';': ';', '\r': 'r'}

    def __init__(self, filename: Optional[str] = None) -> None:
        super().__init__()
        # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html
        xdg_data_home = pathlib.Path(os.getenv('XDG_DATA_HOME', default='~/.local/share')).expanduser()
        self.app_dir_path = xdg_data_home / appname
        self.app_dir_path.mkdir(exist_ok=True, parents=True)

        self.plugin_dir_path = self.app_dir_path / 'plugins'
        self.plugin_dir_path.mkdir(exist_ok=True)

        self.respath_path = pathlib.Path(__file__).parent

        self.internal_plugin_dir_path = self.respath_path / 'plugins'
        self.default_journal_dir_path = None  # type: ignore
        self.identifier = f'uk.org.marginal.{appname.lower()}'  # TODO: Unused?

        config_home = pathlib.Path(os.getenv('XDG_CONFIG_HOME', default='~/.config')).expanduser()

        self.filename = config_home / appname / f'{appname}.ini'
        if filename is not None:
            self.filename = pathlib.Path(filename)

        self.filename.parent.mkdir(exist_ok=True, parents=True)

        self.config: Optional[ConfigParser] = ConfigParser(comment_prefixes=('#',), interpolation=None)

        try:
            self.config.read(self.filename)
        except Exception as e:
            logger.debug(f'Error occurred while reading in file. Assuming that we are creating a new one: {e}')
            self.config.add_section(self.SECTION)

        if (outdir := self.get_str('outdir')) is None or not pathlib.Path(outdir).is_dir():
            self.set('outdir', self.home)

    def __escape(self, s: str) -> str:
        """
        Escape the string using self.__escape_lut.

        This does NOT support multi-character escapes
        """
        out = ""
        for c in s:
            if c not in self.__escape_lut:
                out += c
                continue

            out += '\\' + self.__escape_lut[c]

        return out

    def __unescape(self, s: str) -> str:
        out: List[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if c != '\\':
                out.append(c)
                i += 1
                continue

            # We have a backslash, check what its escaping
            if i == len(s)-1:
                raise ValueError('Escaped string has unescaped trailer')

            unescaped = self.__unescape_lut.get(s[i+1])
            if unescaped is None:
                raise ValueError(f'Unknown escape: \\ {s[i+1]}')

            out.append(unescaped)
            i += 2

        return "".join(out)

    def __raw_get(self, key: str) -> Optional[str]:
        if self.config is None:
            raise ValueError('Attempt to use a closed config')

        return self.config[self.SECTION].get(key)

    def get_str(self, key: str, *, default: str = None) -> str:
        data = self.__raw_get(key)
        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if '\n' in data:
            raise ValueError('asked for string, got list')

        return self.__unescape(data)

    def get_list(self, key: str, *, default: list = None) -> list:
        data = self.__raw_get(key)

        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        split = data.split('\n')
        if split[-1] != ';':
            raise ValueError('Encoded list does not have trailer sentinel')

        return list(map(self.__unescape, split[:-1]))

    def get_int(self, key: str, *, default: int = 0) -> int:
        data = self.__raw_get(key)

        if data is None:
            return default

        try:
            return int(data)

        except ValueError as e:
            raise ValueError(f'requested {key=} as int cannot be converted to int') from e

    def get_bool(self, key: str, *, default: bool = None) -> bool:
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        data = self.__raw_get(key)
        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        return bool(int(data))

    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        to_set: Optional[str] = None
        if isinstance(val, bool):
            to_set = str(int(val))

        elif isinstance(val, str):
            to_set = self.__escape(val)

        elif isinstance(val, int):
            to_set = str(val)

        elif isinstance(val, list):
            to_set = '\n'.join([self.__escape(s) for s in val] + [';'])

        else:
            raise NotImplementedError(f'value of type {type(val)} is not supported')

        self.config.set(self.SECTION, key, to_set)

    def delete(self, key: str, *, suppress=False) -> None:
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        self.config.remove_option(self.SECTION, key)

    def save(self) -> None:
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def close(self) -> None:
        self.save()
        self.config = None


def get_config(*args, **kwargs) -> AbstractConfig:
    if sys.platform == "darwin":
        return MacConfig(*args, **kwargs)
    elif sys.platform == "win32":
        return WinConfig(*args, **kwargs)
    elif sys.platform == "linux":
        return LinuxConfig(*args, **kwargs)
    else:
        raise ValueError(f'Unknown platform: {sys.platform=}')


config = get_config()
