"""
dashboard.py - Handle the game Status.json file.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import json
import sys
import time
import tkinter as tk
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()


class Dashboard(FileSystemEventHandler):
    """Status.json handler leveraging unified Watchdog observers."""

    def __init__(self) -> None:
        super().__init__()
        self.session_start: int = int(time.time())
        self.root: tk.Tk = None  # type: ignore
        self.currentdir: Path | None = None  # The actual logdir that we're monitoring
        self.observer: Observer | PollingObserver | None = None  # type: ignore
        self.status: dict[str, Any] = {}  # Current status for communicating back to main thread

    def start(self, root: tk.Tk, started: int) -> bool:
        """
        Start monitoring of Journal directory.

        :param root: tkinter parent window.
        :param started: unix epoch timestamp of LoadGame event. Ref: monitor.started.
        :return: Successful start.
        """
        logger.debug('Starting...')
        self.root = root
        self.session_start = started

        logdir_str = config.get_str('journaldir', default=config.default_journal_dir)
        logdir = Path(logdir_str).expanduser() if logdir_str else Path(config.default_journal_dir).expanduser()
        if not logdir.is_dir():
            logger.info(f"No logdir, or it isn't a directory: {logdir=}")
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            logger.debug(f"{self.currentdir=} != {logdir=}")
            self.stop()

        self.currentdir = logdir

        # Set up a watchdog observer.
        # Native file system events are unreliable over network drives (CIFS/NFS).
        # We use standard native Observer on Windows, and PollingObserver everywhere else
        # to ensure seamless cross-platform compatibility without manual tkinter loops.
        if not self.observer:
            logger.debug('Setting up observer...')
            if sys.platform == 'win32':
                self.observer = Observer()
            else:
                self.observer = PollingObserver(timeout=1.0)

            self.observer.daemon = True
            self.observer.schedule(self, path=str(self.currentdir), recursive=False)
            self.observer.start()
            logger.debug('Done')

        logger.info(f'{"Monitoring" if sys.platform == "win32" else "Polling"} Dashboard "{self.currentdir}"')

        # Process the initial file state immediately to catch pre-existing data
        logger.debug('Processing initial state...')
        self.process()
        logger.debug('Done.')

        return True

    def stop(self) -> None:
        """Stop monitoring dashboard."""
        logger.debug('Stopping monitoring Dashboard')
        self.currentdir = None

        if self.observer:
            logger.debug('Stopping observer thread...')
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception:
                logger.exception('Error tearing down observer')
            self.observer = None
            logger.debug('Done.')

        self.status = {}
        logger.debug('Done.')

    def close(self) -> None:
        """Close down dashboard."""
        logger.debug('Calling self.stop()')
        self.stop()
        logger.debug('Done.')

    def on_modified(self, event) -> None:
        """
        Watchdog callback - FileModifiedEvent.

        :param event: Watchdog event.
        """
        if event.is_directory:
            self.process()
            return

        modpath = Path(event.src_path)
        if modpath.name == 'Status.json' and modpath.stat().st_size > 0:
            self.process()

    def process(self, logfile: str | None = None) -> None:
        """
        Process the contents of current Status.json file.

        Safely handles intermittent race conditions from concurrent game writes.
        """
        if config.shutting_down or not self.currentdir:
            return

        status_json_path = self.currentdir / 'Status.json'
        if not status_json_path.is_file():
            return
        try:
            with open(status_json_path, 'rb') as h:
                data = h.read().strip()

            if not data:
                return  # File is currently empty/being rewritten by the game

            entry = json.loads(data)
            timestamp_str = entry.get('timestamp', '')

            if timestamp_str:
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                entry_timestamp = int(dt.timestamp())

                # Filter out status changes not relevant to the active game session
                if entry_timestamp >= self.session_start and self.status != entry:
                    self.status = entry
                    if self.root:
                        self.root.event_generate('<<DashboardEvent>>', when="tail")

        except (json.JSONDecodeError, KeyError):
            logger.debug('Status.json was caught in a partially written state. Skipping frame.')
        except Exception:
            logger.exception('Processing Status.json')

    def poll(self, first_time: bool = False) -> None:
        """
        Legacy compatibility shim for backwards compatibility with plugins.

        Status.json is now handled entirely via filesystem event observers.
        """
        warnings.warn(
            "Dashboard.poll() is deprecated as EDMC now leverages unified Watchdog observers. "
            "This method is a no-op and will be removed in a future major version.",
            DeprecationWarning,
            stacklevel=2
        )
        # Safely run process once just in case the plugin was using it to force a refresh
        self.process()


# singleton
dashboard = Dashboard()
