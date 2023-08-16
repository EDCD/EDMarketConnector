"""
linux.py - Linux config implementation.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import os
import pathlib
import sys
from configparser import ConfigParser
from typing import Optional, Union, List
from config import AbstractConfig, appname, logger

assert sys.platform == 'linux'


class LinuxConfig(AbstractConfig):
    """Linux implementation of AbstractConfig."""

    SECTION = 'config'

    __unescape_lut = {'\\': '\\', 'n': '\n', ';': ';', 'r': '\r', '#': '#'}
    __escape_lut = {'\\': '\\', '\n': 'n', ';': ';', '\r': 'r'}

    def __init__(self, filename: Optional[str] = None) -> None:
        """
        Initialize LinuxConfig instance.

        :param filename: Optional file name to use for configuration storage.
        """
        super().__init__()

        # Initialize directory paths
        xdg_data_home = pathlib.Path(os.getenv('XDG_DATA_HOME', default='~/.local/share')).expanduser()
        self.app_dir_path = xdg_data_home / appname
        self.app_dir_path.mkdir(exist_ok=True, parents=True)

        self.plugin_dir_path = self.app_dir_path / 'plugins'
        self.plugin_dir_path.mkdir(exist_ok=True)
        self.respath_path = pathlib.Path(__file__).parent.parent
        self.internal_plugin_dir_path = self.respath_path / 'plugins'
        self.default_journal_dir_path = None  # type: ignore

        # Configure the filename
        config_home = pathlib.Path(os.getenv('XDG_CONFIG_HOME', default='~/.config')).expanduser()
        self.filename = pathlib.Path(filename) if filename is not None else config_home / appname / f'{appname}.ini'
        self.filename.parent.mkdir(exist_ok=True, parents=True)

        # Initialize the configuration
        self.config = ConfigParser(comment_prefixes=('#',), interpolation=None)
        self.config.read(self.filename)

        # Ensure the section exists
        try:
            self.config[self.SECTION].get("this_does_not_exist")
        except KeyError:
            logger.info("Config section not found. Backing up existing file (if any) and re-adding a section header")
            backup_filename = self.filename.parent / f'{appname}.ini.backup'
            backup_filename.write_bytes(self.filename.read_bytes())
            self.config.add_section(self.SECTION)

        # Set 'outdir' if not specified or invalid
        outdir = self.get_str('outdir')
        if outdir is None or not pathlib.Path(outdir).is_dir():
            self.set('outdir', self.home)

    def __escape(self, s: str) -> str:
        """
        Escape special characters in a string.

        :param s: The input string.
        :return: The escaped string.
        """
        escaped_chars = []

        for c in s:
            escaped_chars.append(self.__escape_lut.get(c, c))

        return ''.join(escaped_chars)

    def __unescape(self, s: str) -> str:
        """
        Unescape special characters in a string.

        :param s: The input string.
        :return: The unescaped string.
        """
        unescaped_chars = []
        i = 0
        while i < len(s):
            current_char = s[i]
            if current_char != '\\':
                unescaped_chars.append(current_char)
                i += 1
                continue

            if i == len(s) - 1:
                raise ValueError('Escaped string has unescaped trailer')

            unescaped = self.__unescape_lut.get(s[i + 1])
            if unescaped is None:
                raise ValueError(f'Unknown escape: \\{s[i + 1]}')

            unescaped_chars.append(unescaped)
            i += 2

        return "".join(unescaped_chars)

    def __raw_get(self, key: str) -> Optional[str]:
        """
        Get a raw data value from the config file.

        :param key: str - The key data is being requested for.
        :return: str - The raw data, if found.
        """
        if self.config is None:
            raise ValueError('Attempt to use a closed config')

        return self.config[self.SECTION].get(key)

    def get_str(self, key: str, *, default: Optional[str] = None) -> str:
        """
        Return the string referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_str`.
        """
        data = self.__raw_get(key)
        if data is None:
            return default or ""

        if '\n' in data:
            raise ValueError('Expected string, but got list')

        return self.__unescape(data)

    def get_list(self, key: str, *, default: Optional[list] = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        data = self.__raw_get(key)
        if data is None:
            return default or []

        split = data.split('\n')
        if split[-1] != ';':
            raise ValueError('Encoded list does not have trailer sentinel')

        return [self.__unescape(item) for item in split[:-1]]

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
            raise ValueError(f'Failed to convert {key=} to int') from e

    def get_bool(self, key: str, *, default: Optional[bool] = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_bool`.
        """
        if self.config is None:
            raise ValueError('Attempt to use a closed config')

        data = self.__raw_get(key)
        if data is None:
            return default or False

        return bool(int(data))

    def set(self, key: str, val: Union[int, str, List[str]]) -> None:
        """
        Set the given key's data to the given value.

        Implements :meth:`AbstractConfig.set`.
        """
        if self.config is None:
            raise ValueError('Attempt to use a closed config')
        if isinstance(val, bool):
            to_set = str(int(val))
        elif isinstance(val, str):
            to_set = self.__escape(val)
        elif isinstance(val, int):
            to_set = str(val)
        elif isinstance(val, list):
            to_set = '\n'.join([self.__escape(s) for s in val] + [';'])
        else:
            raise ValueError(f'Unexpected type for value {type(val).__name__}')

        self.config.set(self.SECTION, key, to_set)
        self.save()

    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        Implements :meth:`AbstractConfig.delete`.
        """
        if self.config is None:
            raise ValueError('Attempt to delete from a closed config')

        self.config.remove_option(self.SECTION, key)
        self.save()

    def save(self) -> None:
        """
        Save the current configuration.

        Implements :meth:`AbstractConfig.save`.
        """
        if self.config is None:
            raise ValueError('Attempt to save a closed config')

        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def close(self) -> None:
        """
        Close this config and release any associated resources.

        Implements :meth:`AbstractConfig.close`.
        """
        self.save()
        self.config = None
