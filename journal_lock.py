"""
journal_lock.py - Locking of the Journal Directory.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tkinter as tk
from enum import Enum
from os import getpid as os_getpid
from tkinter import ttk
from collections.abc import Callable
from filelock import FileLock, Timeout
from l10n import translations as tr
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()


class JournalLockResult(Enum):
    """Enumeration of possible outcomes of trying to lock the Journal Directory."""

    LOCKED = 1
    JOURNALDIR_NOTEXIST = 2
    JOURNALDIR_READONLY = 3
    ALREADY_LOCKED = 4
    JOURNALDIR_IS_NONE = 5


class JournalLock:
    """Handle locking of journal directory using python-filelock."""

    def __init__(self) -> None:
        """Initialise where the journal directory and lock file are."""
        self.journal_dir: str | None = config.get_str('journaldir') or config.default_journal_dir
        self.journal_dir_path: pathlib.Path | None = None
        self.set_path_from_journaldir()
        self.journal_dir_lockfile_name: pathlib.Path | None = None
        self.lock: FileLock | None = None
        self.locked = False

    def set_path_from_journaldir(self) -> None:
        """Set self.journal_dir_path from self.journal_dir."""
        if self.journal_dir is None:
            self.journal_dir_path = None
        else:
            try:
                self.journal_dir_path = pathlib.Path.expanduser(pathlib.Path(self.journal_dir))
            except Exception:  # pragma: no cover
                logger.exception("Couldn't make pathlib.Path from journal_dir")

    def obtain_lock(self) -> JournalLockResult:
        """
        Attempt to obtain a lock on the journal directory.

        :return: LockResult - See the class Enum definition
        """
        if self.journal_dir_path is None:
            return JournalLockResult.JOURNALDIR_IS_NONE

        self.journal_dir_lockfile_name = self.journal_dir_path / 'edmc-journal-lock.txt'
        logger.trace_if('journal-lock', f'journal_dir_lockfile_name = {self.journal_dir_lockfile_name!r}')

        # Instantiate filelock engine (abstracts win32/fcntl natively)
        self.lock = FileLock(self.journal_dir_lockfile_name)

        try:
            # Write PID metadata into the lockfile for transparency
            try:
                with open(self.journal_dir_lockfile_name, mode='w', encoding='utf-8') as f:
                    f.write(f"Path: {self.journal_dir}\nPID: {os_getpid()}\n")
            except (PermissionError, OSError):
                try:
                    self.lock.acquire(timeout=0)
                    logger.trace_if('journal-lock', 'Done')
                    self.locked = True
                    return JournalLockResult.LOCKED
                except Timeout:
                    logger.info(f"Couldn't lock journal directory \"{self.journal_dir}\","
                                f" assuming another process running.")
                    return JournalLockResult.ALREADY_LOCKED
                except (PermissionError, OSError):
                    return JournalLockResult.JOURNALDIR_READONLY

            # Immediately fail if another process holds the lock
            self.lock.acquire(timeout=0)

            logger.trace_if('journal-lock', 'Done')
            self.locked = True
            return JournalLockResult.LOCKED

        except Timeout:
            logger.info(f"Couldn't lock journal directory \"{self.journal_dir}\", assuming another process running.")
            return JournalLockResult.ALREADY_LOCKED
        except (PermissionError, OSError) as e:
            logger.warning(f"Couldn't open/lock \"{self.journal_dir_lockfile_name}\". "
                           f"Aborting duplicate process checks: {e!r}")
            return JournalLockResult.JOURNALDIR_READONLY

    def release_lock(self) -> bool:
        """
        Release lock on journal directory.

        :return: bool - Whether we're now unlocked.
        """
        if not self.locked or not self.lock:
            return True  # We weren't locked, and still aren't

        try:
            self.lock.release()
            self.locked = False

            # Physically remove the lockfile from disk on a clean exit
            if self.journal_dir_lockfile_name and self.journal_dir_lockfile_name.exists():
                try:
                    os.remove(self.journal_dir_lockfile_name)
                except Exception:
                    pass  # Prevent crashing if a file hook holds it open briefly during shutdown

            return True
        except Exception as e:
            logger.info(f"Exception: Couldn't unlock journal directory \"{self.journal_dir}\": {e!r}")
            return False

    class JournalAlreadyLocked(tk.Toplevel):  # pragma: no cover
        """Pop-up for when Journal directory already locked."""

        def __init__(self, parent: tk.Tk, callback: Callable) -> None:
            """
            Init the user choice popup.

            :param parent: - The tkinter parent window.
            :param callback: - The function to be called when the user makes their choice.
            """
            tk.Toplevel.__init__(self, parent)

            self.parent = parent
            self.callback = callback
            # LANG: Title text on popup when Journal directory already locked
            self.title(tr.tl('Journal directory already locked'))

            # remove decoration
            if sys.platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            self.resizable(tk.FALSE, tk.FALSE)

            frame = ttk.Frame(self)
            frame.grid(sticky=tk.NSEW)

            self.blurb = tk.Label(frame)
            # LANG: Text for when newly selected Journal directory is already locked
            self.blurb['text'] = tr.tl("The new Journal Directory location is already locked.{CR}"
                                       "You can either attempt to resolve this and then Retry, "
                                       "or choose to Ignore this.")
            self.blurb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)

            # LANG: Generic 'Retry' button label
            self.retry_button = ttk.Button(frame, text=tr.tl('Retry'), command=self.retry)
            self.retry_button.grid(row=2, column=0, sticky=tk.EW)

            # LANG: Generic 'Ignore' button label
            self.ignore_button = ttk.Button(frame, text=tr.tl('Ignore'), command=self.ignore)
            self.ignore_button.grid(row=2, column=1, sticky=tk.EW)
            self.protocol("WM_DELETE_WINDOW", self._destroy)

        def retry(self) -> None:
            """Handle user electing to Retry obtaining the lock."""
            logger.trace_if('journal-lock_if', 'User selected: Retry')
            self.destroy()
            self.callback(True, self.parent)

        def ignore(self) -> None:
            """Handle user electing to Ignore failure to obtain the lock."""
            logger.trace_if('journal-lock', 'User selected: Ignore')
            self.destroy()
            self.callback(False, self.parent)

        def _destroy(self) -> None:
            """Destroy the Retry/Ignore popup."""
            logger.trace_if('journal-lock', 'User force-closed popup, treating as Ignore')
            self.ignore()

    def update_lock(self, parent: tk.Tk) -> None:
        """
        Update journal directory lock to new location if possible.

        :param parent: - The parent tkinter window.
        """
        current_journaldir = config.get_str('journaldir') or config.default_journal_dir

        if current_journaldir == self.journal_dir:
            return  # Still the same

        self.release_lock()

        self.journal_dir = current_journaldir
        self.set_path_from_journaldir()

        if self.obtain_lock() == JournalLockResult.ALREADY_LOCKED:
            # Pop-up message asking for Retry or Ignore
            self.retry_popup = self.JournalAlreadyLocked(parent, self.retry_lock)  # pragma: no cover

    def retry_lock(self, retry: bool, parent: tk.Tk) -> None:  # pragma: no cover
        """
        Try again to obtain a lock on the Journal Directory.

        :param retry: - does the user want to retry?  Comes from the dialogue choice.
        :param parent: - The parent tkinter window.
        """
        logger.trace_if('journal-lock', f'We should retry: {retry}')

        if not retry:
            return

        current_journaldir = config.get_str('journaldir') or config.default_journal_dir
        self.journal_dir = current_journaldir
        self.set_path_from_journaldir()
        if self.obtain_lock() == JournalLockResult.ALREADY_LOCKED:
            # Pop-up message asking for Retry or Ignore
            self.retry_popup = self.JournalAlreadyLocked(parent, self.retry_lock)
