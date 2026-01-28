# flake8: noqa
# mypy: ignore-errors
"""Test the Config system."""

import sys
import tomli_w
import semantic_version
from unittest.mock import patch, MagicMock, mock_open

import config
from config import (
    Config,
    git_shorthash_from_head,
    appversion,
    appversion_nobuild,
)


class TestGitFunctions:
    @patch("subprocess.run")
    def test_git_shorthash_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(stdout="a1b2c3d\n", stderr=None),  # rev-parse
            MagicMock(stdout="", stderr=None),  # diff (clean)
        ]
        assert git_shorthash_from_head() == "a1b2c3d"

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_git_shorthash_dirty(self, mock_exists, mock_run):
        mock_exists.return_value = True
        # Simulate the single call to git describe --dirty
        mock_run.return_value = MagicMock(
            stdout="a1b2c3d.DIRTY\n",
            stderr="",
            returncode=0
        )
        assert git_shorthash_from_head() == "a1b2c3d.DIRTY"

    @patch("subprocess.run")
    def test_git_shorthash_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError("git not found")
        assert git_shorthash_from_head() is None


class TestAppVersion:
    def setup_method(self):
        # Reset cached version before each test
        config._cached_version = None


class TestConfigClass:

    def test_init_creates_default_toml(self, mock_app_dir):
        """Test that initializing Config creates config.toml if missing."""
        toml_file = mock_app_dir / "config.toml"
        assert not toml_file.exists()

        with patch("config.Config._init_platform"):
            Config(mock_app_dir)

        assert toml_file.exists()
        assert "generated" in toml_file.read_text()

    def test_load_existing_settings(self, mock_app_dir):
        toml_file = mock_app_dir / "config.toml"
        data = {
            "settings": {
                "theme": "dark",
                # Need plugin_dir or __init__ will auto-add it
                "plugin_dir": str(mock_app_dir / "plugins"),
            }
        }
        with open(toml_file, "wb") as f:
            tomli_w.dump(data, f)

        with patch("config.Config._init_platform"):
            cfg = Config(mock_app_dir)

        assert cfg.get("theme") == "dark"

    def test_set_saves_to_disk(self, mock_app_dir):
        """Test that set() updates memory and writes to disk."""
        with patch("config.Config._init_platform"):
            c = Config(mock_app_dir)

        toml_path = c.toml_path
        c.set("saved_value", "persistence_check")

        # Read file directly to verify
        with open(toml_path, "rb") as f:
            import tomllib

            data = tomllib.load(f)

        assert data["settings"]["saved_value"] == "persistence_check"

    def test_recovery_broken_toml(self, mock_app_dir):
        """Test that the system recovers from a corrupted TOML file."""
        toml_path = mock_app_dir / "config.toml"

        # Write garbage
        with open(toml_path, "w") as f:
            f.write("This is not valid TOML { [ } ]")

        with patch("config.Config._init_platform"):
            cfg = Config(mock_app_dir)

        assert "plugin_dir" in cfg.settings

        # The broken file should be renamed
        broken_files = list(mock_app_dir.glob("config.toml.broken.*"))
        assert len(broken_files) > 0

    def test_recovery_from_backup(self, mock_app_dir):
        """Test recovering from .bak if .toml is broken."""
        toml_path = mock_app_dir / "config.toml"
        bak_path = mock_app_dir / "config.toml.bak"

        with open(toml_path, "w") as f:
            f.write("Garbage")

        valid_data = {
            "settings": {"recovered": True, "plugin_dir": str(mock_app_dir / "plugins")}
        }
        with open(bak_path, "wb") as f:
            tomli_w.dump(valid_data, f)

        with patch("config.Config._init_platform"):
            cfg = Config(mock_app_dir)

        assert cfg.get_bool("recovered") is True

        # This confirms that the rename `bak.replace(self.toml_path)` inside `_load` worked.
        # If this fails, it means `tomllib.load` on the backup file failed.
        assert not bak_path.exists()
        assert toml_path.exists()

    def test_reload_from_path(self, mock_app_dir, tmp_path):
        """Test hot-swapping the config file."""
        with patch("config.Config._init_platform"):
            c = Config(mock_app_dir)

        # Create a second config file elsewhere
        alt_dir = tmp_path / "alt"
        alt_dir.mkdir()
        alt_config = alt_dir / "alternate.toml"

        data = {
            "settings": {
                "mode": "alternate",
                "plugin_dir": str(mock_app_dir / "plugins"),
            }
        }
        with open(alt_config, "wb") as f:
            tomli_w.dump(data, f)

        # Reload
        c.reload_from_path(alt_config)

        assert c.toml_path == alt_config
        assert c.get("mode") == "alternate"


def test_init_platform_calls_linux_helper(mock_app_dir):
    with patch("sys.platform", "linux"):
        mock_module = sys.modules["config.linux"]

        # We must NOT patch _init_platform here, because we want it to run
        # and call the mocked module
        Config(mock_app_dir)

        mock_module.linux_helper.assert_called_once()
