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
    "GITVERSION_FILE",
    "appname",
    "applongname",
    "appcmdname",
    "copyright",
    "update_interval",
    "debug_senders",
    "trace_on",
    "capi_pretend_down",
    "capi_debug_access_token",
    "logger",
    "git_shorthash_from_head",
    "appversion",
    "user_agent",
    "appversion_nobuild",
    "Config",
    "config",
    "get_update_feed",
    "config_logger",
]

import contextlib
import logging
import os
import pathlib
import re
import subprocess
import sys
import tomllib
import tomli_w
from time import gmtime
from typing import Any, Callable, Type, TypeVar
import semantic_version
from constants import GITVERSION_FILE, applongname, appname

# Any of these may be imported by plugins
appcmdname = "EDMC"
# appversion **MUST** follow Semantic Versioning rules:
# <https://semver.org/#semantic-versioning-specification-semver>
# Major.Minor.Patch(-prerelease)(+buildmetadata)
# NB: Do *not* import this, use the functions appversion() and appversion_nobuild()
_static_appversion = "6.0.0-alpha0"
_cached_version: semantic_version.Version | None = None
copyright = "© 2015-2019 Jonathan Harris, 2020-2025 EDCD"


update_interval = 8 * 60 * 60  # 8 Hours
# Providers marked to be in debug mode. Generally this is expected to switch to sending data to a log file
debug_senders: list[str] = []
# TRACE logging code that should actually be used.  Means not spamming it
# *all* if only interested in some things.
trace_on: list[str] = []

capi_pretend_down: bool = False
capi_debug_access_token: str | None = None
# This must be done here in order to avoid an import cycle with EDMCLogging.
# Other code should use EDMCLogging.get_main_logger
logger = (
    logging.getLogger(appcmdname)
    if os.getenv("EDMC_NO_UI")
    else logging.getLogger(appname)
)


_T = TypeVar("_T")


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
        logger.error(
            f"'{shorthash}' doesn't look like a valid git short hash, forcing to None"
        )
        return None

    with contextlib.suppress(Exception):
        diff_result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"], capture_output=True, check=True
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

    if getattr(sys, "frozen", False):
        # Running frozen, so we should have a .gitversion file
        # Yes, .parent because if frozen we're inside library.zip
        with open(
            pathlib.Path(sys.path[0]).parent / GITVERSION_FILE, encoding="utf-8"
        ) as gitv:
            shorthash: str | None = gitv.read()

    else:
        # Running from source. Use git rev-parse --short HEAD
        # or fall back to .gitversion file if it exists.
        # This is also required for the Flatpak
        shorthash = git_shorthash_from_head()
        if shorthash is None:
            if pathlib.Path(sys.path[0] + "/" + GITVERSION_FILE).exists():
                with open(
                    pathlib.Path(sys.path[0] + "/" + GITVERSION_FILE), encoding="utf-8"
                ) as gitv:
                    shorthash = gitv.read()
            else:
                shorthash = "UNKNOWN"

    _cached_version = semantic_version.Version(f"{_static_appversion}+{shorthash}")
    return _cached_version


user_agent = f"EDCD-{appname}-{appversion()}"


def appversion_nobuild() -> semantic_version.Version:
    """
    Determine app version without *any* build meta data.

    This will not only strip any added git short hash, but also any trailing
    '+<string>' in _static_appversion.

    :return: App version without any build meta data.
    """
    return appversion().truncate("prerelease")


class Config:
    """
    Platform-unified Config class for 6.0+.

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

    def __init__(self, app_path) -> None:
        self.home_path = pathlib.Path.home()
        # Set Needed Platform Var for app_dir_path
        self.app_dir_path = app_path

        self.toml_path: pathlib.Path = self.app_dir_path / "config.toml"
        self.generated: str | None = None
        self.source: str | None = None
        self.settings: dict[str, Any] = {}
        self._load()
        self.default_plugin_dir_path = self.app_dir_path / "plugins"
        plugdir_str = self.get_str("plugin_dir")
        if not self.get_str("plugin_dir"):
            plugdir_str = str(self.default_plugin_dir)
            self.plugin_dir_path = self.default_plugin_dir_path
            self.set("plugin_dir", plugdir_str)
        if plugdir_str is None or not pathlib.Path(plugdir_str).is_dir():
            self.set("plugin_dir", str(self.default_plugin_dir_path))
            plugdir_str = self.default_plugin_dir
        self.plugin_dir_path = pathlib.Path(plugdir_str)
        self.plugin_dir_path.mkdir(exist_ok=True)

        # Call the rest of the platform var helpers
        self._init_platform()

    def _init_platform(self):
        if sys.platform == "win32":
            from .windows import win_helper

            win_helper(self)
        elif sys.platform == "linux":
            from .linux import linux_helper

            linux_helper(self)
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")

    def set_shutdown(self):
        """Set flag denoting we're in the shutdown sequence."""
        self.__in_shutdown = True

    def _load(self):
        """Load TOML from disk and store fields. Create file if missing."""
        if not self.toml_path.exists():
            # Ensure parent directories exist
            self.toml_path.parent.mkdir(parents=True, exist_ok=True)

            # Replace None with TOML-serializable defaults
            default_data = {
                "generated": "",  # empty string instead of None
                "source": "",  # empty string instead of None
                "settings": {}  # empty table
            }
            with self.toml_path.open("wb") as f:
                tomli_w.dump(default_data, f)

        # Load the TOML file
        with self.toml_path.open("rb") as f:
            data = tomllib.load(f)

        # Capture metadata, fallback to empty string if missing
        self.generated = data.get("generated", "")
        self.source = data.get("source", "")

        # Settings dict created by write_registry_to_toml()
        self.settings = dict(data.get("settings", {}))

    def get(self, key: str, default=None):
        """Return raw stored value."""
        return self.settings.get(key, default)

    def get_str(self, key: str, default="") -> str:
        """Return string value."""
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_int(self, key: str, default=0) -> int:
        """Adaptive int (handles booleans stored as ints)."""
        val = self.get(key)
        if isinstance(val, int):
            return val
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default=False) -> bool:
        """
        Adaptive boolean reader.

          - Accepts ints 0/1
          - Accepts strings "true"/"false"/"1"/"0"
          - Accepts real booleans
        """
        val = self.get(key)

        if isinstance(val, bool):
            return val

        if isinstance(val, int):
            return val != 0

        if isinstance(val, str):
            v = val.strip().lower()
            if v in ("1", "true", "yes", "on"):
                return True
            if v in ("0", "false", "no", "off"):
                return False

        return default

    def get_list(self, key: str, default=None):
        """Return the list referred to by the given key if it exists, or the default."""
        val = self.get(key)
        return (
            val if isinstance(val, list) else (default if default is not None else [])
        )

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
        func: Callable[..., _T],
        exceptions: Type[BaseException] | list[Type[BaseException]] = Exception,
        *args: Any,
        **kwargs: Any,
    ) -> _T | None:
        if exceptions is None:
            exceptions = [Exception]

        if not isinstance(exceptions, list):
            exceptions = [exceptions]

        with contextlib.suppress(*exceptions):
            return func(*args, **kwargs)

        return None

    def delete(self, key: str, *, suppress=False) -> None:
        """Delete the given key from the config."""
        try:
            self.settings.pop(key, None)
        except (KeyError, IndexError):
            if suppress:
                return
            raise
        self.save()

    def set(self, key: str, value: Any):
        """Modify a setting and save to disk."""
        self.settings[key] = value
        self.save()

    def save(self):
        """Write updated config back to TOML."""
        data = {
            "generated": self.generated,
            "source": self.source,
            "settings": self.settings,
        }

        with self.toml_path.open("wb") as f:
            tomli_w.dump(data, f)

    def close(self) -> None:
        """Save config changes before closing."""
        self.save()


def get_appdirpath():
    """Grab the Application Directory early."""
    app_dir_path = None
    if sys.platform == "win32":
        base = pathlib.Path(os.getenv("LOCALAPPDATA"))  # type: ignore
        app_dir_path = base / appname
    if sys.platform == "linux":
        xdg_data_home = pathlib.Path(
            os.getenv("XDG_DATA_HOME", default="~/.local/share")
        ).expanduser()
        app_dir_path = xdg_data_home / appname
    if app_dir_path is None:
        raise ValueError
    return app_dir_path


def get_config(*args, **kwargs) -> Config:
    """
    Get the appropriate config class for the current platform.

    :param args: Args to be passed through to implementation.
    :param kwargs: Args to be passed through to implementation.
    :return: Instance of the implementation.
    """
    app_dir_path = get_appdirpath()
    config = None
    if pathlib.Path.exists(app_dir_path / "config.toml"):
        return Config(app_path=app_dir_path)

    if sys.platform == "win32":  # pragma: sys-platform-win32
        from .windows import WinConfigMinimal
        try:
            config = WinConfigMinimal()
        except FileNotFoundError:
            return Config(app_path=app_dir_path)  # Nothing to Convert

    if sys.platform == "linux":  # pragma: sys-platform-linux
        from .linux import LinuxConfigMinimal
        try:
            config = LinuxConfigMinimal()
        except (FileNotFoundError, TypeError):
            return Config(app_path=app_dir_path)  # Nothing to Convert

    if config:
        config.write_to_toml(f"{app_dir_path}/config.toml")  # type: ignore
        return Config(app_path=app_dir_path)

    raise ValueError(f"Unknown platform: {sys.platform=}")


# Set internal Config logger, because config is set up before main logger.
config_logger = logging.getLogger("pre_config")
config_logger.setLevel(logging.DEBUG)  # Or INFO

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
formatter.converter = gmtime  # Optional: match your main logger's UTC timestamps
ch.setFormatter(formatter)
config_logger.addHandler(ch)


config = get_config()


# Wiki: https://github.com/EDCD/EDMarketConnector/wiki/Participating-in-Open-Betas-of-EDMC
def get_update_feed() -> str:
    """Select the proper update feed for the current update track."""
    if config.get_bool("beta_optin"):
        return "https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector-beta.xml"
    return "https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml"
