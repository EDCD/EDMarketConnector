"""Base plugin class."""
from __future__ import annotations

import abc
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from EDMCLogging import LoggerMixin

from plugin.plugin_info import PluginInfo


class Plugin(abc.ABC):
    """Base plugin class."""

    def __init__(self, logger: LoggerMixin) -> None:
        self.log = logger
        super().__init__()

    @abc.abstractmethod
    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """
        Load this plugin.

        :param plugin_path: the path at which this module was found.
        """
        raise NotImplementedError

    def unload(self) -> None:
        """Unload this plugin."""
        ...


class MigratedPlugin(Plugin):
    """MigratedPlugin is a wrapper for old-style plugins."""

    def __init__(self, logger: LoggerMixin) -> None:
        super().__init__(logger)

    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        return super().load(plugin_path)

    ...
