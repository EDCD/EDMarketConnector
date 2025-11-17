"""
linux.py - Linux config implementation.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import os
import sys
from config import config_logger

if sys.platform != "linux":
    raise EnvironmentError("This file is for Linux only.")


import pathlib
from configparser import ConfigParser
import datetime
import tomli_w
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Config


class LinuxConfigMinimal:
    """Minimal Linux config for exporting pre-6.0 config values to TOML."""

    SECTION = "config"

    def __init__(self, filename: str | None = None) -> None:
        # Determine config path
        xdg_config_home = pathlib.Path(
            os.getenv("XDG_CONFIG_HOME", "~/.config")
        ).expanduser()
        self.filename = (
            pathlib.Path(filename)
            if filename
            else xdg_config_home / "EDMarketConnector" / "EDMarketConnector.ini"
        )
        if not pathlib.Path(filename).is_file():
            raise FileNotFoundError
        # Load INI
        self.config = ConfigParser(interpolation=None)
        self.config.read(self.filename)

    def _get_settings_dict(self) -> dict[str, Any]:
        """Return all keys/values from SECTION as a dict of strings."""
        return {
            key: self.config[self.SECTION][key] for key in self.config[self.SECTION]
        }

    def write_to_toml(self, toml_path: str) -> None:
        """Dump existing config to TOML file."""
        config_logger.debug("Generating New Config File")
        config_data: dict[str, Any] = {
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": "linux_ini",
            "section": self.SECTION,
            "settings": self._get_settings_dict(),
        }

        path_obj = pathlib.Path(toml_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        config_logger.debug("Writing Config File")
        with path_obj.open("wb") as f:
            tomli_w.dump(config_data, f)

    def close(self) -> None:
        """Release resources (stub)."""
        self.config = None


def linux_helper(config: Config) -> Config:
    """Set Environment Specific Variables for Linux Config."""
    config_logger.debug("Linux environment detected. Setting platform-specific variables.")
    config.respath_path = pathlib.Path(__file__).parent.parent
    config.internal_plugin_dir_path = config.respath_path / "plugins"
    config.default_journal_dir_path = None  # type: ignore
    if (outdir := config.get_str("outdir")) is None or not pathlib.Path(
        outdir
    ).is_dir():
        config.set("outdir", config.home)
    return config
