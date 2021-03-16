"""Main plugin engine."""
from __future__ import annotations

import dataclasses
import importlib
import pathlib
import sys
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Type

if TYPE_CHECKING:
    from types import ModuleType

from EDMCLogging import get_main_logger, get_plugin_logger
from plugin import decorators
from plugin.exceptions import (
    PluginAlreadyLoadedException, PluginDoesNotExistException, PluginHasNoPluginClassException, PluginLoadingException
)
from plugin.plugin import MigratedPlugin, Plugin
from plugin.plugin_info import PluginInfo


@dataclasses.dataclass
class LoadedPlugin:
    """LoadedPlugin represents a single plugin, its module, and callbacks."""

    info: PluginInfo
    plugin: Plugin
    module: ModuleType
    callbacks: Dict[str, List[Callable]]


class PluginManager:
    """PluginManager is an event engine and plugin engine."""

    def __init__(self) -> None:
        self.log = get_main_logger()
        self.log.info("starting new plugin management engine")
        self.plugins: Dict[str, LoadedPlugin] = {}
        self._plugins_previously_loaded: Set[str] = set()

    def find_potential_plugins(self, path: pathlib.Path) -> List[pathlib.Path]:
        """
        Search for plugins at the given path.

        :param path: The path to search at
        :return: All plugins found
        """
        # TODO: ignore ones ending in .disabled, either here or lower down
        return list(filter(lambda f: f.is_dir(), path.iterdir()))

    # def clean_potential_plugins(self, paths: List[pathlib.Path]) -> Tuple[List[pathlib.Path], List[pathlib.Path]]:
    #     """
    #     Split potential plugins into normal and legacy plugins.

    #     Silently drops any potential plugin paths that dont match requirements.

    #     :param paths: The potential plugin paths
    #     :return: A tuple containing plugin and legacy plugin path lists
    #     """
    #     legacy = []
    #     plugins = []

    #     for path in paths:
    #         for file in list(filter(lambda f: f.is_file(), path.iterdir())):
    #             if file.match("__init__.py"):
    #                 # Assume a normal plugin

    #     ...

    def __load_plugin_from_class(
        self, path: pathlib.Path, module: ModuleType, class_name: str, cls: Type[Plugin]
    ) -> LoadedPlugin:

        str_plugin_reference = f"{class_name} -> {cls!r} from path {path}"
        self.log.trace(f"Loading plugin class {str_plugin_reference}")

        plugin_logger = get_plugin_logger(path.parts[-1])

        try:
            instantiated = cls(plugin_logger, self)

        except Exception:
            self.log.exception(f"Could not instantiate plugin class for plugin {str_plugin_reference}")
            raise

        callbacks: Dict[str, List[Callable]] = {}

        for field_name, class_field in cls.__dict__.items():
            if not hasattr(class_field, decorators.CALLBACK_MARKER):
                continue

            events = getattr(class_field, decorators.CALLBACK_MARKER)

            self.log.trace(f"found callback method {field_name} -> {class_field} with callbacks {events}")
            for name in events:
                callbacks[name] = callbacks.get(name, []) + [class_field]

        self.log.trace(f"finished finding callbacks on plugin class {str_plugin_reference}")

        try:
            info = instantiated.load(path)
        except Exception:
            self.log.exception(f"Could not call load on plugin {str_plugin_reference}")
            raise

        if info is None:
            raise PluginLoadingException(f"Plugin {str_plugin_reference} did not return a valid PluginInfo")

        return LoadedPlugin(info, instantiated, module, callbacks)

    @staticmethod
    def resolve_path_to_plugin(path: pathlib.Path, relative_to=None) -> str:
        """
        Convert a file path to a python import path.

        :param path: The path to convert
        :param relative_to: A directory in sys.path that is above the given path, defaults to the current working dir
        :return: The resolved path
        """
        if relative_to is None:
            relative_to = pathlib.Path.cwd()

        relative = path.relative_to(relative_to)
        return ".".join(relative.parts)

    def load_plugin(self, path: pathlib.Path, autoresolve_sys_path=True) -> Optional[LoadedPlugin]:
        """
        Load a plugin at the given path.

        Note that if the parent directory of the given path does _not_ exist in sys.path already, it will be added.
        This can be disabled with the autoresolve_sys_path bool

        :param path: The path to load a plugin from
        :param autoresolve_sys_path: Whether or not to add the parent of the given directory to sys.path if needed
        :return: The LoadedPlugin, or None / an exception.
        """
        self.log.info(f"attempting to load plugin(s) at path {path} ({path.absolute()})")

        # TODO: This probably pollutes sys.path more than needed. Either this should take a relative_to arg to pass
        # TODO: to resolve_path_to_plugin, or, we should somehow indicate what the base plugin path is to this function
        if autoresolve_sys_path and str(path.parent.absolute()) not in sys.path:
            sys.path.append(str(path.parent.absolute()))

        try:
            resolved = self.resolve_path_to_plugin(path, relative_to=path.parent.absolute())
            self.log.trace(f"Resolved plugin path to import path {resolved}")
            module = importlib.import_module(resolved)

        except ImportError as e:
            self.log.warning("Attempted to load nonexistent module path {path}")
            raise PluginDoesNotExistException from e

        except Exception as e:
            self.log.error(f"Unable to load module {path}")
            raise PluginLoadingException(f"Exception occurred while loading: {e}") from e

        loaded = None

        # Okay, we have the module loaded, lets find any actual plugins
        for class_name, cls in module.__dict__.items():
            if not hasattr(cls, decorators.PLUGIN_MARKER):
                continue
            try:
                loaded = self.__load_plugin_from_class(path, module, class_name, cls)
            except Exception as e:
                self.log.info(f"Failed to load plugin {class_name} -> {cls!r}")
                raise PluginLoadingException(f"Cannot load plugin {cls!r}: {e}") from e

            if self.is_plugin_loaded(loaded.info.name):
                self.log.error("Plugins with the same names attempted to load (double load?)")
                raise PluginAlreadyLoadedException(f"Plugin with name {loaded.info.name} cannot be loaded twice")

            break

        if loaded is None:
            self.log.error(f"No plugin class found in {path}")
            raise PluginHasNoPluginClassException(f"No plugin class found in {path}")

        self.plugins[loaded.info.name] = loaded
        return loaded

    def load_legacy_or_normal_plugin(self, path: pathlib.Path, autoresolve_sys_path=True) -> Optional[LoadedPlugin]:
        try:
            return self.load_plugin(path, autoresolve_sys_path=autoresolve_sys_path)
        except PluginDoesNotExistException:
            # No __init__.py. Try load it as a legacy plugin directly from the path
            ...
        ...

    def load_legacy_plugin_from_path(self, path: pathlib.Path) -> Optional[MigratedPlugin]:
        """
        Load a legacy (load.py and plugin_start3()) plugin from the given path.

        :param path: The path to the _directory_ in which the plugin is located
        :raises PluginDoesNotExistException: When the plugin does not exist
        :raises PluginLoadingException: When an exception occurs during loading
        :return: A MigratedPlugin instance
        """
        target = path / "load.py"
        if not target.exists():
            raise PluginDoesNotExistException

        resolved = self.resolve_path_to_plugin(target)[:-3]  # strip off .py

        try:
            module = importlib.import_module(resolved)
        except Exception as e:
            # Something went wrong _but_ the file _DOES_ exist.
            raise PluginLoadingException from e

        ...

    def is_plugin_loaded(self, name: str) -> bool:
        """
        Check if a plugin is loaded under a given name.

        :param name: The name to search for
        :return: Whether or not the name is loaded
        """
        return name in self.plugins

    def get_plugin(self, name: str) -> Optional[LoadedPlugin]:
        """
        Get the plugin identified by name, if it exists.

        :param name: The plugin name to search for.
        :return: The plugin if it exists, otherwise None
        """
        return self.plugins.get(name)

    def unload_plugin(self, name: str):
        """
        Unload the plugin identified by the given name.

        :param name: The name to unload
        """
        to_unload = self.get_plugin(name)
        if to_unload is None:
            self.log.warn(f"Attempt to unload nonexistent plugin {name}")
            return

        try:
            to_unload.plugin.unload()

        except Exception as e:
            self.log.exception(f"Exception occurred while attempting to fire unload callback on {name}: {e}")

        except SystemExit:
            self.log.critical(f"Unload of {name} attempted to stop the running interpreter! Catching!")

        del self.plugins[name]

    def fire_event(self, name: str, data):
        ...

    # TODO: Register(System|station)Provider method, to allow it to be dynamic to plugins
