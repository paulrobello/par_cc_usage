"""Pydantic models for JSON parsing in par_cc_usage."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import ModelType, ServiceTier


class UsageData(BaseModel):
    """Token usage data from Claude API responses."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    service_tier: ServiceTier = ServiceTier.STANDARD

    @field_validator("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    @classmethod
    def validate_token_counts(cls, v: int | None) -> int:
        """Ensure token counts are non-negative integers."""
        return v or 0


class ToolUseBlock(BaseModel):
    """Tool use block from Claude API content."""

    type: str = "tool_use"
    id: str | None = None
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class MessageContent(BaseModel):
    """Message content that may contain tool use blocks."""

    type: str
    text: str | None = None
    # For tool_use blocks
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None


class MessageData(BaseModel):
    """Claude API message data."""

    id: str | None = None
    type: str | None = None
    role: str | None = None
    model: str | None = None
    usage: UsageData | None = None
    content: list[MessageContent] = Field(default_factory=list)
    stop_reason: str | None = None
    stop_sequence: str | None = None
    was_interrupted: bool = Field(False, alias="wasInterrupted")

    @field_validator("model")
    @classmethod
    def normalize_model_name(cls, v: str | None) -> str:
        """Normalize model name to standard format."""
        if not v or not v.strip():
            return ModelType.UNKNOWN

        model_lower = v.lower().strip()

        # Check for Claude 4 models first
        if cls._is_claude_4_model(model_lower):
            return ModelType.CLAUDE_SONNET_4

        # Check for Claude 3.5 models
        if claude_3_5_type := cls._get_claude_3_5_model(model_lower):
            return claude_3_5_type

        # Check for Claude 3 models
        if claude_3_type := cls._get_claude_3_model(model_lower):
            return claude_3_type

        # Check for generic model types (opus/sonnet only for Claude Code)
        if "opus" in model_lower:
            return ModelType.OPUS
        elif "sonnet" in model_lower:
            return ModelType.SONNET

        # Any other model name (including haiku or unknown models) → Unknown
        return ModelType.UNKNOWN

    @staticmethod
    def _is_claude_4_model(model_lower: str) -> bool:
        """Check if model is Claude 4."""
        return "sonnet-4" in model_lower or "claude-sonnet-4" in model_lower

    @staticmethod
    def _get_claude_3_5_model(model_lower: str) -> str | None:
        """Get Claude 3.5 model type."""
        if "3.5" in model_lower or "3-5" in model_lower:
            if "sonnet" in model_lower:
                return ModelType.CLAUDE_3_5_SONNET
            # Note: Haiku not used by Claude Code - return None to fall through to UNKNOWN
        return None

    @staticmethod
    def _get_claude_3_model(model_lower: str) -> str | None:
        """Get Claude 3 model type."""
        if "3" in model_lower:
            if "opus" in model_lower:
                return ModelType.CLAUDE_3_OPUS
            elif "sonnet" in model_lower:
                return ModelType.CLAUDE_3_5_SONNET  # Default to 3.5
            # Note: Haiku not used by Claude Code - return None to fall through to UNKNOWN
        return None


class TokenUsageData(BaseModel):
    """Top-level JSONL data structure."""

    timestamp: str
    request_id: str | None = Field(None, alias="requestId")
    version: str | None = None
    cost_usd: float | None = Field(None, alias="costUSD")
    is_api_error_message: bool = Field(False, alias="isApiErrorMessage")
    message: MessageData | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure timestamp is not empty."""
        if not v:
            raise ValueError("Timestamp cannot be empty")
        return v

    @field_validator("cost_usd")
    @classmethod
    def validate_cost(cls, v: float | None) -> float | None:
        """Ensure cost is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Cost cannot be negative")
        return v


class WebhookPayload(BaseModel):
    """Base webhook payload structure."""

    content: str | None = None
    username: str | None = None
    embeds: list[dict[str, Any]] = Field(default_factory=list)


class DiscordWebhookPayload(WebhookPayload):
    """Discord-specific webhook payload."""

    avatar_url: str | None = None


class SlackWebhookPayload(BaseModel):
    """Slack-specific webhook payload."""

    text: str | None = None
    username: str | None = None
    icon_emoji: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of JSON validation and parsing."""

    is_valid: bool
    data: TokenUsageData | None = None
    errors: list[str] = Field(default_factory=list)

    @classmethod
    def success(cls, data: TokenUsageData) -> ValidationResult:
        """Create a successful validation result."""
        return cls(is_valid=True, data=data)

    @classmethod
    def failure(cls, errors: list[str]) -> ValidationResult:
        """Create a failed validation result."""
        return cls(is_valid=False, errors=errors)
