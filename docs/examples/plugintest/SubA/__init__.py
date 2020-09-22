"""Test class logging."""

import logging


class SubA:
    """Simple class to test logging."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def ping(self) -> None:
        """
        Log a ping to demonstrate correct logging.

        :return:
        """
        self.logger.info('ping!')
