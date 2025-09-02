"""Configuration management for par_cc_usage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from .models import UsageSnapshot

from .enums import DisplayMode, ThemeType, TimeFormat
from .utils import detect_system_timezone, expand_path
from .xdg_dirs import (
    get_cache_dir,
    get_config_file_path,
    get_legacy_config_paths,
    migrate_legacy_config,
)


class DisplayConfig(BaseModel):
    """Display configuration settings."""

    show_progress_bars: bool = True
    show_active_sessions: bool = True
    update_in_place: bool = True
    refresh_interval: int = 5  # seconds
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
        default=True,
        description="Display tool usage information in monitoring and lists",
    )
    display_mode: DisplayMode = Field(
        default=DisplayMode.NORMAL,
        description="Display mode: 'normal' for full display, 'compact' for minimal view",
    )
    show_pricing: bool = Field(
        default=True,
        description="Show pricing information next to token counts",
    )
    theme: ThemeType = Field(
        default=ThemeType.DEFAULT,
        description="Theme to use for display styling: 'default', 'dark', 'light', 'accessibility', or 'minimal'",
    )
    use_p90_limit: bool = Field(
        default=True,
        description="Use P90 values instead of absolute maximum for progress bar limits",
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
        default="auto",
        description="Timezone for display (IANA timezone name or 'auto' for system detection)",
    )
    auto_detected_timezone: str = Field(
        default="America/Los_Angeles",
        description="Automatically detected system timezone (used when timezone='auto')",
    )
    token_limit: int | None = Field(
        default=None,
        description="Token limit (auto-detect if not set)",
    )
    message_limit: int | None = Field(
        default=None,
        description="Message limit (auto-detect if not set)",
    )
    cost_limit: float | None = Field(
        default=None,
        description="Cost limit in USD (no auto-detection)",
    )
    max_unified_block_tokens_encountered: int = Field(
        default=0,
        description="Maximum tokens from any unified block (5-hour period) encountered in history (updated automatically)",
    )
    max_unified_block_messages_encountered: int = Field(
        default=0,
        description="Maximum messages from any unified block (5-hour period) encountered in history (updated automatically)",
    )
    max_unified_block_cost_encountered: float = Field(
        default=0.0,
        description="Maximum cost from any unified block (5-hour period) encountered in history (updated automatically)",
    )
    p90_unified_block_tokens_encountered: int = Field(
        default=0,
        description="P90 tokens from unified blocks (5-hour periods) encountered in history (updated automatically)",
    )
    p90_unified_block_messages_encountered: int = Field(
        default=0,
        description="P90 messages from unified blocks (5-hour periods) encountered in history (updated automatically)",
    )
    p90_unified_block_cost_encountered: float = Field(
        default=0.0,
        description="P90 cost from unified blocks (5-hour periods) encountered in history (updated automatically)",
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
    config_ro: bool = Field(
        default=False,
        description="Read-only mode: prevents automatic updates to config file (max values, limits)",
    )
    model_multipliers: dict[str, float] = Field(
        default_factory=lambda: {"opus": 5.0, "sonnet": 1.0, "default": 1.0},
        description="Token multipliers per model type (default fallback for unlisted models)",
    )
    statusline_enabled: bool = Field(
        default=True,
        description="Enable Claude Code status line generation and caching",
    )
    statusline_use_grand_total: bool = Field(
        default=False,
        description="Always return grand total in status line regardless of session",
    )
    statusline_template: str = Field(
        default="{project}{sep}{tokens}{sep}{cost}{sep}{remaining_block_time}{sep} SES:{model}{sep}{session_tokens}/{session_tokens_total}",
        description="Template for status line format. Available variables: {project}, {tokens}, {messages}, {cost}, {remaining_block_time}, {sep}, {username}, {hostname}, {date}, {current_time}, {model}, {session_tokens}, {session_tokens_total}. Use \\n for multi-line.",
    )
    statusline_date_format: str = Field(
        default="%Y-%m-%d",
        description="Date format for {date} in status line (strftime format). Default: YYYY-MM-DD",
    )
    statusline_time_format: str = Field(
        default="%I:%M %p",
        description="Time format for {current_time} in status line (strftime format). Default: 12hr (HH:MM AM/PM)",
    )
    statusline_git_clean_indicator: str = Field(
        default="✓",
        description="Indicator for clean git status. Can be emoji (✓, ✅, 🟢) or text (clean, OK). Default: ✓",
    )
    statusline_git_dirty_indicator: str = Field(
        default="*",
        description="Indicator for dirty git status. Can be emoji (*, ⚠️, 🔴) or text (dirty, modified). Default: *",
    )
    statusline_progress_bar_length: int = Field(
        default=15,
        description="Length of progress bar in status line. Default: 15 characters",
        ge=5,
        le=50,
    )
    statusline_progress_bar_colorize: bool = Field(
        default=True,
        description="Colorize progress bar based on utilization (green < 50%, yellow < 80%, red >= 80%). Default: True",
    )
    statusline_progress_bar_style: Literal["basic", "rich"] = Field(
        default="rich",
        description="Progress bar style: 'basic' (simple Unicode blocks) or 'rich' (Rich library rendering). Default: rich",
    )
    statusline_progress_bar_show_percent: bool = Field(
        default=True,
        description="Show percentage in the center of the progress bar. Automatically adds 3 chars to bar length. Default: True",
    )
    statusline_separator: str = Field(
        default=" - ",
        description="Separator string for status line template {sep} variable. Default: ' - '",
    )

    @field_validator("model_multipliers")
    @classmethod
    def validate_model_multipliers(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate model multipliers are positive values."""
        for model, multiplier in v.items():
            if multiplier <= 0:
                raise ValueError(f"Model multiplier for '{model}' must be positive, got {multiplier}")

        # Ensure 'default' is present
        if "default" not in v:
            v["default"] = 1.0

        return v

    def model_post_init(self, __context: Any) -> None:
        """Ensure directories exist after initialization."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_effective_timezone(self) -> str:
        """Get the effective timezone to use for display.

        Returns:
            The timezone string to use - either auto_detected_timezone if timezone is 'auto',
            or the configured timezone value
        """
        if self.timezone == "auto":
            return self.auto_detected_timezone or "America/Los_Angeles"
        return self.timezone

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


def _parse_model_multipliers_value(value: str) -> dict[str, float]:
    """Parse model multipliers from string format 'opus=5.0,sonnet=1.5,default=1.0'."""
    multipliers = {}
    for pair in value.split(","):
        if "=" in pair:
            model, multiplier_str = pair.split("=", 1)
            try:
                multiplier = float(multiplier_str.strip())
                if multiplier <= 0:
                    raise ValueError(f"Multiplier for '{model.strip()}' must be positive, got {multiplier}")
                multipliers[model.strip()] = multiplier
            except ValueError as e:
                raise ValueError(f"Invalid multiplier value for '{model.strip()}': {e}") from e

    if not multipliers:
        raise ValueError("No valid multipliers found in input string")

    # Ensure 'default' is present
    if "default" not in multipliers:
        multipliers["default"] = 1.0

    return multipliers


def _parse_env_value(value: str, config_key: str) -> Any:
    """Parse environment variable value based on config key type."""
    # Integer fields
    if config_key in [
        "polling_interval",
        "token_limit",
        "message_limit",
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
        "config_ro",
        "use_p90_limit",
        "statusline_enabled",
        "statusline_use_grand_total",
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

    # Dictionary fields
    elif config_key == "model_multipliers":
        return _parse_model_multipliers_value(value)

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
        "PAR_CC_USAGE_MESSAGE_LIMIT": "message_limit",
        "PAR_CC_USAGE_CACHE_DIR": "cache_dir",
        "PAR_CC_USAGE_DISABLE_CACHE": "disable_cache",
        "PAR_CC_USAGE_RECENT_ACTIVITY_WINDOW_HOURS": "recent_activity_window_hours",
        "PAR_CC_USAGE_CONFIG_RO": "config_ro",
        "PAR_CC_USAGE_MODEL_MULTIPLIERS": "model_multipliers",
        "PAR_CC_USAGE_STATUSLINE_ENABLED": "statusline_enabled",
        "PAR_CC_USAGE_STATUSLINE_USE_GRAND_TOTAL": "statusline_use_grand_total",
        "PAR_CC_USAGE_STATUSLINE_TEMPLATE": "statusline_template",
        "PAR_CC_USAGE_STATUSLINE_DATE_FORMAT": "statusline_date_format",
        "PAR_CC_USAGE_STATUSLINE_TIME_FORMAT": "statusline_time_format",
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
        "PAR_CC_USAGE_USE_P90_LIMIT": "use_p90_limit",
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


def _migrate_legacy_config_fields(config_dict: dict[str, Any]) -> bool:
    """Migrate legacy config fields to new names or remove them if new fields exist.

    Migration rules:
    - max_tokens_encountered -> max_unified_block_tokens_encountered
    - max_messages_encountered -> max_unified_block_messages_encountered
    - max_cost_encountered -> max_unified_block_cost_encountered

    If the new field exists, remove the legacy field.
    If the new field doesn't exist, rename the legacy field to the new name.

    Returns:
        True if any migration was performed, False otherwise
    """
    legacy_mappings = {
        "max_tokens_encountered": "max_unified_block_tokens_encountered",
        "max_messages_encountered": "max_unified_block_messages_encountered",
        "max_cost_encountered": "max_unified_block_cost_encountered",
    }

    migrated = False
    for legacy_field, new_field in legacy_mappings.items():
        if legacy_field in config_dict:
            if new_field not in config_dict:
                # New field doesn't exist, migrate legacy value
                config_dict[new_field] = config_dict[legacy_field]
            # Always remove the legacy field
            del config_dict[legacy_field]
            migrated = True

    return migrated


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
    if config_file is None:
        config_file = get_config_file_path()

    # Load from config file
    try:
        config_dict = _load_config_file(config_file)
    except (PermissionError, OSError):
        # If config file loading fails due to permissions, use empty dict
        config_dict = {}

    # Apply Claude config directory override
    _apply_claude_config_dir_override(config_dict)

    # Migrate legacy config fields and save if migration occurred
    migration_performed = _migrate_legacy_config_fields(config_dict)

    # Apply environment overrides
    _apply_env_overrides(config_dict, _get_top_level_env_mapping())
    _apply_nested_env_overrides(config_dict, "display", _get_display_env_mapping())
    _apply_nested_env_overrides(config_dict, "notifications", _get_notification_env_mapping())

    config = Config(**config_dict)

    # Handle automatic timezone detection
    config_updated = False
    if config.timezone == "auto":
        try:
            detected_tz = detect_system_timezone()
            if detected_tz != config.auto_detected_timezone:
                config.auto_detected_timezone = detected_tz
                config_updated = True
        except Exception:
            # If timezone detection fails, keep the existing auto_detected_timezone value
            pass

    # Save the migrated or updated config back to file if changes were made
    # and the config file exists (don't create new files just for migration)
    if (migration_performed or config_updated) and config_file.exists():
        try:
            save_config(config, config_file)
        except (PermissionError, OSError):
            # If we can't save, just continue - changes still worked in memory
            pass

    return config


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
        "auto_detected_timezone": config.auto_detected_timezone,
        "token_limit": config.token_limit,
        "message_limit": config.message_limit,
        "cost_limit": config.cost_limit,
        "max_unified_block_tokens_encountered": config.max_unified_block_tokens_encountered,
        "max_unified_block_messages_encountered": config.max_unified_block_messages_encountered,
        "max_unified_block_cost_encountered": config.max_unified_block_cost_encountered,
        "p90_unified_block_tokens_encountered": config.p90_unified_block_tokens_encountered,
        "p90_unified_block_messages_encountered": config.p90_unified_block_messages_encountered,
        "p90_unified_block_cost_encountered": config.p90_unified_block_cost_encountered,
        "cache_dir": str(config.cache_dir),
        "model_multipliers": config.model_multipliers,
        "display": {
            "show_progress_bars": config.display.show_progress_bars,
            "show_active_sessions": config.display.show_active_sessions,
            "update_in_place": config.display.update_in_place,
            "refresh_interval": config.display.refresh_interval,
            "time_format": config.display.time_format.value,
            "project_name_prefixes": config.display.project_name_prefixes,
            "display_mode": config.display.display_mode.value,
            "show_pricing": config.display.show_pricing,
            "use_p90_limit": config.display.use_p90_limit,
        },
        "notifications": {
            "discord_webhook_url": config.notifications.discord_webhook_url,
            "slack_webhook_url": config.notifications.slack_webhook_url,
            "notify_on_block_completion": config.notifications.notify_on_block_completion,
            "cooldown_minutes": config.notifications.cooldown_minutes,
        },
        "config_ro": config.config_ro,
        "statusline_enabled": config.statusline_enabled,
        "statusline_use_grand_total": config.statusline_use_grand_total,
        "statusline_template": config.statusline_template,
        "statusline_date_format": config.statusline_date_format,
        "statusline_time_format": config.statusline_time_format,
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
        if config.config_ro:
            return  # Skip update if config is read-only
        config.token_limit = token_limit
        save_config(config, config_file)


def update_config_message_limit(config_file: Path, message_limit: int) -> None:
    """Update message limit in config file.

    Args:
        config_file: Path to config file
        message_limit: New message limit
    """
    if config_file.exists():
        config = load_config(config_file)
        if config.config_ro:
            return  # Skip update if config is read-only
        config.message_limit = message_limit
        save_config(config, config_file)


def get_default_token_limit() -> int:
    """Get default token limit based on detected model.

    Returns:
        Default token limit
    """
    # Default to 500k for now, can be made smarter later
    return 500_000


def get_default_message_limit() -> int:
    """Get default message limit based on detected model.

    Returns:
        Default message limit
    """
    # Default to 50 messages for now, can be made smarter later
    return 50


def detect_message_limit_from_data(projects: dict[str, Any]) -> int | None:
    """Detect appropriate message limit from existing project data.

    Args:
        projects: Dictionary of project data

    Returns:
        Detected message limit or None if no data available
    """
    max_messages = 0

    # Look through all projects to find the highest message count in any block
    for project_data in projects.values():
        if hasattr(project_data, "sessions"):
            for session in project_data.sessions.values():
                if hasattr(session, "blocks"):
                    for block in session.blocks:
                        if hasattr(block, "message_count"):
                            max_messages = max(max_messages, block.message_count)

    # If we found some data, add 20% buffer and round up to nice number
    if max_messages > 0:
        buffered_limit = int(max_messages * 1.2)
        # Round up to nearest 10
        return ((buffered_limit + 9) // 10) * 10

    return None


# Legacy individual block maximum tracking functions removed - unified blocks handle all maximums


def _update_unified_block_maximums(config: Config, unified_tokens: int, unified_messages: int) -> bool:
    """Update unified block maximum encountered values."""
    updated = False

    if unified_tokens > config.max_unified_block_tokens_encountered:
        config.max_unified_block_tokens_encountered = unified_tokens
        updated = True

    if unified_messages > config.max_unified_block_messages_encountered:
        config.max_unified_block_messages_encountered = unified_messages
        updated = True

    return updated


def _auto_scale_limits(config: Config, unified_tokens: int, unified_messages: int) -> bool:
    """Auto-scale token and message limits if exceeded."""
    updated = False

    # Auto-scale token limit if exceeded
    if config.token_limit is not None and unified_tokens > config.token_limit:
        # Add 20% buffer to prevent constant updates
        new_limit = int(unified_tokens * 1.2)
        config.token_limit = new_limit
        updated = True

    # Auto-scale message limit if exceeded
    if config.message_limit is not None and unified_messages > config.message_limit:
        # Add 20% buffer to prevent constant updates
        new_limit = int(unified_messages * 1.2)
        config.message_limit = new_limit
        updated = True

    return updated


def update_max_encountered_values(
    config: Config, usage_snapshot: UsageSnapshot, config_file: Path | None = None
) -> bool:
    """Update max encountered values and auto-scale limits if needed.

    Args:
        config: Current configuration
        usage_snapshot: Current usage snapshot to check for new maximums
        config_file: Path to config file (defaults to XDG location)

    Returns:
        True if config was updated and saved, False otherwise
    """
    if config_file is None:
        config_file = get_config_file_path()

    # Skip all updates if config is read-only
    if config.config_ro:
        return False

    updated = False

    # Track unified block maximums (individual block tracking is now legacy)
    unified_tokens = usage_snapshot.unified_block_tokens()
    unified_messages = usage_snapshot.unified_block_messages()

    # Update unified block max encountered values
    if _update_unified_block_maximums(config, unified_tokens, unified_messages):
        updated = True

    # Auto-scale limits if needed
    if _auto_scale_limits(config, unified_tokens, unified_messages):
        updated = True

    # Save config if any updates were made
    if updated:
        save_config(config, config_file)

    return updated


async def update_max_encountered_values_async(
    config: Config, usage_snapshot: UsageSnapshot, config_file: Path | None = None
) -> bool:
    """Update max encountered values including cost and auto-scale limits if needed.

    Args:
        config: Current configuration
        usage_snapshot: Current usage snapshot to check for new maximums
        config_file: Path to config file (defaults to XDG location)

    Returns:
        True if config was updated and saved, False otherwise
    """
    if config_file is None:
        config_file = get_config_file_path()

    # Skip all updates if config is read-only
    if config.config_ro:
        return False

    # First do the sync updates
    updated = update_max_encountered_values(config, usage_snapshot, config_file)

    # Now handle the async cost calculation
    try:
        unified_cost = await usage_snapshot.get_unified_block_total_cost()

        if unified_cost > config.max_unified_block_cost_encountered:
            config.max_unified_block_cost_encountered = unified_cost
            updated = True

        # Save config again if cost was updated
        if updated:
            save_config(config, config_file)

    except Exception:
        # If cost calculation fails, don't break the entire update process
        pass

    return updated
