"""
linux.py - Linux config implementation.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import os
import pathlib
import sys
from configparser import ConfigParser
from config import AbstractConfig, appname, logger

assert sys.platform == 'linux'


class LinuxConfig(AbstractConfig):
    """Linux implementation of AbstractConfig."""

    SECTION = 'config'
    # TODO: I dislike this, would rather use a sane config file format. But here we are.
    __unescape_lut = {'\\': '\\', 'n': '\n', ';': ';', 'r': '\r', '#': '#'}
    __escape_lut = {'\\': '\\', '\n': 'n', ';': ';', '\r': 'r'}

    def __init__(self, filename: str | None = None) -> None:
        super().__init__()
        # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html
        xdg_data_home = pathlib.Path(os.getenv('XDG_DATA_HOME', default='~/.local/share')).expanduser()
        self.app_dir_path = xdg_data_home / appname
        self.app_dir_path.mkdir(exist_ok=True, parents=True)

        self.default_plugin_dir_path = self.app_dir_path / 'plugins'
        self.respath_path = pathlib.Path(__file__).parent.parent

        self.internal_plugin_dir_path = self.respath_path / 'plugins'
        self.internal_theme_dir_path = self.respath_path / 'themes'
        self.default_journal_dir_path = None  # type: ignore
        self.identifier = f'uk.org.marginal.{appname.lower()}'  # TODO: Unused?

        config_home = pathlib.Path(os.getenv('XDG_CONFIG_HOME', default='~/.config')).expanduser()

        self.filename = config_home / appname / f'{appname}.ini'
        if filename is not None:
            self.filename = pathlib.Path(filename)

        self.filename.parent.mkdir(exist_ok=True, parents=True)

        self.config: ConfigParser | None = ConfigParser(comment_prefixes=('#',), interpolation=None)
        self.config.read(self.filename)  # read() ignores files that dont exist

        # Ensure that our section exists. This is here because configparser will happily create files for us, but it
        # does not magically create sections
        try:
            self.config[self.SECTION].get("this_does_not_exist", fallback=None)
        except KeyError:
            logger.info("Config section not found. Backing up existing file (if any) and readding a section header")
            if self.filename.exists():
                (self.filename.parent / f'{appname}.ini.backup').write_bytes(self.filename.read_bytes())

            self.config.add_section(self.SECTION)

        if (plugdir_str := self.get_str('plugin_dir')) is None or not pathlib.Path(plugdir_str).is_dir():
            self.set("plugin_dir", str(self.default_plugin_dir_path))
            plugdir_str = self.default_plugin_dir
        self.plugin_dir_path = pathlib.Path(plugdir_str)
        self.plugin_dir_path.mkdir(exist_ok=True)

        if (outdir := self.get_str('outdir')) is None or not pathlib.Path(outdir).is_dir():
            self.set('outdir', self.home)

    def __escape(self, s: str) -> str:
        """
        Escape a string using self.__escape_lut.

        This does NOT support multi-character escapes.

        :param s: str - String to be escaped.
        :return: str - The escaped string.
        """
        out = ""
        for c in s:
            if c not in self.__escape_lut:
                out += c
                continue

            out += '\\' + self.__escape_lut[c]

        return out

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

            # We have a backslash, check what its escaping
            if i == len(s)-1:
                raise ValueError('Escaped string has unescaped trailer')

            unescaped = self.__unescape_lut.get(s[i+1])
            if unescaped is None:
                raise ValueError(f'Unknown escape: \\ {s[i+1]}')

            out.append(unescaped)
            i += 2

        return "".join(out)

    def __raw_get(self, key: str) -> str | None:
        """
        Get a raw data value from the config file.

        :param key: str - The key data is being requested for.
        :return: str - The raw data, if found.
        """
        if self.config is None:
            raise ValueError('Attempt to use a closed config')

        return self.config[self.SECTION].get(key)

    def get_str(self, key: str, *, default: str | None = None) -> str:
        """
        Return the string referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_str`.
        """
        data = self.__raw_get(key)
        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if '\n' in data:
            raise ValueError('asked for string, got list')

        return self.__unescape(data)

    def get_list(self, key: str, *, default: list | None = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        data = self.__raw_get(key)

        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        split = data.split('\n')
        if split[-1] != ';':
            raise ValueError('Encoded list does not have trailer sentinel')

        return list(map(self.__unescape, split[:-1]))

    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int referred to by key if it exists in the config.

        Implements :meth:`AbstractConfig.get_int`.
        """
        data = self.__raw_get(key)

        if data is None:
            return default

        try:
            return int(data)

        except ValueError as e:
            raise ValueError(f'requested {key=} as int cannot be converted to int') from e

    def get_bool(self, key: str, *, default: bool | None = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_bool`.
        """
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        data = self.__raw_get(key)
        if data is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        return bool(int(data))

    def set(self, key: str, val: int | str | list[str]) -> None:
        """
        Set the given key's data to the given value.

        Implements :meth:`AbstractConfig.set`.
        """
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        to_set: str | None = None
        if isinstance(val, bool):
            to_set = str(int(val))

        elif isinstance(val, str):
            to_set = self.__escape(val)

        elif isinstance(val, int):
            to_set = str(val)

        elif isinstance(val, list):
            to_set = '\n'.join([self.__escape(s) for s in val] + [';'])

        else:
            raise ValueError(f'Unexpected type for value {type(val)=}')

        self.config.set(self.SECTION, key, to_set)
        self.save()

    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        Implements :meth:`AbstractConfig.delete`.
        """
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        self.config.remove_option(self.SECTION, key)
        self.save()

    def save(self) -> None:
        """
        Save the current configuration.

        Implements :meth:`AbstractConfig.save`.
        """
        if self.config is None:
            raise ValueError('attempt to use a closed config')

        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def close(self) -> None:
        """
        Close this config and release any associated resources.

        Implements :meth:`AbstractConfig.close`.
        """
        self.save()
        self.config = None
