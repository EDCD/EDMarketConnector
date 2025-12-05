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
    raise OSError("This file is for Linux only.")


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
        if not pathlib.Path(self.filename).is_file():
            raise FileNotFoundError
        self.config = ConfigParser(comment_prefixes=('#',), interpolation=None)
        try:
            read_files = self.config.read(self.filename)
            config_logger.debug("ConfigParser.read returned: %s", read_files)
        except Exception as e:
            config_logger.exception("Failed to read INI file %s: %s", self.filename, e)
            raise

    __unescape_lut = {'\\': '\\', 'n': '\n', ';': ';', 'r': '\r', '#': '#'}

    def __unescape(self, s: str) -> str:
        """
        Unescape a string.

        :param s: str - The string to unescape.
        :return: str - The unescaped string.
        """
        out: list[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if c != '\\':
                out.append(c)
                i += 1
                continue

            # We have a backslash, check what it's escaping
            if i == len(s) - 1:
                raise ValueError('Escaped string has unescaped trailer')

            unescaped = self.__unescape_lut.get(s[i + 1])
            if unescaped is None:
                raise ValueError(f'Unknown escape: \\{s[i+1]}')

            out.append(unescaped)
            i += 2

        return "".join(out)

    def _get_settings_dict(self) -> dict[str, Any]:  #noqa: CCR001
        """
        Return all keys/values from SECTION as a dict of strings or lists.

        This decodes the historical encoding where lists are encoded as
        newline-separated values separated by ';'
        """
        result: dict[str, Any] = {}
        for key in self.config[self.SECTION]:
            raw = self.config[self.SECTION][key]

            if raw is None:
                continue

            # If the value contains newline(s), check for trailing ';' sentinel
            if "\n" in raw:
                parts = raw.split("\n")
                if parts and parts[-1].strip() == ";":
                    items = [self.__unescape(p.strip()) for p in parts[:-1]]
                    result[key] = items
                    config_logger.debug("Decoded list for key '%s' with %d items", key, len(items))
                    continue
                else:
                    # Not a valid encoded list; fall back to unescaped string
                    try:
                        result[key] = self.__unescape(raw)
                    except Exception:
                        result[key] = raw
                    continue

            # Single value: unescape and return
            try:
                result[key] = self.__unescape(raw)
            except Exception:
                result[key] = raw

        return result

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
        config_logger.debug("Writing Config File to %s", path_obj)
        with path_obj.open("wb") as f:
            tomli_w.dump(config_data, f)

    def close(self) -> None:
        """Release resources (stub)."""
        del self.config


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
