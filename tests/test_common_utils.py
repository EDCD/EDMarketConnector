# flake8: noqa
# mypy: ignore-errors
"""Test the common utils module."""

from unittest.mock import MagicMock, patch
import common_utils


class TestCommonUtils:

    def test_log_locale(self):
        """Verify that log_locale calls the logger with locale information."""
        with patch("common_utils.logger.debug") as mock_log:
            common_utils.log_locale("TestPrefix")

            assert mock_log.called
            args, _ = mock_log.call_args
            assert "TestPrefix" in args[0]

    def test_ensure_on_screen_non_windows(self):
        """Verify that the function safely does nothing on non-Windows platforms."""
        # Force the platform to something other than win32
        with patch("sys.platform", "darwin"):
            mock_self = MagicMock()
            mock_parent = MagicMock()

            common_utils.ensure_on_screen(mock_self, mock_parent)

            # On non-win32, the function should return early without calling geometry
            mock_self.geometry.assert_not_called()

    def test_ensure_on_screen_exception_handling(self):
        """Ensure that if win32api fails, the function doesn't crash the app."""
        with patch("sys.platform", "win32"):
            mock_win32api = MagicMock()
            mock_win32api.MonitorFromWindow.side_effect = Exception("OS Error")

            with patch.dict("sys.modules", {"win32api": mock_win32api}):
                mock_self = MagicMock()
                common_utils.ensure_on_screen(mock_self, MagicMock())

                # Geometry should not be set if calculation failed
                mock_self.geometry.assert_not_called()
