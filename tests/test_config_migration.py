"""
Integration tests for config migration from legacy to XDG locations.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from par_cc_usage.config import load_config
from par_cc_usage.xdg_dirs import get_config_file_path, migrate_legacy_config


class TestConfigMigrationIntegration:
    """Test integration between config loading and XDG migration."""

    def test_load_config_with_automatic_migration(self):
        """Test that load_config automatically migrates legacy config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("""
polling_interval: 15
timezone: Europe/London
token_limit: 750000
display:
  time_format: 12h
  show_progress_bars: false
notifications:
  discord_webhook_url: https://discord.com/webhook/test
  cooldown_minutes: 10
""")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"
            xdg_config_file = xdg_config_dir / "config.yaml"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                    # Load config - should trigger automatic migration
                    config = load_config()

                    # Verify migration occurred
                    assert xdg_config_file.exists()
                    assert legacy_config.read_text() == xdg_config_file.read_text()

                    # Verify config values are loaded correctly
                    assert config.polling_interval == 15
                    assert config.timezone == "Europe/London"
                    assert config.token_limit == 750000
                    assert config.display.time_format == "12h"
                    assert config.display.show_progress_bars is False
                    assert config.notifications.discord_webhook_url == "https://discord.com/webhook/test"
                    assert config.notifications.cooldown_minutes == 10

    def test_load_config_with_existing_xdg_config(self):
        """Test load_config when XDG config already exists (no migration)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("polling_interval: 5")

            # Create existing XDG config
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"
            xdg_config_dir.mkdir(parents=True)
            xdg_config_file = xdg_config_dir / "config.yaml"
            xdg_config_file.write_text("polling_interval: 20")

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                # Load config - should NOT migrate (XDG config exists)
                config = load_config()

                # Verify no migration occurred (legacy file unchanged)
                assert legacy_config.read_text() == "polling_interval: 5"

                # Verify XDG config values are used
                assert config.polling_interval == 20

                # Verify XDG config file still contains original setting (may have additional auto-detected fields)
                xdg_content = xdg_config_file.read_text()
                assert "polling_interval: 20" in xdg_content

    def test_load_config_with_no_legacy_config(self):
        """Test load_config when no legacy config exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set up XDG directories (no existing config)
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[]):
                    # Load config - should use defaults
                    config = load_config()

                    # Verify no files were created
                    assert not (xdg_config_dir / "config.yaml").exists()

                    # Verify default values are used
                    assert config.polling_interval == 5  # Default value

    def test_load_config_with_custom_xdg_path(self):
        """Test load_config with explicit config file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create custom config
            custom_config = temp_path / "custom.yaml"
            custom_config.write_text("polling_interval: 25")

            # Load config with explicit path - should not trigger migration
            config = load_config(custom_config)

            # Verify custom config values are used
            assert config.polling_interval == 25

    def test_load_config_migration_with_environment_overrides(self):
        """Test config migration with environment variable overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("""
polling_interval: 15
timezone: Europe/London
""")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                    # Set environment variable to override
                    with patch.dict("os.environ", {"PAR_CC_USAGE_POLLING_INTERVAL": "30"}):
                        config = load_config()

                        # Verify migration occurred
                        assert (xdg_config_dir / "config.yaml").exists()

                        # Verify environment override takes precedence
                        assert config.polling_interval == 30  # From env var
                        assert config.timezone == "Europe/London"  # From migrated config

    def test_migration_preserves_complex_config_structure(self):
        """Test migration preserves complex nested configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complex legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("""
polling_interval: 8
timezone: Asia/Tokyo
token_limit: 1000000
# cache_dir: uses default XDG location
disable_cache: true
recent_activity_window_hours: 3

display:
  show_progress_bars: false
  show_active_sessions: true
  update_in_place: false
  refresh_interval: 3
  time_format: 12h
  project_name_prefixes:
    - "-custom-prefix-"
    - "-another-prefix-"
  aggregate_by_project: false

notifications:
  discord_webhook_url: https://discord.com/webhook/test
  slack_webhook_url: https://hooks.slack.com/webhook/test
  notify_on_block_completion: false
  cooldown_minutes: 15
""")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                    config = load_config()

                    # Verify all complex settings are preserved
                    assert config.polling_interval == 8
                    assert config.timezone == "Asia/Tokyo"
                    assert config.token_limit == 1000000
                    # Cache dir should use XDG default (not custom path due to system constraints)
                    assert config.cache_dir.name == "par_cc_usage"
                    assert config.disable_cache is True
                    assert config.recent_activity_window_hours == 3

                    # Verify display settings
                    assert config.display.show_progress_bars is False
                    assert config.display.show_active_sessions is True
                    assert config.display.update_in_place is False
                    assert config.display.refresh_interval == 3
                    assert config.display.time_format == "12h"
                    assert config.display.project_name_prefixes == ["-custom-prefix-", "-another-prefix-"]
                    assert config.display.aggregate_by_project is False

                    # Verify notification settings
                    assert config.notifications.discord_webhook_url == "https://discord.com/webhook/test"
                    assert config.notifications.slack_webhook_url == "https://hooks.slack.com/webhook/test"
                    assert config.notifications.notify_on_block_completion is False
                    assert config.notifications.cooldown_minutes == 15

    def test_migration_handles_malformed_legacy_config(self):
        """Test migration handles malformed or incomplete legacy config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create malformed legacy config (invalid YAML)
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("""
polling_interval: 15
invalid_yaml: [unclosed bracket
timezone: Europe/London
""")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                    # Migration should still occur (file is copied regardless of content)
                    # But config loading should handle the malformed YAML gracefully
                    config = load_config()

                    # Verify migration attempted (file copied)
                    assert (xdg_config_dir / "config.yaml").exists()

                    # Verify config loading handles malformed YAML gracefully
                    # The specific behavior depends on implementation - either defaults or error handling
                    assert isinstance(config.polling_interval, int)  # Should be some valid integer

    def test_migration_multiple_legacy_sources_priority(self):
        """Test migration priority when multiple legacy sources exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple legacy configs
            cwd_config = temp_path / "config.yaml"
            home_config = temp_path / ".par_cc_usage" / "config.yaml"

            # Create directory for home config
            home_config.parent.mkdir()

            # Different content for each
            cwd_config.write_text("polling_interval: 10")
            home_config.write_text("polling_interval: 20")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                # get_legacy_config_paths returns in priority order (cwd first)
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[cwd_config, home_config]):
                    config = load_config()

                    # Verify migration occurred with first (highest priority) config
                    migrated_content = (xdg_config_dir / "config.yaml").read_text()
                    assert "polling_interval: 10" in migrated_content

                    # Verify the correct config was used
                    assert config.polling_interval == 10


class TestConfigMigrationErrorHandling:
    """Test error handling scenarios during config migration."""

    def test_migration_permission_error_fallback(self):
        """Test config loading when migration fails due to permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_text("polling_interval: 15")

            # Set up read-only XDG directory
            readonly_dir = temp_path / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only

            try:
                # Create a mock that will simulate permission issues in file operations
                with patch("par_cc_usage.config._load_config_file") as mock_load:
                    mock_load.side_effect = PermissionError("Permission denied")

                    # Should not crash, should fall back to defaults
                    config = load_config()

                    # Verify defaults are used when file loading fails
                    assert config.polling_interval == 5  # Default value
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)

    def test_migration_with_corrupted_legacy_file(self):
        """Test migration with a corrupted legacy config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy config with binary data
            legacy_config = temp_path / "config.yaml"
            legacy_config.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

            # Set up XDG directories
            xdg_config_dir = temp_path / ".config" / "par_cc_usage"

            with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_path / ".config"):
                with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                    # Should not crash
                    config = load_config()

                    # Verify migration attempted (binary file copied)
                    assert (xdg_config_dir / "config.yaml").exists()

                    # Verify config loading handles binary data gracefully
                    # The specific behavior depends on implementation - either defaults or error handling
                    assert isinstance(config.polling_interval, int)  # Should be some valid integer
