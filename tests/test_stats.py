# flake8: noqa
# mypy: ignore-errors
"""Test stats system."""

import pytest
from unittest.mock import patch
import stats


@pytest.fixture
def mock_capi_data():
    """Simulates a full Frontier CAPI profile payload."""
    return {
        "commander": {
            "name": "Dave",
            "credits": 1000000,
            "debt": 0,
            "rank": {
                "combat": 3,  # Competent
                "trade": 0,  # Penniless
                "explore": 8,  # Elite
                "federation": 0,
                "empire": 0,
                "power": 0,
            },
            "currentShipId": 1,
        },
        "ships": [
            {
                "id": 0,
                "name": "SideWinder",
                "value": {"total": 30000},
                "starsystem": {"name": "Sol"},
                "station": {"name": "Daedalus"},
            },
            {
                "id": 1,
                "name": "CobraMkIII",
                "value": {"total": 300000},
                "starsystem": {"name": "Achenar"},
                "station": {"name": "Dawes Hub"},
            },
        ],
        "lastSystem": {"name": "Lave"},
        "docked": False,
    }


class TestStatsLogic:

    def test_status_rank_mapping(self, mock_capi_data):
        """Verify that integer ranks are correctly translated to human-readable strings."""
        # We need to mock translations 'tr.tl' to just return the input string
        with patch("stats.tr.tl", side_effect=lambda x: x):
            res = stats.status(mock_capi_data)

            # Index 0: Cmdr Name
            assert res[0] == ["Cmdr", "Dave"]
            # Index 1: Balance
            assert res[1] == ["Balance", "1000000"]
            # Combat Rank (Index 3 based on RANK_LINES_START)
            assert res[3] == ["Combat", "Competent"]
            # Explorer Rank (Elite check)
            assert res[5] == ["Explorer", "Elite"]

    def test_ships_sorting_current_first(self, mock_capi_data):
        """Verify the current ship is moved to the top of the list."""
        with patch("stats.ship_name_map", {}):
            ship_list = stats.ships(mock_capi_data)

            # CurrentShipId was 1 (Cobra), so Cobra should be first
            assert ship_list[0].type == "CobraMkIII"
            # Since the CMDR is NOT docked, the system should be 'lastSystem' (Lave)
            assert ship_list[0].system == "Lave"
            assert ship_list[0].station == ""

    def test_ships_docked_location(self, mock_capi_data):
        """Verify that when docked, the current ship shows its station."""
        mock_capi_data["commander"]["docked"] = True
        with patch("stats.ship_name_map", {}):
            ship_list = stats.ships(mock_capi_data)
            # When docked, it falls through to standard listify logic
            assert ship_list[0].system == "Achenar"
            assert ship_list[0].station == "Dawes Hub"
