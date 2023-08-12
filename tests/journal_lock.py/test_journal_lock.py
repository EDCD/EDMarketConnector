"""Tests for journal_lock.py code."""
import multiprocessing as mp
import os
import pathlib
import sys
from typing import Generator, Optional
import pytest
from pytest import MonkeyPatch, TempdirFactory, TempPathFactory
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
    with open(lockfile / "edmc-journal-lock.txt", mode="w+") as lf:
        print(f"sub-process: Opened {lockfile} for read...")
        # This needs to be kept in sync with journal_lock.py:_obtain_lock()
        if not _obtain_lock("sub-process", lf):
            print("sub-process: Failed to get lock, so returning")
            return

        print("sub-process: Got lock, telling main process to go...")
        continue_q.put("go", timeout=5)
        # Wait for signal to exit
        print("sub-process: Waiting for exit signal...")
        exit_q.get(block=True, timeout=None)

        # And clean up
        _release_lock("sub-process", lf)
        os.unlink(lockfile / "edmc-journal-lock.txt")


def _obtain_lock(prefix: str, filehandle) -> bool:
    """
    Obtain the JournalLock.

    :param prefix: str - what to prefix output with.
    :param filehandle: File handle already open on the lockfile.
    :return: bool - True if we obtained the lock.
    """
    if sys.platform == "win32":
        print(f"{prefix}: On win32")
        import msvcrt

        try:
            print(f"{prefix}: Trying msvcrt.locking() ...")
            msvcrt.locking(filehandle.fileno(), msvcrt.LK_NBLCK, 4096)

        except Exception as e:
            print(f"{prefix}: Unable to lock file: {e!r}")
            return False

    else:
        import fcntl

        print(f"{prefix}: Not win32, using fcntl")
        try:
            fcntl.flock(filehandle, fcntl.LOCK_EX | fcntl.LOCK_NB)

        except Exception as e:
            print(f"{prefix}: Unable to lock file: {e!r}")
            return False

    return True


def _release_lock(prefix: str, filehandle) -> bool:
    """
    Release the JournalLock.

    :param prefix: str - what to prefix output with.
    :param filehandle: File handle already open on the lockfile.
    :return: bool - True if we released the lock.
    """
    if sys.platform == "win32":
        print(f"{prefix}: On win32")
        import msvcrt

        try:
            print(f"{prefix}: Trying msvcrt.locking() ...")
            filehandle.seek(0)
            msvcrt.locking(filehandle.fileno(), msvcrt.LK_UNLCK, 4096)

        except Exception as e:
            print(f"{prefix}: Unable to unlock file: {e!r}")
            return False

    else:
        import fcntl

        print(f"{prefix}: Not win32, using fcntl")
        try:
            fcntl.flock(filehandle, fcntl.LOCK_UN)

        except Exception as e:
            print(f"{prefix}: Unable to unlock file: {e!r}")
            return False

    return True


###########################################################################


class TestJournalLock:
    """JournalLock test class."""

    @pytest.fixture
    def mock_journaldir(
        self, monkeypatch: MonkeyPatch, tmp_path_factory: TempdirFactory
    ) -> Generator:
        """Fixture for mocking config.get_str('journaldir')."""

        def get_str(key: str, *, default: Optional[str] = None) -> str:
            """Mock config.*Config get_str to provide fake journaldir."""
            if key == "journaldir":
                return str(tmp_path_factory.getbasetemp())

            print("Other key, calling up ...")
            return config.get_str(key)  # Call the non-mocked

        with monkeypatch.context() as m:
            m.setattr(config, "get_str", get_str)
            yield tmp_path_factory

    @pytest.fixture
    def mock_journaldir_changing(
        self, monkeypatch: MonkeyPatch, tmp_path_factory: TempdirFactory
    ) -> Generator:
        """Fixture for mocking config.get_str('journaldir')."""

        def get_str(key: str, *, default: Optional[str] = None) -> str:
            """Mock config.*Config get_str to provide fake journaldir."""
            if key == "journaldir":
                return tmp_path_factory.mktemp("changing")

            print("Other key, calling up ...")
            return config.get_str(key)  # Call the non-mocked

        with monkeypatch.context() as m:
            m.setattr(config, "get_str", get_str)
            yield tmp_path_factory

    ###########################################################################
    # Tests against JournalLock.__init__()
    def test_journal_lock_init(self, mock_journaldir: TempPathFactory):
        """Test JournalLock instantiation."""
        print(f"{type(mock_journaldir)=}")
        tmpdir = str(mock_journaldir.getbasetemp())

        jlock = JournalLock()
        # Check members are properly initialised.
        assert jlock.journal_dir == tmpdir
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

    def test_path_from_journaldir_with_tmpdir(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.set_path_from_journaldir() with tmpdir."""
        tmpdir = mock_journaldir

        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        jlock.journal_dir = str(tmpdir)
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
        assert jlock.journal_dir_path is None
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.JOURNALDIR_IS_NONE

    def test_obtain_lock_with_tmpdir(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.obtain_lock() with tmpdir."""
        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.LOCKED
        assert jlock.locked

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        os.unlink(str(jlock.journal_dir_lockfile_name))

    def test_obtain_lock_with_tmpdir_ro(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.obtain_lock() with read-only tmpdir."""
        tmpdir = str(mock_journaldir.getbasetemp())
        print(f"{tmpdir=}")

        # Make tmpdir read-only ?
        if sys.platform == "win32":
            # Ref: <https://stackoverflow.com/a/12168268>
            import ntsecuritycon as con
            import win32security

            # Fetch user details
            winuser, domain, type = win32security.LookupAccountName(
                "", os.environ.get("USERNAME")
            )
            # Fetch the current security of tmpdir for that user.
            sd = win32security.GetFileSecurity(
                tmpdir, win32security.DACL_SECURITY_INFORMATION
            )
            dacl = (
                sd.GetSecurityDescriptorDacl()
            )  # instead of dacl = win32security.ACL()

            # Add Write to Denied list
            # con.FILE_WRITE_DATA results in a 'Special permissions' being
            # listed on Properties > Security for the user in the 'Deny' column.
            # Clicking through to 'Advanced' shows a 'Deny' for
            # 'Create files / write data'.
            dacl.AddAccessDeniedAce(
                win32security.ACL_REVISION, con.FILE_WRITE_DATA, winuser
            )
            # Apply that change.
            sd.SetSecurityDescriptorDacl(1, dacl, 0)  # may not be necessary
            win32security.SetFileSecurity(
                tmpdir, win32security.DACL_SECURITY_INFORMATION, sd
            )

        else:
            import stat

            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)

        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        locked = jlock.obtain_lock()

        # Revert permissions for test cleanup
        if sys.platform == "win32":
            # We can reuse winuser etc from before
            import pywintypes

            # We have to call GetAce() until we find one that looks like what
            # we added.
            i = 0
            ace = dacl.GetAce(i)
            while ace:
                if (
                    ace[0] == (con.ACCESS_DENIED_ACE_TYPE, 0)
                    and ace[1] == con.FILE_WRITE_DATA
                ):
                    # Delete the Ace that we added
                    dacl.DeleteAce(i)
                    # Apply that change.
                    sd.SetSecurityDescriptorDacl(1, dacl, 0)  # may not be necessary
                    win32security.SetFileSecurity(
                        tmpdir, win32security.DACL_SECURITY_INFORMATION, sd
                    )
                    break

                i += 1
                try:
                    ace = dacl.GetAce(i)

                except pywintypes.error:
                    print("Couldn't find the Ace we added, so can't remove")
                    break

        else:
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        assert locked == JournalLockResult.JOURNALDIR_READONLY

    def test_obtain_lock_already_locked(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.obtain_lock() with tmpdir."""
        continue_q: mp.Queue = mp.Queue()
        exit_q: mp.Queue = mp.Queue()
        locker = mp.Process(
            target=other_process_lock,
            args=(continue_q, exit_q, mock_journaldir.getbasetemp()),
        )
        print("Starting sub-process other_process_lock()...")
        locker.start()
        # Wait for the sub-process to have locked
        print('Waiting for "go" signal from sub-process...')
        continue_q.get(block=True, timeout=5)

        print("Attempt actual lock test...")
        # Now attempt to lock with to-test code
        jlock = JournalLock()
        second_attempt = jlock.obtain_lock()
        assert second_attempt == JournalLockResult.ALREADY_LOCKED

        # Need to release any handles on the lockfile else the sub-process
        # might not be able to clean up properly, and that will impact
        # on later tests.
        jlock.journal_dir_lockfile.close()

        print("Telling sub-process to quit...")
        exit_q.put("quit")
        print("Waiting for sub-process...")
        locker.join()
        print("Done.")

    ###########################################################################
    # Tests against JournalLock.release_lock()
    def test_release_lock(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.release_lock()."""
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        jlock.obtain_lock()
        assert jlock.locked

        # Now release the lock
        assert jlock.release_lock()

        # And finally check it actually IS unlocked.
        with open(
            mock_journaldir.getbasetemp() / "edmc-journal-lock.txt", mode="w+"
        ) as lf:
            assert _obtain_lock("release-lock", lf)
            assert _release_lock("release-lock", lf)

        # Cleanup, to avoid side-effect on other tests
        os.unlink(str(jlock.journal_dir_lockfile_name))

    def test_release_lock_not_locked(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.release_lock() when not locked."""
        jlock = JournalLock()
        assert jlock.release_lock()

    def test_release_lock_lie_locked(self, mock_journaldir: TempPathFactory):
        """Test JournalLock.release_lock() when not locked, but lie we are."""
        jlock = JournalLock()
        jlock.locked = True
        assert jlock.release_lock() is False

    ###########################################################################
    # Tests against JournalLock.update_lock()
    def test_update_lock(self, mock_journaldir_changing: TempPathFactory):
        """
        Test JournalLock.update_lock().

        NB: This uses mock_journaldir_changing so that each subsequent call
            to config.get_str('journaldir') gets a new, unique, path.
            This should mean that the call to update_lock() switches to a new
            journaldir.
        """
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        jlock.obtain_lock()
        assert jlock.locked

        # Now store the 'current' journaldir for reference and attempt
        # to update to a new one.
        old_journaldir = jlock.journal_dir
        old_journaldir_lockfile_name = jlock.journal_dir_lockfile_name
        jlock.update_lock(None)  # type: ignore
        assert jlock.journal_dir != old_journaldir
        assert jlock.locked

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        os.unlink(str(jlock.journal_dir_lockfile_name))
        # And the old_journaldir's lockfile too
        os.unlink(str(old_journaldir_lockfile_name))

    def test_update_lock_same(self, mock_journaldir: TempPathFactory):
        """
        Test JournalLock.update_lock().

        Due to using 'static' mock_journaldir this should 'work', because the
        directory is still the same.
        """
        # First actually obtain the lock, and check it worked
        jlock = JournalLock()
        assert jlock.obtain_lock() == JournalLockResult.LOCKED
        assert jlock.locked

        # Now store the 'current' journaldir for reference and attempt
        # to update to a new one.
        old_journaldir = jlock.journal_dir
        jlock.update_lock(None)  # type: ignore
        assert jlock.journal_dir == old_journaldir
        assert jlock.locked

        # Cleanup, to avoid side-effect on other tests
        assert jlock.release_lock()
        os.unlink(str(jlock.journal_dir_lockfile_name))
