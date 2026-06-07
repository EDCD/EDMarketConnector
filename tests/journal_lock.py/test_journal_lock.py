# flake8: noqa
# mypy: ignore-errors
"""Tests for journal_lock.py code."""

from __future__ import annotations

import multiprocessing as mp
import pathlib
from collections.abc import Generator
import pytest
from pytest import MonkeyPatch
from config import config
from journal_lock import JournalLock, JournalLockResult


###########################################################################
# For some tests (at least on Linux) we need another process to already
# hold the lock.
# This is at top level due to multiprocessing.Process wanting to
# pickle its arguments, other_process_lock() being one of them.
def other_process_lock(continue_q: mp.Queue, exit_q: mp.Queue, lockfile: pathlib.Path):
    """
    Obtain the lock in a sub-process.

    :param continue_q: Write to this when parent should continue.
    :param exit_q: When there's an item in this, exit.
    :param lockfile: Path where the lockfile should be.
    """
    from filelock import FileLock
    lock_path = lockfile / "edmc-journal-lock.txt"
    lock = FileLock(lock_path)

    try:
        lock.acquire(timeout=0)
        print("sub-process: Got lock, telling main process to go...")
        continue_q.put("go", timeout=5)
        # Wait for signal to exit
        print("sub-process: Waiting for exit signal...")
        exit_q.get(block=True, timeout=None)

        lock.release()
    except Exception as e:
        print(f"sub-process: Failed execution handle context: {e!r}")
    finally:
        lock_path.unlink(missing_ok=True)


def _obtain_lock_with_filelock(lockfile_path: pathlib.Path) -> bool:
    """Helper verifying lock state using filelock."""
    from filelock import FileLock, Timeout
    lock = FileLock(lockfile_path)
    try:
        lock.acquire(timeout=0)
        lock.release()
        return True
    except (Timeout, Exception):
        return False


###########################################################################


class TestJournalLock:
    """JournalLock test class."""

    @pytest.fixture
    def mock_journaldir(
            self, monkeypatch: MonkeyPatch, tmp_path: pathlib.Path
    ) -> Generator[pathlib.Path, None, None]:
        """Fixture for mocking config.get_str('journaldir') with a unique directory per test."""

        def get_str(key: str, *, default: str | None = None) -> str:
            """Mock config.*Config get_str to provide fake journaldir."""
            if key == "journaldir":
                return str(tmp_path)

            print("Other key, calling up ...")
            return config.get_str(key)

        with monkeypatch.context() as m:
            m.setattr(config, "get_str", get_str)
            yield tmp_path

    @pytest.fixture
    def mock_journaldir_changing(
            self, monkeypatch: MonkeyPatch, tmp_path: pathlib.Path
    ) -> Generator[pathlib.Path, None, None]:
        """Fixture for mocking config.get_str('journaldir') returning changing directories."""
        counter = 0

        def get_str(key: str, *, default: str | None = None) -> str:
            """Mock config.*Config get_str to provide changing fake journaldirs."""
            nonlocal counter
            if key == "journaldir":
                new_path = tmp_path / f"changing_{counter}"
                new_path.mkdir(exist_ok=True)
                counter += 1
                return str(new_path)

            print("Other key, calling up ...")
            return config.get_str(key)

        with monkeypatch.context() as m:
            m.setattr(config, "get_str", get_str)
            yield tmp_path

    ###########################################################################
    # Tests against JournalLock.__init__()
    def test_journal_lock_init(self, mock_journaldir: pathlib.Path):
        """Test JournalLock instantiation."""
        jlock = JournalLock()
        assert jlock.journal_dir == str(mock_journaldir)
        assert jlock.journal_dir_path is not None
        assert jlock.journal_dir_lockfile_name is None

    ###########################################################################
    # Tests against JournalLock.set_path_from_journaldir()
    def test_path_from_journaldir_with_none(self):
        """Test JournalLock.set_path_from_journaldir() with None."""
        jlock = JournalLock()

        # Check that 'None' is handled correctly.
        jlock.journal_dir = None
        jlock.set_path_from_journaldir()
        assert jlock.journal_dir_path is None

    def test_path_from_journaldir_with_tmpdir(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.set_path_from_journaldir() with tmpdir."""
        jlock = JournalLock()
        jlock.journal_dir = str(mock_journaldir)
        jlock.set_path_from_journaldir()
        assert isinstance(jlock.journal_dir_path, pathlib.Path)

    ###########################################################################
    # Tests against JournalLock.obtain_lock()
    def test_obtain_lock_with_none(self):
        """Test JournalLock.obtain_lock() with None."""
        jlock = JournalLock()

        # Check that 'None' is handled correctly.
        jlock.journal_dir = None
        jlock.set_path_from_journaldir()
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.JOURNALDIR_IS_NONE

    def test_obtain_lock_with_tmpdir(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.obtain_lock() with tmpdir."""
        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.LOCKED
        assert jlock.locked

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        if jlock.journal_dir_lockfile_name:
            jlock.journal_dir_lockfile_name.unlink(missing_ok=True)

    def test_obtain_lock_already_locked(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.obtain_lock() when already locked by another process."""
        continue_q: mp.Queue = mp.Queue()
        exit_q: mp.Queue = mp.Queue()
        locker = mp.Process(
            target=other_process_lock,
            args=(continue_q, exit_q, mock_journaldir),
        )
        print("Starting sub-process other_process_lock()...")
        locker.start()

        try:
            # Wait for the sub-process to have locked
            print('Waiting for "go" signal from sub-process...')
            continue_q.get(block=True, timeout=5)

            print("Attempt actual lock test...")
            # Now attempt to lock with to-test code
            jlock = JournalLock()
            assert jlock.obtain_lock() == JournalLockResult.ALREADY_LOCKED
        finally:
            print("Telling sub-process to quit...")
            exit_q.put("quit")
            print("Waiting for sub-process...")
            locker.join()
            print("Done.")

    ###########################################################################
    # Tests against JournalLock.release_lock()
    def test_release_lock(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.release_lock()."""
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        jlock.obtain_lock()
        assert jlock.locked

        # Now release the lock
        assert jlock.release_lock()

        # Check it actually IS unlocked using the filelock backend engine
        lock_file_path = mock_journaldir / "edmc-journal-lock.txt"
        assert _obtain_lock_with_filelock(lock_file_path)
        jlock.journal_dir_lockfile_name.unlink(missing_ok=True)

    def test_release_lock_not_locked(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.release_lock() when not locked."""
        jlock = JournalLock()
        assert jlock.release_lock()

    def test_release_lock_lie_locked(self, mock_journaldir: pathlib.Path):
        """Test JournalLock.release_lock() when an internal exception occurs during release."""
        jlock = JournalLock()
        jlock.journal_dir_lockfile_name = mock_journaldir / "edmc-journal-lock.txt"

        from filelock import FileLock
        jlock.lock = FileLock(jlock.journal_dir_lockfile_name)
        jlock.locked = True

        # Monkeypatch filelock's release method to raise an exception, verifying the failure path
        def mock_release_fail(*args, **kwargs):
            raise OSError("Simulated structural lock release failure")

        jlock.lock.release = mock_release_fail

        try:
            assert jlock.release_lock() is False
        finally:
            # Revert monkeypatch to prevent unraisable deallocator warning on GC cleanup
            del jlock.lock.release
            jlock.lock = None
            jlock.locked = False

    ###########################################################################
    # Tests against JournalLock.update_lock()
    def test_update_lock(self, mock_journaldir_changing: pathlib.Path):
        """
        Test JournalLock.update_lock().
        """
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        jlock.obtain_lock()
        assert jlock.locked

        old_lockfile = jlock.journal_dir_lockfile_name
        jlock.update_lock(None)  # type: ignore
        assert jlock.locked

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        jlock.journal_dir_lockfile_name.unlink(missing_ok=True)
        if old_lockfile:
            old_lockfile.unlink(missing_ok=True)

    def test_update_lock_same(self, mock_journaldir: pathlib.Path):
        """
        Test JournalLock.update_lock() when path remains identical.
        """
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        assert jlock.obtain_lock() == JournalLockResult.LOCKED

        old_dir = jlock.journal_dir
        jlock.update_lock(None)  # type: ignore
        assert jlock.journal_dir == old_dir

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        jlock.journal_dir_lockfile_name.unlink(missing_ok=True)
