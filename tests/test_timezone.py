"""
Tests for timezone functionality including dynamic updates and dual-field architecture.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from par_cc_usage.config import Config, load_config, save_config


class TestTimezoneArchitecture:
    """Test the dual-field timezone architecture behavior."""

    def test_timezone_field_stores_user_preference(self):
        """Test that timezone field preserves user's preference."""
        # Test with auto preference
        config_auto = Config(timezone="auto")
        assert config_auto.timezone == "auto"

        # Test with explicit preference
        config_explicit = Config(timezone="Europe/Berlin")
        assert config_explicit.timezone == "Europe/Berlin"

    def test_auto_detected_timezone_field_stores_detected_value(self):
        """Test that auto_detected_timezone stores the detected value."""
        config = Config(auto_detected_timezone="Asia/Tokyo")
        assert config.auto_detected_timezone == "Asia/Tokyo"

    def test_effective_timezone_respects_user_preference(self):
        """Test that get_effective_timezone respects user's timezone preference."""
        # When user chooses auto, use detected timezone
        config_auto = Config(
            timezone="auto",
            auto_detected_timezone="America/Denver"
        )
        assert config_auto.get_effective_timezone() == "America/Denver"

        # When user chooses explicit, use their choice (ignore detected)
        config_explicit = Config(
            timezone="Europe/London",
            auto_detected_timezone="America/Denver"
        )
        assert config_explicit.get_effective_timezone() == "Europe/London"

    def test_config_preserves_both_fields_when_saved(self, temp_dir):
        """Test that both timezone fields are preserved when config is saved."""
        config_file = temp_dir / "config.yaml"

        # Create config with both fields
        config = Config(
            timezone="auto",
            auto_detected_timezone="Pacific/Auckland"
        )

        save_config(config, config_file)

        # Verify both fields are in the saved file
        content = config_file.read_text()
        assert "timezone: auto" in content
        assert "auto_detected_timezone: Pacific/Auckland" in content

    def test_config_loading_preserves_user_intent(self, temp_dir):
        """Test that loading config preserves whether user chose auto or explicit."""
        config_file = temp_dir / "config.yaml"

        # Test with auto preference
        config_file.write_text("""
timezone: auto
auto_detected_timezone: America/Chicago
""")

        with patch("par_cc_usage.config.detect_system_timezone") as mock_detect:
            mock_detect.return_value = "America/Chicago"  # Same timezone
            config = load_config(config_file)

            assert config.timezone == "auto"  # User's preference preserved
            assert config.auto_detected_timezone == "America/Chicago"
            assert config.get_effective_timezone() == "America/Chicago"

        # Test with explicit preference
        config_file.write_text("""
timezone: Europe/Madrid
auto_detected_timezone: America/Chicago
""")

        with patch("par_cc_usage.config.detect_system_timezone") as mock_detect:
            mock_detect.return_value = "America/New_York"  # Different timezone
            config = load_config(config_file)

            assert config.timezone == "Europe/Madrid"  # User's preference preserved
            assert config.auto_detected_timezone == "America/Chicago"  # Not updated for explicit
            assert config.get_effective_timezone() == "Europe/Madrid"
            mock_detect.assert_not_called()  # Should not detect for explicit timezone


class TestDynamicTimezoneUpdates:
    """Test dynamic timezone update functionality."""

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_system_timezone_change_detected_on_reload(self, mock_detect, temp_dir):
        """Test that system timezone changes are detected when config is reloaded."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
timezone: auto
auto_detected_timezone: America/Los_Angeles
""")

        # First load - original timezone
        mock_detect.return_value = "America/Los_Angeles"
        config1 = load_config(config_file)
        assert config1.auto_detected_timezone == "America/Los_Angeles"

        # Second load - system timezone changed
        mock_detect.return_value = "America/New_York"
        config2 = load_config(config_file)
        assert config2.auto_detected_timezone == "America/New_York"

        # Verify config file was updated
        content = config_file.read_text()
        assert "auto_detected_timezone: America/New_York" in content

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_timezone_change_updates_effective_timezone(self, mock_detect, temp_dir):
        """Test that timezone changes affect get_effective_timezone."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
timezone: auto
auto_detected_timezone: America/Los_Angeles
""")

        # Simulate timezone change
        mock_detect.return_value = "Europe/London"
        config = load_config(config_file)

        # Effective timezone should reflect the change
        assert config.get_effective_timezone() == "Europe/London"

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_traveler_scenario_multiple_timezone_changes(self, mock_detect, temp_dir):
        """Test scenario where user travels and timezone changes multiple times."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: auto\n")

        # Simulate traveling through different timezones
        timezones = [
            "America/Denver",       # Start in Denver
            "America/Chicago",      # Continue to Chicago
            "America/New_York",     # Continue to NYC
            "America/Los_Angeles",  # End in LA
        ]

        for expected_tz in timezones:
            mock_detect.return_value = expected_tz
            config = load_config(config_file)

            assert config.timezone == "auto"  # User preference unchanged
            assert config.auto_detected_timezone == expected_tz
            assert config.get_effective_timezone() == expected_tz

            # Verify file is updated each time
            content = config_file.read_text()
            assert f"auto_detected_timezone: {expected_tz}" in content

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_no_update_when_timezone_unchanged(self, mock_detect, temp_dir):
        """Test that config file is not unnecessarily updated when timezone is unchanged."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
timezone: auto
auto_detected_timezone: America/Denver
polling_interval: 10
""")

        # Get original modification time
        original_mtime = config_file.stat().st_mtime

        # Load config with same timezone
        mock_detect.return_value = "America/Denver"
        config = load_config(config_file)

        # Small delay to ensure mtime would change if file was written
        import time
        time.sleep(0.01)

        # Verify file was not modified
        new_mtime = config_file.stat().st_mtime
        assert new_mtime == original_mtime

        # But config should still work correctly
        assert config.get_effective_timezone() == "America/Denver"

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_explicit_timezone_ignores_system_changes(self, mock_detect, temp_dir):
        """Test that explicit timezone ignores system timezone changes."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
timezone: Asia/Shanghai
auto_detected_timezone: America/Los_Angeles
""")

        # Simulate system timezone change
        mock_detect.return_value = "Europe/Berlin"
        config = load_config(config_file)

        # Should ignore system change and use explicit timezone
        assert config.timezone == "Asia/Shanghai"
        assert config.auto_detected_timezone == "America/Los_Angeles"  # Not updated
        assert config.get_effective_timezone() == "Asia/Shanghai"

        # Should not call detect function for explicit timezone
        mock_detect.assert_not_called()


class TestTimezoneEdgeCases:
    """Test edge cases and error conditions for timezone functionality."""

    @patch("par_cc_usage.config.detect_system_timezone")
    def test_detection_failure_preserves_old_value(self, mock_detect, temp_dir):
        """Test that detection failure preserves the old auto_detected_timezone value."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
timezone: auto
auto_detected_timezone: America/Chicago
""")

        # Simulate detection failure
        mock_detect.side_effect = Exception("System error")

        config = load_config(config_file)

        # Should preserve old value
        assert config.timezone == "auto"
        assert config.auto_detected_timezone == "America/Chicago"
        assert config.get_effective_timezone() == "America/Chicago"

    def test_config_with_missing_auto_detected_field(self, temp_dir):
        """Test config loading when auto_detected_timezone field is missing."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: auto\n")  # Missing auto_detected_timezone

        with patch("par_cc_usage.config.detect_system_timezone") as mock_detect:
            mock_detect.return_value = "America/Phoenix"

            config = load_config(config_file)

            assert config.timezone == "auto"
            assert config.auto_detected_timezone == "America/Phoenix"
            assert config.get_effective_timezone() == "America/Phoenix"

    def test_backward_compatibility_with_old_configs(self, temp_dir):
        """Test that old configs without auto_detected_timezone still work."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("""
polling_interval: 5
timezone: Europe/Stockholm
token_limit: 500000
""")  # Old-style config without auto_detected_timezone

        config = load_config(config_file)

        # Should work with explicit timezone
        assert config.timezone == "Europe/Stockholm"
        assert config.get_effective_timezone() == "Europe/Stockholm"

        # auto_detected_timezone should have default value
        assert config.auto_detected_timezone == "America/Los_Angeles"

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)
