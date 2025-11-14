"""
__init__.py - Code dealing with the configuration of the program.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Windows uses the Registry to store values in a flat manner.
Linux uses a file, but for commonality it's still a flat data structure.
"""
from __future__ import annotations

__all__ = [
    # defined in the order they appear in the file
    'GITVERSION_FILE',
    'appname',
    'applongname',
    'appcmdname',
    'copyright',
    'update_interval',
    'debug_senders',
    'trace_on',
    'capi_pretend_down',
    'capi_debug_access_token',
    'logger',
    'git_shorthash_from_head',
    'appversion',
    'user_agent',
    'appversion_nobuild',
    'AbstractConfig',
    'config',
    'get_update_feed',
]

import abc
import contextlib
import logging
import os
import pathlib
import re
import subprocess
import sys
from abc import abstractmethod
from typing import Any, Callable, Type, TypeVar
import semantic_version
from constants import GITVERSION_FILE, applongname, appname

# Any of these may be imported by plugins
appcmdname = 'EDMC'
# appversion **MUST** follow Semantic Versioning rules:
# <https://semver.org/#semantic-versioning-specification-semver>
# Major.Minor.Patch(-prerelease)(+buildmetadata)
# NB: Do *not* import this, use the functions appversion() and appversion_nobuild()
_static_appversion = '6.0.0-alpha0'
_cached_version: semantic_version.Version | None = None
copyright = '© 2015-2019 Jonathan Harris, 2020-2025 EDCD'


update_interval = 8*60*60  # 8 Hours
# Providers marked to be in debug mode. Generally this is expected to switch to sending data to a log file
debug_senders: list[str] = []
# TRACE logging code that should actually be used.  Means not spamming it
# *all* if only interested in some things.
trace_on: list[str] = []

capi_pretend_down: bool = False
capi_debug_access_token: str | None = None
# This must be done here in order to avoid an import cycle with EDMCLogging.
# Other code should use EDMCLogging.get_main_logger
logger = logging.getLogger(appcmdname) if os.getenv("EDMC_NO_UI") else logging.getLogger(appname)


_T = TypeVar('_T')


def git_shorthash_from_head() -> str | None:
    """
    Determine short hash for current git HEAD.

    Includes `.DIRTY` if any changes have been made from HEAD.

    :return: str | None: None if we couldn't determine the short hash.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        shorthash = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.info(f"Couldn't run git command for short hash: {e!r}")
        return None

    if not re.fullmatch(r"[0-9a-f]{7,}", shorthash):
        logger.error(f"'{shorthash}' doesn't look like a valid git short hash, forcing to None")
        return None

    with contextlib.suppress(Exception):
        diff_result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            capture_output=True,
            check=True
        )
        if diff_result.stdout:
            shorthash += ".DIRTY"
        if diff_result.stderr:
            logger.warning(f"Data from git on stderr:\n{diff_result.stderr.decode()}")

    return shorthash


def appversion() -> semantic_version.Version:
    """
    Determine app version including git short hash if possible.

    :return: The augmented app version.
    """
    global _cached_version
    if _cached_version is not None:
        return _cached_version

    if getattr(sys, 'frozen', False):
        # Running frozen, so we should have a .gitversion file
        # Yes, .parent because if frozen we're inside library.zip
        with open(pathlib.Path(sys.path[0]).parent / GITVERSION_FILE, encoding='utf-8') as gitv:
            shorthash: str | None = gitv.read()

    else:
        # Running from source. Use git rev-parse --short HEAD
        # or fall back to .gitversion file if it exists.
        # This is also required for the Flatpak
        shorthash = git_shorthash_from_head()
        if shorthash is None:
            if pathlib.Path(sys.path[0] + "/" + GITVERSION_FILE).exists():
                with open(pathlib.Path(sys.path[0] + "/" + GITVERSION_FILE), encoding='utf-8') as gitv:
                    shorthash = gitv.read()
            else:
                shorthash = 'UNKNOWN'

    _cached_version = semantic_version.Version(f'{_static_appversion}+{shorthash}')
    return _cached_version


user_agent = f'EDCD-{appname}-{appversion()}'


def appversion_nobuild() -> semantic_version.Version:
    """
    Determine app version without *any* build meta data.

    This will not only strip any added git short hash, but also any trailing
    '+<string>' in _static_appversion.

    :return: App version without any build meta data.
    """
    return appversion().truncate('prerelease')


class AbstractConfig(abc.ABC):
    """
    Abstract root class of all platform specific Config implementations.

    Commented lines are no longer supported or replaced.
    """

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

    app_dir_path: pathlib.Path
    plugin_dir_path: pathlib.Path
    default_plugin_dir_path: pathlib.Path
    internal_plugin_dir_path: pathlib.Path
    respath_path: pathlib.Path
    home_path: pathlib.Path
    default_journal_dir_path: pathlib.Path
    identifier: str

    __in_shutdown = False  # Is the application currently shutting down ?
    __auth_force_localserver = False  # Should we use localhost for auth callback ?
    __auth_force_edmc_protocol = False  # Should we force edmc:// protocol ?
    __eddn_url = None  # Non-default EDDN URL
    __eddn_tracking_ui = False  # Show EDDN tracking UI ?
    __skip_timecheck = False  # Skip checking event timestamps?

    def __init__(self) -> None:
        self.home_path = pathlib.Path.home()

    def set_shutdown(self):
        """Set flag denoting we're in the shutdown sequence."""
        self.__in_shutdown = True

    @property
    def shutting_down(self) -> bool:
        """
        Determine if we're in the shutdown sequence.

        :return: bool - True if in shutdown sequence.
        """
        return self.__in_shutdown

    def set_auth_force_localserver(self):
        """Set flag to force use of localhost web server for Frontier Auth callback."""
        self.__auth_force_localserver = True

    @property
    def auth_force_localserver(self) -> bool:
        """
        Determine if use of localhost is forced for Frontier Auth callback.

        :return: bool - True if we should use localhost web server.
        """
        return self.__auth_force_localserver

    def set_auth_force_edmc_protocol(self):
        """Set flag to force use of localhost web server for Frontier Auth callback."""
        self.__auth_force_edmc_protocol = True

    @property
    def auth_force_edmc_protocol(self) -> bool:
        """
        Determine if use of localhost is forced for Frontier Auth callback.

        :return: bool - True if we should use localhost web server.
        """
        return self.__auth_force_edmc_protocol

    def set_eddn_url(self, eddn_url: str):
        """Set the specified eddn URL."""
        self.__eddn_url = eddn_url

    @property
    def eddn_url(self) -> str | None:
        """
        Provide the custom EDDN URL.

        :return: str - Custom EDDN URL to use.
        """
        return self.__eddn_url

    def set_eddn_tracking_ui(self):
        """Activate EDDN tracking UI."""
        self.__eddn_tracking_ui = True

    @property
    def eddn_tracking_ui(self) -> bool:
        """
        Determine if the EDDN tracking UI be shown.

        :return: bool - Should tracking UI be active?
        """
        return self.__eddn_tracking_ui

    def set_skip_timecheck(self):
        """Set the Event Timecheck bool."""
        self.__skip_timecheck = True

    @property
    def skip_timecheck(self) -> bool:
        """
        Determine if the Event Timecheck bool is enabled.

        :return: bool - Should EDMC check event timechecks?
        """
        return self.__skip_timecheck

    @property
    def app_dir(self) -> str:
        """Return a string version of app_dir."""
        return str(self.app_dir_path)

    @property
    def plugin_dir(self) -> str:
        """Return a string version of plugin_dir."""
        return str(self.plugin_dir_path)

    @property
    def default_plugin_dir(self) -> str:
        """Return a string version of plugin_dir."""
        return str(self.default_plugin_dir_path)

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
        func: Callable[..., _T], exceptions: Type[BaseException] | list[Type[BaseException]] = Exception,
        *args: Any, **kwargs: Any
    ) -> _T | None:
        if exceptions is None:
            exceptions = [Exception]

        if not isinstance(exceptions, list):
            exceptions = [exceptions]

        with contextlib.suppress(*exceptions):
            return func(*args, **kwargs)

        return None

    @abstractmethod
    def get_list(self, key: str, *, default: list | None = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        raise NotImplementedError

    @abstractmethod
    def get_str(self, key: str, *, default: str | None = None) -> str:
        """
        Return the string referred to by the given key if it exists, or the default.

        :param key: The key data is being requested for.
        :param default: Default to return if the key does not exist, defaults to None.
        :raises ValueError: If an internal error occurs getting or converting a value.
        :raises OSError: On Windows, if a Registry error occurs.
        :return: The requested data or the default.
        """
        raise NotImplementedError

    @abstractmethod
    def get_bool(self, key: str, *, default: bool | None = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        :param key: The key data is being requested for.
        :param default: Default to return if the key does not exist, defaults to None
        :raises ValueError: If an internal error occurs getting or converting a value
        :raises OSError: On Windows, if a Registry error occurs.
        :return: The requested data or the default
        """
        raise NotImplementedError

    @abstractmethod
    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int referred to by key if it exists in the config.

        For legacy reasons, the default is 0 and not None.

        :param key: The key data is being requested for.
        :param default: Default to return if the key does not exist, defaults to 0.
        :raises ValueError: If the internal representation of this key cannot be converted to an int.
        :raises OSError: On Windows, if a Registry error occurs.
        :return: The requested data or the default.
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, val: int | str | list[str] | bool) -> None:
        """
        Set the given key's data to the given value.

        :param key: The key to set the value on.
        :param val: The value to set the key's data to.
        :raises ValueError: On an invalid type.
        :raises OSError: On Windows, if a Registry error occurs.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        :param key: The key to delete.
        :param suppress: bool - Whether to suppress any errors.  Useful in case
          code to migrate settings is blindly removing an old key.
        :raises OSError: On Windows, if a registry error occurs.
        """
        raise NotImplementedError

    @abstractmethod
    def save(self) -> None:
        """
        Save the current configuration.

        :raises OSError: On Windows, if a Registry error occurs.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close this config and release any associated resources."""
        raise NotImplementedError


def get_config(*args, **kwargs) -> AbstractConfig:
    """
    Get the appropriate config class for the current platform.

    :param args: Args to be passed through to implementation.
    :param kwargs: Args to be passed through to implementation.
    :return: Instance of the implementation.
    """
    if sys.platform == "win32":  # pragma: sys-platform-win32
        from .windows import WinConfig
        return WinConfig(*args, **kwargs)

    if sys.platform == "linux":  # pragma: sys-platform-linux
        from .linux import LinuxConfig
        return LinuxConfig(*args, **kwargs)

    raise ValueError(f'Unknown platform: {sys.platform=}')


config = get_config()
if sys.platform == "win32":
    config.write_registry_to_toml(f"{config.app_dir_path}/config.toml")  # type: ignore


# Wiki: https://github.com/EDCD/EDMarketConnector/wiki/Participating-in-Open-Betas-of-EDMC
def get_update_feed() -> str:
    """Select the proper update feed for the current update track."""
    if config.get_bool('beta_optin'):
        return 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector-beta.xml'
    return 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml'
