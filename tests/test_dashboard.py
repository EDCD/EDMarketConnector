# flake8: noqa
# mypy: ignore-errors
"""Test the Dashboard for reading Status.json."""

import pytest
import json
from unittest.mock import MagicMock, patch
import dashboard


class TestDashboard:

    @pytest.fixture
    def mock_root(self):
        """Mock tkinter root window."""
        root = MagicMock()
        return root

    @pytest.fixture
    def temp_journal_dir(self, tmp_path):
        """Create a temporary directory simulating the game journal path."""
        d = tmp_path / "journal"
        d.mkdir()
        # Create a dummy Status.json
        status_file = d / "Status.json"
        status_file.write_text(
            json.dumps(
                {"timestamp": "2026-01-25T12:00:00Z", "event": "Status", "Flags": 12345}
            )
        )
        return d

    def test_start_logic_windows(self, mock_root, temp_journal_dir):
        """Verify observer setup on Windows platform."""
        with patch("sys.platform", "win32"), patch(
            "dashboard.Observer"
        ) as mock_obs_cls, patch("dashboard.config") as mock_config:
            mock_config.get_str.return_value = str(temp_journal_dir)
            db = dashboard.Dashboard()

            success = db.start(mock_root, started=0)

            assert success is True
            assert db.observer is not None
            mock_obs_cls.return_value.start.assert_called_once()
            # Ensure a poll is scheduled to catch pre-existing data
            mock_root.after.assert_called()

    def test_start_logic_linux_polling(self, mock_root, temp_journal_dir):
        """Verify polling behavior on Linux/non-Windows platforms."""
        with patch("sys.platform", "linux"), patch("dashboard.config") as mock_config:
            mock_config.get_str.return_value = str(temp_journal_dir)
            db = dashboard.Dashboard()

            success = db.start(mock_root, started=0)

            assert success is True
            assert db.observer is None  # Should be None on Linux
            # Ensure the polling loop is started
            mock_root.after.assert_called()

    def test_process_valid_json(self, mock_root, temp_journal_dir):
        """Verify Status.json content is parsed and triggers a UI event."""
        db = dashboard.Dashboard()
        db.currentdir = str(temp_journal_dir)
        db.root = mock_root
        db.session_start = 0  # Ensure timestamp check passes

        db.process()

        assert db.status["event"] == "Status"
        mock_root.event_generate.assert_called_with("<<DashboardEvent>>", when="tail")

    def test_process_stale_data_filter(self, mock_root, temp_journal_dir):
        """Verify that status updates from previous sessions are ignored."""
        db = dashboard.Dashboard()
        db.currentdir = str(temp_journal_dir)
        db.root = mock_root

        # Set session start to a future date relative to the file timestamp
        db.session_start = 2000000000

        db.process()

        # Status should remain empty because file timestamp < session_start
        assert db.status == {}
        mock_root.event_generate.assert_not_called()

    def test_poll_recursion(self, mock_root):
        """Verify that poll schedules itself for the next interval."""
        db = dashboard.Dashboard()
        db.root = mock_root
        db.currentdir = "/fake/dir"

        with patch.object(db, "process"):
            db.poll(first_time=False)

            # Should call after() to schedule the next poll in 1000ms
            mock_root.after.assert_called_with(1000, db.poll)
