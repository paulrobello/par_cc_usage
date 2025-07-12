"""Theme system for par_cc_usage display styling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.theme import Theme

from .enums import ThemeType


class ColorScheme(BaseModel):
    """Color scheme definition with semantic color mappings."""

    # Status colors
    success: str = Field(description="Success/positive state color")
    warning: str = Field(description="Warning/caution state color")
    error: str = Field(description="Error/danger state color")
    info: str = Field(description="Information/neutral state color")

    # UI element colors
    primary: str = Field(description="Primary UI element color")
    secondary: str = Field(description="Secondary UI element color")
    accent: str = Field(description="Accent/highlight color")
    border: str = Field(description="Border color for panels and tables")
    background: str = Field(description="Background color")
    text: str = Field(description="Primary text color")
    text_dim: str = Field(description="Dimmed/secondary text color")

    # Data-specific colors
    token_count: str = Field(description="Token count display color")
    model_name: str = Field(description="Model name display color")
    project_name: str = Field(description="Project name display color")
    tool_usage: str = Field(description="Tool usage display color")
    cost: str = Field(description="Cost/pricing display color")

    # Progress and status indicators
    progress_low: str = Field(description="Progress bar low usage color (0-50%)")
    progress_medium: str = Field(description="Progress bar medium usage color (50-75%)")
    progress_high: str = Field(description="Progress bar high usage color (75-90%)")
    progress_critical: str = Field(description="Progress bar critical usage color (90%+)")

    # Burn rate and timing
    burn_rate: str = Field(description="Burn rate display color")
    eta_normal: str = Field(description="Normal ETA display color")
    eta_urgent: str = Field(description="Urgent ETA display color")

    # Interruption indicators
    interruption_none: str = Field(description="No interruptions color (good)")
    interruption_present: str = Field(description="Interruptions present color (warning)")


@dataclass
class ThemeDefinition:
    """Complete theme definition with metadata."""

    name: str
    description: str
    colors: ColorScheme
    rich_theme: Theme


class ThemeManager:
    """Manages themes and provides color resolution."""

    def __init__(self) -> None:
        """Initialize the theme manager with built-in themes."""
        self._themes: dict[ThemeType, ThemeDefinition] = {}
        self._current_theme: ThemeType = ThemeType.DEFAULT
        self._load_builtin_themes()

    def _load_builtin_themes(self) -> None:
        """Load all built-in theme definitions."""
        # Default theme (current bright colors)
        default_colors = ColorScheme(
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
            cost="#00FF80",
            progress_low="#00FF00",
            progress_medium="#FFFF00",
            progress_high="#FFA500",
            progress_critical="#FF0000",
            burn_rate="#00FFFF",
            eta_normal="#00FFFF",
            eta_urgent="#FF0000",
            interruption_none="#00FF00",
            interruption_present="#FF6B6B",
        )

        default_rich_theme = Theme(
            {
                "success": default_colors.success,
                "warning": default_colors.warning,
                "error": default_colors.error,
                "info": default_colors.info,
                "primary": default_colors.primary,
                "secondary": default_colors.secondary,
                "accent": default_colors.accent,
                "border": default_colors.border,
                "text": default_colors.text,
                "text_dim": default_colors.text_dim,
                "token_count": default_colors.token_count,
                "model_name": default_colors.model_name,
                "project_name": default_colors.project_name,
                "tool_usage": default_colors.tool_usage,
                "cost": default_colors.cost,
                "progress_low": default_colors.progress_low,
                "progress_medium": default_colors.progress_medium,
                "progress_high": default_colors.progress_high,
                "progress_critical": default_colors.progress_critical,
                "burn_rate": default_colors.burn_rate,
                "eta_normal": default_colors.eta_normal,
                "eta_urgent": default_colors.eta_urgent,
                "interruption_none": default_colors.interruption_none,
                "interruption_present": default_colors.interruption_present,
            }
        )

        self._themes[ThemeType.DEFAULT] = ThemeDefinition(
            name="Default",
            description="Default bright color theme (current colors)",
            colors=default_colors,
            rich_theme=default_rich_theme,
        )

        # Dark theme (similar to default but optimized for dark backgrounds)
        dark_colors = ColorScheme(
            success="#00FF00",
            warning="#FFA500",
            error="#FF4444",
            info="#5555FF",
            primary="#6699FF",
            secondary="#00FFFF",
            accent="#FF88FF",
            border="#FFFF00",
            background="#000000",
            text="#FFFFFF",
            text_dim="dim",
            token_count="#FFFF00",
            model_name="bright_green",
            project_name="#00FFFF",
            tool_usage="#FF9900",
            cost="#00FF80",
            progress_low="#00FF00",
            progress_medium="#FFFF00",
            progress_high="#FFA500",
            progress_critical="#FF4444",
            burn_rate="#00FFFF",
            eta_normal="#00FFFF",
            eta_urgent="#FF4444",
            interruption_none="#00FF00",
            interruption_present="#FF6B6B",
        )

        dark_rich_theme = Theme(
            {
                "success": dark_colors.success,
                "warning": dark_colors.warning,
                "error": dark_colors.error,
                "info": dark_colors.info,
                "primary": dark_colors.primary,
                "secondary": dark_colors.secondary,
                "accent": dark_colors.accent,
                "border": dark_colors.border,
                "text": dark_colors.text,
                "text_dim": dark_colors.text_dim,
                "token_count": dark_colors.token_count,
                "model_name": dark_colors.model_name,
                "project_name": dark_colors.project_name,
                "tool_usage": dark_colors.tool_usage,
                "cost": dark_colors.cost,
                "progress_low": dark_colors.progress_low,
                "progress_medium": dark_colors.progress_medium,
                "progress_high": dark_colors.progress_high,
                "progress_critical": dark_colors.progress_critical,
                "burn_rate": dark_colors.burn_rate,
                "eta_normal": dark_colors.eta_normal,
                "eta_urgent": dark_colors.eta_urgent,
                "interruption_none": dark_colors.interruption_none,
                "interruption_present": dark_colors.interruption_present,
            }
        )

        self._themes[ThemeType.DARK] = ThemeDefinition(
            name="Dark",
            description="Dark theme optimized for dark terminals",
            colors=dark_colors,
            rich_theme=dark_rich_theme,
        )

        # Light theme (Solarized Light inspired)
        light_colors = ColorScheme(
            success="#859900",  # Solarized green
            warning="#cb4b16",  # Solarized orange
            error="#dc322f",  # Solarized red
            info="#268bd2",  # Solarized blue
            primary="#6c71c4",  # Solarized violet
            secondary="#2aa198",  # Solarized cyan
            accent="#d33682",  # Solarized magenta
            border="#93a1a1",  # Solarized base1
            background="#fdf6e3",  # Solarized base3
            text="#586e75",  # Solarized base01
            text_dim="#839496",  # Solarized base0
            token_count="#b58900",  # Solarized yellow
            model_name="#859900",  # Solarized green
            project_name="#2aa198",  # Solarized cyan
            tool_usage="#cb4b16",  # Solarized orange
            cost="#859900",  # Solarized green
            progress_low="#859900",  # Green
            progress_medium="#b58900",  # Yellow
            progress_high="#cb4b16",  # Orange
            progress_critical="#dc322f",  # Red
            burn_rate="#2aa198",  # Cyan
            eta_normal="#2aa198",  # Cyan
            eta_urgent="#dc322f",  # Red
            interruption_none="#859900",  # Green
            interruption_present="#dc322f",  # Red
        )

        light_rich_theme = Theme(
            {
                "success": light_colors.success,
                "warning": light_colors.warning,
                "error": light_colors.error,
                "info": light_colors.info,
                "primary": light_colors.primary,
                "secondary": light_colors.secondary,
                "accent": light_colors.accent,
                "border": light_colors.border,
                "text": light_colors.text,
                "text_dim": light_colors.text_dim,
                "token_count": light_colors.token_count,
                "model_name": light_colors.model_name,
                "project_name": light_colors.project_name,
                "tool_usage": light_colors.tool_usage,
                "cost": light_colors.cost,
                "progress_low": light_colors.progress_low,
                "progress_medium": light_colors.progress_medium,
                "progress_high": light_colors.progress_high,
                "progress_critical": light_colors.progress_critical,
                "burn_rate": light_colors.burn_rate,
                "eta_normal": light_colors.eta_normal,
                "eta_urgent": light_colors.eta_urgent,
                "interruption_none": light_colors.interruption_none,
                "interruption_present": light_colors.interruption_present,
            }
        )

        self._themes[ThemeType.LIGHT] = ThemeDefinition(
            name="Light",
            description="Light theme based on Solarized Light with high contrast",
            colors=light_colors,
            rich_theme=light_rich_theme,
        )

        # Accessibility theme (high contrast)
        accessibility_colors = ColorScheme(
            success="#00AA00",  # High contrast green
            warning="#FF8800",  # High contrast orange
            error="#CC0000",  # High contrast red
            info="#0066CC",  # High contrast blue
            primary="#000080",  # Navy blue
            secondary="#006666",  # Teal
            accent="#800080",  # Purple
            border="#666666",  # Gray
            background="#FFFFFF",  # White
            text="#000000",  # Black
            text_dim="#666666",  # Gray
            token_count="#CC6600",  # Dark orange
            model_name="#00AA00",  # High contrast green
            project_name="#006666",  # Teal
            tool_usage="#FF8800",  # High contrast orange
            cost="#00AA00",  # High contrast green
            progress_low="#00AA00",  # Green
            progress_medium="#CC6600",  # Orange
            progress_high="#FF8800",  # Orange
            progress_critical="#CC0000",  # Red
            burn_rate="#006666",  # Teal
            eta_normal="#006666",  # Teal
            eta_urgent="#CC0000",  # Red
            interruption_none="#00AA00",  # Green
            interruption_present="#CC0000",  # Red
        )

        accessibility_rich_theme = Theme(
            {
                "success": accessibility_colors.success,
                "warning": accessibility_colors.warning,
                "error": accessibility_colors.error,
                "info": accessibility_colors.info,
                "primary": accessibility_colors.primary,
                "secondary": accessibility_colors.secondary,
                "accent": accessibility_colors.accent,
                "border": accessibility_colors.border,
                "text": accessibility_colors.text,
                "text_dim": accessibility_colors.text_dim,
                "token_count": accessibility_colors.token_count,
                "model_name": accessibility_colors.model_name,
                "project_name": accessibility_colors.project_name,
                "tool_usage": accessibility_colors.tool_usage,
                "cost": accessibility_colors.cost,
                "progress_low": accessibility_colors.progress_low,
                "progress_medium": accessibility_colors.progress_medium,
                "progress_high": accessibility_colors.progress_high,
                "progress_critical": accessibility_colors.progress_critical,
                "burn_rate": accessibility_colors.burn_rate,
                "eta_normal": accessibility_colors.eta_normal,
                "eta_urgent": accessibility_colors.eta_urgent,
                "interruption_none": accessibility_colors.interruption_none,
                "interruption_present": accessibility_colors.interruption_present,
            }
        )

        self._themes[ThemeType.ACCESSIBILITY] = ThemeDefinition(
            name="Accessibility",
            description="High contrast theme meeting WCAG AAA standards",
            colors=accessibility_colors,
            rich_theme=accessibility_rich_theme,
        )

        # Minimal theme (grayscale with minimal color)
        minimal_colors = ColorScheme(
            success="#AAAAAA",  # Gray
            warning="#AAAAAA",  # Gray
            error="#CCCCCC",  # Light gray
            info="#AAAAAA",  # Gray
            primary="#FFFFFF",  # White
            secondary="#CCCCCC",  # Light gray
            accent="#FFFFFF",  # White
            border="#666666",  # Dark gray
            background="#000000",  # Black
            text="#FFFFFF",  # White
            text_dim="#AAAAAA",  # Gray
            token_count="#FFFFFF",  # White
            model_name="#CCCCCC",  # Light gray
            project_name="#FFFFFF",  # White
            tool_usage="#AAAAAA",  # Gray
            cost="#CCCCCC",  # Light gray
            progress_low="#AAAAAA",  # Gray
            progress_medium="#CCCCCC",  # Light gray
            progress_high="#FFFFFF",  # White
            progress_critical="#FFFFFF",  # White
            burn_rate="#CCCCCC",  # Light gray
            eta_normal="#CCCCCC",  # Light gray
            eta_urgent="#FFFFFF",  # White
            interruption_none="#AAAAAA",  # Gray
            interruption_present="#CCCCCC",  # Light gray
        )

        minimal_rich_theme = Theme(
            {
                "success": minimal_colors.success,
                "warning": minimal_colors.warning,
                "error": minimal_colors.error,
                "info": minimal_colors.info,
                "primary": minimal_colors.primary,
                "secondary": minimal_colors.secondary,
                "accent": minimal_colors.accent,
                "border": minimal_colors.border,
                "text": minimal_colors.text,
                "text_dim": minimal_colors.text_dim,
                "token_count": minimal_colors.token_count,
                "model_name": minimal_colors.model_name,
                "project_name": minimal_colors.project_name,
                "tool_usage": minimal_colors.tool_usage,
                "cost": minimal_colors.cost,
                "progress_low": minimal_colors.progress_low,
                "progress_medium": minimal_colors.progress_medium,
                "progress_high": minimal_colors.progress_high,
                "progress_critical": minimal_colors.progress_critical,
                "burn_rate": minimal_colors.burn_rate,
                "eta_normal": minimal_colors.eta_normal,
                "eta_urgent": minimal_colors.eta_urgent,
                "interruption_none": minimal_colors.interruption_none,
                "interruption_present": minimal_colors.interruption_present,
            }
        )

        self._themes[ThemeType.MINIMAL] = ThemeDefinition(
            name="Minimal",
            description="Minimal grayscale theme with reduced color usage",
            colors=minimal_colors,
            rich_theme=minimal_rich_theme,
        )

    def get_theme(self, theme_type: ThemeType) -> ThemeDefinition:
        """Get a theme definition by type.

        Args:
            theme_type: The theme type to retrieve

        Returns:
            The theme definition

        Raises:
            KeyError: If the theme type is not found
        """
        return self._themes[theme_type]

    def set_current_theme(self, theme_type: ThemeType) -> None:
        """Set the current active theme.

        Args:
            theme_type: The theme type to set as current
        """
        if theme_type not in self._themes:
            raise ValueError(f"Unknown theme type: {theme_type}")
        self._current_theme = theme_type

    def get_current_theme(self) -> ThemeDefinition:
        """Get the current active theme definition.

        Returns:
            The current theme definition
        """
        return self._themes[self._current_theme]

    def get_current_theme_type(self) -> ThemeType:
        """Get the current active theme type.

        Returns:
            The current theme type
        """
        return self._current_theme

    def list_themes(self) -> dict[ThemeType, ThemeDefinition]:
        """List all available themes.

        Returns:
            Dictionary of theme types to theme definitions
        """
        return self._themes.copy()

    def get_color(self, semantic_name: str) -> str:
        """Get a color value by semantic name from the current theme.

        Args:
            semantic_name: The semantic name of the color

        Returns:
            The color value for the current theme

        Raises:
            AttributeError: If the semantic name is not found
        """
        current_theme = self.get_current_theme()
        return getattr(current_theme.colors, semantic_name)

    def get_style(self, semantic_name: str, **kwargs: Any) -> str:
        """Get a style string by semantic name from the current theme.

        Args:
            semantic_name: The semantic name of the color
            **kwargs: Additional style attributes (bold, italic, etc.)

        Returns:
            The style string for the current theme

        Raises:
            AttributeError: If the semantic name is not found
        """
        color = self.get_color(semantic_name)
        style_parts = [color]

        # Add style attributes
        for attr, value in kwargs.items():
            if value:
                style_parts.append(attr)

        return " ".join(style_parts)

    def get_progress_color(self, percentage: float) -> str:
        """Get the appropriate progress color based on percentage.

        Args:
            percentage: The progress percentage (0-100)

        Returns:
            The appropriate progress color
        """
        if percentage >= 90:
            return self.get_color("progress_critical")
        elif percentage >= 75:
            return self.get_color("progress_high")
        elif percentage >= 50:
            return self.get_color("progress_medium")
        else:
            return self.get_color("progress_low")

    def create_rich_console(self, **kwargs: Any) -> Console:
        """Create a Rich Console with the current theme applied.

        Args:
            **kwargs: Additional arguments to pass to Console constructor

        Returns:
            A Rich Console instance with the current theme
        """
        current_theme = self.get_current_theme()
        return Console(theme=current_theme.rich_theme, **kwargs)


# Global theme manager instance
_theme_manager: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance.

    Returns:
        The global theme manager instance
    """
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def get_color(semantic_name: str) -> str:
    """Get a color value by semantic name from the current theme.

    Args:
        semantic_name: The semantic name of the color

    Returns:
        The color value for the current theme
    """
    return get_theme_manager().get_color(semantic_name)


def get_style(semantic_name: str, **kwargs: Any) -> str:
    """Get a style string by semantic name from the current theme.

    Args:
        semantic_name: The semantic name of the color
        **kwargs: Additional style attributes (bold, italic, etc.)

    Returns:
        The style string for the current theme
    """
    return get_theme_manager().get_style(semantic_name, **kwargs)


def get_progress_color(percentage: float) -> str:
    """Get the appropriate progress color based on percentage.

    Args:
        percentage: The progress percentage (0-100)

    Returns:
        The appropriate progress color
    """
    return get_theme_manager().get_progress_color(percentage)


def create_themed_console(**kwargs: Any) -> Console:
    """Create a Rich Console with the current theme applied.

    Args:
        **kwargs: Additional arguments to pass to Console constructor

    Returns:
        A Rich Console instance with the current theme
    """
    return get_theme_manager().create_rich_console(**kwargs)


def apply_temporary_theme(theme_type: ThemeType) -> None:
    """Apply a theme temporarily for the current session.

    Args:
        theme_type: The theme type to apply temporarily

    Raises:
        ValueError: If the theme type is invalid
    """
    theme_manager = get_theme_manager()
    theme_manager.set_current_theme(theme_type)
