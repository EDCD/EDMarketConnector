"""
Set up required logging for the application.

This module provides for a common logging-powered log facility.
This module uses Loguru for the backend, to handle more complex
situations (like log rotation, compression, and async multi-threading),
while still using the default logging library conventions to ensure strict
drop-in compatibility with legacy plugins.

If type checking, e.g. mypy, objects to `logging.trace(...)` then include this
stanza:

    # See EDMCLogging.py docs.
    # isort: off
    if TYPE_CHECKING:
        from logging import trace, TRACE  # type: ignore # noqa: F401
    # isort: on

This is needed because we add the TRACE level and the trace() function
ourselves at runtime.

To utilise logging in core code, or internal plugins, include this:

    from EDMCLogging import get_main_logger

    logger = get_main_logger()

To utilise logging in a 'found' (third-party) plugin, include this:

    from pathlib import Path
    import logging

    # Retrieve the name of the plugin folder
    plugin_name = Path(__file__).resolve().parent.name
    # Set up logger with hierarchical name including appname and plugin_name
    # plugin_name here *must* be the name of the folder the plugin resides in
    logger = logging.getLogger(f'{appname}.{plugin_name}')
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import pathlib
import sys
import warnings
from fnmatch import fnmatch
# So that any warning about accessing a protected member is only in one place.
from threading import get_native_id as thread_native_id
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from loguru import logger as loguru_logger
import config as config_mod  # This has to be imported separately for trace_if to work... for some reason.
from config import appcmdname, appname, config, config_logger

_default_loglevel = logging.DEBUG

# Define a TRACE level
LEVEL_TRACE = 5
LEVEL_TRACE_ALL = 3
logging.addLevelName(LEVEL_TRACE, "TRACE")
logging.addLevelName(LEVEL_TRACE_ALL, "TRACE_ALL")
logging.TRACE = LEVEL_TRACE  # type: ignore
logging.TRACE_ALL = LEVEL_TRACE_ALL  # type: ignore
# Legacy Monkey-Patch for plugins calling logger.trace()
logging.Logger.trace = lambda self, message, *args, **kwargs: self._log(  # type: ignore
    logging.TRACE,  # type: ignore
    message,
    args,
    **kwargs
)

# Configure Custom Levels in Loguru
try:
    loguru_logger.level("TRACE", no=LEVEL_TRACE, color="<magenta>")
except ValueError:
    pass

try:
    loguru_logger.level("TRACE_ALL", no=LEVEL_TRACE_ALL, color="<magenta><bold>")
except ValueError:
    pass

logging.Formatter.converter = lambda ts: datetime.fromtimestamp(
    ts, timezone.utc  # type: ignore
).utctimetuple()
warnings.simplefilter('default', DeprecationWarning)


LOG_STATE = {
    "console_level": logging.INFO,
    "file_level": logging.TRACE  # type: ignore
}


def console_filter(record: 'Record') -> bool:
    """Dynamic filter for the console sink."""
    return record["level"].no >= LOG_STATE["console_level"]


def file_filter(record: 'Record') -> bool:
    """Dynamic filter for the file sink."""
    return record["level"].no >= LOG_STATE["file_level"]


def _trace_if(self: logging.Logger, condition: str, message: str, *args, **kwargs) -> None:
    if any(fnmatch(condition, p) for p in config_mod.trace_on):
        self._log(logging.TRACE, message, args, **kwargs)  # type: ignore # we added it
        return

    self._log(logging.TRACE_ALL, message, args, **kwargs)  # type: ignore # we added it


logging.Logger.trace_if = _trace_if  # type: ignore

# we cant hide this from `from xxx` imports and I'd really rather no-one other than `logging` had access to it
del _trace_if

if TYPE_CHECKING:
    from types import FrameType
    from loguru import Record

    # Fake type that we can use here to tell type checkers that trace exists

    class LoggerMixin(logging.Logger):
        """LoggerMixin is a fake class that tells type checkers that trace exists on a given type."""

        def trace(self, message, *args, **kwargs) -> None:
            """See implementation above."""

        def trace_if(self, condition: str, message, *args, **kwargs) -> None:
            """
            Fake trace if method, traces only if condition exists in trace_on.

            See implementation above.
            """


def enhanced_formatter(record: 'Record') -> str:
    """Format log messages using Loguru."""
    record["time"] = record["time"].astimezone(timezone.utc)
    record["extra"]["safe_osthreadid"] = record["extra"].get("osthreadid", thread_native_id())
    record["extra"]["safe_module"] = record["extra"].get("module", record["name"])
    record["extra"]["safe_qualname"] = record["extra"].get("qualname", record["function"])
    record["extra"]["safe_lineno"] = record["extra"].get("custom_lineno", record["line"])

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}Z</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{process.id}:{thread.id}:{extra[safe_osthreadid]}</cyan> | "
        "<blue>{extra[safe_module]}.{extra[safe_qualname]}:{extra[safe_lineno]}</blue> - "
        "<level>{message}</level>\n"
    )


def munge_module_name(pathname: str, default_module: str) -> str:
    """Adjust module_name based on the file path from standard logging."""
    file_name = pathlib.Path(pathname).expanduser()
    plugin_dir = config.plugin_dir_path.expanduser()
    internal_plugin_dir = config.internal_plugin_dir_path.expanduser()
    plugin_top = file_name

    while plugin_top and plugin_top.name != '':
        if plugin_top.parent.name == 'plugins':
            break
        plugin_top = plugin_top.parent

    if plugin_top.name != '':
        if plugin_top.parent == plugin_dir:
            pt_len = len(plugin_top.parts)
            name_path = '.'.join(file_name.parts[(pt_len - 1):-1])
            return f'<plugins>.{name_path}.{default_module}'
        elif file_name.parent == internal_plugin_dir:
            pt_len = len(plugin_top.parts)
            name_path = '.'.join(file_name.parts[(pt_len - 1):-1])
            if name_path == '':
                return f'plugins.{default_module}'
            return f'plugins.{name_path}.{default_module}'

    return default_module


class InterceptHandler(logging.Handler):
    """Intercept standard Python logging and route it to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Intercept standard logging and send to Loguru with context."""
        level: str | int
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        munged_module = munge_module_name(record.pathname, record.module)
        extra = {
            "osthreadid": getattr(record, "osthreadid", thread_native_id()),
            "qualname": getattr(record, "qualname", record.funcName),
            "class": getattr(record, "class", ""),
            "module": munged_module,
            "custom_lineno": record.lineno,
        }

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = cast('FrameType', frame.f_back)
            depth += 1

        loguru_logger.bind(**extra).opt(
            depth=depth,
            exception=record.exc_info
        ).log(level, record.getMessage())


class DummyStreamHandler(logging.StreamHandler):
    """Compatibility shim for plugins that attempt to access and modify the stream handler directly."""

    def __init__(self, logger_instance: Logger):
        super().__init__(sys.stdout)
        self._logger_instance = logger_instance

    def setLevel(self, level: int | str) -> None:  # noqa: N802
        """Set the logging level."""
        self._logger_instance.set_console_loglevel(level)

    def setFormatter(self, fmt: logging.Formatter | None) -> None:  # noqa: N802
        """Set the logging format."""
        warnings.warn(
            "EDMC now uses Loguru. Direct formatting of StreamHandlers via "
            "setFormatter is deprecated and will be ignored.",
            DeprecationWarning,
            stacklevel=2
        )


class Logger:
    """Wrapper class for all logging configuration and code."""

    def __init__(self, logger_name: str, loglevel: int | str = _default_loglevel):
        """
        Set up a `logging.Logger` with our preferred configuration.

        This utilizes the InterceptHandler to catch standard logging,
        extract contextual metadata, and forward it to Loguru.
        """
        self.logger_name = logger_name
        self.logger = logging.getLogger(logger_name)

        # This needs to always be TRACE in order to let TRACE level messages
        # through to check the *handler* levels.
        self.logger.setLevel(logging.TRACE)  # type: ignore
        self.logger.propagate = False

        # Clear default Loguru sinks to avoid double-logging
        loguru_logger.remove()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Hijack the standard logging pipeline
        interceptor = InterceptHandler()
        root_logger.addHandler(interceptor)
        self.logger.addHandler(interceptor)

        numeric_level = loglevel if isinstance(loglevel, int) else logging.getLevelName(loglevel)
        LOG_STATE["console_level"] = numeric_level

        self.console_sink_id = loguru_logger.add(
            sys.stdout,
            filter=console_filter,
            format=enhanced_formatter,
            colorize=True, enqueue=True, backtrace=True
        )

        logfile_rotating = pathlib.Path(config.app_dir_path / 'logs') / f'{logger_name}-debug.log'
        logfile_rotating.parent.mkdir(exist_ok=True)

        self.file_sink_id = loguru_logger.add(
            logfile_rotating,
            filter=file_filter,
            format=enhanced_formatter,
            rotation="1 MB", retention=10, compression="zip",
            encoding="utf-8", colorize=False, enqueue=True, backtrace=True
        )

        self.logger_channel = DummyStreamHandler(self)
        self.logger_channel_rotating = DummyStreamHandler(self)

    def get_logger(self) -> LoggerMixin:
        """
        Obtain the self.logger of the class instance.

        Not to be confused with logging.getLogger().
        """
        return cast('LoggerMixin', self.logger)

    def get_streamhandler(self) -> logging.Handler:
        """
        Obtain the self.logger_channel StreamHandler instance.

        :return: logging.StreamHandler
        """
        return self.logger_channel

    def set_channels_loglevel(self, level: int | str) -> None:
        """
        Set the specified log level on the channels.

        :param level: A valid `logging` level.
        :return: None
        """
        self.set_console_loglevel(level)
        numeric_level = level if isinstance(level, int) else logging.getLevelName(level)
        LOG_STATE["file_level"] = numeric_level

    def set_console_loglevel(self, level: int | str) -> None:
        """
        Set the specified log level on the console channel.

        :param level: A valid `logging` level.
        :return: None
        """
        numeric_level = level if isinstance(level, int) else logging.getLevelName(level)

        if numeric_level != logging.TRACE:  # type: ignore
            LOG_STATE["console_level"] = numeric_level
        else:
            self.logger.trace("Not changing log level because it's TRACE")  # type: ignore


def get_plugin_logger(plugin_name: str, loglevel: int = _default_loglevel) -> LoggerMixin:
    """
    Return a logger suitable for a plugin.

    'Found' plugins need their own logger to call out where the logging is
    coming from, but we don't need to set up *everything* for them.

    The name will be '{config.appname}.{plugin.name}', e.g.
    'EDMarketConnector.plugintest', or using appcmdname for EDMC CLI tool.
      Note that `plugin_name` must be the same as the name of the folder the
    plugin resides in.

        Because the application now intercepts standard Python logging globally,
        we no longer need to attach custom filters or handlers directly to this logger.
        Any logs sent through here automatically propagate up to the root, where
        they are caught by the `InterceptHandler`, enriched with context (thread IDs,
        caller names, exact file/line numbers), and safely dispatched to Loguru's
        asynchronous sinks.

        If we added our own handlers or filters here, the output would get duplicated
        or double-processed.

    :param plugin_name: Name of this Logger.  **Must** be the name of the
        folder the plugin resides in.
    :param loglevel: Optional logLevel for this Logger.
    :return: logging.Logger instance, all set up.
    """
    base_logger_name = appcmdname if os.getenv('EDMC_NO_UI') else appname

    plugin_logger = logging.getLogger(f'{base_logger_name}.{plugin_name}')
    plugin_logger.setLevel(loglevel)
    return cast('LoggerMixin', plugin_logger)


# Note: June 2026, removed EDMCContextFilter. Logging handles the stack walk fine,
# munged into InterceptHandler. Logger/Loguru both are handling this complex logic
# without sys._getframe() calls.

class EDMCContextFilter(logging.Filter):
    """
    Legacy compatibility shim.

    EDMC now intercepts standard logging globally via Loguru,
    making manual context filtering obsolete.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        warnings.warn(
            "EDMCContextFilter is deprecated and no longer performs log enrichment. "
            "It will be completely removed in a future major version release.",
            DeprecationWarning,
            stacklevel=2
        )

    def filter(self, record: logging.LogRecord) -> bool:
        """Establish Compatibilty Shim."""
        # Pass everything through cleanly without altering the record
        return True


def get_main_logger(sublogger_name: str = '') -> LoggerMixin:
    """Return the correct logger for how the program is being run."""
    if not os.getenv("EDMC_NO_UI"):
        # GUI app being run
        return cast('LoggerMixin', logging.getLogger(appname))
    # Must be the CLI
    return cast('LoggerMixin', logging.getLogger(appcmdname))


# Singleton
loglevel: str | int = config.get_str('loglevel')
if not loglevel:
    loglevel = logging.INFO

base_logger_name = appcmdname if os.getenv('EDMC_NO_UI') else appname

edmclogger = Logger(base_logger_name, loglevel=loglevel)
logger: LoggerMixin = edmclogger.get_logger()
for handler in list(config_logger.handlers):
    if hasattr(handler, "replay_to"):
        handler.replay_to(logger)
        config_logger.removeHandler(handler)
config_logger.propagate = True
