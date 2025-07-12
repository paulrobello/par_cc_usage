"""Configuration management for par_cc_usage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .enums import DisplayMode, ThemeType, TimeFormat
from .utils import expand_path
from .xdg_dirs import (
    get_cache_dir,
    get_config_file_path,
    get_legacy_config_paths,
    migrate_legacy_config,
)


class DisplayConfig(BaseModel):
    """Display configuration settings."""

    show_progress_bars: bool = True
    show_active_sessions: bool = False
    update_in_place: bool = True
    refresh_interval: int = 1  # seconds
    time_format: TimeFormat = Field(
        default=TimeFormat.TWENTY_FOUR_HOUR,
        description="Time format: '12h' for 12-hour format, '24h' for 24-hour format",
    )
    project_name_prefixes: list[str] = Field(
        default_factory=lambda: ["-Users-", "-home-"],
        description="List of prefixes to strip from project names for cleaner display",
    )
    aggregate_by_project: bool = Field(
        default=True,
        description="Aggregate token usage by project instead of individual sessions",
    )
    show_tool_usage: bool = Field(
        default=False,
        description="Display tool usage information in monitoring and lists",
    )
    display_mode: DisplayMode = Field(
        default=DisplayMode.NORMAL,
        description="Display mode: 'normal' for full display, 'compact' for minimal view",
    )
    show_pricing: bool = Field(
        default=False,
        description="Show pricing information next to token counts",
    )
    theme: ThemeType = Field(
        default=ThemeType.DEFAULT,
        description="Theme to use for display styling: 'default', 'dark', 'light', 'accessibility', or 'minimal'",
    )


class NotificationConfig(BaseModel):
    """Notification configuration settings."""

    discord_webhook_url: str | None = Field(
        default=None,
        description="Discord webhook URL for block completion notifications",
    )
    slack_webhook_url: str | None = Field(
        default=None,
        description="Slack webhook URL for block completion notifications",
    )
    notify_on_block_completion: bool = Field(
        default=True,
        description="Send notification when a 5-hour block completes",
    )
    cooldown_minutes: int = Field(
        default=5,
        description="Minimum minutes between notifications for the same block",
    )


class Config(BaseModel):
    """Main configuration for par_cc_usage."""

    projects_dir: Path = Field(
        default_factory=lambda: Path.home() / ".claude" / "projects",
        description="Directory containing Claude Code project JSONL files",
    )
    # New field for multi-directory support
    projects_dirs: list[Path] | None = Field(
        default=None,
        description="Multiple Claude directories (overrides projects_dir if set)",
    )
    polling_interval: int = Field(
        default=5,
        description="File polling interval in seconds",
    )
    timezone: str = Field(
        default="America/Los_Angeles",
        description="Timezone for display (IANA timezone name)",
    )
    token_limit: int | None = Field(
        default=None,
        description="Token limit (auto-detect if not set)",
    )
    cache_dir: Path = Field(
        default_factory=get_cache_dir,
        description="Directory for caching file states",
    )
    disable_cache: bool = Field(
        default=False,
        description="Disable file monitoring cache",
    )
    display: DisplayConfig = Field(
        default_factory=DisplayConfig,
        description="Display configuration",
    )
    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig,
        description="Notification configuration",
    )
    recent_activity_window_hours: int = Field(
        default=5,
        description="Hours to consider as 'recent' activity for smart block selection (matches billing block duration)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Ensure directories exist after initialization."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_claude_paths(self) -> list[Path]:
        """Get all Claude project directories to monitor.

        Returns:
            List of valid Claude project directories
        """
        paths: list[Path] = []

        if self.projects_dirs:
            # Use explicitly configured directories
            paths.extend(self.projects_dirs)
        else:
            # Check default paths
            default_paths = [
                Path.home() / ".config" / "claude" / "projects",  # New default
                Path.home() / ".claude" / "projects",  # Legacy default
            ]
            for path in default_paths:
                if path.exists() and path.is_dir():
                    paths.append(path)

            # If no defaults exist, use configured single path
            if not paths and self.projects_dir:
                paths.append(self.projects_dir)

        # Deduplicate and validate paths
        valid_paths: list[Path] = []
        seen: set[str] = set()

        for path in paths:
            path_str = str(path.resolve())
            if path_str not in seen and path.exists() and path.is_dir():
                seen.add(path_str)
                valid_paths.append(path)

        return valid_paths


def _load_config_file(config_file: Path | None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if config_file is None:
        config_file = get_config_file_path()

    # Check for and migrate legacy config files
    try:
        config_exists = config_file.exists()
    except (PermissionError, OSError):
        # If we can't check if config exists due to permissions, skip migration
        config_exists = True

    if not config_exists:
        for legacy_path in get_legacy_config_paths():
            if migrate_legacy_config(legacy_path):
                # Config was migrated, use the new XDG location
                config_file = get_config_file_path()
                break

    try:
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config_dict = yaml.safe_load(f) or {}
                    # Expand paths in the config
                    _expand_paths_in_config(config_dict)
                    return config_dict
            except (UnicodeDecodeError, yaml.YAMLError, OSError):
                # If config file is corrupted or unreadable, return empty dict
                # This allows the application to continue with defaults
                return {}
    except (PermissionError, OSError):
        # If we can't check if config exists due to permissions, return empty dict
        return {}
    return {}


def _expand_paths_in_config(config_dict: dict[str, Any]) -> None:
    """Expand tilde and environment variables in path fields."""
    path_fields = ["projects_dir", "cache_dir"]

    for field in path_fields:
        if field in config_dict and isinstance(config_dict[field], str):
            config_dict[field] = expand_path(config_dict[field])


def _parse_int_value(value: str) -> int | None:
    """Parse integer value with error handling."""
    try:
        return int(value)
    except ValueError:
        return None


def _parse_bool_value(value: str) -> bool:
    """Parse boolean value from string."""
    return value.lower() in ("true", "1", "yes", "on")


def _parse_time_format_value(value: str) -> TimeFormat | None:
    """Parse time format value with validation."""
    try:
        return TimeFormat(value)
    except ValueError:
        return None


def _parse_display_mode_value(value: str) -> DisplayMode | None:
    """Parse display mode value with validation."""
    try:
        return DisplayMode(value)
    except ValueError:
        return None


def _parse_prefix_list_value(value: str) -> list[str]:
    """Parse comma-separated prefix list."""
    return [prefix.strip() for prefix in value.split(",") if prefix.strip()]


def _parse_env_value(value: str, config_key: str) -> Any:
    """Parse environment variable value based on config key type."""
    # Integer fields
    if config_key in [
        "polling_interval",
        "token_limit",
        "refresh_interval",
        "cooldown_minutes",
        "recent_activity_window_hours",
    ]:
        return _parse_int_value(value)

    # Path fields
    elif config_key in ["projects_dir", "cache_dir"]:
        return expand_path(value)

    # Boolean fields
    elif config_key in [
        "disable_cache",
        "notify_on_block_completion",
        "show_progress_bars",
        "show_active_sessions",
        "update_in_place",
        "aggregate_by_project",
        "show_tool_usage",
        "show_pricing",
    ]:
        return _parse_bool_value(value)

    # Special enum fields
    elif config_key == "time_format":
        return _parse_time_format_value(value)
    elif config_key == "display_mode":
        return _parse_display_mode_value(value)

    # List fields
    elif config_key == "project_name_prefixes":
        return _parse_prefix_list_value(value)

    # String fields (timezone, webhook URLs, etc.)
    else:
        return value


def _apply_env_overrides(config_dict: dict[str, Any], env_mapping: dict[str, str]) -> None:
    """Apply environment variable overrides to config dictionary."""
    for env_var, config_key in env_mapping.items():
        if value := os.getenv(env_var):
            parsed_value = _parse_env_value(value, config_key)
            if parsed_value is not None:
                config_dict[config_key] = parsed_value


def _apply_nested_env_overrides(config_dict: dict[str, Any], section_name: str, env_mapping: dict[str, str]) -> None:
    """Apply environment variable overrides to nested config section."""
    section_dict = config_dict.get(section_name, {})
    for env_var, config_key in env_mapping.items():
        if value := os.getenv(env_var):
            parsed_value = _parse_env_value(value, config_key)
            if parsed_value is not None:
                section_dict[config_key] = parsed_value

    if section_dict:
        config_dict[section_name] = section_dict


def _get_top_level_env_mapping() -> dict[str, str]:
    """Get environment variable mapping for top-level config fields."""
    return {
        "PAR_CC_USAGE_PROJECTS_DIR": "projects_dir",
        "PAR_CC_USAGE_POLLING_INTERVAL": "polling_interval",
        "PAR_CC_USAGE_TIMEZONE": "timezone",
        "PAR_CC_USAGE_TOKEN_LIMIT": "token_limit",
        "PAR_CC_USAGE_CACHE_DIR": "cache_dir",
        "PAR_CC_USAGE_DISABLE_CACHE": "disable_cache",
        "PAR_CC_USAGE_RECENT_ACTIVITY_WINDOW_HOURS": "recent_activity_window_hours",
    }


def _get_display_env_mapping() -> dict[str, str]:
    """Get environment variable mapping for display config fields."""
    return {
        "PAR_CC_USAGE_SHOW_PROGRESS_BARS": "show_progress_bars",
        "PAR_CC_USAGE_SHOW_ACTIVE_SESSIONS": "show_active_sessions",
        "PAR_CC_USAGE_UPDATE_IN_PLACE": "update_in_place",
        "PAR_CC_USAGE_REFRESH_INTERVAL": "refresh_interval",
        "PAR_CC_USAGE_TIME_FORMAT": "time_format",
        "PAR_CC_USAGE_PROJECT_NAME_PREFIXES": "project_name_prefixes",
        "PAR_CC_USAGE_SHOW_TOOL_USAGE": "show_tool_usage",
        "PAR_CC_USAGE_DISPLAY_MODE": "display_mode",
        "PAR_CC_USAGE_SHOW_PRICING": "show_pricing",
        "PAR_CC_USAGE_THEME": "theme",
    }


def _get_notification_env_mapping() -> dict[str, str]:
    """Get environment variable mapping for notification config fields."""
    return {
        "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "discord_webhook_url",
        "PAR_CC_USAGE_SLACK_WEBHOOK_URL": "slack_webhook_url",
        "PAR_CC_USAGE_NOTIFY_ON_BLOCK_COMPLETION": "notify_on_block_completion",
        "PAR_CC_USAGE_COOLDOWN_MINUTES": "cooldown_minutes",
    }


def _apply_claude_config_dir_override(config_dict: dict[str, Any]) -> None:
    """Apply CLAUDE_CONFIG_DIR environment variable for multi-directory support."""
    if claude_dirs := os.getenv("CLAUDE_CONFIG_DIR"):
        config_dict["projects_dirs"] = [Path(p.strip()) for p in claude_dirs.split(",") if p.strip()]


def load_config(config_file: Path | None = None) -> Config:
    """Load configuration from file and environment variables.

    Priority order:
    1. Environment variables (PAR_CC_USAGE_*)
    2. Config file (XDG location or legacy)
    3. Default values

    Args:
        config_file: Path to configuration file (defaults to XDG config location)

    Returns:
        Loaded configuration
    """
    # Load from config file
    try:
        config_dict = _load_config_file(config_file)
    except (PermissionError, OSError):
        # If config file loading fails due to permissions, use empty dict
        config_dict = {}

    # Apply Claude config directory override
    _apply_claude_config_dir_override(config_dict)

    # Apply environment overrides
    _apply_env_overrides(config_dict, _get_top_level_env_mapping())
    _apply_nested_env_overrides(config_dict, "display", _get_display_env_mapping())
    _apply_nested_env_overrides(config_dict, "notifications", _get_notification_env_mapping())

    return Config(**config_dict)


def save_default_config(config_file: Path) -> None:
    """Save default configuration to file.

    Args:
        config_file: Path to save configuration
    """
    default_config = Config()
    save_config(default_config, config_file)


def save_config(config: Config, config_file: Path) -> None:
    """Save configuration to file.

    Args:
        config: Configuration to save
        config_file: Path to save configuration
    """
    config_dict: dict[str, Any] = {
        "projects_dir": str(config.projects_dir),
        "polling_interval": config.polling_interval,
        "timezone": config.timezone,
        "token_limit": config.token_limit,
        "cache_dir": str(config.cache_dir),
        "display": {
            "show_progress_bars": config.display.show_progress_bars,
            "show_active_sessions": config.display.show_active_sessions,
            "update_in_place": config.display.update_in_place,
            "refresh_interval": config.display.refresh_interval,
            "time_format": config.display.time_format.value,
            "project_name_prefixes": config.display.project_name_prefixes,
            "display_mode": config.display.display_mode.value,
            "show_pricing": config.display.show_pricing,
        },
        "notifications": {
            "discord_webhook_url": config.notifications.discord_webhook_url,
            "slack_webhook_url": config.notifications.slack_webhook_url,
            "notify_on_block_completion": config.notifications.notify_on_block_completion,
            "cooldown_minutes": config.notifications.cooldown_minutes,
        },
    }

    # Add projects_dirs if configured
    if config.projects_dirs:
        config_dict["projects_dirs"] = [str(p) for p in config.projects_dirs]

    # Ensure XDG directories exist
    from .xdg_dirs import ensure_xdg_directories

    ensure_xdg_directories()

    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


def update_config_token_limit(config_file: Path, token_limit: int) -> None:
    """Update token limit in config file.

    Args:
        config_file: Path to config file
        token_limit: New token limit
    """
    if config_file.exists():
        config = load_config(config_file)
        config.token_limit = token_limit
        save_config(config, config_file)


def get_default_token_limit() -> int:
    """Get default token limit based on detected model.

    Returns:
        Default token limit
    """
    # Default to 500k for now, can be made smarter later
    return 500_000
