"""
darwin.py - Darwin/macOS implementation of AbstractConfig.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import pathlib
import sys
from typing import Any, Dict, List, Union
from Foundation import (  # type: ignore
    NSApplicationSupportDirectory,
    NSBundle,
    NSDocumentDirectory,
    NSSearchPathForDirectoriesInDomains,
    NSUserDefaults,
    NSUserDomainMask,
)
from config import AbstractConfig, appname, logger

assert sys.platform == "darwin"


class MacConfig(AbstractConfig):
    """MacConfig is the implementation of AbstractConfig for Darwin based OSes."""

    def __init__(self) -> None:
        super().__init__()
        support_path = pathlib.Path(
            NSSearchPathForDirectoriesInDomains(
                NSApplicationSupportDirectory, NSUserDomainMask, True
            )[0]
        )

        self.app_dir_path = support_path / appname
        self.app_dir_path.mkdir(exist_ok=True)

        self.plugin_dir_path = self.app_dir_path / "plugins"
        self.plugin_dir_path.mkdir(exist_ok=True)

        # Bundle IDs identify a singled app though out a system

        if getattr(sys, "frozen", False):
            exe_dir = pathlib.Path(sys.executable).parent
            self.internal_plugin_dir_path = exe_dir.parent / "Library" / "plugins"
            self.respath_path = exe_dir.parent / "Resources"
            self.identifier = NSBundle.mainBundle().bundleIdentifier()

        else:
            file_dir = pathlib.Path(__file__).parent.parent
            self.internal_plugin_dir_path = file_dir / "plugins"
            self.respath_path = file_dir

            self.identifier = f"uk.org.marginal.{appname.lower()}"
            NSBundle.mainBundle().infoDictionary()[
                "CFBundleIdentifier"
            ] = self.identifier

        self.default_journal_dir_path = (
            support_path / "Frontier Developments" / "Elite Dangerous"
        )
        self._defaults: Any = NSUserDefaults.standardUserDefaults()
        self._settings: Dict[str, Union[int, str, list]] = dict(
            self._defaults.persistentDomainForName_(self.identifier) or {}
        )  # make writeable

        if (out_dir := self.get_str("out_dir")) is None or not pathlib.Path(
            out_dir
        ).exists():
            self.set(
                "outdir",
                NSSearchPathForDirectoriesInDomains(
                    NSDocumentDirectory, NSUserDomainMask, True
                )[0],
            )

    def __raw_get(self, key: str) -> Union[None, list, str, int]:
        """
        Retrieve the raw data for the given key.

        :param str: str - The key data is being requested for.
        :return: The requested data.
        """
        res = self._settings.get(key)
        # On MacOS Catalina, with python.org python 3.9.2 any 'list'
        # has type __NSCFArray so a simple `isinstance(res, list)` is
        # False.  So, check it's not-None, and not the other types.
        #
        # If we can find where to import the definition of NSCFArray
        # then we could possibly test against that.
        if res is not None and not isinstance(res, str) and not isinstance(res, int):
            return list(res)

        return res

    def get_str(self, key: str, *, default: str = None) -> str:
        """
        Return the string referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_str`.
        """
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, str):
            raise ValueError(
                f"unexpected data returned from __raw_get: {type(res)=} {res}"
            )

        return res

    def get_list(self, key: str, *, default: list = None) -> list:
        """
        Return the list referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_list`.
        """
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, list):
            raise ValueError(f"__raw_get returned unexpected type {type(res)=} {res!r}")

        return res

    def get_int(self, key: str, *, default: int = 0) -> int:
        """
        Return the int referred to by key if it exists in the config.

        Implements :meth:`AbstractConfig.get_int`.
        """
        res = self.__raw_get(key)
        if res is None:
            return default

        if not isinstance(res, (str, int)):
            raise ValueError(f"__raw_get returned unexpected type {type(res)=} {res!r}")

        try:
            return int(res)

        except ValueError as e:
            logger.error(
                f"__raw_get returned {res!r} which cannot be parsed to an int: {e}"
            )
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

    def get_bool(self, key: str, *, default: bool = None) -> bool:
        """
        Return the bool referred to by the given key if it exists, or the default.

        Implements :meth:`AbstractConfig.get_bool`.
        """
        res = self.__raw_get(key)
        if res is None:
            return default  # type: ignore # Yes it could be None, but we're _assuming_ that people gave us a default

        if not isinstance(res, bool):
            raise ValueError(f"__raw_get returned unexpected type {type(res)=} {res!r}")

        return res

    def set(self, key: str, val: Union[int, str, List[str], bool]) -> None:
        """
        Set the given key's data to the given value.

        Implements :meth:`AbstractConfig.set`.
        """
        if self._settings is None:
            raise ValueError("attempt to use a closed _settings")

        if not isinstance(val, (bool, str, int, list)):
            raise ValueError(f"Unexpected type for value {type(val)=}")

        self._settings[key] = val

    def delete(self, key: str, *, suppress=False) -> None:
        """
        Delete the given key from the config.

        Implements :meth:`AbstractConfig.delete`.
        """
        try:
            del self._settings[key]

        except Exception:
            if suppress:
                pass

    def save(self) -> None:
        """
        Save the current configuration.

        Implements :meth:`AbstractConfig.save`.
        """
        self._defaults.setPersistentDomain_forName_(self._settings, self.identifier)
        self._defaults.synchronize()

    def close(self) -> None:
        """
        Close this config and release any associated resources.

        Implements :meth:`AbstractConfig.close`.
        """
        self.save()
        self._defaults = None
