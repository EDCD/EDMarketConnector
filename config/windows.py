"""Windows config implementation."""

# spell-checker: words folderid deps hkey edcd
import ctypes
import functools
import pathlib
import sys
import uuid
import winreg
from ctypes.wintypes import DWORD, HANDLE
from typing import List, Optional, Union

from config import AbstractConfig, applongname, appname, logger, update_interval

assert sys.platform == 'win32'

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


class WinConfig(AbstractConfig):
    """Implementation of AbstractConfig for Windows."""

    def __init__(self, do_winsparkle=True) -> None:
        self.app_dir_path = pathlib.Path(str(known_folder_path(FOLDERID_LocalAppData))) / appname
        self.app_dir_path.mkdir(exist_ok=True)

        self.plugin_dir_path = self.app_dir_path / 'plugins'
        self.plugin_dir_path.mkdir(exist_ok=True)

        if getattr(sys, 'frozen', False):
            self.respath_path = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir_path = self.respath_path / 'plugins'

        else:
            self.respath_path = pathlib.Path(__file__).parent.parent
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
        """Ensure the necessary Registry keys for WinSparkle are present."""
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
            logger.exception('could not open WinSparkle handle')
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
        """Access the Registry for the raw entry."""
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
        Return the string referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_str`.
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, str):
            raise ValueError(f'Data from registry is not a string: {type(res)=} {res=}')

        return res

    def get_list(self, key: str, *, default: list = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        elif not isinstance(res, list):
            raise ValueError(f'Data from registry is not a list: {type(res)=} {res}')

        return res

    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int referred to by key if it exists in the config.

        Implements :meth:`AbstractConfig.get_int`.
        """
        res = self.__get_regentry(key)
        if res is None:
            return default

        if not isinstance(res, int):
            raise ValueError(f'Data from registry is not an int: {type(res)=} {res}')

        return res

    def get_bool(self, key: str, *, default: bool = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_bool`.
        """
        res = self.get_int(key, default=default)  # type: ignore
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        return bool(res)

    def set(self, key: str, val: Union[int, str, List[str], bool]) -> None:
        """
        Set the given key's data to the given value.

        Implements :meth:`AbstractConfig.set`.
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
        """
        Delete the given key from the config.

        'key' is relative to the base Registry path we use.

        Implements :meth:`AbstractConfig.delete`.
        """
        try:
            winreg.DeleteValue(self.__reg_handle, key)
        except OSError:
            if suppress:
                return

            raise

    def save(self) -> None:
        """
        Save the configuration.

        Not required for WinConfig as Registry keys are flushed on write.
        """
        pass

    def close(self):
        """
        Close this config and release any associated resources.

        Implements :meth:`AbstractConfig.close`.
        """
        self.__reg_handle.Close()
