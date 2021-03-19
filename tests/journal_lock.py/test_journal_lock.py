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

import pytest
# Import as other names else they get picked up when used as fixtures
from _pytest import monkeypatch as _pytest_monkeypatch
from _pytest import tmpdir as _pytest_tmpdir
from py._path.local import LocalPath as py_path_local_LocalPath

from config import config
from journal_lock import JournalLock


class TestJournalLock:
    """JournalLock test class."""

    @pytest.fixture
    def mock_journaldir(self, monkeypatch: _pytest_monkeypatch, tmpdir: _pytest_tmpdir) -> py_path_local_LocalPath:
        """Fixture for mocking config.get_str('journaldir')."""
        def get_str(key: str, *, default: str = None) -> str:
            """Mock config.*Config get_str to provide fake journaldir."""
            if key == 'journaldir':
                print(f'journaldir: using tmpdir: {tmpdir}')
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
        assert jlock.journal_dir == tmpdir
        assert jlock.journal_dir_path is not None
        assert jlock.journal_dir_lockfile_name is None
