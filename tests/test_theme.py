"""Tests for theme system functionality."""

from __future__ import annotations

import pytest
from rich.console import Console
from rich.theme import Theme

from par_cc_usage.enums import ThemeType
from par_cc_usage.theme import (
    ColorScheme,
    ThemeDefinition,
    ThemeManager,
    apply_temporary_theme,
    create_themed_console,
    get_color,
    get_progress_color,
    get_style,
    get_theme_manager,
)


class TestColorScheme:
    """Test ColorScheme pydantic model."""

    def test_color_scheme_creation(self):
        """Test creating a color scheme with all required fields."""
        colors = ColorScheme(
            success="#00FF00",
            warning="#FFA500",
            error="#FF0000",
            info="#0000FF",
            primary="#4169E1",
            secondary="#00FFFF",
            accent="#FF00FF",
            border="#FFFF00",
            background="#000000",
            text="#FFFFFF",
            text_dim="dim",
            token_count="#FFFF00",
            model_name="green",
            project_name="#00FFFF",
            tool_usage="#FF9900",
            tool_mcp="#FF6600",
            tool_total="#00FFFF",
            cost="#00FF80",
            progress_low="#00FF00",
            progress_medium="#FFFF00",
            progress_high="#FFA500",
            progress_critical="#FF0000",
            burn_rate="#00FFFF",
            eta_normal="#00FFFF",
            eta_urgent="#FF0000",
        )
        assert colors.success == "#00FF00"
        assert colors.warning == "#FFA500"
        assert colors.error == "#FF0000"
        assert colors.info == "#0000FF"


class TestThemeDefinition:
    """Test ThemeDefinition dataclass."""

    def test_theme_definition_creation(self):
        """Test creating a theme definition."""
        colors = ColorScheme(
            success="#00FF00",
            warning="#FFA500",
            error="#FF0000",
            info="#0000FF",
            primary="#4169E1",
            secondary="#00FFFF",
            accent="#FF00FF",
            border="#FFFF00",
            background="#000000",
            text="#FFFFFF",
            text_dim="dim",
            token_count="#FFFF00",
            model_name="green",
            project_name="#00FFFF",
            tool_usage="#FF9900",
            tool_mcp="#FF6600",
            tool_total="#00FFFF",
            cost="#00FF80",
            progress_low="#00FF00",
            progress_medium="#FFFF00",
            progress_high="#FFA500",
            progress_critical="#FF0000",
            burn_rate="#00FFFF",
            eta_normal="#00FFFF",
            eta_urgent="#FF0000",
        )
        rich_theme = Theme({"success": colors.success, "error": colors.error})

        theme_def = ThemeDefinition(
            name="Test Theme",
            description="A test theme",
            colors=colors,
            rich_theme=rich_theme,
        )

        assert theme_def.name == "Test Theme"
        assert theme_def.description == "A test theme"
        assert theme_def.colors == colors
        assert theme_def.rich_theme == rich_theme


class TestThemeManager:
    """Test ThemeManager class."""

    def test_theme_manager_initialization(self):
        """Test theme manager initializes with all built-in themes."""
        manager = ThemeManager()

        # Check all theme types are available
        assert ThemeType.DEFAULT in manager.list_themes()
        assert ThemeType.DARK in manager.list_themes()
        assert ThemeType.LIGHT in manager.list_themes()
        assert ThemeType.ACCESSIBILITY in manager.list_themes()
        assert ThemeType.MINIMAL in manager.list_themes()

        # Check initial theme is default
        assert manager.get_current_theme_type() == ThemeType.DEFAULT

    def test_get_theme(self):
        """Test getting a theme by type."""
        manager = ThemeManager()

        # Test getting default theme
        default_theme = manager.get_theme(ThemeType.DEFAULT)
        assert default_theme.name == "Default"
        assert isinstance(default_theme.colors, ColorScheme)
        assert isinstance(default_theme.rich_theme, Theme)

        # Test getting light theme
        light_theme = manager.get_theme(ThemeType.LIGHT)
        assert light_theme.name == "Light"
        assert light_theme.colors.success == "#859900"  # Solarized green

    def test_set_current_theme(self):
        """Test setting the current theme."""
        manager = ThemeManager()

        # Initially default
        assert manager.get_current_theme_type() == ThemeType.DEFAULT

        # Set to light theme
        manager.set_current_theme(ThemeType.LIGHT)
        assert manager.get_current_theme_type() == ThemeType.LIGHT

        # Set to accessibility theme
        manager.set_current_theme(ThemeType.ACCESSIBILITY)
        assert manager.get_current_theme_type() == ThemeType.ACCESSIBILITY

    def test_set_invalid_theme(self):
        """Test setting an invalid theme raises error."""
        manager = ThemeManager()

        with pytest.raises(ValueError, match="Unknown theme type"):
            manager.set_current_theme("invalid_theme")  # type: ignore

    def test_get_current_theme(self):
        """Test getting current theme definition."""
        manager = ThemeManager()

        # Set to light theme
        manager.set_current_theme(ThemeType.LIGHT)
        current_theme = manager.get_current_theme()

        assert current_theme.name == "Light"
        assert current_theme.colors.success == "#859900"  # Solarized green

    def test_get_color(self):
        """Test getting color by semantic name."""
        manager = ThemeManager()

        # Default theme
        assert manager.get_color("success") == "#00FF00"
        assert manager.get_color("warning") == "#FFA500"
        assert manager.get_color("error") == "#FF0000"

        # Switch to light theme
        manager.set_current_theme(ThemeType.LIGHT)
        assert manager.get_color("success") == "#859900"  # Solarized green
        assert manager.get_color("warning") == "#cb4b16"  # Solarized orange

    def test_get_invalid_color(self):
        """Test getting invalid color raises error."""
        manager = ThemeManager()

        with pytest.raises(AttributeError):
            manager.get_color("invalid_color")

    def test_get_style(self):
        """Test getting style string."""
        manager = ThemeManager()

        # Basic style
        style = manager.get_style("success")
        assert style == "#00FF00"

        # Style with attributes
        style = manager.get_style("success", bold=True, italic=True)
        assert "bold" in style
        assert "italic" in style
        assert "#00FF00" in style

    def test_get_progress_color(self):
        """Test getting progress color based on percentage."""
        manager = ThemeManager()

        # Test different percentage ranges
        assert manager.get_progress_color(25) == "#00FF00"  # progress_low
        assert manager.get_progress_color(60) == "#FFFF00"  # progress_medium
        assert manager.get_progress_color(80) == "#FFA500"  # progress_high
        assert manager.get_progress_color(95) == "#FF0000"  # progress_critical

    def test_create_rich_console(self):
        """Test creating Rich console with theme."""
        manager = ThemeManager()

        # Create console with default theme
        console = manager.create_rich_console()
        assert isinstance(console, Console)

        # Create console with light theme
        manager.set_current_theme(ThemeType.LIGHT)
        console = manager.create_rich_console()
        assert isinstance(console, Console)

    def test_list_themes(self):
        """Test listing all available themes."""
        manager = ThemeManager()

        themes = manager.list_themes()
        assert len(themes) == 6  # All built-in themes

        # Check all theme types present
        for theme_type in ThemeType:
            assert theme_type in themes
            theme_def = themes[theme_type]
            assert isinstance(theme_def, ThemeDefinition)
            assert theme_def.name
            assert theme_def.description
            assert isinstance(theme_def.colors, ColorScheme)
            assert isinstance(theme_def.rich_theme, Theme)


class TestGlobalThemeManager:
    """Test global theme manager functions."""

    def test_get_theme_manager_singleton(self):
        """Test that get_theme_manager returns the same instance."""
        manager1 = get_theme_manager()
        manager2 = get_theme_manager()

        assert manager1 is manager2
        assert isinstance(manager1, ThemeManager)

    def test_get_color_global(self):
        """Test global get_color function."""
        # Should use global theme manager
        color = get_color("success")
        assert color == "#00FF00"  # Default theme success color

    def test_get_style_global(self):
        """Test global get_style function."""
        style = get_style("success", bold=True)
        assert "#00FF00" in style
        assert "bold" in style

    def test_get_progress_color_global(self):
        """Test global get_progress_color function."""
        color = get_progress_color(50)
        assert color == "#FFFF00"  # Default theme medium progress

    def test_apply_temporary_theme(self):
        """Test applying temporary theme."""
        # Get initial theme
        get_theme_manager().get_current_theme_type()

        # Apply temporary theme
        apply_temporary_theme(ThemeType.LIGHT)
        assert get_theme_manager().get_current_theme_type() == ThemeType.LIGHT

        # Verify color changed
        assert get_color("success") == "#859900"  # Solarized green

        # Apply different theme
        apply_temporary_theme(ThemeType.ACCESSIBILITY)
        assert get_theme_manager().get_current_theme_type() == ThemeType.ACCESSIBILITY
        assert get_color("success") == "#00AA00"  # High contrast green

    def test_apply_invalid_temporary_theme(self):
        """Test applying invalid temporary theme raises error."""
        with pytest.raises(ValueError, match="Unknown theme type"):
            apply_temporary_theme("invalid_theme")  # type: ignore

    def test_create_themed_console(self):
        """Test creating themed console."""
        # Test with default theme
        console = create_themed_console()
        assert isinstance(console, Console)

        # Test with light theme
        apply_temporary_theme(ThemeType.LIGHT)
        console = create_themed_console()
        assert isinstance(console, Console)


class TestThemeColors:
    """Test specific theme color schemes."""

    def test_default_theme_colors(self):
        """Test default theme has expected colors."""
        manager = ThemeManager()
        manager.set_current_theme(ThemeType.DEFAULT)

        # Test key colors
        assert manager.get_color("success") == "#00FF00"
        assert manager.get_color("warning") == "#FFA500"
        assert manager.get_color("error") == "#FF0000"
        assert manager.get_color("info") == "#0000FF"
        assert manager.get_color("primary") == "#4169E1"

    def test_light_theme_colors(self):
        """Test light theme has Solarized Light colors."""
        manager = ThemeManager()
        manager.set_current_theme(ThemeType.LIGHT)

        # Test Solarized Light colors
        assert manager.get_color("success") == "#859900"  # Solarized green
        assert manager.get_color("warning") == "#cb4b16"  # Solarized orange
        assert manager.get_color("error") == "#dc322f"    # Solarized red
        assert manager.get_color("info") == "#268bd2"     # Solarized blue
        assert manager.get_color("primary") == "#6c71c4"  # Solarized violet

    def test_accessibility_theme_colors(self):
        """Test accessibility theme has high contrast colors."""
        manager = ThemeManager()
        manager.set_current_theme(ThemeType.ACCESSIBILITY)

        # Test high contrast colors
        assert manager.get_color("success") == "#00AA00"  # High contrast green
        assert manager.get_color("warning") == "#FF8800"  # High contrast orange
        assert manager.get_color("error") == "#CC0000"    # High contrast red
        assert manager.get_color("text") == "#000000"     # Black text
        assert manager.get_color("background") == "#FFFFFF"  # White background

    def test_minimal_theme_colors(self):
        """Test minimal theme has grayscale colors."""
        manager = ThemeManager()
        manager.set_current_theme(ThemeType.MINIMAL)

        # Test grayscale colors
        assert manager.get_color("success") == "#AAAAAA"  # Gray
        assert manager.get_color("warning") == "#AAAAAA"  # Gray
        assert manager.get_color("error") == "#CCCCCC"    # Light gray
        assert manager.get_color("text") == "#FFFFFF"     # White text
        assert manager.get_color("background") == "#000000"  # Black background

    def test_dark_theme_colors(self):
        """Test dark theme has optimized dark colors."""
        manager = ThemeManager()
        manager.set_current_theme(ThemeType.DARK)

        # Test dark-optimized colors
        assert manager.get_color("success") == "#00FF00"
        assert manager.get_color("warning") == "#FFA500"
        assert manager.get_color("error") == "#FF4444"    # Softer red
        assert manager.get_color("info") == "#5555FF"     # Softer blue
        assert manager.get_color("primary") == "#6699FF"  # Softer primary


class TestThemeIntegration:
    """Test theme integration with other components."""

    def test_theme_persistence_across_operations(self):
        """Test theme persists across multiple operations."""
        # Set to light theme
        apply_temporary_theme(ThemeType.LIGHT)

        # Check color is correct
        assert get_color("success") == "#859900"

        # Use progress color function
        progress_color = get_progress_color(30)
        assert progress_color == "#859900"  # Light theme progress_low

        # Check theme is still light
        assert get_theme_manager().get_current_theme_type() == ThemeType.LIGHT

    def test_multiple_theme_switches(self):
        """Test switching between multiple themes."""
        # Ensure we start with default
        apply_temporary_theme(ThemeType.DEFAULT)
        initial_color = get_color("success")
        assert initial_color == "#00FF00"

        # Switch to light
        apply_temporary_theme(ThemeType.LIGHT)
        assert get_color("success") == "#859900"

        # Switch to accessibility
        apply_temporary_theme(ThemeType.ACCESSIBILITY)
        assert get_color("success") == "#00AA00"

        # Switch to minimal
        apply_temporary_theme(ThemeType.MINIMAL)
        assert get_color("success") == "#AAAAAA"

        # Switch back to default
        apply_temporary_theme(ThemeType.DEFAULT)
        assert get_color("success") == "#00FF00"

    def test_theme_affects_progress_colors(self):
        """Test theme affects progress color calculations."""
        # Test with default theme
        apply_temporary_theme(ThemeType.DEFAULT)
        default_low = get_progress_color(25)
        default_critical = get_progress_color(95)

        # Test with light theme
        apply_temporary_theme(ThemeType.LIGHT)
        light_low = get_progress_color(25)
        light_critical = get_progress_color(95)

        # Colors should be different
        assert default_low != light_low
        assert default_critical != light_critical

        # Light theme should have Solarized colors
        assert light_low == "#859900"      # Solarized green
        assert light_critical == "#dc322f"  # Solarized red
