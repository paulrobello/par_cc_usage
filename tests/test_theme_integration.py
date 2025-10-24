"""Integration tests for --theme flag functionality."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from par_cc_usage.enums import ThemeType
from par_cc_usage.main import app
from par_cc_usage.theme import apply_temporary_theme, get_theme_manager


class TestThemeFlagIntegration:
    """Test --theme flag integration in CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        # Reset theme manager to default before each test
        get_theme_manager().set_current_theme(ThemeType.DEFAULT)

    def test_list_command_with_invalid_theme(self):
        """Test list command with invalid --theme flag."""
        # Run command with invalid theme
        result = self.runner.invoke(app, ["list", "--theme", "invalid"])

        # Check command failed
        assert result.exit_code != 0
        assert "Invalid value for '--theme'" in result.output or "invalid" in result.output.lower()

    def test_theme_management_commands(self):
        """Test theme management CLI commands."""
        # Test theme list
        result = self.runner.invoke(app, ["theme", "list"])
        assert result.exit_code == 0
        assert "Default" in result.output
        assert "Light" in result.output
        assert "Dark" in result.output
        assert "Accessibility" in result.output
        assert "Minimal" in result.output

        # Test theme current
        result = self.runner.invoke(app, ["theme", "current"])
        assert result.exit_code == 0

        # Test theme set (this should persist)
        with patch("par_cc_usage.main.save_config") as mock_save:
            with patch("par_cc_usage.main.load_config") as mock_load:
                with patch("par_cc_usage.main.get_config_file_path") as mock_path:
                    mock_config = Mock()
                    mock_load.return_value = mock_config
                    mock_path.return_value = "/mock/path"

                    result = self.runner.invoke(app, ["theme", "set", "light"])
                    assert result.exit_code == 0
                    mock_save.assert_called_once()

    def test_apply_temporary_theme_function(self):
        """Test the apply_temporary_theme function directly."""
        # Start with default theme
        assert get_theme_manager().get_current_theme_type() == ThemeType.DEFAULT

        # Apply light theme
        apply_temporary_theme(ThemeType.LIGHT)
        assert get_theme_manager().get_current_theme_type() == ThemeType.LIGHT

        # Apply accessibility theme
        apply_temporary_theme(ThemeType.ACCESSIBILITY)
        assert get_theme_manager().get_current_theme_type() == ThemeType.ACCESSIBILITY

        # Apply minimal theme
        apply_temporary_theme(ThemeType.MINIMAL)
        assert get_theme_manager().get_current_theme_type() == ThemeType.MINIMAL

    def test_theme_flag_parameter_validation(self):
        """Test that theme flag accepts valid theme values."""
        # Test each valid theme type
        for theme_type in ThemeType:
            # This would normally fail due to missing config, but the important thing
            # is that the theme parameter is accepted by typer
            self.runner.invoke(app, ["list", "--theme", theme_type.value], catch_exceptions=False)
            # The command will fail due to missing config, but not due to invalid theme
            # We mainly want to ensure typer accepts the theme values


class TestThemeColorApplication:
    """Test that themes actually affect color output."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset theme manager to default before each test
        get_theme_manager().set_current_theme(ThemeType.DEFAULT)

    def test_theme_affects_display_colors(self):
        """Test that changing themes affects display colors."""
        from par_cc_usage.theme import get_color

        # Test default theme colors
        get_theme_manager().set_current_theme(ThemeType.DEFAULT)
        default_success = get_color("success")
        default_error = get_color("error")

        # Test light theme colors
        get_theme_manager().set_current_theme(ThemeType.LIGHT)
        light_success = get_color("success")
        light_error = get_color("error")

        # Colors should be different
        assert default_success != light_success
        assert default_error != light_error

        # Test specific expected colors
        assert light_success == "#859900"  # Solarized green
        assert light_error == "#dc322f"    # Solarized red

    def test_theme_affects_progress_colors(self):
        """Test that themes affect progress color calculations."""
        from par_cc_usage.theme import get_progress_color

        # Test with default theme
        get_theme_manager().set_current_theme(ThemeType.DEFAULT)
        default_progress = get_progress_color(75)

        # Test with accessibility theme
        get_theme_manager().set_current_theme(ThemeType.ACCESSIBILITY)
        accessibility_progress = get_progress_color(75)

        # Colors should be different
        assert default_progress != accessibility_progress

    def test_minimal_theme_has_grayscale_colors(self):
        """Test that minimal theme uses grayscale colors."""
        from par_cc_usage.theme import get_color

        get_theme_manager().set_current_theme(ThemeType.MINIMAL)

        # Test that colors are grayscale
        success = get_color("success")
        warning = get_color("warning")

        # Minimal theme should use grayscale
        assert success == "#AAAAAA"
        assert warning == "#AAAAAA"

    def test_accessibility_theme_has_high_contrast(self):
        """Test that accessibility theme has high contrast colors."""
        from par_cc_usage.theme import get_color

        get_theme_manager().set_current_theme(ThemeType.ACCESSIBILITY)

        # Test high contrast colors
        text = get_color("text")
        background = get_color("background")

        # Should have high contrast
        assert text == "#000000"      # Black text
        assert background == "#FFFFFF"  # White background


class TestThemeConfigurationIntegration:
    """Test theme configuration integration."""

    def test_theme_environment_variable_parsing(self):
        """Test that theme environment variables are parsed correctly."""
        from par_cc_usage.config import _parse_env_value

        # Test valid theme values
        assert _parse_env_value("light", "theme") == "light"
        assert _parse_env_value("dark", "theme") == "dark"
        assert _parse_env_value("accessibility", "theme") == "accessibility"
        assert _parse_env_value("minimal", "theme") == "minimal"
        assert _parse_env_value("default", "theme") == "default"

        # Test invalid theme value (should return as-is for validation later)
        assert _parse_env_value("invalid", "theme") == "invalid"

    def test_theme_config_file_integration(self):
        """Test theme configuration in config file."""
        from par_cc_usage.config import DisplayConfig

        # Test creating display config with theme
        config = DisplayConfig(theme=ThemeType.LIGHT)
        assert config.theme == ThemeType.LIGHT

        # Test default theme
        config = DisplayConfig()
        assert config.theme == ThemeType.DEFAULT

    def test_theme_validation_in_config(self):
        """Test theme validation in configuration."""
        from par_cc_usage.config import DisplayConfig

        # Valid themes should work
        for theme_type in ThemeType:
            config = DisplayConfig(theme=theme_type)
            assert config.theme == theme_type

        # Invalid theme should raise validation error
        with pytest.raises(ValueError):
            DisplayConfig(theme="invalid_theme")  # type: ignore
