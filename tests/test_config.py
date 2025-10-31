"""
Tests for the config module.
"""

from pathlib import Path
from unittest.mock import patch

import yaml

from par_cc_usage.config import Config, DisplayConfig, NotificationConfig, load_config
from par_cc_usage.enums import DisplayMode, TimeFormat


class TestDisplayConfig:
    """Test the DisplayConfig model."""

    def test_default_values(self):
        """Test DisplayConfig default values."""
        config = DisplayConfig()

        assert config.show_progress_bars is True
        assert config.show_active_sessions is True
        assert config.update_in_place is True
        assert config.refresh_interval == 5
        assert config.time_format == TimeFormat.TWENTY_FOUR_HOUR
        # Default includes Windows paths (C--, D--, E--) and Unix paths
        assert config.project_name_prefixes == ["C--Users-", "D--Users-", "E--Users-", "-Users-", "-home-"]
        assert config.aggregate_by_project is True
        assert config.show_tool_usage is True
        assert config.show_pricing is True
        assert config.display_mode == DisplayMode.NORMAL

    def test_custom_values(self):
        """Test DisplayConfig with custom values."""
        config = DisplayConfig(
            show_progress_bars=False,
            show_active_sessions=True,
            update_in_place=False,
            refresh_interval=5,
            time_format=TimeFormat.TWELVE_HOUR,
            project_name_prefixes=["custom-", "prefix-"],
            aggregate_by_project=False,
            display_mode=DisplayMode.COMPACT,
        )

        assert config.show_progress_bars is False
        assert config.show_active_sessions is True
        assert config.update_in_place is False
        assert config.refresh_interval == 5
        assert config.time_format == TimeFormat.TWELVE_HOUR
        assert config.project_name_prefixes == ["custom-", "prefix-"]
        assert config.aggregate_by_project is False
        assert config.display_mode == DisplayMode.COMPACT

    def test_display_mode_configuration(self):
        """Test DisplayMode configuration specifically."""
        # Test with normal mode
        config_normal = DisplayConfig(display_mode=DisplayMode.NORMAL)
        assert config_normal.display_mode == DisplayMode.NORMAL

        # Test with compact mode
        config_compact = DisplayConfig(display_mode=DisplayMode.COMPACT)
        assert config_compact.display_mode == DisplayMode.COMPACT

        # Test with string values
        config_normal_str = DisplayConfig(display_mode="normal")
        assert config_normal_str.display_mode == DisplayMode.NORMAL

        config_compact_str = DisplayConfig(display_mode="compact")
        assert config_compact_str.display_mode == DisplayMode.COMPACT


class TestNotificationConfig:
    """Test the NotificationConfig model."""

    def test_default_values(self):
        """Test NotificationConfig default values."""
        config = NotificationConfig()

        assert config.discord_webhook_url is None
        assert config.notify_on_block_completion is True
        assert config.cooldown_minutes == 5

    def test_custom_values(self):
        """Test NotificationConfig with custom values."""
        config = NotificationConfig(
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            slack_webhook_url="https://hooks.slack.com/services/123/abc",
            notify_on_block_completion=False,
            cooldown_minutes=30,
        )

        assert config.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert config.slack_webhook_url == "https://hooks.slack.com/services/123/abc"
        assert config.notify_on_block_completion is False
        assert config.cooldown_minutes == 30


class TestConfig:
    """Test the Config model."""

    def test_default_values(self):
        """Test Config default values."""
        config = Config()

        # Check default paths
        assert config.projects_dir == Path.home() / ".claude" / "projects"
        # Verify cache_dir uses XDG-compliant location
        assert config.cache_dir.name == "par_cc_usage"
        assert str(config.cache_dir).endswith("par_cc_usage")

        # Check other defaults
        assert config.polling_interval == 5
        assert config.timezone == "auto"
        assert config.token_limit is None
        assert config.disable_cache is False
        assert config.recent_activity_window_hours == 5

    def test_custom_values(self, temp_dir):
        """Test Config with custom values."""
        config = Config(
            projects_dir=temp_dir / "claude",
            cache_dir=temp_dir / "cache",
            polling_interval=10,
            timezone="Europe/London",
            token_limit=1000000,
            disable_cache=True,
            recent_activity_window_hours=3,
        )

        assert config.projects_dir == temp_dir / "claude"
        assert config.cache_dir == temp_dir / "cache"
        assert config.polling_interval == 10
        assert config.timezone == "Europe/London"
        assert config.token_limit == 1000000
        assert config.disable_cache is True
        assert config.recent_activity_window_hours == 3

    def test_nested_config_objects(self):
        """Test that nested config objects are properly initialized."""
        config = Config()

        assert isinstance(config.display, DisplayConfig)
        assert isinstance(config.notifications, NotificationConfig)

    def test_get_claude_paths_with_projects_dirs(self, temp_dir):
        """Test get_claude_paths with explicit projects_dirs."""
        dir1 = temp_dir / "claude1"
        dir2 = temp_dir / "claude2"
        dir1.mkdir()
        dir2.mkdir()

        config = Config(projects_dirs=[dir1, dir2])
        paths = config.get_claude_paths()

        assert len(paths) == 2
        assert dir1 in paths
        assert dir2 in paths

    def test_get_claude_paths_default(self, temp_dir, monkeypatch):
        """Test get_claude_paths with default paths."""
        # Mock home to temp_dir
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create default directories
        new_default = temp_dir / ".config" / "claude" / "projects"
        legacy_default = temp_dir / ".claude" / "projects"
        new_default.mkdir(parents=True)
        legacy_default.mkdir(parents=True)

        config = Config()
        paths = config.get_claude_paths()

        # Should find both default paths
        assert len(paths) == 2
        assert new_default in paths
        assert legacy_default in paths

    def test_get_effective_timezone_with_auto(self):
        """Test get_effective_timezone when timezone is 'auto'."""
        config = Config(timezone="auto", auto_detected_timezone="America/New_York")

        result = config.get_effective_timezone()
        assert result == "America/New_York"

    def test_get_effective_timezone_with_explicit_timezone(self):
        """Test get_effective_timezone with explicit timezone."""
        config = Config(timezone="Europe/London", auto_detected_timezone="America/New_York")

        result = config.get_effective_timezone()
        assert result == "Europe/London"

    def test_get_effective_timezone_auto_with_empty_detected(self):
        """Test get_effective_timezone when auto_detected_timezone is empty."""
        config = Config(timezone="auto", auto_detected_timezone="")

        result = config.get_effective_timezone()
        assert result == "America/Los_Angeles"  # Falls back to default

    def test_get_effective_timezone_auto_with_none_detected(self):
        """Test get_effective_timezone when auto_detected_timezone is None."""
        config = Config(timezone="auto")
        config.auto_detected_timezone = None

        result = config.get_effective_timezone()
        assert result == "America/Los_Angeles"  # Falls back to default


class TestLoadConfig:
    """Test the load_config function."""

    def test_load_default_config(self, temp_dir, monkeypatch):
        """Test loading config with no file or env vars."""
        # Ensure no config file exists
        config_path = temp_dir / "config.yaml"

        with patch("par_cc_usage.config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            config = load_config(config_path)

        assert isinstance(config, Config)
        assert config.polling_interval == 5  # Default value

    def test_load_from_yaml_file(self, temp_dir):
        """Test loading config from YAML file."""
        config_data = {
            "polling_interval": 10,
            "timezone": "Europe/Paris",
            "token_limit": 2000000,
            "display": {
                "time_format": "12h",
                "refresh_interval": 2,
                "display_mode": "compact",
            },
            "notifications": {
                "discord_webhook_url": "https://discord.com/api/webhooks/123/abc",
                "cooldown_minutes": 10,
            },
        }

        config_path = temp_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        config = load_config(config_path)

        assert config.polling_interval == 10
        assert config.timezone == "Europe/Paris"
        assert config.token_limit == 2000000
        assert config.display.time_format == "12h"
        assert config.display.refresh_interval == 2
        assert config.display.display_mode == DisplayMode.COMPACT
        assert config.notifications.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert config.notifications.cooldown_minutes == 10

    def test_load_from_env_vars(self, monkeypatch, clean_env):
        """Test loading config from environment variables."""
        # Set environment variables
        monkeypatch.setenv("PAR_CC_USAGE_POLLING_INTERVAL", "15")
        monkeypatch.setenv("PAR_CC_USAGE_TIMEZONE", "Asia/Tokyo")
        monkeypatch.setenv("PAR_CC_USAGE_TOKEN_LIMIT", "3000000")
        monkeypatch.setenv("PAR_CC_USAGE_TIME_FORMAT", "12h")
        monkeypatch.setenv("PAR_CC_USAGE_DISPLAY_MODE", "compact")
        monkeypatch.setenv("PAR_CC_USAGE_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/456/def")
        monkeypatch.setenv("PAR_CC_USAGE_COOLDOWN_MINUTES", "15")

        config = load_config()

        assert config.polling_interval == 15
        assert config.timezone == "Asia/Tokyo"
        assert config.token_limit == 3000000
        assert config.display.time_format == "12h"
        assert config.display.display_mode == DisplayMode.COMPACT
        assert config.notifications.discord_webhook_url == "https://discord.com/api/webhooks/456/def"
        assert config.notifications.cooldown_minutes == 15

    def test_env_vars_override_yaml(self, temp_dir, monkeypatch, clean_env):
        """Test that environment variables override YAML config."""
        # Create YAML config
        config_data = {
            "polling_interval": 10,
            "timezone": "Europe/London",
        }

        config_path = temp_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Set environment variable to override
        monkeypatch.setenv("PAR_CC_USAGE_POLLING_INTERVAL", "20")

        config = load_config(config_path)

        # Env var should override YAML
        assert config.polling_interval == 20
        # YAML value should still be used for non-overridden
        assert config.timezone == "Europe/London"

    def test_claude_config_dir_env(self, temp_dir, monkeypatch):
        """Test CLAUDE_CONFIG_DIR environment variable."""
        dir1 = temp_dir / "claude1"
        dir2 = temp_dir / "claude2"
        dir1.mkdir()
        dir2.mkdir()

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", f"{dir1},{dir2}")

        config = load_config()

        assert config.projects_dirs == [dir1, dir2]


class TestTimezoneDetection:
    """Test automatic timezone detection in config loading."""

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_load_config_detects_timezone_when_auto(self, mock_detect, temp_dir):
        """Test that load_config detects timezone when set to 'auto'."""
        mock_detect.return_value = "America/Chicago"

        # Create a config file with timezone: auto
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: auto\n")

        config = load_config(config_file)

        assert config.timezone == "auto"
        assert config.auto_detected_timezone == "America/Chicago"
        mock_detect.assert_called_once()

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_load_config_skips_detection_when_explicit(self, mock_detect, temp_dir):
        """Test that load_config skips detection when timezone is explicit."""
        mock_detect.return_value = "America/Chicago"

        # Create a config file with explicit timezone
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: Europe/London\n")

        config = load_config(config_file)

        assert config.timezone == "Europe/London"
        assert config.auto_detected_timezone == "America/Los_Angeles"  # Default value
        mock_detect.assert_not_called()

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_load_config_updates_detected_timezone(self, mock_detect, temp_dir):
        """Test that load_config updates auto_detected_timezone when it changes."""
        mock_detect.return_value = "Europe/Paris"

        # Create a config file with timezone: auto and old detected timezone
        config_file = temp_dir / "config.yaml"
        config_content = """
timezone: auto
auto_detected_timezone: America/New_York
"""
        config_file.write_text(config_content)

        config = load_config(config_file)

        assert config.timezone == "auto"
        assert config.auto_detected_timezone == "Europe/Paris"
        mock_detect.assert_called_once()

        # Verify the config file was updated
        updated_content = config_file.read_text()
        assert "auto_detected_timezone: Europe/Paris" in updated_content

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_load_config_no_update_when_same_timezone(self, mock_detect, temp_dir):
        """Test that config file is not updated when detected timezone is the same."""
        mock_detect.return_value = "America/New_York"

        # Create a config file with matching detected timezone
        config_file = temp_dir / "config.yaml"
        config_content = """
timezone: auto
auto_detected_timezone: America/New_York
"""
        config_file.write_text(config_content)
        original_mtime = config_file.stat().st_mtime

        config = load_config(config_file)

        assert config.timezone == "auto"
        assert config.auto_detected_timezone == "America/New_York"
        mock_detect.assert_called_once()

        # Verify the config file was not updated (same modification time)
        # Small delay to ensure mtime would change if file was written
        import time
        time.sleep(0.01)
        new_mtime = config_file.stat().st_mtime
        assert new_mtime == original_mtime

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_load_config_handles_detection_failure(self, mock_detect, temp_dir):
        """Test that load_config handles timezone detection failure gracefully."""
        mock_detect.side_effect = Exception("Detection failed")

        # Create a config file with timezone: auto
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: auto\n")

        config = load_config(config_file)

        assert config.timezone == "auto"
        # Should still have the default auto_detected_timezone value
        assert config.auto_detected_timezone == "America/Los_Angeles"
        mock_detect.assert_called_once()

    def test_load_config_default_timezone_is_auto(self, temp_dir):
        """Test that default timezone is 'auto' when no config exists."""
        config_file = temp_dir / "nonexistent_config.yaml"

        with patch("par_cc_usage.config.detect_system_timezone") as mock_detect:
            mock_detect.return_value = "America/Denver"

            config = load_config(config_file)

            assert config.timezone == "auto"
            assert config.auto_detected_timezone == "America/Denver"
            mock_detect.assert_called_once()


class TestXDGConfigIntegration:
    """Test XDG integration with config loading."""

    def test_load_config_uses_xdg_path_by_default(self, temp_dir):
        """Test that load_config uses XDG path when no explicit path provided."""
        # Create XDG config
        xdg_config_dir = temp_dir / ".config" / "par_cc_usage"
        xdg_config_dir.mkdir(parents=True)
        xdg_config_file = xdg_config_dir / "config.yaml"
        xdg_config_file.write_text("polling_interval: 25")

        with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_dir / ".config"):
            config = load_config()
            assert config.polling_interval == 25

    def test_config_cache_dir_uses_xdg_by_default(self):
        """Test that Config uses XDG cache directory by default."""
        # Test that the default factory function is properly set up
        # We can't easily mock the default factory at runtime, so we test the behavior
        config = Config()
        # The cache_dir should be a Path ending with 'par_cc_usage'
        assert config.cache_dir.name == "par_cc_usage"
        assert str(config.cache_dir).endswith("par_cc_usage")

    def test_load_config_with_legacy_migration(self, temp_dir):
        """Test load_config performs legacy migration when needed."""
        # Create legacy config
        legacy_config = temp_dir / "config.yaml"
        legacy_config.write_text("polling_interval: 12")

        # Set up XDG directories
        xdg_config_dir = temp_dir / ".config" / "par_cc_usage"

        with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_dir / ".config"):
            with patch("par_cc_usage.config.get_legacy_config_paths", return_value=[legacy_config]):
                config = load_config()

                # Verify migration occurred
                assert (xdg_config_dir / "config.yaml").exists()
                assert config.polling_interval == 12

    def test_load_config_explicit_path_skips_migration(self, temp_dir):
        """Test that explicit config path skips XDG migration."""
        # Create legacy config
        legacy_config = temp_dir / "legacy.yaml"
        legacy_config.write_text("polling_interval: 8")

        # Create explicit config
        explicit_config = temp_dir / "explicit.yaml"
        explicit_config.write_text("polling_interval: 18")

        with patch("par_cc_usage.xdg_dirs.xdg_config_home", return_value=temp_dir / ".config"):
            config = load_config(explicit_config)

            # Verify explicit config is used, no migration occurred
            assert config.polling_interval == 18
            assert not (temp_dir / ".config" / "par_cc_usage" / "config.yaml").exists()

    def test_config_model_post_init_creates_xdg_cache_dir(self, temp_dir):
        """Test that Config model_post_init creates XDG cache directory."""
        cache_dir = temp_dir / "custom_cache" / "par_cc_usage"

        config = Config(cache_dir=cache_dir)

        # Verify directory was created
        assert cache_dir.exists()
        assert cache_dir.is_dir()
