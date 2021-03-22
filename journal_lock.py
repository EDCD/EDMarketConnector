import pathlib
import tkinter as tk
from os import getpid as os_getpid
from sys import platform
from tkinter import ttk
from typing import Callable, TYPE_CHECKING

from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x


class JournalLock:
    """Handle locking of journal directory."""

    def __init__(self):
        """Initialise where the journal directory and lock file are."""
        self.journal_dir: str = config.get_str('journaldir') or config.default_journal_dir
        self.journal_dir_path = pathlib.Path(self.journal_dir)
        self.journal_dir_lockfile_name = None
        self.journal_dir_lockfile = None

    def obtain_lock(self) -> bool:
        """
        Attempt to obtain a lock on the journal directory.

        :return: bool - True if we successfully obtained the lock
        """

        self.journal_dir_lockfile_name = self.journal_dir_path / 'edmc-journal-lock.txt'
        logger.trace(f'journal_dir_lockfile_name = {self.journal_dir_lockfile_name!r}')
        try:
            self.journal_dir_lockfile = open(self.journal_dir_lockfile_name, mode='w+', encoding='utf-8')

        # Linux CIFS read-only mount throws: OSError(30, 'Read-only file system')
        # Linux no-write-perm directory throws: PermissionError(13, 'Permission denied')
        except Exception as e:  # For remote FS this could be any of a wide range of exceptions
            logger.warning(f"Couldn't open \"{self.journal_dir_lockfile_name}\" for \"w+\""
                           f" Aborting duplicate process checks: {e!r}")

        if platform == 'win32':
            logger.trace('win32, using msvcrt')
            # win32 doesn't have fcntl, so we have to use msvcrt
            import msvcrt

            try:
                msvcrt.locking(self.journal_dir_lockfile.fileno(), msvcrt.LK_NBLCK, 4096)

            except Exception as e:
                logger.info(f"Exception: Couldn't lock journal directory \"{self.journal_dir}\""
                            f", assuming another process running: {e!r}")
                return False

        else:
            logger.trace('NOT win32, using fcntl')
            try:
                import fcntl

            except ImportError:
                logger.warning("Not on win32 and we have no fcntl, can't use a file lock!"
                               "Allowing multiple instances!")
                return True  # Lie about being locked

            try:
                fcntl.flock(self.journal_dir_lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

            except Exception as e:
                logger.info(f"Exception: Couldn't lock journal directory \"{self.journal_dir}\", "
                            f"assuming another process running: {e!r}")
                return False

        self.journal_dir_lockfile.write(f"Path: {self.journal_dir}\nPID: {os_getpid()}\n")
        self.journal_dir_lockfile.flush()

        logger.trace('Done')
        return True

    def release_lock(self) -> bool:
        """
        Release lock on journal directory.

        :return: bool - Success of unlocking operation."""
        unlocked = False
        if platform == 'win32':
            logger.trace('win32, using msvcrt')
            # win32 doesn't have fcntl, so we have to use msvcrt
            import msvcrt

            try:
                # Need to seek to the start first, as lock range is relative to
                # current position
                self.journal_dir_lockfile.seek(0)
                msvcrt.locking(self.journal_dir_lockfile.fileno(), msvcrt.LK_UNLCK, 4096)

            except Exception as e:
                logger.info(f"Exception: Couldn't unlock journal directory \"{self.journal_dir}\": {e!r}")

            else:
                unlocked = True

        else:
            logger.trace('NOT win32, using fcntl')
            try:
                import fcntl

            except ImportError:
                logger.warning("Not on win32 and we have no fcntl, can't use a file lock!")
                return True  # Lie about being unlocked

            try:
                fcntl.flock(self.journal_dir_lockfile, fcntl.LOCK_UN)

            except Exception as e:
                logger.info(f"Exception: Couldn't unlock journal directory \"{self.journal_dir}\": {e!r}")

            else:
                unlocked = True

        # Close the file whether or not the unlocking succeeded.
        self.journal_dir_lockfile.close()

        self.journal_dir_lockfile_name = None
        self.journal_dir_lockfile = None

        return unlocked

    class JournalAlreadyLocked(tk.Toplevel):
        """Pop-up for when Journal directory already locked."""

        def __init__(self, parent: tk.Tk, callback: Callable):
            tk.Toplevel.__init__(self, parent)

            self.parent = parent
            self.callback = callback
            self.title(_('Journal directory already locked'))

            # remove decoration
            if platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            elif platform == 'darwin':
                # http://wiki.tcl.tk/13428
                parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

            self.resizable(tk.FALSE, tk.FALSE)

            frame = ttk.Frame(self)
            frame.grid(sticky=tk.NSEW)

            self.blurb = tk.Label(frame)
            self.blurb['text'] = _("The new Journal Directory location is already locked.{CR}"
                                   "You can either attempt to resolve this and then Retry, or choose to Ignore this.")
            self.blurb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)

            self.retry_button = ttk.Button(frame, text=_('Retry'), command=self.retry)
            self.retry_button.grid(row=2, column=0, sticky=tk.EW)

            self.ignore_button = ttk.Button(frame, text=_('Ignore'), command=self.ignore)
            self.ignore_button.grid(row=2, column=1, sticky=tk.EW)
            self.protocol("WM_DELETE_WINDOW", self._destroy)

        def retry(self):
            logger.trace('User selected: Retry')
            self.destroy()
            self.callback(True, self.parent)

        def ignore(self):
            logger.trace('User selected: Ignore')
            self.destroy()
            self.callback(False, self.parent)

        def _destroy(self):
            logger.trace('User force-closed popup, treating as Ignore')
            self.ignore()

    def update_lock(self, parent: tk.Tk):
        """Update journal directory lock to new location if possible."""
        current_journaldir = config.get_str('journaldir') or config.default_journal_dir

        if current_journaldir == self.journal_dir:
            return  # Still the same

        self.release_lock()

        self.journal_dir = current_journaldir
        self.journal_dir_path = pathlib.Path(self.journal_dir)
        if not self.obtain_lock():
            # Pop-up message asking for Retry or Ignore
            self.retry_popup = self.JournalAlreadyLocked(parent, self.retry_lock)

    def retry_lock(self, retry: bool, parent: tk.Tk):
        logger.trace(f'We should retry: {retry}')

        if not retry:
            return

        current_journaldir = config.get_str('journaldir') or config.default_journal_dir
        self.journal_dir = current_journaldir
        self.journal_dir_path = pathlib.Path(self.journal_dir)
        if not self.obtain_lock():
            # Pop-up message asking for Retry or Ignore
            self.retry_popup = self.JournalAlreadyLocked(parent, self.retry_lock)
