"""
Base plugin class.

This is distinct from plugin.py as plugin.py imports various bits of EDMC that are not needed for testing.
"""
from __future__ import annotations

import abc
import pathlib
from collections import defaultdict
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from EDMCLogging import LoggerMixin
    from plugin.manager import PluginManager

from plugin.plugin_info import PluginInfo


class BasePlugin(abc.ABC):
    """Base plugin class."""

    # TODO: a similar level of paranoia about defined methods where needed

    def __init__(self, logger: LoggerMixin, manager: PluginManager, path: pathlib.Path) -> None:
        self.log = logger
        self._manager = manager
        self.can_reload = True  # Set to false to prevent reload support
        self.path = path
        # TODO: self.loaded?

    @abc.abstractmethod
    def load(self) -> PluginInfo:
        """
        Load this plugin.

        :param plugin_path: the path at which this module was found.
        """
        raise NotImplementedError

    def unload(self) -> None:
        """Unload this plugin."""
        raise NotImplementedError

    def reload(self) -> None:
        """Reload this plugin."""
        raise NotImplementedError

    def _find_marked_funcs(self, marker) -> Dict[str, List[Callable]]:
        out: Dict[str, List[Callable]] = defaultdict(list)

        field_names = list(self.__class__.__dict__.keys()) + list(self.__dict__.keys())

        for field in (getattr(self, f) for f in field_names):
            callbacks: Optional[List[str]] = getattr(field, marker, None)
            if callbacks is None:
                continue

            for name in callbacks:
                out[name].append(field)

        return dict(out)

    def __str__(self) -> str:
        """Return BasePlugin represented as a string."""
        return f'Plugin at {self.path} on {self._manager} '

    def __repr__(self) -> str:
        return f'BasePlugin({self._manager!r}, {self.path!r})'
