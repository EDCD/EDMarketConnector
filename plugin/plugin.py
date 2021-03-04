"""Base plugin class."""

import abc
import pathlib

from plugin.plugin_info import PluginInfo


class Plugin(abc.ABC):
    """Base plugin class."""

    @abc.abstractmethod
    def load(self, plugin_path: pathlib.Path) -> PluginInfo:
        """
        Load this plugin.

        :param plugin_path: the path at which this module was found.
        """
        ...
