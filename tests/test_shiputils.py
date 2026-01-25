# flake8: noqa
# mypy: ignore-errors
"""Test util_ships."""

from unittest.mock import patch
import util_ships


class TestShipUtils:

    def test_ship_file_name_basic(self):
        """Verify standard ship names are returned correctly."""
        # 'SideWinder' is in the ship_name_map as 'Sidewinder'
        assert util_ships.ship_file_name(None, "SideWinder") == "Sidewinder"
        assert (
            util_ships.ship_file_name("My Corvette", "Federal_Corvette")
            == "My Corvette"
        )

    def test_ship_file_name_suffix_removal(self):
        """Verify that any file suffixes provided in the name are stripped."""
        assert util_ships.ship_file_name("MyShip.txt", "Sidewinder") == "MyShip"
        assert util_ships.ship_file_name("Config.json", "CobraMkIII") == "Config"

    @patch("sys.platform", "win32")
    @patch("os.path.isreserved")
    def test_ship_file_name_reserved_windows(self, mock_isreserved):
        """Verify that reserved Windows names get an underscore suffix."""
        mock_isreserved.return_value = True

        # If the ship name is 'CON' (a reserved Windows device name)
        assert util_ships.ship_file_name("CON", "Sidewinder") == "CON_"

    @patch("sys.platform", "linux")
    @patch("os.path.isreserved", create=True)
    def test_ship_file_name_reserved_linux(self, mock_isreserved):
        """Verify that reserved names are NOT suffixed on non-Windows platforms."""
        # Even if os.path.isreserved (hypothetically) exists/returns True
        mock_isreserved.return_value = True

        assert util_ships.ship_file_name("CON", "Sidewinder") == "CON"

    def test_ship_file_name_strip_and_empty(self):
        """Verify whitespace is stripped and fallback logic works."""
        assert util_ships.ship_file_name("   Cobra   ", "CobraMkIII") == "Cobra"
        # If ship_name is empty string, it should fall back to type map
        assert util_ships.ship_file_name("", "anaconda") == "Anaconda"
