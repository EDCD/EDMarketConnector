"""Implements locking of Journal directory."""

import pathlib
import sys
import tkinter as tk
from enum import Enum
from os import getpid as os_getpid
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, Optional

from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

if TYPE_CHECKING:  # pragma: no cover
    def _(x: str) -> str:
        return x


class JournalLockResult(Enum):
    """Enumeration of possible outcomes of trying to lock the Journal Directory."""

    LOCKED = 1
    JOURNALDIR_NOTEXIST = 2
    JOURNALDIR_READONLY = 3
    ALREADY_LOCKED = 4
    JOURNALDIR_IS_NONE = 5


class JournalLock:
    """Handle locking of journal directory."""

    def __init__(self) -> None:
        """Initialise where the journal directory and lock file are."""
        self.journal_dir: str = config.get_str('journaldir') or config.default_journal_dir
        self.journal_dir_path: Optional[pathlib.Path] = None
        self.set_path_from_journaldir()
        self.journal_dir_lockfile_name: Optional[pathlib.Path] = None
        # We never test truthiness of this, so let it be defined when first assigned.  Avoids type hint issues.
        # self.journal_dir_lockfile: Optional[IO] = None
        self.locked = False

    def set_path_from_journaldir(self):
        """Set self.journal_dir_path from self.journal_dir."""
        if self.journal_dir is None:
            self.journal_dir_path = None

        else:
            try:
                self.journal_dir_path = pathlib.Path(self.journal_dir)

            except Exception:  # pragma: no cover
                logger.exception("Couldn't make pathlib.Path from journal_dir")

    def open_journal_dir_lockfile(self) -> bool:
        """Open journal_dir lockfile ready for locking."""
        self.journal_dir_lockfile_name = self.journal_dir_path / 'edmc-journal-lock.txt'  # type: ignore
        logger.trace_if('journal-lock', f'journal_dir_lockfile_name = {self.journal_dir_lockfile_name!r}')
        try:
            self.journal_dir_lockfile = open(self.journal_dir_lockfile_name, mode='w+', encoding='utf-8')

        # Linux CIFS read-only mount throws: OSError(30, 'Read-only file system')
        # Linux no-write-perm directory throws: PermissionError(13, 'Permission denied')
        except Exception as e:  # For remote FS this could be any of a wide range of exceptions
            logger.warning(f"Couldn't open \"{self.journal_dir_lockfile_name}\" for \"w+\""
                           f" Aborting duplicate process checks: {e!r}")
            return False

        return True

    def obtain_lock(self) -> JournalLockResult:
        """
        Attempt to obtain a lock on the journal directory.

        :return: LockResult - See the class Enum definition
        """
        if self.journal_dir_path is None:
            return JournalLockResult.JOURNALDIR_IS_NONE

        if not self.open_journal_dir_lockfile():
            return JournalLockResult.JOURNALDIR_READONLY

        return self._obtain_lock()

    def _obtain_lock(self) -> JournalLockResult:
        """
        Actual code for obtaining a lock.

        This is split out so tests can call *just* it, without the attempt
        at opening the file.  If we call open_journal_dir_lockfile() we
        re-use self.journal_dir_lockfile and in the process close the
        previous handle stored in it and thus release the lock.

        :return: LockResult - See the class Enum definition
        """
        if sys.platform == 'win32':
            logger.trace_if('journal-lock', 'win32, using msvcrt')
            # win32 doesn't have fcntl, so we have to use msvcrt
            import msvcrt

            try:
                msvcrt.locking(self.journal_dir_lockfile.fileno(), msvcrt.LK_NBLCK, 4096)

            except Exception as e:
                logger.info(f"Exception: Couldn't lock journal directory \"{self.journal_dir}\""
                            f", assuming another process running: {e!r}")
                return JournalLockResult.ALREADY_LOCKED

        else:  # pytest coverage only sees this on !win32
            logger.trace_if('journal-lock', 'NOT win32, using fcntl')
            try:
                import fcntl

            except ImportError:
                logger.warning("Not on win32 and we have no fcntl, can't use a file lock!"
                               "Allowing multiple instances!")
                return JournalLockResult.LOCKED

            try:
                fcntl.flock(self.journal_dir_lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

            except Exception as e:
                logger.info(f"Exception: Couldn't lock journal directory \"{self.journal_dir}\", "
                            f"assuming another process running: {e!r}")
                return JournalLockResult.ALREADY_LOCKED

        self.journal_dir_lockfile.write(f"Path: {self.journal_dir}\nPID: {os_getpid()}\n")
        self.journal_dir_lockfile.flush()

        logger.trace_if('journal-lock', 'Done')
        self.locked = True

        return JournalLockResult.LOCKED

    def release_lock(self) -> bool:  # noqa: CCR001
        """
        Release lock on journal directory.

        :return: bool - Whether we're now unlocked.
        """
        if not self.locked:
            return True  # We weren't locked, and still aren't

        unlocked = False
        if sys.platform == 'win32':
            logger.trace_if('journal-lock', 'win32, using msvcrt')
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

        else:  # pytest coverage only sees this on !win32
            logger.trace_if('journal-lock', 'NOT win32, using fcntl')
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
        if hasattr(self, 'journal_dir_lockfile'):
            self.journal_dir_lockfile.close()

        self.journal_dir_lockfile_name = None
        # Avoids type hint issues, see 'declaration' in JournalLock.__init__()
        # self.journal_dir_lockfile = None

        return unlocked

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
            self.title(_('Journal directory already locked'))

            # remove decoration
            if sys.platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            elif sys.platform == 'darwin':
                # http://wiki.tcl.tk/13428
                parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

            self.resizable(tk.FALSE, tk.FALSE)

            frame = ttk.Frame(self)
            frame.grid(sticky=tk.NSEW)

            self.blurb = tk.Label(frame)
            # LANG: Text for when newly selected Journal directory is already locked
            self.blurb['text'] = _("The new Journal Directory location is already locked.{CR}"
                                   "You can either attempt to resolve this and then Retry, or choose to Ignore this.")
            self.blurb.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW)

            # LANG: Generic 'Retry' button label
            self.retry_button = ttk.Button(frame, text=_('Retry'), command=self.retry)
            self.retry_button.grid(row=2, column=0, sticky=tk.EW)

            # LANG: Generic 'Ignore' button label
            self.ignore_button = ttk.Button(frame, text=_('Ignore'), command=self.ignore)
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
