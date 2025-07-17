"""
Tests for the xdg_dirs module.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from par_cc_usage.xdg_dirs import (
    get_cache_dir,
    get_cache_file_path,
    get_config_dir,
    get_config_file_path,
    get_data_dir,
    get_data_file_path,
    get_legacy_config_paths,
    migrate_legacy_config,
    ensure_xdg_directories,
)


class TestXDGDirectories:
    """Test XDG directory functions."""

    def test_get_config_dir(self):
        """Test get_config_dir returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_config_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.config")
            result = get_config_dir()
            assert result == Path("/home/user/.config/par_cc_usage")

    def test_get_cache_dir(self):
        """Test get_cache_dir returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_cache_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.cache")
            result = get_cache_dir()
            assert result == Path("/home/user/.cache/par_cc_usage")

    def test_get_data_dir(self):
        """Test get_data_dir returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_data_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.local/share")
            result = get_data_dir()
            assert result == Path("/home/user/.local/share/par_cc_usage")

    def test_get_config_file_path(self):
        """Test get_config_file_path returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_config_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.config")
            result = get_config_file_path()
            assert result == Path("/home/user/.config/par_cc_usage/config.yaml")

    def test_get_cache_file_path(self):
        """Test get_cache_file_path returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_cache_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.cache")
            result = get_cache_file_path("test.json")
            assert result == Path("/home/user/.cache/par_cc_usage/test.json")

    def test_get_data_file_path(self):
        """Test get_data_file_path returns correct path."""
        with patch("par_cc_usage.xdg_dirs.xdg_data_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.local/share")
            result = get_data_file_path("data.db")
            assert result == Path("/home/user/.local/share/par_cc_usage/data.db")

    def test_ensure_xdg_directories(self):
        """Test ensure_xdg_directories creates directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("par_cc_usage.xdg_dirs.get_config_dir", return_value=temp_path / "config"):
                with patch("par_cc_usage.xdg_dirs.get_cache_dir", return_value=temp_path / "cache"):
                    with patch("par_cc_usage.xdg_dirs.get_data_dir", return_value=temp_path / "data"):
                        ensure_xdg_directories()

                        assert (temp_path / "config").exists()
                        assert (temp_path / "cache").exists()
                        assert (temp_path / "data").exists()

    def test_ensure_xdg_directories_already_exist(self):
        """Test ensure_xdg_directories when directories already exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Pre-create directories
            (temp_path / "config").mkdir()
            (temp_path / "cache").mkdir()
            (temp_path / "data").mkdir()

            with patch("par_cc_usage.xdg_dirs.get_config_dir", return_value=temp_path / "config"):
                with patch("par_cc_usage.xdg_dirs.get_cache_dir", return_value=temp_path / "cache"):
                    with patch("par_cc_usage.xdg_dirs.get_data_dir", return_value=temp_path / "data"):
                        # Should not raise error
                        ensure_xdg_directories()

                        assert (temp_path / "config").exists()
                        assert (temp_path / "cache").exists()
                        assert (temp_path / "data").exists()

    def test_ensure_xdg_directories_nested_creation(self):
        """Test ensure_xdg_directories creates nested directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test deeply nested paths
            with patch("par_cc_usage.xdg_dirs.get_config_dir", return_value=temp_path / "a" / "b" / "config"):
                with patch("par_cc_usage.xdg_dirs.get_cache_dir", return_value=temp_path / "x" / "y" / "z" / "cache"):
                    with patch("par_cc_usage.xdg_dirs.get_data_dir", return_value=temp_path / "deep" / "nested" / "data"):
                        ensure_xdg_directories()

                        assert (temp_path / "a" / "b" / "config").exists()
                        assert (temp_path / "x" / "y" / "z" / "cache").exists()
                        assert (temp_path / "deep" / "nested" / "data").exists()


class TestXDGEnvironmentVariables:
    """Test XDG directory functions with environment variable overrides."""

    def test_custom_xdg_config_home(self):
        """Test get_config_dir with custom XDG_CONFIG_HOME."""
        with patch("par_cc_usage.xdg_dirs.xdg_config_home") as mock_xdg:
            mock_xdg.return_value = Path("/custom/config")
            result = get_config_dir()
            assert result == Path("/custom/config/par_cc_usage")

    def test_custom_xdg_cache_home(self):
        """Test get_cache_dir with custom XDG_CACHE_HOME."""
        with patch("par_cc_usage.xdg_dirs.xdg_cache_home") as mock_xdg:
            mock_xdg.return_value = Path("/custom/cache")
            result = get_cache_dir()
            assert result == Path("/custom/cache/par_cc_usage")

    def test_custom_xdg_data_home(self):
        """Test get_data_dir with custom XDG_DATA_HOME."""
        with patch("par_cc_usage.xdg_dirs.xdg_data_home") as mock_xdg:
            mock_xdg.return_value = Path("/custom/data")
            result = get_data_dir()
            assert result == Path("/custom/data/par_cc_usage")


class TestXDGEdgeCases:
    """Test edge cases and error conditions for XDG functions."""

    def test_get_config_dir_with_special_characters(self):
        """Test get_config_dir with special characters in path."""
        with patch("par_cc_usage.xdg_dirs.xdg_config_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user name/.config")
            result = get_config_dir()
            assert result == Path("/home/user name/.config/par_cc_usage")

    def test_get_legacy_config_paths_current_directory(self):
        """Test get_legacy_config_paths includes current directory."""
        paths = get_legacy_config_paths()
        current_dir_config = Path.cwd() / "config.yaml"
        assert current_dir_config in paths

    def test_get_legacy_config_paths_home_directory(self):
        """Test get_legacy_config_paths includes home directory variant."""
        paths = get_legacy_config_paths()
        home_config = Path.home() / ".par_cc_usage" / "config.yaml"
        assert home_config in paths


class TestLegacyMigration:
    """Test legacy config migration."""

    def test_get_legacy_config_paths(self):
        """Test get_legacy_config_paths returns expected paths."""
        paths = get_legacy_config_paths()
        assert len(paths) >= 2
        assert any("config.yaml" in str(path) for path in paths)

    def test_migrate_legacy_config_success(self):
        """Test successful legacy config migration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "legacy_config.yaml"
            legacy_config.write_text("polling_interval: 10\ntimezone: UTC")

            # Set up XDG path
            xdg_config_dir = temp_path / "xdg_config"
            xdg_config_file = xdg_config_dir / "config.yaml"

            with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                result = migrate_legacy_config(legacy_config)

                assert result is True
                assert xdg_config_file.exists()
                assert xdg_config_file.read_text() == legacy_config.read_text()

    def test_migrate_legacy_config_no_legacy_file(self):
        """Test migration when legacy file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            legacy_config = temp_path / "nonexistent.yaml"

            result = migrate_legacy_config(legacy_config)
            assert result is False

    def test_migrate_legacy_config_xdg_exists(self):
        """Test migration when XDG config already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "legacy_config.yaml"
            legacy_config.write_text("polling_interval: 10")

            # Create existing XDG config
            xdg_config_dir = temp_path / "xdg_config"
            xdg_config_dir.mkdir()
            xdg_config_file = xdg_config_dir / "config.yaml"
            xdg_config_file.write_text("polling_interval: 20")

            with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                result = migrate_legacy_config(legacy_config)

                assert result is False
                # XDG config should remain unchanged
                assert xdg_config_file.read_text() == "polling_interval: 20"

    def test_migrate_legacy_config_preserves_permissions(self):
        """Test migration preserves file permissions and metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config with specific permissions
            legacy_config = temp_path / "legacy_config.yaml"
            legacy_config.write_text("polling_interval: 15")
            legacy_config.chmod(0o600)  # Restrictive permissions

            # Set up XDG path
            xdg_config_dir = temp_path / "xdg_config"
            xdg_config_file = xdg_config_dir / "config.yaml"

            with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                result = migrate_legacy_config(legacy_config)

                assert result is True
                assert xdg_config_file.exists()
                # Check that file content is preserved
                assert xdg_config_file.read_text() == "polling_interval: 15"
                # Check that permissions are preserved (on Unix systems)
                if hasattr(xdg_config_file, "stat"):
                    assert oct(xdg_config_file.stat().st_mode)[-3:] == "600"

    def test_migrate_legacy_config_empty_file(self):
        """Test migration of empty legacy config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create empty legacy config
            legacy_config = temp_path / "empty_config.yaml"
            legacy_config.write_text("")

            # Set up XDG path
            xdg_config_dir = temp_path / "xdg_config"
            xdg_config_file = xdg_config_dir / "config.yaml"

            with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                result = migrate_legacy_config(legacy_config)

                assert result is True
                assert xdg_config_file.exists()
                assert xdg_config_file.read_text() == ""

    def test_migrate_legacy_config_large_file(self):
        """Test migration of large legacy config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create large legacy config with lots of comments
            large_content = "# Large config file\n" * 1000 + "polling_interval: 30\n"
            legacy_config = temp_path / "large_config.yaml"
            legacy_config.write_text(large_content)

            # Set up XDG path
            xdg_config_dir = temp_path / "xdg_config"
            xdg_config_file = xdg_config_dir / "config.yaml"

            with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                result = migrate_legacy_config(legacy_config)

                assert result is True
                assert xdg_config_file.exists()
                assert xdg_config_file.read_text() == large_content

    def test_migrate_legacy_config_permission_error(self):
        """Test migration behavior when XDG directory creation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "legacy_config.yaml"
            legacy_config.write_text("polling_interval: 5")

            # Set up XDG path in a read-only directory
            readonly_dir = temp_path / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only
            xdg_config_file = readonly_dir / "config" / "config.yaml"

            try:
                with patch("par_cc_usage.xdg_dirs.get_config_file_path", return_value=xdg_config_file):
                    result = migrate_legacy_config(legacy_config)

                    # Should return False due to permission error
                    assert result is False
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)


class TestFilePaths:
    """Test file path utility functions."""

    def test_get_cache_file_path_simple(self):
        """Test get_cache_file_path with simple filename."""
        with patch("par_cc_usage.xdg_dirs.xdg_cache_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.cache")
            result = get_cache_file_path("file_states.json")
            assert result == Path("/home/user/.cache/par_cc_usage/file_states.json")

    def test_get_cache_file_path_with_subdirectory(self):
        """Test get_cache_file_path with subdirectory in filename."""
        with patch("par_cc_usage.xdg_dirs.xdg_cache_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.cache")
            result = get_cache_file_path("subdir/file.json")
            assert result == Path("/home/user/.cache/par_cc_usage/subdir/file.json")

    def test_get_data_file_path_database(self):
        """Test get_data_file_path with database file."""
        with patch("par_cc_usage.xdg_dirs.xdg_data_home") as mock_xdg:
            mock_xdg.return_value = Path("/home/user/.local/share")
            result = get_data_file_path("usage.db")
            assert result == Path("/home/user/.local/share/par_cc_usage/usage.db")


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_full_migration_workflow(self):
        """Test complete migration workflow from legacy to XDG."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set up mock XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"
            xdg_cache_dir = temp_path / ".cache" / "par_cc_usage"
            xdg_data_dir = temp_path / ".local" / "share" / "par_cc_usage"

            # Create legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("""
polling_interval: 10
timezone: UTC
token_limit: 500000
display:
  time_format: 12h
notifications:
  discord_webhook_url: https://example.com/webhook
""")

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.xdg_dirs.xdg_cache_home", return_value=temp_path / ".cache"):
                    with patch("par_cc_usage.xdg_dirs.xdg_data_home", return_value=temp_path / ".local" / "share"):
                        # Test directory creation
                        ensure_xdg_directories()
                        assert xdg_config_dir.exists()
                        assert xdg_cache_dir.exists()
                        assert xdg_data_dir.exists()

                        # Test migration
                        result = migrate_legacy_config(legacy_config)
                        assert result is True

                        # Verify migration
                        xdg_config_file = get_config_file_path()
                        assert xdg_config_file.exists()
                        assert xdg_config_file.read_text() == legacy_config.read_text()

    def test_multiple_legacy_locations(self):
        """Test behavior with multiple legacy config locations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple legacy configs
            legacy_configs = [
                temp_path / "config.yaml",
                temp_path / ".par_cc_usage" / "config.yaml",
            ]

            # Create parent directory for second config
            legacy_configs[1].parent.mkdir()

            # Write different content to each
            legacy_configs[0].write_text("polling_interval: 5")
            legacy_configs[1].write_text("polling_interval: 10")

            # Test that get_legacy_config_paths finds them
            with patch("pathlib.Path.cwd", return_value=temp_path):
                with patch("pathlib.Path.home", return_value=temp_path):
                    paths = get_legacy_config_paths()

                    # Should include both locations
                    assert legacy_configs[0] in paths
                    assert legacy_configs[1] in paths

    def test_concurrent_directory_creation(self):
        """Test ensure_xdg_directories with concurrent access simulation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Simulate partial directory creation (as if another process started)
            config_dir = temp_path / "config"
            config_dir.mkdir()

            with patch("par_cc_usage.xdg_dirs.get_config_dir", return_value=config_dir):
                with patch("par_cc_usage.xdg_dirs.get_cache_dir", return_value=temp_path / "cache"):
                    with patch("par_cc_usage.xdg_dirs.get_data_dir", return_value=temp_path / "data"):
                        # Should handle existing directory gracefully
                        ensure_xdg_directories()

                        assert config_dir.exists()
                        assert (temp_path / "cache").exists()
                        assert (temp_path / "data").exists()
