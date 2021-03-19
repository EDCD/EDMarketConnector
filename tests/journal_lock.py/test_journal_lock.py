"""Tests for journal_lock.py code."""
# Tests:
#  - Need logging set up, at TRACE level.
#
#  - Will need to mock config for the retrieval of journaldir.
#  - Can ask pytest to create a unique tmp dir:
#
#       <https://docs.pytest.org/en/stable/getting-started.html#request-a-unique-temporary-directory-for-functional-tests>
#
#  - Is file actually locked after obtain_lock().  Problem: We opened the
#     file in a manner which means nothing else can open it.  Also I assume
#     that the same process will either be allowed to lock it 'again' or
#     overwrite the lock.
#
#     Expected failures if:
#
#      1. Lock already held (elsewhere).
#      2. Can't open lock file 'w+'.
#      3. Path to lock file doesn't exist.
#      4. journaldir is None (default on Linux).
#
#  - Does release_lock() work?  Easier to test, if it's worked....
#      1. return True if not locked.
#      2. return True if locked, but successful unlock.
#      3. return False otherwise.
#
#  - JournalLock.set_path_from_journaldir
#      1. When journaldir is None.
#      2. Succeeds otherwise?
#
#  - Can any string to pathlib.Path result in an invalid path for other
#    operations?
#
#  - Not sure about testing JournalAlreadyLocked class.

import os
import pathlib
import sys

import pytest
# Import as other names else they get picked up when used as fixtures
from _pytest import monkeypatch as _pytest_monkeypatch
from _pytest import tmpdir as _pytest_tmpdir
from py._path.local import LocalPath as py_path_local_LocalPath

from config import config
from journal_lock import JournalLock, JournalLockResult


class TestJournalLock:
    """JournalLock test class."""

    @pytest.fixture
    def mock_journaldir(self, monkeypatch: _pytest_monkeypatch, tmpdir: _pytest_tmpdir) -> py_path_local_LocalPath:
        """Fixture for mocking config.get_str('journaldir')."""
        # Force the directory to pre-defined for testing making !Write
        # tmpdir = pathlib.Path(r'C:\Users\Athan\AppData\Local\Temp\rotest')

        def get_str(key: str, *, default: str = None) -> str:
            """Mock config.*Config get_str to provide fake journaldir."""
            if key == 'journaldir':
                return tmpdir

            print('Other key, calling up ...')
            return config.get_str(key)  # Call the non-mocked

        with monkeypatch.context() as m:
            m.setattr(config, "get_str", get_str)
            yield tmpdir

    def test_journal_lock_init(self, mock_journaldir: py_path_local_LocalPath):
        """Test JournalLock instantiation."""
        tmpdir = mock_journaldir

        jlock = JournalLock()
        # Check members are properly initialised.
        assert jlock.journal_dir == tmpdir
        assert jlock.journal_dir_path is not None
        assert jlock.journal_dir_lockfile_name is None

    def test_path_from_journaldir_with_none(self):
        """Test JournalLock.set_path_from_journaldir() with None."""
        jlock = JournalLock()

        # Check that 'None' is handled correctly.
        jlock.journal_dir = None
        jlock.set_path_from_journaldir()
        assert jlock.journal_dir_path is None

    def test_path_from_journaldir_with_tmpdir(self, mock_journaldir: py_path_local_LocalPath):
        """Test JournalLock.set_path_from_journaldir() with tmpdir."""
        tmpdir = mock_journaldir

        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        jlock.journal_dir = tmpdir
        jlock.set_path_from_journaldir()
        assert isinstance(jlock.journal_dir_path, pathlib.Path)

    def test_obtain_lock_with_none(self):
        """Test JournalLock.obtain_lock() with None."""
        jlock = JournalLock()

        # Check that 'None' is handled correctly.
        jlock.journal_dir = None
        jlock.set_path_from_journaldir()
        assert jlock.journal_dir_path is None
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.JOURNALDIR_IS_NONE

    def test_obtain_lock_with_tmpdir(self, mock_journaldir: py_path_local_LocalPath):
        """Test JournalLock.obtain_lock() with tmpdir."""
        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.LOCKED

    def test_obtain_lock_with_tmpdir_ro(self, mock_journaldir: py_path_local_LocalPath):
        """Test JournalLock.obtain_lock() with read-only tmpdir."""
        tmpdir = mock_journaldir

        # Make tmpdir read-only ?
        if sys.platform == 'win32':
            # Ref: <https://stackoverflow.com/a/12168268>
            import ntsecuritycon as con
            import win32security

            # Fetch user details
            winuser, domain, type = win32security.LookupAccountName("", os.environ.get('USERNAME'))
            # Fetch the current security of tmpdir for that user.
            sd = win32security.GetFileSecurity(str(tmpdir), win32security.DACL_SECURITY_INFORMATION)
            dacl = sd.GetSecurityDescriptorDacl()  # instead of dacl = win32security.ACL()

            # Add Write to Denied list
            # con.FILE_WRITE_DATA results in a 'Special permissions' being
            # listed on Properties > Security for the user in the 'Deny' column.
            # Clicking through to 'Advanced' shows a 'Deny' for
            # 'Create files / write data'.
            dacl.AddAccessDeniedAce(win32security.ACL_REVISION, con.FILE_WRITE_DATA, winuser)
            # Apply that change.
            sd.SetSecurityDescriptorDacl(1, dacl, 0)  # may not be necessary
            win32security.SetFileSecurity(str(tmpdir), win32security.DACL_SECURITY_INFORMATION, sd)

        else:
            import stat
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)

        jlock = JournalLock()

        # Check that an actual journaldir is handled correctly.
        locked = jlock.obtain_lock()

        # Revert permissions for test cleanup
        if sys.platform == 'win32':
            # We can reuse winuser etc from before
            import pywintypes

            # We have to call GetAce() until we find one that looks like what
            # we added.
            i = 0
            ace = dacl.GetAce(i)
            while ace:
                if ace[0] == (con.ACCESS_DENIED_ACE_TYPE, 0) and ace[1] == con.FILE_WRITE_DATA:
                    # Delete the Ace that we added
                    dacl.DeleteAce(i)
                    # Apply that change.
                    sd.SetSecurityDescriptorDacl(1, dacl, 0)  # may not be necessary
                    win32security.SetFileSecurity(str(tmpdir), win32security.DACL_SECURITY_INFORMATION, sd)
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

    def test_obtain_lock_already_locked(self, mock_journaldir: py_path_local_LocalPath):
        """Test JournalLock.obtain_lock() with tmpdir."""
        jlock = JournalLock()

        locked = jlock.obtain_lock()
        assert locked == JournalLockResult.LOCKED
        # Now attempt to lock again, but only that.
        second_attempt = jlock._obtain_lock()
        assert second_attempt == JournalLockResult.ALREADY_LOCKED
