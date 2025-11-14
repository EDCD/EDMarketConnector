"""
windows.py - Windows config implementation.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import functools
import pathlib
import sys
import uuid
import winreg
import datetime
import tomli_w
import base64
from typing import Literal, Any
from config import AbstractConfig, applongname, appname, logger
from win32comext.shell import shell

if sys.platform != 'win32':
    raise EnvironmentError("This file is for Windows only.")

REG_RESERVED_ALWAYS_ZERO = 0


def known_folder_path(guid: uuid.UUID) -> str | None:
    """Look up a Windows GUID to actual folder path name."""
    return shell.SHGetKnownFolderPath(guid, 0, 0)


class WinConfig(AbstractConfig):
    """Implementation of AbstractConfig for Windows."""

    def __init__(self) -> None:
        super().__init__()

        self.REGISTRY_SUBKEY = r'Software\Marginal\EDMarketConnector'
        create_key_defaults = functools.partial(
            winreg.CreateKeyEx,
            key=winreg.HKEY_CURRENT_USER,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )

        try:
            self.__reg_handle: winreg.HKEYType = create_key_defaults(sub_key=self.REGISTRY_SUBKEY)

        except OSError:
            logger.exception('Could not create required registry keys')
            raise

        if local_appdata := known_folder_path(shell.FOLDERID_LocalAppData):
            self.app_dir_path = pathlib.Path(local_appdata) / appname
        self.app_dir_path.mkdir(exist_ok=True)

        self.default_plugin_dir_path = self.app_dir_path / 'plugins'
        if (plugdir_str := self.get_str('plugin_dir')) is None or not pathlib.Path(plugdir_str).is_dir():
            self.set("plugin_dir", str(self.default_plugin_dir_path))
            plugdir_str = self.default_plugin_dir
        self.plugin_dir_path = pathlib.Path(plugdir_str)
        self.plugin_dir_path.mkdir(exist_ok=True)

        if getattr(sys, 'frozen', False):
            self.respath_path = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir_path = self.respath_path / 'plugins'
        else:
            self.respath_path = pathlib.Path(__file__).parent.parent
            self.internal_plugin_dir_path = self.respath_path / 'plugins'

        self.home_path = pathlib.Path.home()

        journal_dir_path = pathlib.Path(
            known_folder_path(shell.FOLDERID_SavedGames)) / 'Frontier Developments' / 'Elite Dangerous'  # type: ignore
        self.default_journal_dir_path = journal_dir_path if journal_dir_path.is_dir() else None  # type: ignore

        self.identifier = applongname
        if (outdir_str := self.get_str('outdir')) is None or not pathlib.Path(outdir_str).is_dir():
            docs = known_folder_path(shell.FOLDERID_Documents)
            self.set("outdir", docs if docs is not None else self.home)

    def _convert_reg_value_for_toml(self, data, data_type):
        """Convert Windows registry values into TOML-native types for 6.0's global config."""
        # Plain string
        if data_type == winreg.REG_SZ:
            return str(data)

        # Expandable string: keep as string
        if data_type == winreg.REG_EXPAND_SZ:
            try:
                expanded = winreg.ExpandEnvironmentStrings(data)
            except Exception:
                expanded = data
            return str(expanded)

        # DWORD or QWORD: store as integer
        if data_type in (winreg.REG_DWORD, winreg.REG_QWORD):
            return int(data)

        # Multi-string: store as list
        if data_type == winreg.REG_MULTI_SZ:
            return list(data)

        # Binary: store as base64 string
        if data_type == winreg.REG_BINARY:
            return base64.b64encode(data).decode("ascii")

        # Else, force to string
        return str(data)

    def write_registry_to_toml(self, toml_path: str) -> None:
        """
        Export all registry values under self.REGISTRY_SUBKEY into a global TOML config.

        Values are normalized into TOML-native types (str, int, list, base64).
        Booleans are left as ints (0/1) and should be interpreted adaptively by get_bool.
        """
        key = self.__reg_handle

        try:
            _, num_values, _ = winreg.QueryInfoKey(key)

            # Write config, including writing where and when we got this from.
            config_data: dict[str, Any] = {
                "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "windows_registry",
                "subkey": self.REGISTRY_SUBKEY,
                "settings": {}
            }

            settings = config_data["settings"]

            for i in range(num_values):
                name, data, data_type = winreg.EnumValue(key, i)
                settings[name] = self._convert_reg_value_for_toml(data, data_type)

            # Write TOML to file
            path_obj = pathlib.Path(toml_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            with path_obj.open("wb") as f:
                tomli_w.dump(config_data, f)

            logger.info(f"Registry exported to TOML: {toml_path}")

        except OSError:
            logger.exception(f"Could not export registry key {self.REGISTRY_SUBKEY}")
            raise

    def __get_regentry(self, key: str) -> None | list | str | int:
        """Access the Registry for the raw entry."""
        try:
            value, _type = winreg.QueryValueEx(self.__reg_handle, key)
        except FileNotFoundError:
            # Key doesn't exist
            return None

        # For programmers who want to actually know what is going on
        if _type == winreg.REG_SZ:
            return str(value)

        if _type == winreg.REG_DWORD:
            return int(value)

        if _type == winreg.REG_MULTI_SZ:
            return list(value)

        logger.warning(f'Registry key {key=} returned unknown type {_type=} {value=}')
        return None

    def get_str(self, key: str, *, default: str | None = None) -> str:
        """
        Return the string referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_str`.
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, str):
            raise ValueError(f'Data from registry is not a string: {type(res)=} {res=}')

        return res

    def get_list(self, key: str, *, default: list | None = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        res = self.__get_regentry(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, list):
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

    def get_bool(self, key: str, *, default: bool | None = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_bool`.
        """
        res = self.get_int(key, default=default)  # type: ignore
        if res is None:
            return default  # Yes it could be None, but we're _assuming_ that people gave us a default

        return bool(res)

    def set(self, key: str, val: int | str | list[str] | bool) -> None:
        """
        Set the given key's data to the given value.

        Implements :meth:`AbstractConfig.set`.
        """
        # These are the types that winreg.REG_* below resolve to.
        reg_type: Literal[1] | Literal[4] | Literal[7]
        if isinstance(val, str):
            reg_type = winreg.REG_SZ

        elif isinstance(val, int):
            reg_type = winreg.REG_DWORD

        elif isinstance(val, list):
            reg_type = winreg.REG_MULTI_SZ

        elif isinstance(val, bool):
            reg_type = winreg.REG_DWORD
            val = int(val)

        else:
            raise ValueError(f'Unexpected type for value {type(val)=}')

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
