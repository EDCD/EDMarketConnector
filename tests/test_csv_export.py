# flake8: noqa
# mypy: ignore-errors
"""Test the CSV Export System."""

import pytest
import csv
import commodity


@pytest.fixture
def sample_capi_data():
    """Provides a standard CAPI data structure for testing."""
    return {
        "timestamp": "2024-01-01T12:00:00Z",
        "lastSystem": {"name": "Sol"},
        "lastStarport": {
            "name": "Daedalus",
            "commodities": [
                {
                    "id": 123,
                    "name": "Gold",
                    "sellPrice": 1000,
                    "buyPrice": 1100,
                    "demand": 500,
                    "demandBracket": 3,
                    "stock": 10,
                    "stockBracket": 1,
                    "meanPrice": 1050,
                }
            ],
        },
    }


class TestCSVExport:

    def test_delimiter_mapping(self, tmp_path, sample_capi_data):
        """Verify that 'kind' correctly changes the file delimiter."""
        kinds = [
            (commodity.COMMODITY_CSV, ","),
            (commodity.COMMODITY_TAB, "\t"),
            (commodity.COMMODITY_PIPE, "|"),
            (commodity.COMMODITY_SEMICOLON, ";"),
        ]

        for kind, expected_delim in kinds:
            fname = tmp_path / f"test_{kind}.txt"
            commodity.export(sample_capi_data, kind=kind, filename=fname)

            # Read first line to check delimiter
            content = fname.read_text(encoding="utf-8")
            assert expected_delim in content

    def test_legacy_csv_format_row_length(self, tmp_path, sample_capi_data):
        """COMMODITY_CSV (Legacy) should have 10 columns."""
        fname = tmp_path / "legacy.csv"
        commodity.export(sample_capi_data, kind=commodity.COMMODITY_CSV, filename=fname)

        with open(fname, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=",")
            header = next(reader)
            first_row = next(reader)

            assert len(header) == 10
            assert "Average" not in header
            assert len(first_row) == 10

    def test_new_format_row_length(self, tmp_path, sample_capi_data):
        """Other formats (TAB, PIPE, etc) should have 12 columns."""
        fname = tmp_path / "new_format.txt"
        commodity.export(sample_capi_data, kind=commodity.COMMODITY_TAB, filename=fname)

        with open(fname, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            first_row = next(reader)

            assert len(header) == 12
            assert "Average" in header
            assert "FDevID" in header
            assert len(first_row) == 12

    def test_data_value_mapping(self, tmp_path, sample_capi_data):
        """Check if specific fields like demandBracket are mapped via bracketmap."""
        fname = tmp_path / "data_check.csv"
        commodity.export(
            sample_capi_data, kind=commodity.COMMODITY_CSV_NEW, filename=fname
        )

        with open(fname, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=",")
            row = next(reader)

            assert row["System"] == "Sol"
            assert row["Commodity"] == "Gold"
            assert row["demandBracket"] == "High"  # Mapped from 3
            assert row["stockBracket"] == "Low"  # Mapped from 1
            assert row["FDevID"] == "123"

    def test_missing_data_handling(self, tmp_path):
        """Ensure the exporter handles None values gracefully by writing empty strings."""
        minimal_data = {
            "timestamp": "now",
            "lastSystem": {"name": "Sothis"},
            "lastStarport": {
                "name": "MiningHub",
                "commodities": [
                    {
                        "name": "Iron",
                        "sellPrice": None,
                        "buyPrice": None,
                        "demandBracket": None,
                        "stockBracket": None,
                    }
                ],
            },
        }
        fname = tmp_path / "empty.csv"
        commodity.export(minimal_data, kind=commodity.COMMODITY_CSV, filename=fname)

        with open(fname, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)

            # Indices for Sell, Buy, Demand, Supply
            # ['Sothis', 'MiningHub', 'Iron', '', '', '', '', '', '', 'now']
            assert row[3] == ""
            assert row[4] == ""
            assert row[5] == ""
            assert row[7] == ""
