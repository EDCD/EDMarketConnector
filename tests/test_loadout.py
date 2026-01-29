# flake8: noqa
# mypy: ignore-errors
"""Test Loadout system."""

import pytest
from unittest.mock import patch
import loadout


class TestLoadout:

    @pytest.fixture
    def mock_capi_data(self):
        """Simulates the CAPI data structure required for export."""
        return {
            "ship": {
                "name": "Anaconda",
                "shipName": "Starship One",
                "modules": {"Slot01": {"module": {"id": 1, "name": "Int_Engine"}}},
            },
            "commander": {"name": "Tester"},
            "lastSystem": {"name": "Sol"},
        }

    @patch("loadout.companion.ship")
    @patch("loadout.json.dumps")
    def test_export_with_requested_filename(
        self, mock_dumps, mock_ship_func, mock_capi_data, tmp_path
    ):
        """Verify that providing a filename bypasses auto-naming and writes directly."""
        mock_ship_func.return_value = {"id": "mock_ship"}
        mock_dumps.return_value = '{"dummy": "json"}'

        target_file = tmp_path / "manual_export.json"

        loadout.export(mock_capi_data, requested_filename=str(target_file))

        assert target_file.exists()
        assert target_file.read_text() == '{"dummy": "json"}'
