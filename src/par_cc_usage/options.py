"""Command options dataclasses for par_cc_usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .enums import DisplayMode, OutputFormat, SortBy, TimeFormat


@dataclass
class MonitorOptions:
    """Options for the monitor command."""

    interval: int = 5
    token_limit: int | None = None
    config_file: Path | None = None
    show_sessions: bool = False
    show_tools: bool = False
    show_pricing: bool = False
    no_cache: bool = False
    block_start_override: int | None = None
    block_start_override_utc: datetime | None = None
    snapshot: bool = False
    display_mode: DisplayMode | None = None


@dataclass
class ListOptions:
    """Options for the list command."""

    output_format: OutputFormat = OutputFormat.TABLE
    sort_by: SortBy = SortBy.TOKENS
    output: Path | None = None
    config_file: Path | None = None


@dataclass
class InitOptions:
    """Options for the init command."""

    config_file: Path = Path("config.yaml")


@dataclass
class SetLimitOptions:
    """Options for the set-limit command."""

    limit: int
    config_file: Path = Path("config.yaml")


@dataclass
class ClearCacheOptions:
    """Options for the clear-cache command."""

    config_file: Path | None = None


@dataclass
class TestWebhookOptions:
    """Options for the test-webhook command."""

    config_file: Path | None = None
    block_start_override: int | None = None
    block_start_override_utc: datetime | None = None


@dataclass
class DisplayOptions:
    """Options for display configuration."""

    show_progress_bars: bool = True
    show_active_sessions: bool = False
    update_in_place: bool = True
    refresh_interval: int = 1
    time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR
    project_name_prefixes: list[str] = field(default_factory=list)
    aggregate_by_project: bool = True
    show_tool_usage: bool = False

    def __post_init__(self) -> None:
        """Set default project name prefixes if None."""
        if self.project_name_prefixes is None:
            self.project_name_prefixes = ["-Users-", "-home-"]


@dataclass
class NotificationOptions:
    """Options for notification configuration."""

    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    notify_on_block_completion: bool = True
    cooldown_minutes: int = 5


@dataclass
class CommandOptions:
    """Base options for all commands."""

    verbose: bool = False
    debug: bool = False
    config_file: Path | None = None

    def get_config_file(self) -> Path:
        """Get the config file path, defaulting to config.yaml."""
        return self.config_file or Path("config.yaml")
