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
appversion = '4.2.0-beta1'  # -rc1+a872b5f'
# For some things we want appversion without (possible) +build metadata
appversion_nobuild = str(semantic_version.Version(appversion).truncate('prerelease'))
copyright = '© 2015-2019 Jonathan Harris, 2020 EDCD'

update_feed = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml'
update_interval = 8*60*60

if getenv("EDMC_NO_UI"):
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

    app_dir: pathlib.Path
    plugin_dir: pathlib.Path
    internal_plugin_dir: pathlib.Path
    respath: pathlib.Path
    home: pathlib.Path
    default_journal_dir: Optional[pathlib.Path]

    identifier: str

    def __init__(self) -> None:
        self.home = pathlib.Path.home()

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

    def get(self, key: str, default: Union[None, list, str, bool, int] = None) -> Union[None, list, str, bool, int]:
        """
        Get the requested key, or a default.

        :param key: the key to get
        :param default: the default to return if the key does not exist, defaults to None
        :raises OSError: on windows, if a registry error occurs.
        :return: the data or the default
        """
        warnings.warn(DeprecationWarning('get is Deprecated. use the specific getter for your type'))
        if (l := self._suppress_call(self.get_list, ValueError, key, None)) is not None:
            return l

        elif (s := self._suppress_call(self.get_str, ValueError, key, None)) is not None:
            return s

        elif (b := self._suppress_call(self.get_bool, ValueError, key, None)) is not None:
            return b

        elif (i := self._suppress_call(self.get_int, ValueError, key, None)) is not None:
            return i

        return default

    @abstractmethod
    def get_list(self, key: str, default: Optional[list] = None) -> Optional[list]:
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
    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
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
    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """
        Get the bool referred to by the given key if it exists, or the default.

        :param key: The key to search for
        :param default: Default to return if the key does not exist, defaults to None
        :raises ValueError: If an internal error occurs getting or converting a value
        :raises OSError: on windows, if a registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    def getint(self, key: str, default: Optional[int] = 0) -> Optional[int]:
        """
        Getint is a Deprecated getter method.

        See get_int for its replacement.
        :raises OSError: on windows, if a registry error occurs.
        """
        warnings.warn(DeprecationWarning('getint is Deprecated. Use get_int instead'))
        return self.get_int(key, default)

    @abstractmethod
    def get_int(self, key: str, default: Optional[int] = 0) -> Optional[int]:
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
    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
        """Set the given key to the given data."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
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

    def __init__(self) -> None:
        self.app_dir = pathlib.Path(str(known_folder_path(FOLDERID_LocalAppData))) / appname
        self.app_dir.mkdir(exist_ok=True)

        self.plugin_dir = self.app_dir / 'plugins'
        self.plugin_dir.mkdir(exist_ok=True)

        if getattr(sys, 'frozen', False):
            self.respath = pathlib.Path(dirname(sys.executable))
            self.internal_plugin_dir = self.respath / 'plugins'

        else:
            self.respath = pathlib.Path(dirname(__file__))
            self.internal_plugin_dir = self.respath / 'plugins'

        self.home = pathlib.Path.home()

        journal_dir_str = known_folder_path(FOLDERID_SavedGames)
        journaldir = pathlib.Path(journal_dir_str) if journal_dir_str is not None else None
        self.default_journal_dir = None
        if journaldir is not None:
            self.default_journal_dir = journaldir / 'Frontier Developments' / 'Elite Dangerous'

        create_key_defaults = functools.partial(
            winreg.CreateKeyEx,
            key=winreg.HKEY_CURRENT_USER,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )

        try:
            self.__reg_handle: winreg.HKEYType = create_key_defaults(
                subkey=r'Software\Marginal\EDMarketConnector'
            )
            if do_winsparkle:
                self.__setup_winsparkle()

        except OSError:
            logger.exception('could not create required registry keys')
            raise

        self.identifier = applongname
        if (outdir_str := self.get_str('outdir')) is None or not pathlib.Path(outdir_str).is_dir():
            docs = known_folder_path(FOLDERID_Documents)
            self.set('outdir',  docs if docs is not None else str(self.home))

    def __setup_winsparkle(self):
        create_key_defaults = functools.partial(
            winreg.CreateKeyEx,
            key=winreg.HKEY_CURRENT_USER,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )
        try:
            edcd_handle: winreg.HKEYType = create_key_defaults(subkey=r'Software\EDCD\EDMarketConnector')
            winsparkle_reg: winreg.HKEYType = winreg.CreateKeyEx(
                edcd_handle, 'WinSparkle', access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY
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

        self.identifier = applongname
        if (outdir_str := self.get_str('outdir')) is None or not isdir(outdir_str):
            docs = known_folder_path(FOLDERID_Documents)
            self.set('outdir',  docs if docs is not None else str(self.home))

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

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Return the string represented by the key, or the default if it does not exist.

        :param key: the key to access
        :param default: the default to return when the key does not exist, defaults to None
        :raises ValueError: when the key is not a string type
        :return: the requested data, or the default
        """
        res = self.__get_regentry(key)
        if res is None:
            return default

        elif not isinstance(res, str):
            raise ValueError(f'Data from registry is not a string: {type(res)=} {res=}')

        return res

    def get_list(self, key: str, default: Optional[list] = None) -> Optional[list]:
        """
        Return the list found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to None
        :raises ValueError: When the data at the given key is not a list
        :return: the requested data or the default
        """
        res = self.__get_regentry(key)
        if res is None:
            return default

        elif not isinstance(res, list):
            raise ValueError(f'Data from registry is not a list: {type(res)=} {res}')

        return res

    def get_int(self, key: str, default: Optional[int] = 0) -> Optional[int]:
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

    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
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

        else:
            raise ValueError(f'Unexpected type for value {type(val)=}')

        # Its complaining about the list, it works, tested on windows, ignored.
        winreg.SetValueEx(self.__reg_handle, key, REG_RESERVED_ALWAYS_ZERO, reg_type, val)  # type: ignore

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

        self.app_dir = support_path / appname
        self.app_dir.mkdir(exist_ok=True)

        self.plugin_dir = self.app_dir / 'plugins'
        self.plugin_dir.mkdir(exist_ok=True)

        # Bundle IDs identify a singled app though out a system

        if getattr(sys, 'frozen', False):
            exe_dir = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir = exe_dir.parent / 'Library' / 'plugins'
            self.respath = exe_dir.parent / 'Resources'
            self.identifier = NSBundle.mainBundle().bundleIdentifier()

        else:
            file_dir = pathlib.Path(__file__).parent
            self.internal_plugin_dir = file_dir / 'plugins'
            self.respath = file_dir

            self.identifier = f'uk.org.marginal.{appname.lower()}'
            NSBundle.mainBundle().infoDictionary()['CFBundleIdentifier'] = self.identifier

        self.default_journal_dir = support_path / 'Frontier Developments' / 'Elite Dangerous'
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

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Return the string represented by the key, or the default if it does not exist.

        :param key: the key to access
        :param default: the default to return when the key does not exist, defaults to None
        :raises ValueError: when the key is not a string type
        :return: the requested data, or the default
        """
        res = self.__raw_get(key)
        if res is None:
            return default

        if not isinstance(res, str):
            raise ValueError(f'unexpected data returned from __raw_get: {type(res)=} {res}')

        return res

    def get_list(self, key: str, default: Optional[list] = None) -> Optional[list]:
        """
        Return the list found at the given key, or the default if none exists.

        :param key: The key to access
        :param default: Default to return when the key does not exist, defaults to None
        :raises ValueError: When the data at the given key is not a list
        :return: the requested data or the default
        """
        res = self.__raw_get(key)
        if res is None:
            return default

        elif not isinstance(res, list):
            raise ValueError(f'__raw_get returned unexpected type {type(res)=} {res!r}')

        return res

    def get_int(self, key: str, default: Optional[int] = 0) -> Optional[int]:
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
            return default

    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
        """
        Set sets the given key to the given value.

        :param key: The key to set the value to
        :param val: The value to set the key
        """
        self._settings[key] = val

    def delete(self, key: str) -> None:
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

    def __init__(self) -> None:
        # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html
        xdg_data_home = pathlib.Path(os.getenv('XDG_DATA_HOME', default='~/.local/share')).expanduser()
        self.app_dir = xdg_data_home / appname
        self.app_dir.mkdir(exist_ok=True, parents=True)

        self.plugin_dir = self.app_dir / 'plugins'
        self.plugin_dir.mkdir(exist_ok=True)

        self.respath = pathlib.Path(__file__).parent

        self.internal_plugin_dir = self.respath / 'plugins'
        self.default_journal_dir = None
        self.identifier = f'uk.org.marginal.{appname.lower()}'  # TODO: Unused?

        config_home = pathlib.Path(os.getenv('XDG_CONFIG_HOME', default='~/.config')).expanduser()

        self.filename = config_home / appname / f'{appname}.ini'
        self.filename.mkdir(exist_ok=True, parents=True)

        self.config: Optional[ConfigParser] = ConfigParser(comment_prefixes=('#',), interpolation=None)

        try:
            self.config.read(self.filename)
        except Exception as e:
            logger.debug(f'Error occurred while reading in file. Assuming that we are creating a new one: {e}')
            self.config.add_section(self.SECTION)

        if (outdir := self.get_str('outdir')) is None or not pathlib.Path(outdir).is_dir():
            self.set('outdir', str(self.home))

        # TODO: I dislike this, would rather use a sane config file format. But here we are.
        self.__unescape_table = str.maketrans({'\\n': '\n', '\\\\': '\\', '\\;': ';'})
        self.__escape_table = str.maketrans({'\n': '\\n', '\\': '\\\\', ';': '\\;'})

    def __raw_get(self, key: str) -> Optional[str]:
        if self.config is None:
            raise ValueError('Attempt to use a closed config')

        return self.config[self.SECTION].get(key)

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        data = self.__raw_get(key)
        if data is None:
            return default

        if '\n' in data:
            raise ValueError('asked for string, got list')

        return data.translate(self.__unescape_table)

    def get_list(self, key: str, default: Optional[list] = None) -> Optional[list]:
        data = self.__raw_get(key)

        if data is None:
            return default

        split = data.split('\n')
        if split[-1] != ';':
            raise ValueError('Encoded list does not have trailer sentinel')

        return [s.translate(self.__unescape_table) for s in split[:-1]]

    def get_int(self, key: str, default: Optional[int] = 0) -> Optional[int]:
        data = self.__raw_get(key)

        if data is None:
            return default

        try:
            return int(data)

        except ValueError as e:
            raise ValueError(f'requested {key=} as int cannot be converted to int') from e

    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        to_set: Optional[str] = None
        if isinstance(val, bool):
            to_set = str(int(val))

        elif isinstance(val, str):
            to_set = val.translate(self.__escape_table)

        elif isinstance(val, int):
            to_set = str(val)

        elif isinstance(val, list):
            to_set = '\n'.join(s.translate(self.__escape_table) for s in val + [';'])

        else:
            raise NotImplementedError(f'value of type {type(val)} is not supported')

        self.config.set(self.SECTION, key, to_set)

    def delete(self, key: str) -> None:
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


class Config():
    """Object that holds all configuration data."""

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

    if platform == 'darwin':  # noqa: C901 # It's gating *all* the functions

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

            self.default_journal_dir = join(
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

            elif isinstance(val, str):
                return str(val)

            elif isinstance(val, list):
                return list(val)  # make writeable

            else:
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

    elif platform == 'win32':

        def __init__(self):
            self.app_dir = join(known_folder_path(FOLDERID_LocalAppData), appname)
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
                self.default_journal_dir = join(journaldir, 'Frontier Developments', 'Elite Dangerous')

            else:
                self.default_journal_dir = None

            self.identifier = applongname
            self.hkey = HKEY()
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

            if not self.get('outdir') or not isdir(self.get('outdir')):
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

            elif key_type.value == REG_MULTI_SZ:
                return list(ctypes.wstring_at(buf, len(buf)-2).split('\x00'))

            else:
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

            else:
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

    elif platform == 'linux':
        SECTION = 'config'

        def __init__(self):
            self.__in_shutdown = False  # Is the application currently shutting down ?
            self.__auth_force_localserver = False  # Should we use localhost for auth callback ?

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
            self.identifier = f'uk.org.marginal.{appname.lower()}'

            self.filename = join(getenv('XDG_CONFIG_HOME', expanduser('~/.config')), appname, f'{appname}.ini')
            if not isdir(dirname(self.filename)):
                makedirs(dirname(self.filename))

            self.config = RawConfigParser(comment_prefixes=('#',))
            try:
                with codecs.open(self.filename, 'r') as h:
                    self.config.read_file(h)

            except Exception as e:
                logger.debug('Reading config failed, assuming we\'re making a new one...', exc_info=e)
                self.config.add_section(self.SECTION)

            if not self.get('outdir') or not isdir(self.get('outdir')):
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
                else:
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
                self.config.set(self.SECTION, key, val and '1' or '0')

            elif isinstance(val, str) or isinstance(val, numbers.Integral):
                self.config.set(self.SECTION, key, self._escape(val))

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


# singleton
config = Config()
