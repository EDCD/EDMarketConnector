# flake8: noqa
# mypy: ignore-errors
"""Test the Dashboard for reading Status.json."""

import pytest
import json
import sys
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

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific logic")
    def test_start_logic_windows(self, mock_root, temp_journal_dir):
        """Verify observer setup on Windows platform."""
        with patch("sys.platform", "win32"), patch(
            "dashboard.Observer"
        ) as mock_obs_cls, patch("dashboard.config") as mock_config:
            mock_config.shutting_down = False
            mock_config.get_str.return_value = str(temp_journal_dir)
            db = dashboard.Dashboard()
            success = db.start(mock_root, started=0)

            try:
                assert success is True
                assert db.observer is not None
                mock_obs_cls.return_value.start.assert_called_once()
                assert db.status["event"] == "Status"
                mock_root.event_generate.assert_called_with(
                    "<<DashboardEvent>>", when="tail"
                )
            finally:
                db.stop()

    def test_start_logic_linux_polling(self, mock_root, temp_journal_dir):
        """Verify polling behavior on Linux/non-Windows platforms."""
        with patch("sys.platform", "linux"), patch(
            "dashboard.PollingObserver"
        ) as mock_poll_obs_cls, patch("dashboard.config") as mock_config:
            mock_config.shutting_down = False
            mock_config.get_str.return_value = str(temp_journal_dir)
            db = dashboard.Dashboard()

            success = db.start(mock_root, started=0)

            try:
                assert success is True
                assert db.observer is not None
                mock_poll_obs_cls.return_value.start.assert_called_once()
                assert db.status["event"] == "Status"
            finally:
                db.stop()

    def test_process_valid_json(self, mock_root, temp_journal_dir):
        """Verify Status.json content is parsed and triggers a UI event."""
        with patch("dashboard.config") as mock_config:
            mock_config.shutting_down = False
            db = dashboard.Dashboard()
            db.currentdir = temp_journal_dir
            db.root = mock_root
            db.session_start = 0

            db.process()

            assert db.status["event"] == "Status"
            mock_root.event_generate.assert_called_with(
                "<<DashboardEvent>>", when="tail"
            )

    def test_process_stale_data_filter(self, mock_root, temp_journal_dir):
        """Verify that status updates from previous sessions are ignored."""
        with patch("dashboard.config") as mock_config:
            mock_config.shutting_down = False
            db = dashboard.Dashboard()
            db.currentdir = temp_journal_dir
            db.root = mock_root

            # Set session start to a future date relative to the file timestamp
            db.session_start = 2000000000

            db.process()

            # Status should remain empty because file timestamp < session_start
            assert db.status == {}
            mock_root.event_generate.assert_not_called()

    def test_process_midpoint_flush_resilience(self, mock_root, temp_journal_dir):
        """Verify resilience against json.JSONDecodeError when catching partial writes."""
        with patch("dashboard.config") as mock_config:
            mock_config.shutting_down = False
            db = dashboard.Dashboard()
            db.currentdir = temp_journal_dir
            db.root = mock_root
            db.session_start = 0
            status_file = temp_journal_dir / "Status.json"
            status_file.write_text(
                '{ "timestamp": "2026-01-25T12:00:00Z", truncated_json...'
            )

            db.process()

            assert db.status == {}
            mock_root.event_generate.assert_not_called()
