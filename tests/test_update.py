# flake8: noqa
# mypy: ignore-errors
"""Test the Updater."""

import pytest
import pathlib
import hashlib
import requests
from unittest.mock import MagicMock, patch
import semantic_version
import update


@pytest.fixture
def mock_directory(tmp_path):
    """Creates a temporary directory for update files."""
    d = tmp_path / "FDevIDs"
    d.mkdir()
    return d


class TestFileNormalization:
    def test_read_normalized_file_basic(self, tmp_path):
        """Verify that line endings are normalized to \n and whitespace is stripped."""
        p = tmp_path / "test.txt"
        # Write with CRLF and trailing spaces
        p.write_bytes(b"line1\r\nline2  \n")

        content, hash_val, newline = update.read_normalized_file(p)

        assert content == "line1\nline2"
        assert newline == "\r\n"
        assert hash_val == hashlib.sha256(b"line1\nline2").hexdigest()

    def test_read_normalized_file_missing(self, tmp_path):
        p = tmp_path / "nonexistent.txt"
        assert update.read_normalized_file(p) is None


class TestNetworkUpdates:
    @patch("requests.get")
    def test_fetch_remote_file_success(self, mock_get):
        """Verify remote file fetching and normalization."""
        mock_response = MagicMock()
        mock_response.text = "remote_line1\r\nremote_line2"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        content, hash_val = update.fetch_remote_file("http://fake.url")

        assert content == "remote_line1\nremote_line2"
        assert hash_val == hashlib.sha256(b"remote_line1\nremote_line2").hexdigest()

    @patch("requests.get")
    @patch("time.sleep", return_value=None)  # Speed up test
    def test_fetch_remote_file_retries(self, mock_sleep, mock_get):
        """Verify that fetch_remote_file retries on failure."""
        mock_get.side_effect = requests.RequestException("Timeout")

        result = update.fetch_remote_file("http://fake.url")

        assert result is None
        assert mock_get.call_count == 3  # Matches HTTP_RETRIES


class TestUpdateLogic:
    def test_update_single_file_no_change(self, mock_directory):
        """Verify no write occurs if hashes match."""
        filename = "commodity.csv"
        file_path = mock_directory / filename
        content = "already_up_to_date"
        file_path.write_text(content)

        remote_content = content
        remote_hash = hashlib.sha256(content.encode()).hexdigest()

        with patch(
            "update.fetch_remote_file", return_value=(remote_content, remote_hash)
        ):
            with patch.object(pathlib.Path, "write_text") as mock_write:
                update.update_single_file(mock_directory, filename, "http://url")
                mock_write.assert_not_called()

    def test_update_single_file_changes(self, mock_directory):
        """Verify file is updated when remote content differs."""
        filename = "commodity.csv"
        file_path = mock_directory / filename
        file_path.write_text("old_content")

        new_content = "new_content"
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()

        with patch("update.fetch_remote_file", return_value=(new_content, new_hash)):
            update.update_single_file(mock_directory, filename, "http://url")
            assert file_path.read_text() == "new_content"


class TestVersionChecking:
    @patch("requests.get")
    def test_check_appcast_newer_version(self, mock_get):
        """Verify that check_appcast identifies a newer version correctly."""
        # Mock XML response from Sparkle feed
        xml_data = """<?xml version="1.0" encoding="utf-8"?>
        <rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0">
            <channel>
                <item>
                    <title>Version 6.0.0</title>
                    <enclosure sparkle:version="6.0.0" sparkle:os="windows" />
                </item>
            </channel>
        </rss>"""

        mock_get.return_value.text = xml_data

        # Patch appversion_nobuild to be lower than the XML version
        with patch(
            "update.appversion_nobuild", return_value=semantic_version.Version("5.0.0")
        ):
            updater = update.Updater(provider="internal")
            result = updater.check_appcast()

            assert result is not None
            assert result.version == "6.0.0"
            assert result.title == "Version 6.0.0"

    @patch("requests.get")
    def test_check_appcast_older_version(self, mock_get):
        """Verify no version returned if local version is newer."""
        mock_response = MagicMock()
        mock_response.text = """<rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0">
                <channel><item>
                    <title>Old Version</title>
                    <enclosure sparkle:version="4.0.0" sparkle:os="windows" />
                </item></channel>
            </rss>"""

        mock_get.return_value = mock_response

        with patch(
            "update.appversion_nobuild", return_value=semantic_version.Version("5.0.0")
        ):
            updater = update.Updater(provider="internal")
            assert updater.check_appcast() is None


class TestWinSparkleInit:
    @patch("sys.platform", "win32")
    @patch("ctypes.cdll.WinSparkle", create=True)
    def test_winsparkle_init_success(self, mock_ws):
        """Verify WinSparkle initialization logic on Windows."""
        with patch("update.get_update_feed", return_value="http://feed"):
            with patch("update.appversion_nobuild", return_value="5.0.0"):
                updater = update.Updater(provider="external")
                assert mock_ws.win_sparkle_init.called
                assert mock_ws.win_sparkle_set_appcast_url.called
