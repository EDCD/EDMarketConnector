"""
Set up required logging for the application.

This module provides for a common logging-powered log facility.
Mostly it implements a logging.Filter() in order to get two extra
members on the logging.LogRecord instance for use in logging.Formatter()
strings.

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

    import os
    import logging

    plugin_name = os.path.basename(os.path.dirname(__file__))
    # plugin_name here *must* be the name of the folder the plugin resides in
    # See, plug.py:load_plugins()
    logger = logging.getLogger(f'{appname}.{plugin_name}')
"""

import inspect
import logging
import logging.handlers
import os
import pathlib
import tempfile
# So that any warning about accessing a protected member is only in one place.
from sys import _getframe as getframe
from threading import get_native_id as thread_native_id
from typing import TYPE_CHECKING, Tuple, cast

from config import appcmdname, appname, config

# TODO: Tests:
#
#       1. Call from bare function in file.
#       2. Call from `if __name__ == "__main__":` section
#
#       3. Call from 1st level function in 1st level Class in file
#       4. Call from 2nd level function in 1st level Class in file
#       5. Call from 3rd level function in 1st level Class in file
#
#       6. Call from 1st level function in 2nd level Class in file
#       7. Call from 2nd level function in 2nd level Class in file
#       8. Call from 3rd level function in 2nd level Class in file
#
#       9. Call from 1st level function in 3rd level Class in file
#      10. Call from 2nd level function in 3rd level Class in file
#      11. Call from 3rd level function in 3rd level Class in file
#
#      12. Call from 2nd level file, all as above.
#
#      13. Call from *module*
#
#      14. Call from *package*

_default_loglevel = logging.DEBUG

# Define a TRACE level
LEVEL_TRACE = 5
logging.addLevelName(LEVEL_TRACE, "TRACE")
logging.TRACE = LEVEL_TRACE  # type: ignore
logging.Logger.trace = lambda self, message, *args, **kwargs: self._log(  # type: ignore
    logging.TRACE,  # type: ignore
    message,
    args,
    **kwargs
)

if TYPE_CHECKING:
    # Fake type that we can use here to tell type checkers that trace exists
    class LoggerMixin(logging.Logger):
        """LoggerMixin is a fake class that tells type checkers that trace exists on a given type."""

        def trace(self, message, *args, **kwargs) -> None:
            """Fake trace method."""
            return self._log(LEVEL_TRACE, message, args, **kwargs)


class Logger:
    """
    Wrapper class for all logging configuration and code.

    Class instantiation requires the 'logger name' and optional loglevel.
    It is intended that this 'logger name' be re-used in all files/modules
    that need to log.

    Users of this class should then call getLogger() to get the
    logging.Logger instance.
    """

    def __init__(self, logger_name: str, loglevel: int = _default_loglevel):
        """
        Set up a `logging.Logger` with our preferred configuration.

        This includes using an EDMCContextFilter to add 'class' and 'qualname'
        expansions for logging.Formatter().
        """
        self.logger = logging.getLogger(logger_name)
        # Configure the logging.Logger
        # This needs to always be TRACE in order to let TRACE level messages
        # through to check the *handler* levels.
        self.logger.setLevel(logging.TRACE)  # type: ignore

        # Set up filter for adding class name
        self.logger_filter = EDMCContextFilter()
        self.logger.addFilter(self.logger_filter)

        # Our basic channel handling stdout
        self.logger_channel = logging.StreamHandler()
        # This should be affected by the user configured log level
        self.logger_channel.setLevel(loglevel)

        self.logger_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(process)d:%(thread)d:%(osthreadid)d %(module)s.%(qualname)s:%(lineno)d: %(message)s')  # noqa: E501
        self.logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
        self.logger_formatter.default_msec_format = '%s.%03d'

        self.logger_channel.setFormatter(self.logger_formatter)
        self.logger.addHandler(self.logger_channel)

        # Rotating Handler in sub-directory
        # We want the files in %TEMP%\{appname}\ as {logger_name}-debug.log and
        # rotated versions.
        # This is {logger_name} so that EDMC.py logs to a different file.
        logfile_rotating = pathlib.Path(tempfile.gettempdir())
        logfile_rotating = logfile_rotating / f'{appname}'
        logfile_rotating.mkdir(exist_ok=True)
        logfile_rotating = logfile_rotating / f'{logger_name}-debug.log'

        self.logger_channel_rotating = logging.handlers.RotatingFileHandler(
            logfile_rotating,
            mode='a',
            maxBytes=1024 * 1024,  # 1MiB
            backupCount=10,
            encoding='utf-8',
            delay=False
        )
        # Yes, we always want these rotated files to be at TRACE level
        self.logger_channel_rotating.setLevel(logging.TRACE)  # type: ignore
        self.logger_channel_rotating.setFormatter(self.logger_formatter)
        self.logger.addHandler(self.logger_channel_rotating)

    def get_logger(self) -> 'LoggerMixin':
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

    def set_channels_loglevel(self, level: int) -> None:
        """
        Set the specified log level on the channels.

        :param level: A valid `logging` level.
        :return: None
        """
        self.logger_channel.setLevel(level)
        self.logger_channel_rotating.setLevel(level)

    def set_console_loglevel(self, level: int) -> None:
        """
        Set the specified log level on the console channel.

        :param level: A valid `logging` level.
        :return: None
        """
        if self.logger_channel.level != logging.TRACE:  # type: ignore
            self.logger_channel.setLevel(level)
        else:
            logger.trace("Not changing log level because it's TRACE")  # type: ignore


def get_plugin_logger(plugin_name: str, loglevel: int = _default_loglevel) -> 'LoggerMixin':
    """
    Return a logger suitable for a plugin.

    'Found' plugins need their own logger to call out where the logging is
    coming from, but we don't need to set up *everything* for them.

    The name will be '{config.appname}.{plugin.name}', e.g.
    'EDMarketConnector.plugintest', or using appcmdname for EDMC CLI tool.
      Note that `plugin_name` must be the same as the name of the folder the
    plugin resides in.
      This means that any logging sent through there *also* goes to the channels
    defined in the 'EDMarketConnector' (or 'EDMC') logger, so we can let that
    take care of the formatting.

    If we add our own channel then the output gets duplicated (assuming same
    logLevel set).

    However we do need to attach our filter to this still.  That's not at
    the channel level.

    :param plugin_name: Name of this Logger.  **Must** be the name of the
        folder the plugin resides in.
    :param loglevel: Optional logLevel for this Logger.
    :return: logging.Logger instance, all set up.
    """
    if not os.getenv('EDMC_NO_UI'):
        base_logger_name = appname
    else:
        base_logger_name = appcmdname

    plugin_logger = logging.getLogger(f'{base_logger_name}.{plugin_name}')
    plugin_logger.setLevel(loglevel)

    plugin_logger.addFilter(EDMCContextFilter())

    return cast('LoggerMixin', plugin_logger)


class EDMCContextFilter(logging.Filter):
    """
    Implements filtering to add extra format specifiers, and tweak others.

    logging.Filter sub-class to place extra attributes of the calling site
    into the record.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Attempt to set/change fields in the LogRecord.

        1. class = class name(s) of the call site, if applicable
        2. qualname = __qualname__ of the call site.  This simplifies
         logging.Formatter() as you can use just this no matter if there is
         a class involved or not, so you get a nice clean:
             <file/module>.<classA>[.classB....].<function>
        3. osthreadid = OS level thread ID.

        If we fail to be able to properly set either then:

        1. Use print() to alert, to be SURE a message is seen.
        2. But also return strings noting the error, so there'll be
         something in the log output if it happens.

        :param record: The LogRecord we're "filtering"
        :return: bool - Always true in order for this record to be logged.
        """
        (class_name, qualname, module_name) = self.caller_attributes(module_name=getattr(record, 'module'))

        # Only set if we got a useful value
        if module_name:
            setattr(record, 'module', module_name)

        # Only set if not already provided by logging itself
        if getattr(record, 'class', None) is None:
            setattr(record, 'class', class_name)

        # Only set if not already provided by logging itself
        if getattr(record, 'qualname', None) is None:
            setattr(record, 'qualname', qualname)

        setattr(record, 'osthreadid', thread_native_id())

        return True

    @classmethod
    def caller_attributes(cls, module_name: str = '') -> Tuple[str, str, str]:  # noqa: CCR001, E501, C901 # this is as refactored as is sensible
        """
        Determine extra or changed fields for the caller.

        1. qualname finds the relevant object and its __qualname__
        2. caller_class_names is just the full class names of the calling
         class if relevant.
        3. module is munged if we detect the caller is an EDMC plugin,
         whether internal or found.

        :param module_name: The name of the calling module.
        :return: Tuple[str, str, str] - class_name, qualname, module_name
        """
        frame = cls.find_caller_frame()

        caller_qualname = caller_class_names = ''
        if frame:
            # <https://stackoverflow.com/questions/2203424/python-how-to-retrieve-class-information-from-a-frame-object#2220759>
            try:
                frame_info = inspect.getframeinfo(frame)
                # raise(IndexError)  # TODO: Remove, only for testing

            except Exception:
                # Separate from the print below to guarantee we see at least this much.
                print('EDMCLogging:EDMCContextFilter:caller_attributes(): Failed in `inspect.getframinfo(frame)`')

                # We want to *attempt* to show something about the nature of 'frame',
                # but at this point we can't trust it will work.
                try:
                    print(f'frame: {frame}')

                except Exception:
                    pass

                # We've given up, so just return '??' to signal we couldn't get the info
                return '??', '??', module_name

            args, _, _, value_dict = inspect.getargvalues(frame)
            if len(args) and args[0] in ('self', 'cls'):
                frame_class: 'object' = value_dict[args[0]]

                if frame_class:
                    # See https://en.wikipedia.org/wiki/Name_mangling#Python for how name mangling works.
                    # For more detail, see _Py_Mangle in CPython's Python/compile.c.
                    name = frame_info.function
                    class_name = frame_class.__class__.__name__.lstrip("_")
                    if name.startswith("__") and not name.endswith("__") and class_name:
                        name = f'_{class_name}{frame_info.function}'

                    # Find __qualname__ of the caller
                    fn = inspect.getattr_static(frame_class, name, None)
                    if fn is None:
                        # For some reason getattr_static cant grab this. Try and grab it with getattr, bail out
                        # if we get a RecursionError indicating a property
                        try:
                            fn = getattr(frame_class, name, None)
                        except RecursionError:
                            print(
                                "EDMCLogging:EDMCContextFilter:caller_attributes():"
                                "Failed to get attribute for function info. Bailing out"
                            )
                            # class_name is better than nothing for __qualname__
                            return class_name, class_name, module_name

                    if fn is not None:
                        if isinstance(fn, property):
                            class_name = str(frame_class)
                            # If somehow you make your __class__ or __class__.__qualname__ recursive, I'll be impressed.
                            if hasattr(frame_class, '__class__') and hasattr(frame_class.__class__, "__qualname__"):
                                class_name = frame_class.__class__.__qualname__
                                caller_qualname = f"{class_name}.{name}(property)"

                            else:
                                caller_qualname = f"<property {name} on {class_name}>"

                        elif fn.__qualname__:
                            caller_qualname = fn.__qualname__

                    # Find containing class name(s) of caller, if any
                    if frame_class.__class__ and frame_class.__class__.__qualname__:
                        caller_class_names = frame_class.__class__.__qualname__

            # It's a call from the top level module file
            elif frame_info.function == '<module>':
                caller_class_names = '<none>'
                caller_qualname = value_dict['__name__']

            elif frame_info.function != '':
                caller_class_names = '<none>'
                caller_qualname = frame_info.function

            module_name = cls.munge_module_name(frame_info, module_name)

            # https://docs.python.org/3.7/library/inspect.html#the-interpreter-stack
            del frame

        if caller_qualname == '':
            print('ALERT!  Something went wrong with finding caller qualname for logging!')
            caller_qualname = '<ERROR in EDMCLogging.caller_class_and_qualname() for "qualname">'

        if caller_class_names == '':
            print('ALERT!  Something went wrong with finding caller class name(s) for logging!')
            caller_class_names = '<ERROR in EDMCLogging.caller_class_and_qualname() for "class">'

        return caller_class_names, caller_qualname, module_name

    @classmethod
    def find_caller_frame(cls):
        """
        Find the stack frame of the logging caller.

        :returns: 'frame' object such as from sys._getframe()
        """
        # Go up through stack frames until we find the first with a
        # type(f_locals.self) of logging.Logger.  This should be the start
        # of the frames internal to logging.
        frame: 'frame' = getframe(0)
        while frame:
            if isinstance(frame.f_locals.get('self'), logging.Logger):
                frame = frame.f_back  # Want to start on the next frame below
                break
            frame = frame.f_back
        # Now continue up through frames until we find the next one where
        # that is *not* true, as it should be the call site of the logger
        # call
        while frame:
            if not isinstance(frame.f_locals.get('self'), logging.Logger):
                break  # We've found the frame we want
            frame = frame.f_back
        return frame

    @classmethod
    def munge_module_name(cls, frame_info: inspect.Traceback, module_name: str) -> str:
        """
        Adjust module_name based on the file path for the given frame.

        We want to distinguish between other code and both our internal plugins
        and the 'found' ones.

        For internal plugins we want "plugins.<filename>".
        For 'found' plugins we want "<plugins>.<plugin_name>...".

        :param frame_info: The frame_info of the caller.
        :param module_name: The module_name string to munge.
        :return: The munged module_name.
        """
        file_name = pathlib.Path(frame_info.filename).expanduser()
        plugin_dir = pathlib.Path(config.plugin_dir_path).expanduser()
        internal_plugin_dir = pathlib.Path(config.internal_plugin_dir_path).expanduser()
        # Find the first parent called 'plugins'
        plugin_top = file_name
        while plugin_top and plugin_top.name != '':
            if plugin_top.parent.name == 'plugins':
                break

            plugin_top = plugin_top.parent

        # Check we didn't walk up to the root/anchor
        if plugin_top.name != '':
            # Check we're still inside config.plugin_dir
            if plugin_top.parent == plugin_dir:
                # In case of deeper callers we need a range of the file_name
                pt_len = len(plugin_top.parts)
                name_path = '.'.join(file_name.parts[(pt_len - 1):-1])
                module_name = f'<plugins>.{name_path}.{module_name}'

            # Check we're still inside the installation folder.
            elif file_name.parent == internal_plugin_dir:
                # Is this a deeper caller ?
                pt_len = len(plugin_top.parts)
                name_path = '.'.join(file_name.parts[(pt_len - 1):-1])

                # Pre-pend 'plugins.<plugin folder>.' to module
                if name_path == '':
                    # No sub-folder involved so module_name is sufficient
                    module_name = f'plugins.{module_name}'

                else:
                    # Sub-folder(s) involved, so include them
                    module_name = f'plugins.{name_path}.{module_name}'

        return module_name


def get_main_logger() -> 'LoggerMixin':
    """Return the correct logger for how the program is being run."""
    if not os.getenv("EDMC_NO_UI"):
        # GUI app being run
        return cast('LoggerMixin', logging.getLogger(appname))
    else:
        # Must be the CLI
        return cast('LoggerMixin', logging.getLogger(appcmdname))


# Singleton
loglevel = config.get_str('loglevel')
if not loglevel:
    loglevel = logging.INFO

if not os.getenv('EDMC_NO_UI'):
    base_logger_name = appname
else:
    base_logger_name = appcmdname

edmclogger = Logger(base_logger_name, loglevel=loglevel)
logger: 'LoggerMixin' = edmclogger.get_logger()
