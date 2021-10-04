"""Main plugin engine."""
from __future__ import annotations

import importlib
import itertools
import pathlib
import sys
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

if TYPE_CHECKING:
    from types import ModuleType
    from EDMCLogging import LoggerMixin

from EDMCLogging import get_main_logger, get_plugin_logger
from plugin import decorators
from plugin.base_plugin import BasePlugin
from plugin.event import BaseEvent
from plugin.exceptions import (
    LegacyPluginNeedsMigrating, PluginAlreadyLoadedException, PluginDoesNotExistException,
    PluginHasNoPluginClassException, PluginLoadingException
)
from plugin.legacy_plugin import MigratedPlugin
from plugin.plugin_info import PluginInfo

PLUGIN_MODULE_PAIR = Tuple[Optional[BasePlugin], Optional['ModuleType']]


class LoadedPlugin:
    """LoadedPlugin represents a single plugin, its module, and callbacks."""

    def __init__(self, info: PluginInfo, plugin: BasePlugin, module: ModuleType) -> None:
        # TODO: System to mark incompatibilities
        self.info: PluginInfo = info
        self.plugin: BasePlugin = plugin
        self.module: ModuleType = module
        self.callbacks: Dict[str, List[Callable]] = plugin._find_marked_funcs(decorators.CALLBACK_MARKER)
        self.providers: Dict[str, Callable] = {}

        for provides, funcs in plugin._find_marked_funcs(decorators.PROVIDER_MARKER).items():
            if len(funcs) != 1:
                raise ValueError('plugin {self} provides multiple functions for provider {provides!r}')

            self.providers[provides] = funcs[0]

    def __str__(self) -> str:
        """Represent this plugin as a string."""
        return (
            f'Plugin {self.info.name} from {self.module} on {self.plugin._manager}'
            f' with {len(self.callbacks)} callbacks'
        )

    def __repr__(self) -> str:
        """Python(ish) string representation."""
        return f'LoadedPlugin({self.info}, {self.plugin}, {self.module})'

    @property
    def log(self) -> 'LoggerMixin':
        """Get the plugin logger represented by this LoadedPlugin."""
        return self.plugin.log

    def _fire_event_funcs(self, event: BaseEvent, funcs: list[Callable], keep_exceptions: bool) -> list[Any]:
        out = []
        for func in funcs:
            try:
                res = func(event)
                if res is not None:
                    out.append(res)

            except Exception as e:
                self.log.exception(f'Caught an exception while firing event {event.name!r} on func {func}')
                if keep_exceptions:
                    out.append(e)

        return out

    def fire_event(self, event: BaseEvent, keep_exceptions: bool = False) -> list[Any]:
        """
        Call all event callbacks that match the given event.

        :param event: the event to pass
        """
        called: set[Callable] = set()
        results = []
        for e, funcs in self.callbacks.items():
            if not (e == event.name or e == '*' or fnmatch(event.name, e)):
                continue

            for f in filter(lambda f: f in called, funcs):
                self.log.warn(f'Refusing to call func {f} on {self} repeatedly for event {event.name}')

            results.extend(self._fire_event_funcs(event, [f for f in funcs if f not in called], keep_exceptions))
            called = called.union(funcs)

        return results

    def provides(self, name: str) -> Optional[Callable]:
        """If this plugin provides a given provider name, return the function that provides it."""
        return self.providers.get(name, None)


class PluginManager:
    """PluginManager is an event engine and plugin engine."""

    def __init__(self) -> None:
        self.log = get_main_logger()
        self.log.info("starting new plugin management engine")
        self.plugins: Dict[str, LoadedPlugin] = {}
        self.failed_loading: Dict[pathlib.Path, Exception] = {}  # path -> reason
        self.disabled_plugins: List[pathlib.Path] = []
        # self._plugins_previously_loaded: Set[str] = set()

    def find_potential_plugins(self, path: pathlib.Path) -> List[pathlib.Path]:
        """
        Search for plugins at the given path.

        :param path: The path to search at
        :return: All plugins found
        """
        # TODO: ignore ones ending in .disabled, either here or lower down
        return list(filter(lambda f: f.is_dir(), path.iterdir()))

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

    def load_normal_plugin(self, path: pathlib.Path, autoresolve_sys_path=True) -> PLUGIN_MODULE_PAIR:
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

        uninstantiated: Optional[Type[BasePlugin]] = None

        self.log.trace(f'Searching for decorated plugin class in module at {path}')
        # Okay, we have the module loaded, lets find any actual plugins
        for class_name, cls in module.__dict__.items():
            if not hasattr(cls, decorators.PLUGIN_MARKER):
                continue

            self.log.trace(f'Found decorated plugin class for {path}: {class_name} ({cls!r})')
            uninstantiated = cls
            break

        if uninstantiated is None:
            self.log.trace(f'No plugin class found in module at {path}')
            raise PluginHasNoPluginClassException

        plugin_logger = get_plugin_logger(path.parts[-1])
        instance: Optional[BasePlugin] = None

        try:
            instance = uninstantiated(plugin_logger, self, path)

        except Exception as e:
            self.log.exception(f'Could not load plugin class for plugin at {path} ({uninstantiated!r}): {e}')
            raise PluginLoadingException(f'Cannot load plugin {uninstantiated!r}: {e}') from e

        return instance, module

    def __get_plugin_at(self, path: pathlib.Path, autoresolve_sys_path=True) -> PLUGIN_MODULE_PAIR:  # noqa: CCR001
        init = path / '__init__.py'
        load = path / 'load.py'

        if not path.exists() or (not init.exists() and not load.exists()):
            raise PluginDoesNotExistException

        plugin: Optional[BasePlugin] = None
        module: Optional[ModuleType] = None

        if init.exists():
            # Could be either type, start by trying a normal plugin
            try:
                plugin, module = self.load_normal_plugin(path, autoresolve_sys_path=autoresolve_sys_path)
            except PluginHasNoPluginClassException:
                if not load.exists():
                    raise

            except PluginLoadingException as e:
                self.log.exception(f'Unable to load plugin at {path}: {e}')
                raise

            except Exception as e:
                self.log.exception(f'Exception occurred during loading plugin at {path}: {e} THIS IS A BUG!')
                raise

        if load.exists() and plugin is None:
            # We have a load.py, and loading the plugin as a new style plugin failed. Try migrate the plugin
            self.log.trace(
                f'Attempt to load {path} as a normal plugin failed. Attempting to load it as a legacy plugin'
            )

            try:
                plugin, module = self.load_legacy_plugin(path)

            except PluginLoadingException as e:
                self.log.exception(f'Unable to load legacy plugin at {path}: {e}')
                raise

            except Exception as e:
                self.log.exception(f'Exception occurred during loading of legacy plugin at {path}: {e} THIS IS A BUG')
                raise

        return plugin, module

    def load_all_plugins_in(self, plugin_dir: pathlib.Path) -> List[LoadedPlugin]:
        """
        Load all plugins in the given path.

        As a side effect, this also notes what plugins are disabled.

        :param plugin_dir: The directory in which to search for plugins.
        :return: All the plugins loaded by this call.
        """
        if not plugin_dir.exists():
            return []

        possible_plugins = self.find_potential_plugins(plugin_dir)
        to_load = list(filter(self.is_valid_plugin_directory, possible_plugins))
        self.disabled_plugins = sorted(set(possible_plugins) ^ set(to_load))

        return [x for x in self.load_plugins(to_load) if x is not None]

    def load_plugins(
        self, paths: Sequence[pathlib.Path], autoresolve_sys_path=True
    ) -> list[Optional[LoadedPlugin]]:
        """
        Load all plugins described by paths.

        Plugins that error on load will return None rather than a LoadedPlugin

        :param paths: The paths to load
        :param autoresolve_sys_path: See load_plugin, defaults to True
        :return: Loaded plugins, same order as the given paths (assuming an order exists in the sequence)
        """
        out: list[Optional[LoadedPlugin]] = []

        for path in paths:
            try:
                res = self.load_plugin(path)

            except PluginLoadingException:
                res = None

            out.append(res)

        return out

    def load_plugin(self, path: pathlib.Path, autoresolve_sys_path=True) -> Optional[LoadedPlugin]:
        """
        Load either a normal or legacy plugin from the given path.

        Normal plugins are tried first, then the two legacy plugin types in order

        :param path: The path to the directory in which the plugin lies
        :param autoresolve_sys_path: See load_normal_plugin, defaults to True
        :return: The loaded plugin, if successful
        """
        # TODO: PLUGINS.md indicates that for legacy plugins, plugins _with_ an __init__.py should be loaded first
        # TODO: Likely this will be done a step above in whatever is done for ordering the list for iteration
        self.log.trace(f'start load of {path} ({autoresolve_sys_path=}')

        plugin, module = None, None
        try:
            plugin, module = self.__get_plugin_at(path, autoresolve_sys_path=autoresolve_sys_path)
        except LegacyPluginNeedsMigrating as e:
            # This is the only "expected" exception that can happen here.
            self.failed_loading[path] = e
            return None

        if plugin is None or module is None:
            raise ValueError('All attempts to load both failed and did not raise any exceptions. THIS IS A BUG')

        # At this point, we have _a_ plugin. Don't really care if its a legacy or otherwise, as far as we're concerned
        # if it walks like a duck, talks like a duck, and quacks like a duck, its a plugin

        self.log.trace(f'Calling load method on {plugin}')
        try:
            info = plugin.load()
        except PluginLoadingException as e:
            self.failed_loading[path] = e
            return None

        except Exception as e:
            raise PluginLoadingException(f'Exception in load method of {plugin}: {e}') from e

        if info is None:
            raise PluginLoadingException(f'{plugin} did not return a valid PluginInfo')

        elif not isinstance(info, PluginInfo):
            raise PluginLoadingException(
                f'{plugin} returned an invalid type for its PluginInfo: {type(info)}({info!r})'
            )

        if info.name in self.plugins:
            raise PluginAlreadyLoadedException(info.name)

        loaded = LoadedPlugin(info, plugin, module)
        self.plugins[info.name] = loaded
        self.log.trace(f'successfully loaded {loaded}')

        return loaded

    def load_legacy_plugin(self, path: pathlib.Path) -> PLUGIN_MODULE_PAIR:
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

        # TODO: set up the plugin path in sys.path? Note that this probably has special behaviour if an __init__ is
        # TODO: present

        resolved = self.resolve_path_to_plugin(target)[:-3]  # strip off .py

        try:
            module = importlib.import_module(resolved)
        except Exception as e:
            # Something went wrong _but_ the file _DOES_ exist.
            raise PluginLoadingException(f'Exception while loading {resolved}: {e}') from e

        logger = get_plugin_logger(path.parts[-1])

        self.log.trace(f'Begin migration of legacy plugin at {path}')

        # This can raise, but we want it to go through us to the upper loading machinery
        plugin = MigratedPlugin(logger, module, self, path)
        self.log.trace(f'Migration of {plugin} complete.')

        return plugin, module

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

    def fire_event(self, event: BaseEvent, keep_exceptions: bool = False) -> Dict[str, List[Any]]:
        """Call all callbacks listening for the given event."""
        out: Dict[str, Any] = {}
        for name, p in self.plugins.items():
            self.log.trace(f'Firing event {event.name} for plugin {name} (keeping exceptions: {keep_exceptions})')
            res = p.fire_event(event, keep_exceptions=keep_exceptions)
            if name in out:
                self.log.warning(f'Two plugins with the same name?????? {out[name]=} {name=} {res=}')

            out[name] = res

        return out

    def fire_str_event(self, event_name: str, time: Optional[float] = None, keep_exceptions: bool = False) -> Dict[str, List[Any]]:
        """Construct a BaseEvent from the given string and time and fire it."""
        return self.fire_event(BaseEvent(event_name, event_time=time), keep_exceptions=keep_exceptions)

    def fire_targeted_event(self, target: Union[LoadedPlugin, str], event: BaseEvent) -> list[Any]:
        """Fire an event just for a particular plugin."""
        if isinstance(target, str):
            found = self.get_plugin(target)
            if found is None:
                raise PluginDoesNotExistException(found)

            target = found

        self.log.trace(f'Firing targeted event {event.name} at {target.info.name}')
        return target.fire_event(event)

    def get_providers(self, name: str) -> List[LoadedPlugin]:
        """
        Get all LoadedPlugins that provide the given provider name.

        :param name: The provider name to search for
        :return: A list of plugins that provide the given name
        """
        out = []
        for p in self.plugins.values():
            if p.provides(name):
                out.append(p)

        return out

    @property
    def legacy_plugins(self) -> List[LoadedPlugin]:
        """Return a list of LoadedPlugin instances that are MigratedPlugins."""
        return [p for p in self.plugins.values() if isinstance(p.plugin, MigratedPlugin)]

    @staticmethod
    def is_valid_plugin_directory(p: pathlib.Path) -> bool:
        """Return whether or not the given path is a valid plugin directory."""
        return p.is_dir() and p.exists() and not (p.name.startswith('.') or p.name.startswith('_'))


def string_fire_results(results: Dict[str, List[Any]]) -> str:
    """
    Return a string representing the given results list.

    Utility method for EDMarketConnector.py and others to extract
    exception infomation to present to users.

    :param results: a list as returned from fire_event
    :return: a string with information about thrown exceptions, if any
    """
    exceptions = [e for e in itertools.chain(*results.values()) if isinstance(e, Exception)]
    if len(exceptions) == 0:
        return ''

    if len(exceptions) == 1:
        return str(exceptions)[0]

    return f'{len(exceptions)} Exceptions thrown during hook processing'
