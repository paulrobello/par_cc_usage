"""Enums for par_cc_usage to replace string-based configurations."""

from __future__ import annotations

from enum import Enum


class TimeFormat(str, Enum):
    """Time format options for display."""

    TWELVE_HOUR = "12h"
    TWENTY_FOUR_HOUR = "24h"


class ModelType(str, Enum):
    """Claude model types with normalized names."""

    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku"
    CLAUDE_SONNET_4 = "sonnet-4"
    CLAUDE_SONNET_4_5 = "sonnet-4-5"
    CLAUDE_OPUS_4_1 = "opus-4-1"
    CLAUDE_HAIKU_4_5 = "haiku-4-5"
    UNKNOWN = "unknown"


class WebhookType(str, Enum):
    """Webhook notification types."""

    DISCORD = "discord"
    SLACK = "slack"


class ServiceTier(str, Enum):
    """Claude service tiers."""

    STANDARD = "standard"
    PREMIUM = "premium"


class OutputFormat(str, Enum):
    """Output format options for list command."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class SortBy(str, Enum):
    """Sort by options for list command."""

    TOKENS = "tokens"
    TIMESTAMP = "timestamp"
    TIME = "time"  # Alias for timestamp for backward compatibility
    PROJECT = "project"
    SESSION = "session"
    MODEL = "model"


class DisplayMode(str, Enum):
    """Display mode options for monitor."""

    NORMAL = "normal"
    COMPACT = "compact"


class ThemeType(str, Enum):
    """Theme type options for display styling."""

    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    ACCESSIBILITY = "accessibility"
    MINIMAL = "minimal"


class TimeBucket(str, Enum):
    """Time bucket options for usage summary."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL = "all"
