"""Handle the game Status.json file."""

import json
import pathlib
import time
import tkinter as tk
from calendar import timegm
from os.path import getsize, isdir, isfile
from sys import platform
from typing import Any, Dict

from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

if platform == 'darwin':
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

elif platform == 'win32':
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object  # dummy


class Dashboard(FileSystemEventHandler):
    """Status.json handler."""

    _POLL = 1  # Fallback polling interval

    def __init__(self) -> None:
        FileSystemEventHandler.__init__(self)  # futureproofing - not need for current version of watchdog
        self.root: tk.Tk = None  # type: ignore
        self.currentdir: str = None                 # type: ignore # The actual logdir that we're monitoring
        self.observer: Observer = None  # type: ignore
        self.observed = None                   # a watchdog ObservedWatch, or None if polling
        self.status: Dict[str, Any] = {}       # Current status for communicating status back to main thread

    def start(self, root: tk.Tk, started: int) -> bool:
        """
        Start monitoring of Journal directory.

        :param root: tkinter parent window.
        :param started: unix epoch timestamp of LoadGame event.  Ref: monitor.started.
        :return: Successful start.
        """
        logger.debug('Starting...')
        self.root = root
        self.session_start = started

        logdir = config.get_str('journaldir', default=config.default_journal_dir)
        if logdir == '':
            logdir = config.default_journal_dir

        if not logdir or not isdir(logdir):
            logger.info(f"No logdir, or it isn't a directory: {logdir=}")
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            logger.debug(f"{self.currentdir=} != {logdir=}")
            self.stop()

        self.currentdir = logdir

        # Set up a watchdog observer.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = platform != 'win32'
        if not polling and not self.observer:
            logger.debug('Setting up observer...')
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()
            logger.debug('Done')

        elif polling and self.observer:
            logger.debug('Using polling, stopping observer...')
            self.observer.stop()
            self.observer = None  # type: ignore
            logger.debug('Done')

        if not self.observed and not polling:
            logger.debug('Starting observer...')
            self.observed = self.observer.schedule(self, self.currentdir)
            logger.debug('Done')

        logger.info(f'{polling and "Polling" or "Monitoring"} Dashboard "{self.currentdir}"')

        # Even if we're not intending to poll, poll at least once to process pre-existing
        # data and to check whether the watchdog thread has crashed due to events not
        # being supported on this filesystem.
        logger.debug('Polling once to process pre-existing data, and check whether watchdog thread crashed...')
        self.root.after(int(self._POLL * 1000/2), self.poll, True)
        logger.debug('Done.')

        return True

    def stop(self) -> None:
        """Stop monitoring dashboard."""
        logger.debug('Stopping monitoring Dashboard')
        self.currentdir = None  # type: ignore

        if self.observed:
            logger.debug('Was observed')
            self.observed = None
            logger.debug('Unscheduling all observer')
            self.observer.unschedule_all()
            logger.debug('Done.')

        self.status = {}
        logger.debug('Done.')

    def close(self) -> None:
        """Close down dashboard."""
        logger.debug('Calling self.stop()')
        self.stop()

        if self.observer:
            logger.debug('Calling self.observer.stop()')
            self.observer.stop()
            logger.debug('Done')

        if self.observer:
            logger.debug('Joining self.observer...')
            self.observer.join()
            logger.debug('Done')
            self.observer = None  # type: ignore

        logger.debug('Done.')

    def poll(self, first_time: bool = False) -> None:
        """
        Poll Status.json via calling self.process() once a second.

        :param first_time: True if first call of this.
        """
        if not self.currentdir:
            # Stopped
            self.status = {}

        else:
            self.process()

            if first_time:
                emitter = None
                # Watchdog thread
                if self.observed:
                    emitter = self.observer._emitter_for_watch[self.observed]  # Note: Uses undocumented attribute

                if emitter and emitter.is_alive():  # type: ignore
                    return  # Watchdog thread still running - stop polling

            self.root.after(self._POLL * 1000, self.poll)  # keep polling

    def on_modified(self, event) -> None:
        """
        Watchdog callback - DirModifiedEvent on macOS, FileModifiedEvent on Windows.

        :param event: Watchdog event.
        """
        if event.is_directory or (isfile(event.src_path) and getsize(event.src_path)):
            # Can get on_modified events when the file is emptied
            self.process(event.src_path if not event.is_directory else None)

    def process(self, logfile: str = None) -> None:
        """
        Process the contents of current Status.json file.

        Can be called either in watchdog thread or, if polling, in main thread.
        """
        if config.shutting_down:
            return

        try:
            with (pathlib.Path(self.currentdir) / 'Status.json').open('rb') as h:
                data = h.read().strip()

                if data:  # Can be empty if polling while the file is being re-written
                    entry = json.loads(data)

                    # Status file is shared between beta and live. So filter out status not in this game session.
                    if (
                            timegm(time.strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ')) >= self.session_start
                            and self.status != entry
                    ):
                        self.status = entry
                        self.root.event_generate('<<DashboardEvent>>', when="tail")

        except Exception:
            logger.exception('Processing Status.json')


# singleton
dashboard = Dashboard()
