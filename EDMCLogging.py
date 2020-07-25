"""
This module provides for a common logging-powered log facility.
Mostly it implements a logging.Filter() in order to get two extra
members on the logging.LogRecord instance for use in logging.Formatter()
strings.
"""

import sys
import logging
from typing import Tuple

class logger(object):
    """
    Wrapper class for all logging configuration and code.

    Class instantiation requires the 'logger name' and optional loglevel.
    It is intended that this 'logger name' be re-used in all files/modules
    that need to log.

    Users of this class should then call getLogger() to get the
    logging.Logger instance.
    """
    def __init__(self, logger_name: str, loglevel: int=logging.DEBUG):
        """
        Set up a `logging.Logger` with our preferred configuration.
        This includes using an EDMCContextFilter to add 'class' and 'qualname'
        expansions for logging.Formatter().
        """
        self.logger = logging.getLogger(logger_name)
        # Configure the logging.Logger
        self.logger.setLevel(loglevel)

        # Set up filter for adding class name
        self.logger_filter = EDMCContextFilter()
        self.logger.addFilter(self.logger_filter)

        self.logger_channel = logging.StreamHandler()
        self.logger_channel.setLevel(loglevel)

        self.logger_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(qualname)s:%(lineno)d: %(class)s: %(message)s')
        self.logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
        self.logger_formatter.default_msec_format = '%s.%03d'

        self.logger_channel.setFormatter(self.logger_formatter)
        self.logger.addHandler(self.logger_channel)

    def get_logger(self) -> logging.Logger:
        """
        :return: The logging.Logger instance.
        """
        return self.logger


class EDMCContextFilter(logging.Filter):
    """
    logging.Filter sub-class to place extra attributes of the calling site
    into the record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Attempt to set the following in the LogRecord:

            1. class = class name(s) of the call site, if applicable
            2. qualname = __qualname__ of the call site.  This simplifies
             logging.Formatter() as you can use just this no matter if there is
             a class involved or not, so you get a nice clean:
                 <file/module>.<classA>[.classB....].<function>

        If we fail to be able to properly set either then:

            1. Use print() to alert, to be SURE a message is seen.
            2. But also return strings noting the error, so there'll be
             something in the log output if it happens.

        :param record: The LogRecord we're "filtering"
        :return: bool - Always true in order for this record to be logged.
        """
        class_name = qualname = ''
        # Don't even call in if both already set.
        if not getattr(record, 'class', None) or not getattr(record, 'qualname', None):
            (class_name, qualname) = self.caller_class_and_qualname()

        # Only set if not already provided by logging itself
        if getattr(record, 'class', None) is None:
            setattr(record, 'class', class_name)

        # Only set if not already provided by logging itself
        if getattr(record, 'qualname', None) is None:
            setattr(record, 'qualname', qualname)

        return True

    def caller_class_and_qualname(self) -> Tuple[str, str]:
        """
        Figure out our caller's class name(s) and qualname

        Ref: <https://gist.github.com/techtonik/2151726#gistcomment-2333747>

        :return: Tuple[str, str]: The caller's class name(s) and qualname
        """
        # Go up through stack frames until we find the first with a
        # type(f_locals.self) of logging.Logger.  This should be the start
        # of the frames internal to logging.
        frame = sys._getframe(0)
        while frame:
            if type(frame.f_locals.get('self')) == logging.Logger:
                frame = frame.f_back  # Want to start on the next frame below
                break
            frame = frame.f_back

        # Now continue up through frames until we find the next one where
        # that is *not* true, as it should be the call site of the logger
        # call
        while frame:
            if type(frame.f_locals.get('self')) != logging.Logger:
                break  # We've found the frame we want
            frame = frame.f_back

        caller_qualname = caller_class_names = ''
        if frame:
            if frame.f_locals and 'self' in frame.f_locals:
                # Find __qualname__ of the caller
                # Paranoia checks
                if frame.f_code and frame.f_code.co_name:
                    fn = getattr(frame.f_locals['self'], frame.f_code.co_name)

                    if fn and fn.__qualname__:
                        caller_qualname = fn.__qualname__

                # Find containing class name(s) of caller, if any
                frame_class = frame.f_locals['self'].__class__
                # Paranoia checks
                if frame_class and frame_class.__qualname__:
                    caller_class_names = frame_class.__qualname__

        if caller_qualname == '':
            print('ALERT!  Something went wrong with finding caller qualname for logging!')
            caller_qualname = '<ERROR in EDMCLogging.caller_class_and_qualname() for "qualname">'

        if caller_class_names == '':
            print('ALERT!  Something went wrong with finding caller class name(s) for logging!')
            caller_class_names = '<ERROR in EDMCLogging.caller_class_and_qualname() for "class">'

        return (caller_class_names, caller_qualname)
