# flake8: noqa
# mypy: ignore-errors
"""Test the collate system."""

import pytest
import csv
from unittest.mock import patch
import collate


class TestCollate:

    @pytest.fixture
    def mock_data(self):
        """Simulates the CAPI 'lastStarport' data structure."""
        return {
            "lastStarport": {
                "commodities": [
                    {
                        "id": 128049152,
                        "name": "Gold",
                        "categoryname": "Metals",
                        "locName": "Gold",
                    }
                ],
                "modules": {
                    "128000000": {
                        "id": 128000000,
                        "name": "Int_Engine_Size2_Class1",
                    }
                },
                "ships": {
                    "shipyard_list": {"1": {"id": 1, "name": "SideWinder"}},
                    "unavailable_list": [],
                },
            }
        }

    def test_addcommodities_new_entry(self, tmp_path, mock_data):
        """Verify adding a brand new commodity to the CSV."""
        fdev_dir = tmp_path / "FDevIDs"
        fdev_dir.mkdir()
        commodity_csv = fdev_dir / "commodity.csv"

        # Start with an empty CSV (only headers)
        with open(commodity_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "symbol", "category", "name"])
            writer.writeheader()

        with patch("collate.config.app_dir_path", tmp_path):
            collate.addcommodities(mock_data)

        # Verify content
        with open(commodity_csv, "r") as f:
            reader = list(csv.DictReader(f))
            assert len(reader) == 1
            assert reader[0]["symbol"] == "Gold"
            assert reader[0]["id"] == "128049152"

    def test_addcommodities_mismatch_error(self, tmp_path, mock_data):
        """Ensure ValueError is raised if new data conflicts with existing symbol/name."""
        fdev_dir = tmp_path / "FDevIDs"
        fdev_dir.mkdir()
        commodity_csv = fdev_dir / "commodity.csv"

        # Existing data with same ID but different symbol
        with open(commodity_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "symbol", "category", "name"])
            writer.writeheader()
            writer.writerow(
                {
                    "id": 128049152,
                    "symbol": "Silver",
                    "category": "Metals",
                    "name": "Silver",
                }
            )

        with patch("collate.config.app_dir_path", tmp_path):
            with pytest.raises(ValueError, match="128049152"):
                collate.addcommodities(mock_data)

    @patch("collate.outfitting.lookup")
    def test_addmodules_sanity_check(self, mock_lookup, tmp_path, mock_data):
        """Verify addmodules raises ValueError if the dictionary key doesn't match the inner ID."""
        # Corrupt the mock data
        mock_data["lastStarport"]["modules"] = {"999": {"id": 111, "name": "WrongID"}}

        with pytest.raises(ValueError, match="id: 999 != 111"):
            collate.addmodules(mock_data)
