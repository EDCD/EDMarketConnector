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

from pytest._pytest import monkeypatch, tmpdir

from config import config
from journal_lock import JournalLock


def test_journal_lock_init(monkeypatch: monkeypatch, tmpdir: tmpdir):  # type: ignore
    """Test JournalLock instantiation."""

    def get_str(key: str, *, default: str = None) -> str:
        """Mock config.*Config get_str to provide fake journaldir."""
        if key == 'journaldir':
            print('journaldir: using tmpdir')
            return tmpdir

        print('Other key, calling up ...')
        return config.get_str(key)  # Call the non-mocked

    with monkeypatch.context() as m:
        m.setattr(config, "get_str", get_str)
        print(f'{tmpdir=}')
        jlock = JournalLock()
