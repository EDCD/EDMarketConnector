# flake8: noqa
# mypy: ignore-errors
"""Test outfitting."""

import pytest
import json
from unittest.mock import patch
import outfitting


@pytest.fixture
def mock_modules_json(tmp_path):
    """Create a dummy modules.json file for the lookup function."""
    data = {
        "hpt_beamlaser_fixed_medium": {"mass": 4.0},
        "federation_dropship_armour_grade1": {"mass": 0.0},
        "int_engine_size2_class1": {"mass": 2.0},
    }
    modules_path = tmp_path / "modules.json"
    modules_path.write_text(json.dumps(data))
    return modules_path


class TestOutfitting:

    def test_lookup_armour(self, mock_modules_json):
        """Verify that ship-specific armour is parsed correctly."""
        module = {"id": 100, "name": "Federation_Dropship_Armour_Grade1"}
        # Ship map uses internal symbol -> Display Name
        ship_map = {"federation_dropship": "Federal Dropship"}

        with patch("outfitting.config.app_dir_path", mock_modules_json.parent):
            # Reset moduledata for the test
            outfitting.moduledata = {}
            result = outfitting.lookup(module, ship_map)

            assert result["category"] == "standard"
            assert result["ship"] == "Federal Dropship"
            assert result["name"] == "Lightweight Alloy"  # From armour_map
            assert result["rating"] == "I"

    def test_lookup_hardpoint_weapon(self, mock_modules_json):
        """Verify hardpoint parsing for standard weapons."""
        module = {"id": 200, "name": "Hpt_BeamLaser_Fixed_Medium"}

        with patch("outfitting.config.app_dir_path", mock_modules_json.parent):
            outfitting.moduledata = {}
            result = outfitting.lookup(module, {})

            assert result["category"] == "hardpoint"
            assert result["name"] == "Beam Laser"
            assert result["mount"] == "Fixed"
            assert result["class"] == "2"
            assert result["rating"] == "D"  # Assuming D is mapped for Medium Fixed Beam

    def test_lookup_skip_cosmetics(self, mock_modules_json):
        """Verify that paintjobs and decals return None as uninteresting."""
        module = {"id": 300, "name": "PaintJob_Anaconda_Default"}

        with patch("outfitting.config.app_dir_path", mock_modules_json.parent):
            result = outfitting.lookup(module, {})
            assert result is None

    def test_lookup_error_missing_name(self):
        """Verify ValueError is raised if the name field is missing."""
        with pytest.raises(ValueError, match="missing a 'name' field"):
            outfitting.lookup({"id": 400}, {})

    def test_lookup_unknown_prefix(self, mock_modules_json):
        """Verify that an unknown module prefix triggers a ValueError."""
        module = {"id": 500, "name": "Unknown_Module_Size1_Class1"}

        with patch("outfitting.config.app_dir_path", mock_modules_json.parent):
            with pytest.raises(ValueError, match="Unknown prefix"):
                outfitting.lookup(module, {})

    @patch("outfitting.lookup")
    def test_export_structure(self, mock_lookup, tmp_path):
        """Verify the CSV export header and row generation."""
        mock_lookup.return_value = {
            "category": "hardpoint",
            "name": "Laser",
            "mount": "Fixed",
            "guidance": "",
            "ship": "",
            "class": "1",
            "rating": "E",
            "id": 123,
        }

        data = {
            "lastSystem": {"name": "Sol"},
            "lastStarport": {
                "name": "Daedalus",
                "modules": {"1": {"id": 1, "name": "M_Name"}},
            },
            "timestamp": "2026-01-25",
        }

        export_file = tmp_path / "outfitting.csv"
        outfitting.export(data, str(export_file))

        content = export_file.read_text()
        assert "System,Station,Category,Name" in content
        assert "Sol,Daedalus, hardpoint, Laser" in content


@pytest.fixture(autouse=True)
def setup_moduledata(tmp_path):
    """Global setup for moduledata to satisfy the __debug__ mass checks."""
    mock_json_content = {
        "hpt_slugshot_fixed_large_range": {"mass": 8.0},
        "int_guardianfsdbooster_size5": {"mass": 0.0},
        "int_guardianpowerplant_size5": {"mass": 20.0},
        "hpt_plasma_pointdefence_turret_tiny": {"mass": 0.5},
        "int_dronecontrol_collection_size1_class1": {"mass": 2.0},
        "int_hyperdrive_overcharge_size6_class3": {"mass": 40.0},
    }
    modules_json = tmp_path / "modules.json"
    modules_json.write_text(json.dumps(mock_json_content))

    with patch("outfitting.config.app_dir_path", tmp_path):
        outfitting.moduledata = {}  # Force reload
        yield


class TestOutfittingAdvanced:

    def test_lookup_guardian_internal_no_class(self):
        """Verify internal Guardian modules that lack a 'Class' in the symbol."""
        # Guardian FSD Boosters only have Size, no Class (e.g., Int_GuardianFSDBooster_Size5)
        module = {"id": 1002, "name": "Int_GuardianFSDBooster_Size5"}

        result = outfitting.lookup(module, {})
        assert result["name"] == "Guardian FSD Booster"
        assert result["class"] == "5"
        assert result["rating"] == "H"  # Hardcoded in lookup logic

    def test_lookup_drone_control_normalization(self):
        """Verify 'int' is popped for drone controllers to match standard_map."""
        module = {"id": 1005, "name": "Int_DroneControl_Collection_Size1_Class1"}

        result = outfitting.lookup(module, {})
        assert result["category"] == "internal"
        assert result["name"] == "Collector Limpet Controller"
        assert result["class"] == "1"
