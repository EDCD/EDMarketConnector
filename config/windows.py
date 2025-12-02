"""
windows.py - Windows config implementation.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import pathlib
import sys
import uuid
import winreg
import datetime
import tomli_w
from config import config_logger
from win32comext.shell import shell
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Config

if sys.platform != "win32":
    raise OSError("This file is for Windows only.")

REG_RESERVED_ALWAYS_ZERO = 0


def known_folder_path(guid: uuid.UUID) -> str | None:
    """Look up a Windows GUID to actual folder path name."""
    return shell.SHGetKnownFolderPath(guid, 0, 0)


class WinConfigMinimal:
    """Minimal Windows config for exporting pre-6.0 config values to TOML."""

    REGISTRY_SUBKEY = r"Software\Marginal\EDMarketConnector"

    def __init__(self) -> None:
        # Try to open the key with read access
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REGISTRY_SUBKEY,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ):
            pass  # If this fails, key doesn't exist, nothing to convert
        # Open or create the registry key
        self.__reg_handle = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            self.REGISTRY_SUBKEY,
            access=winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY,
        )

    def _convert_reg_value_for_toml(self, data, data_type) -> Any:
        """Convert Windows registry values into TOML-native types."""
        if data_type == winreg.REG_SZ:
            return str(data)
        if data_type == winreg.REG_EXPAND_SZ:
            try:
                return str(winreg.ExpandEnvironmentStrings(data))
            except Exception:
                return str(data)
        if data_type in (winreg.REG_DWORD, winreg.REG_QWORD):
            return int(data)
        if data_type == winreg.REG_MULTI_SZ:
            return list(data)
        # Fallback: force to string
        return str(data)

    def write_to_toml(self, toml_path: str) -> None:
        """Export all registry values under REGISTRY_SUBKEY to TOML."""
        config_logger.debug("Generating New Config File")
        key = self.__reg_handle
        _, num_values, _ = winreg.QueryInfoKey(key)

        config_data: dict[str, Any] = {
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": "windows_registry",
            "settings": {},
        }

        for i in range(num_values):
            name, data, data_type = winreg.EnumValue(key, i)
            config_data["settings"][name] = self._convert_reg_value_for_toml(
                data, data_type
            )

        path_obj = pathlib.Path(toml_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        config_logger.debug("Writing Config File")
        with path_obj.open("wb") as f:
            tomli_w.dump(config_data, f)

    def close(self):
        """Close registry handle."""
        self.__reg_handle.Close()


def win_helper(config: Config) -> Config:
    """Set Environment Specific Variables for Windows Config."""
    config_logger.debug("Windows environment detected. Setting platform-specific variables.")
    if getattr(sys, "frozen", False):
        config.respath_path = pathlib.Path(sys.executable).parent
        config.internal_plugin_dir_path = config.respath_path / "plugins"
    else:
        config.respath_path = pathlib.Path(__file__).parent.parent
        config.internal_plugin_dir_path = config.respath_path / "plugins"

    journal_dir_path = (
        pathlib.Path(known_folder_path(shell.FOLDERID_SavedGames))  # type: ignore
        / "Frontier Developments"
        / "Elite Dangerous"
    )
    config.default_journal_dir_path = journal_dir_path if journal_dir_path.is_dir() else None  # type: ignore

    if (outdir_str := config.get_str("outdir")) is None or not pathlib.Path(
        outdir_str
    ).is_dir():
        docs = known_folder_path(shell.FOLDERID_Documents)
        config.set("outdir", docs if docs is not None else config.home)
    return config
