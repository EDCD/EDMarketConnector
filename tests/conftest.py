# flake8: noqa
# mypy: ignore-errors
"""Needed Mocking of the Configuration System for Testing."""

import sys
import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_dependencies():
    """
    Mock external dependencies to allow config/__init__.py to import without the actual files existing.
    """
    mock_constants = MagicMock()
    mock_constants.GITVERSION_FILE = ".gitversion"
    mock_constants.appname = "EDMarketConnector"
    mock_constants.applongname = "EDMarketConnector"
    sys.modules["constants"] = mock_constants

    # This prevents ImportErrors when the Config class tries to import platform helpers
    sys.modules["config.linux"] = MagicMock()
    sys.modules["config.windows"] = MagicMock()

    yield

    sys.modules.pop("constants", None)
    sys.modules.pop("config.linux", None)
    sys.modules.pop("config.windows", None)


@pytest.fixture
def mock_app_dir(tmp_path):
    """Create a temporary directory acting as the application directory."""
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def mock_config_and_data():
    # Mock config module
    mock_cfg_mod = MagicMock()
    mock_cfg_mod.config.get_int.return_value = 1700000000  # Fixed timestamp
    mock_cfg_mod.config.get_str.return_value = "."  # Current dir for output
    sys.modules["config"] = mock_cfg_mod

    # Mock edmc_data
    mock_data_mod = MagicMock()
    mock_data_mod.commodity_bracketmap = {0: "", 1: "Low", 2: "Med", 3: "High"}
    sys.modules["edmc_data"] = mock_data_mod

    yield
