"""Exceptions for plugin loading."""


class PluginLoadingException(Exception):
    """Plugin load failed."""


class PluginAlreadyLoadedException(PluginLoadingException):
    """Plugin is already loaded."""


class PluginHasNoPluginClassException(PluginLoadingException):
    """Plugin has no decorated plugin class."""


class PluginDoesNotExistException(PluginLoadingException):
    """Requested module does not exist, or requested plugin name does not exist."""

    def __init__(self, *args: object) -> None:
        if len(args) > 0 and isinstance(args[0], str):
            new_args: list[object] = [f'Unknown plugin {args[0]!r}']
            new_args.extend(args[1:])
            return super().__init__(*new_args)

        super().__init__(*args)


class LegacyPluginNeedsMigrating(PluginLoadingException):
    """Legacy plugin has no plugin_start3 but has a plugin_start."""


class LegacyPluginHasNoStart3(PluginLoadingException):
    """
    Legacy plugin has no plugin_start3.

    Mostly used as a sentinel to indicate that whatever module is being loaded is not a plugin
    """
