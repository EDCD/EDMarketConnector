"""New plugin system."""


from typing import Callable, List, Type

from EDMCLogging import get_main_logger
from plugin.plugin import Plugin

logger = get_main_logger()

CALLBACK_MARKER = "__edmc_callback_marker"
PLUGIN_MARKER = "__edmc_plugin_marker__"


def edmc_plugin(cls: Type[Plugin]) -> Type[Plugin]:
    """Mark any classes decorated with this function."""
    logger.info(f"Found plugin class {cls!r}")

    if not issubclass(cls, Plugin):
        raise ValueError(f"Cannot decorate non-subclass of Plugin {cls!r} as EDMC Plugin")

    if hasattr(cls, PLUGIN_MARKER):
        raise ValueError(f"Cannot re-register plugin class {cls!r}")

    setattr(cls, PLUGIN_MARKER, 0)
    logger.trace(f"Successfully marked class {cls!r} as EDMC plugin")
    return cls


def hook(name: str) -> Callable:
    """
    Create event callback.

    :param name: The event to hook onto
    :return: (Internal python decoration implementation)
    """
    def decorate(func: Callable) -> Callable:
        """
        Decorate a function.

        The outer function is used to provide name to us at the decorate site
        """
        logger.debug(f"Found function {func!r} marked as {name!r} callback")
        # If this hook is already being used as a callback, just add the given name, otherwise, set it
        if hasattr(func, CALLBACK_MARKER):
            current: List[str] = getattr(func, CALLBACK_MARKER)
            logger.trace(f"func {func!r} already marked as callback for others: {current}")

            if not isinstance(current, list):
                raise ValueError(f"Hook function has marker with unexpected content. THIS IS A BUG: {current!r}")

            if name in current:
                raise ValueError(f"Hook function hooked onto {name!r} multiple times")

            current.append(name)
            setattr(func, CALLBACK_MARKER, current)

        else:
            setattr(func, CALLBACK_MARKER, [name])

        logger.trace(f"successfully marked callback {func!r} as a callback for event {name!r}")
        return func

    return decorate
