"""
TODO: blurb
"""

import sys
import logging
from typing import Tuple

class logger(object):
    """
    TODO: desc
    Wrapper class for all logging configuration and code.
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

    def getLogger(self) -> logging.Logger:
        return self.logger


class EDMCContextFilter(logging.Filter):
    """
    TODO: Update this
    logging.Filter sub-class to place the calling __class__ in the record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """

        :param record:
        :return: bool - True for this record to be logged.
        """
        # TODO: Only set these if they're not already, in case upstream
        #       adds them.
        # TODO: Try setattr(record, 'class', ...
        (class_name, qualname) = self.caller_class_and_qualname()
        record.__dict__['class'] = class_name
        record.__dict__['qualname'] = qualname
        return True

    def caller_class_and_qualname(self, skip=4) -> Tuple[str, str]:
        """
        Figure out our caller's qualname

        Ref: <https://gist.github.com/techtonik/2151726#gistcomment-2333747>

        :param skip: How many stack frames above to look.
        :return: str: The caller's qualname
        """
        import inspect

        # TODO: Fold this into caller_class()
        def stack_(frame):
            framelist = []
            while frame:
                framelist.append(frame)
                frame = frame.f_back
            return framelist

        stack = stack_(sys._getframe(0))
        # Go up through stack frames until we find the first with a
        # type(f_locals.self) of logging.Logger.  This should be the start
        # of the frames internal to logging.
        f = 0
        while stack[f]:
            if type(stack[f].f_locals.get('self')) == logging.Logger:
                f += 1  # Want to start on the next frame below
                break
            f += 1

        # Now continue up through frames until we find the next one where
        # that is *not* true, as it should be the call site of the logger
        # call
        while stack[f]:
            if type(stack[f].f_locals.get('self')) != logging.Logger:
                break  # We've found the frame we want
            f += 1

        caller_qualname = caller_class_name = ''
        if stack[f]:
            frame = stack[f]
            if frame.f_locals and 'self' in frame.f_locals:

                # Find __qualname__ of the caller
                # Paranoia checks
                if frame.f_code and frame.f_code.co_name:
                    fn = getattr(frame.f_locals['self'], frame.f_code.co_name)

                    if fn and fn.__qualname__:
                        caller_qualname = fn.__qualname__

                # Find immediate containing class name of caller, if any
                frame_class = frame.f_locals['self'].__class__
                # Paranoia checks
                if frame_class and frame_class.__qualname__:
                    caller_class_name = frame_class.__qualname__

        if caller_qualname == '':
            print('ALERT!  Something went wrong with finding caller qualname for logging!')

        if caller_class_name == '':
            print('ALERT!  Something went wrong with finding caller class name for logging!')

        return (caller_class_name, caller_qualname)
