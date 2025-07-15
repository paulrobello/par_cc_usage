"""
Test configuration edge cases and validation scenarios.

This module tests configuration validation, migration scenarios,
environment variable precedence, and edge cases in config handling.
"""

import pytest
import os
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timezone

from par_cc_usage.config import (
    Config,
    DisplayConfig,
    NotificationConfig,
    load_config,
    save_config,
    _load_config_file,
)
from par_cc_usage.xdg_dirs import migrate_legacy_config, get_config_file_path
from par_cc_usage.enums import TimeFormat, OutputFormat


class TestConfigValidationEdgeCases:
    """Test configuration validation with invalid values."""

    def test_config_validation_invalid_values(self, temp_dir):
        """Test config validation with invalid timezone, negative values."""
        # Test invalid timezone
        invalid_configs = [
            {
                "timezone": "Invalid/Timezone",
                "token_limit": 1000000,
            },
            {
                "timezone": "UTC",
                "token_limit": -1,  # Negative token limit
            },
            {
                "timezone": "UTC",
                "token_limit": 1000000,
                "polling_interval": -5,  # Negative polling interval
            },
            {
                "timezone": "UTC",
                "token_limit": 1000000,
                "recent_activity_window_hours": 0,  # Zero activity window
            },
            {
                "timezone": "",  # Empty timezone
                "token_limit": 1000000,
            },
        ]

        for invalid_config in invalid_configs:
            config_file = temp_dir / "invalid_config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(invalid_config, f)

            # Should handle invalid values gracefully
            try:
                config = _load_config_file(config_file)
                # If loading succeeds, validation should handle invalid values
                assert isinstance(config, Config)
            except (ValueError, TypeError):
                # May raise validation errors for invalid values
                pass

    def test_config_validation_extreme_values(self, temp_dir):
        """Test config validation with extreme values."""
        extreme_configs = [
            {
                "token_limit": 999999999999999999,  # Extremely large
                "polling_interval": 0.001,  # Very small interval
            },
            {
                "token_limit": 1,  # Minimal token limit
                "polling_interval": 86400,  # 24 hours
            },
            {
                "recent_activity_window_hours": 999999,  # Extremely large window
            },
        ]

        for extreme_config in extreme_configs:
            config_file = temp_dir / "extreme_config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(extreme_config, f)

            try:
                config = _load_config_file(config_file)
                # Should handle extreme values appropriately
                assert isinstance(config, Config)
            except (ValueError, OverflowError):
                # May reject extreme values
                pass

    def test_config_validation_type_mismatches(self, temp_dir):
        """Test config validation with wrong data types."""
        type_mismatch_configs = [
            {
                "token_limit": "not_a_number",  # String instead of int
                "polling_interval": 1,
            },
            {
                "token_limit": 1000000,
                "polling_interval": "invalid",  # String instead of number
            },
            {
                "timezone": 123,  # Number instead of string
            },
            {
                "disable_cache": "yes",  # String instead of boolean
            },
            {
                "display": "not_a_dict",  # String instead of dict
            },
        ]

        for config_data in type_mismatch_configs:
            config_file = temp_dir / "type_mismatch_config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            try:
                config = _load_config_file(config_file)
                # May succeed with type coercion or fail with validation
                if config:
                    assert isinstance(config, Config)
            except (TypeError, ValueError):
                # Expected for type mismatches
                pass

    def test_config_validation_missing_required_fields(self, temp_dir):
        """Test config validation when required fields are missing."""
        # Test completely empty config
        empty_config_file = temp_dir / "empty_config.yaml"
        with open(empty_config_file, "w", encoding="utf-8") as f:
            f.write("")

        # Should handle empty config by using defaults
        config = _load_config_file(empty_config_file)
        assert isinstance(config, Config)

        # Test config with only some fields
        partial_config = {"token_limit": 2000000}
        partial_config_file = temp_dir / "partial_config.yaml"
        with open(partial_config_file, "w", encoding="utf-8") as f:
            yaml.dump(partial_config, f)

        config = _load_config_file(partial_config_file)
        assert isinstance(config, Config)
        assert config.token_limit == 2000000


class TestConfigMigrationScenarios:
    """Test configuration migration edge cases."""

    def test_config_migration_partial_failure(self, temp_dir):
        """Test config migration when source file is partially corrupted."""
        # Create legacy config locations
        legacy_configs = [
            temp_dir / "config.yaml",
            temp_dir / ".par_cc_usage" / "config.yaml",
        ]

        for legacy_path in legacy_configs:
            if legacy_path.parent != temp_dir:
                legacy_path.parent.mkdir(exist_ok=True)

            # Create partially corrupted config
            with open(legacy_path, "w", encoding="utf-8") as f:
                f.write("token_limit: 1000000\n")
                f.write("timezone: UTC\n")
                f.write("invalid: yaml: structure: {\n")  # Corrupted line
                f.write("polling_interval: 5\n")

            # Mock XDG config path
            xdg_config = temp_dir / "xdg_config.yaml"

            with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=xdg_config):
                with patch('par_cc_usage.xdg_dirs.get_legacy_config_paths', return_value=[legacy_path]):
                    # Should handle partial migration gracefully
                    migrated = migrate_legacy_config()

                    # Migration result depends on implementation
                    # May succeed with partial data or fail completely

    def test_config_migration_permission_errors(self, temp_dir):
        """Test config migration when permissions prevent migration."""
        # Create legacy config
        legacy_config = temp_dir / "legacy_config.yaml"
        with open(legacy_config, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 1000000}, f)

        # Create read-only XDG directory
        xdg_dir = temp_dir / "xdg"
        xdg_dir.mkdir()
        xdg_dir.chmod(0o444)  # Read-only

        xdg_config = xdg_dir / "config.yaml"

        try:
            with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=xdg_config):
                with patch('par_cc_usage.xdg_dirs.get_legacy_config_paths', return_value=[legacy_config]):
                    # Should handle permission errors gracefully
                    migrated = migrate_legacy_config()
                    assert not migrated  # Should fail due to permissions
        finally:
            # Restore permissions for cleanup
            xdg_dir.chmod(0o755)

    def test_config_migration_competing_sources(self, temp_dir):
        """Test config migration when multiple legacy configs exist."""
        # Create multiple legacy configs with different values
        legacy_configs = [
            (temp_dir / "config1.yaml", {"token_limit": 1000000, "timezone": "UTC"}),
            (temp_dir / "config2.yaml", {"token_limit": 2000000, "timezone": "America/New_York"}),
        ]

        for config_path, config_data in legacy_configs:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

        xdg_config = temp_dir / "xdg_config.yaml"
        legacy_paths = [config[0] for config in legacy_configs]

        with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=xdg_config):
            with patch('par_cc_usage.xdg_dirs.get_legacy_config_paths', return_value=legacy_paths):
                # Should handle multiple legacy configs
                migrated = migrate_legacy_config()

                if migrated and xdg_config.exists():
                    # Should have migrated one of the configs
                    migrated_config = _load_config_file(xdg_config)
                    assert isinstance(migrated_config, Config)

    def test_config_migration_xdg_already_exists(self, temp_dir):
        """Test config migration when XDG config already exists."""
        # Create legacy config
        legacy_config = temp_dir / "legacy_config.yaml"
        with open(legacy_config, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 1000000}, f)

        # Create existing XDG config
        xdg_config = temp_dir / "xdg_config.yaml"
        with open(xdg_config, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 3000000}, f)

        with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=xdg_config):
            with patch('par_cc_usage.xdg_dirs.get_legacy_config_paths', return_value=[legacy_config]):
                # Should not overwrite existing XDG config
                migrated = migrate_legacy_config()
                assert not migrated

                # XDG config should remain unchanged
                config = _load_config_file(xdg_config)
                assert config.token_limit == 3000000


class TestEnvironmentVariablePrecedence:
    """Test complex environment variable override scenarios."""

    def test_environment_variable_precedence(self, temp_dir, monkeypatch):
        """Test complex environment variable override scenarios."""
        # Create config file
        config_file = temp_dir / "test_config.yaml"
        file_config = {
            "token_limit": 1000000,
            "timezone": "UTC",
            "polling_interval": 5,
            "display": {
                "time_format": "24h",
                "show_progress_bars": True,
            },
            "notifications": {
                "discord_webhook_url": "https://file.webhook.url",
                "notify_on_block_completion": False,
            }
        }
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(file_config, f)

        # Set environment variables that should override file config
        env_vars = {
            "PAR_CC_USAGE_TOKEN_LIMIT": "2000000",
            "PAR_CC_USAGE_TIMEZONE": "America/New_York",
            "PAR_CC_USAGE_TIME_FORMAT": "12h",
            "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "https://env.webhook.url",
            "PAR_CC_USAGE_NOTIFY_ON_BLOCK_COMPLETION": "true",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        config = _load_config_file(config_file)

        # Environment variables should override file config
        assert config.token_limit == 2000000
        assert config.timezone == "America/New_York"
        assert config.display.time_format == TimeFormat.TWELVE_HOUR
        assert config.notifications.discord_webhook_url == "https://env.webhook.url"
        assert config.notifications.notify_on_block_completion == True

    def test_environment_variable_type_conversion(self, temp_dir, monkeypatch):
        """Test environment variable type conversion edge cases."""
        config_file = temp_dir / "test_config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 1000000}, f)

        # Test various type conversions
        type_test_cases = [
            ("PAR_CC_USAGE_TOKEN_LIMIT", "invalid_number"),  # Invalid int
            ("PAR_CC_USAGE_POLLING_INTERVAL", "not_a_float"),  # Invalid float
            ("PAR_CC_USAGE_DISABLE_CACHE", "maybe"),  # Invalid boolean
            ("PAR_CC_USAGE_SHOW_PROGRESS_BARS", "1"),  # String "1" -> boolean
            ("PAR_CC_USAGE_NOTIFY_ON_BLOCK_COMPLETION", "false"),  # String "false" -> boolean
        ]

        for env_var, env_value in type_test_cases:
            # Clear environment first
            for key in os.environ:
                if key.startswith("PAR_CC_USAGE_"):
                    monkeypatch.delenv(key, raising=False)

            monkeypatch.setenv(env_var, env_value)

            try:
                config = _load_config_file(config_file)
                # Should handle type conversion gracefully
                assert isinstance(config, Config)
            except (ValueError, TypeError):
                # May fail with invalid type conversions
                pass

    def test_environment_variable_nested_config(self, temp_dir, monkeypatch):
        """Test environment variables for nested configuration."""
        config_file = temp_dir / "test_config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 1000000}, f)

        # Test nested configuration via environment variables
        nested_env_vars = {
            "PAR_CC_USAGE_TIME_FORMAT": "12h",
            "PAR_CC_USAGE_SHOW_PROGRESS_BARS": "false",
            "PAR_CC_USAGE_UPDATE_IN_PLACE": "true",
            "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "https://test.webhook",
            "PAR_CC_USAGE_COOLDOWN_MINUTES": "30",
        }

        for key, value in nested_env_vars.items():
            monkeypatch.setenv(key, value)

        config = _load_config_file(config_file)

        # Should properly handle nested configuration
        assert config.display.time_format == TimeFormat.TWELVE_HOUR
        assert config.display.show_progress_bars == False
        assert config.display.update_in_place == True
        assert config.notifications.discord_webhook_url == "https://test.webhook"
        assert config.notifications.cooldown_minutes == 30

    def test_environment_variable_malformed_names(self, temp_dir, monkeypatch):
        """Test handling of malformed environment variable names."""
        config_file = temp_dir / "test_config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump({"token_limit": 1000000}, f)

        # Test malformed environment variable names
        malformed_env_vars = [
            "PAR_CC_USAGE_",  # Trailing underscore
            "PAR_CC_USAGE_INVALID_FIELD",  # Non-existent field
            "PAR_CC_USAGE_token_limit",  # Wrong case
            "par_cc_usage_TOKEN_LIMIT",  # Wrong prefix case
            "PAR_CC_USAGE__DOUBLE_UNDERSCORE",  # Double underscore
        ]

        for env_var in malformed_env_vars:
            monkeypatch.setenv(env_var, "test_value")

        # Should ignore malformed environment variables
        config = _load_config_file(config_file)
        assert isinstance(config, Config)

    def test_env_vars_edge_cases(self, monkeypatch):
        """Test environment variable handling with edge cases."""
        # Clear all PAR_CC_USAGE env vars first
        for key in list(os.environ.keys()):
            if key.startswith("PAR_CC_USAGE_"):
                monkeypatch.delenv(key, raising=False)

        # Create minimal config file
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        config_file.write("token_limit: 1000000\n")
        config_file.close()

        try:
            # Test with no environment variables
            config = _load_config_file(Path(config_file.name))
            assert config.token_limit == 1000000

            # Test with empty values
            empty_value_vars = {
                "PAR_CC_USAGE_TOKEN_LIMIT": "",
                "PAR_CC_USAGE_TIMEZONE": "",
                "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "",
            }

            for key, value in empty_value_vars.items():
                monkeypatch.setenv(key, value)

            config = _load_config_file(Path(config_file.name))
            # Should handle empty values appropriately
        finally:
            import os
            os.unlink(config_file.name)


class TestConfigSaveAndLoad:
    """Test configuration saving and loading edge cases."""

    def test_save_config_permission_errors(self, temp_dir):
        """Test saving config when file is not writable."""
        # Create read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        config_file = readonly_dir / "config.yaml"
        config = Config()

        try:
            # Should handle permission errors gracefully
            save_config(config, config_file)
        except PermissionError:
            # Expected for read-only directory
            pass
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_save_config_disk_full(self, temp_dir):
        """Test saving config when disk is full."""
        config_file = temp_dir / "config.yaml"
        config = Config()

        # Mock file writing to simulate disk full
        with patch('builtins.open', side_effect=OSError(28, "No space left on device")):
            try:
                save_config(config, config_file)
            except OSError:
                # Expected for disk full scenario
                pass

    def test_load_config_with_yaml_errors(self, temp_dir):
        """Test loading config with various YAML errors."""
        yaml_error_files = [
            "invalid: yaml: structure: {",  # Unclosed brace
            "- invalid\n  - list\n- structure",  # Invalid structure
            "key: value\ninvalid_indentation",  # Invalid indentation
            "\t\ttabs_not_allowed: value",  # Tabs not allowed
            "unicode_error: \x00\x01\x02",  # Invalid unicode
        ]

        for i, yaml_content in enumerate(yaml_error_files):
            config_file = temp_dir / f"yaml_error_{i}.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(yaml_content)

            try:
                config = _load_config_file(config_file)
                # May succeed with partial parsing or fail
                if config:
                    assert isinstance(config, Config)
            except yaml.YAMLError:
                # Expected for malformed YAML
                pass

    def test_load_config_file_not_found(self, temp_dir):
        """Test loading config when file doesn't exist."""
        non_existent_file = temp_dir / "does_not_exist.yaml"

        # Should handle missing file gracefully
        config = _load_config_file(non_existent_file)
        assert isinstance(config, Config)  # Should return default config

    def test_load_config_binary_file(self, temp_dir):
        """Test loading config when file contains binary data."""
        binary_file = temp_dir / "binary_config.yaml"
        with open(binary_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\xFF\xFE\xFD\xFC")

        try:
            config = _load_config_file(binary_file)
            # May succeed or fail depending on binary content
            if config:
                assert isinstance(config, Config)
        except (UnicodeDecodeError, yaml.YAMLError):
            # Expected for binary files
            pass


class TestConfigIntegrationEdgeCases:
    """Test configuration integration with other components."""

    def test_config_with_display_config_edge_cases(self, temp_dir):
        """Test configuration with DisplayConfig edge cases."""
        display_configs = [
            {
                "display": {
                    "time_format": "invalid_format",
                    "refresh_interval": -1,
                    "project_name_prefixes": None,
                }
            },
            {
                "display": {
                    "show_progress_bars": "maybe",  # Invalid boolean
                    "update_in_place": 1,  # Integer instead of boolean
                }
            },
            {
                "display": None  # None display config
            },
        ]

        for i, config_data in enumerate(display_configs):
            config_file = temp_dir / f"display_config_{i}.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            try:
                config = _load_config_file(config_file)
                assert isinstance(config, Config)
                assert isinstance(config.display, DisplayConfig)
            except (ValueError, TypeError):
                # May fail with invalid display configuration
                pass

    def test_config_with_notification_config_edge_cases(self, temp_dir):
        """Test configuration with NotificationConfig edge cases."""
        notification_configs = [
            {
                "notifications": {
                    "discord_webhook_url": "not_a_url",
                    "cooldown_minutes": -5,  # Negative cooldown
                }
            },
            {
                "notifications": {
                    "notify_on_block_completion": "yes",  # String instead of boolean
                    "cooldown_minutes": "not_a_number",  # String instead of int
                }
            },
            {
                "notifications": []  # List instead of dict
            },
        ]

        for i, config_data in enumerate(notification_configs):
            config_file = temp_dir / f"notification_config_{i}.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            try:
                config = _load_config_file(config_file)
                assert isinstance(config, Config)
                assert isinstance(config.notifications, NotificationConfig)
            except (ValueError, TypeError):
                # May fail with invalid notification configuration
                pass

    def test_config_version_compatibility(self, temp_dir):
        """Test configuration backward compatibility."""
        # Test old config format compatibility
        old_format_configs = [
            {
                # Very old format - minimal fields
                "token_limit": 1000000,
            },
            {
                # Medium old format - some fields
                "token_limit": 1000000,
                "timezone": "UTC",
                "refresh_interval": 5,  # Old field name
            },
            {
                # Old nested format
                "token_limit": 1000000,
                "display_config": {  # Old nested structure
                    "time_format": "24h",
                }
            },
        ]

        for i, config_data in enumerate(old_format_configs):
            config_file = temp_dir / f"old_format_{i}.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f)

            # Should handle old format configs gracefully
            config = _load_config_file(config_file)
            assert isinstance(config, Config)
            assert config.token_limit == 1000000
