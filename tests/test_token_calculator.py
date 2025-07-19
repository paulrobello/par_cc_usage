"""
Tests for the token_calculator module.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from par_cc_usage.models import Project
from par_cc_usage.token_calculator import (
    calculate_block_start,
    create_unified_blocks,
    format_token_count,
    get_model_display_name,
    normalize_model_name,
    parse_timestamp,
    process_jsonl_line,
)


class TestParseTimestamp:
    """Test timestamp parsing functionality."""

    def test_parse_iso_format_with_z(self):
        """Test parsing ISO format with Z suffix."""
        timestamp_str = "2025-01-09T14:30:45.123Z"
        result = parse_timestamp(timestamp_str)

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 9
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45
        assert result.tzinfo == timezone.utc

    def test_parse_iso_format_with_timezone(self):
        """Test parsing ISO format with timezone offset."""
        timestamp_str = "2025-01-09T14:30:45.123+00:00"
        result = parse_timestamp(timestamp_str)

        assert result.year == 2025
        assert result.hour == 14
        assert result.tzinfo == timezone.utc


class TestCalculateBlockStart:
    """Test block start time calculation."""

    def test_calculate_block_start_at_hour(self):
        """Test block start when timestamp is exactly on the hour."""
        timestamp = datetime(2025, 1, 9, 14, 0, 0, tzinfo=timezone.utc)
        result = calculate_block_start(timestamp)

        # Should round down to the hour
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0

    def test_calculate_block_start_past_hour(self):
        """Test block start when timestamp is past the hour."""
        timestamp = datetime(2025, 1, 9, 14, 30, 45, tzinfo=timezone.utc)
        result = calculate_block_start(timestamp)

        assert result.hour == 14
        assert result.minute == 0
        assert result.second == 0


class TestNormalizeModelName:
    """Test model name normalization."""

    def test_normalize_opus_models(self):
        """Test normalizing various Opus model names."""
        assert normalize_model_name("claude-3-opus-20240229") == "opus"
        assert normalize_model_name("claude-3-opus-latest") == "opus"
        assert normalize_model_name("claude-opus-4-20250514") == "opus"

    def test_normalize_sonnet_models(self):
        """Test normalizing various Sonnet model names."""
        assert normalize_model_name("claude-3-sonnet-20240229") == "sonnet"
        assert normalize_model_name("claude-3-5-sonnet-20240620") == "sonnet"
        assert normalize_model_name("claude-3-5-sonnet-latest") == "sonnet"

    def test_normalize_haiku_models(self):
        """Test normalizing various Haiku model names."""
        assert normalize_model_name("claude-3-haiku-20240307") == "haiku"
        assert normalize_model_name("claude-3-haiku-latest") == "haiku"

    def test_normalize_unknown_model(self):
        """Test normalizing unknown model names."""
        assert normalize_model_name("gpt-4") == "gpt"
        assert normalize_model_name("some-random-model") == "some-random-model"


class TestGetModelDisplayName:
    """Test model display name functionality."""

    def test_get_display_names(self):
        """Test getting display names for models."""
        assert get_model_display_name("claude-3-opus-latest") == "Opus"
        assert get_model_display_name("claude-3-5-sonnet-latest") == "Sonnet"
        assert get_model_display_name("claude-3-haiku-latest") == "Haiku"
        assert get_model_display_name("unknown-model") == "unknown-model"
        assert get_model_display_name("unknown") == "Unknown"
        assert get_model_display_name("") == "Unknown"


class TestFormatTokenCount:
    """Test token count formatting."""

    def test_format_small_counts(self):
        """Test formatting small token counts."""
        assert format_token_count(0) == "0"
        assert format_token_count(999) == "999"

    def test_format_thousands(self):
        """Test formatting thousands."""
        assert format_token_count(1000) == "1K"
        assert format_token_count(1500) == "2K"  # .0f rounds to nearest int

    def test_format_millions(self):
        """Test formatting millions."""
        assert format_token_count(1000000) == "1.0M"
        assert format_token_count(1500000) == "1.5M"


class TestProcessJsonlLine:
    """Test JSONL line processing."""

    def test_process_valid_line_basic(self, deduplication_state):
        """Test processing a basic valid JSONL line."""
        data = {
            "timestamp": "2025-01-09T14:30:45.123Z",
            "request": {
                "model": "claude-3-5-sonnet-latest",
            },
            "response": {
                "id": "msg_123",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            },
        }

        projects = {}

        process_jsonl_line(
            data=data,
            project_path="test_project",
            session_id="session_123",
            projects=projects,
            dedup_state=deduplication_state,
        )

        # Should have created the project
        assert "test_project" in projects


class TestCreateUnifiedBlocks:
    """Test unified block calculation functionality."""

    def test_create_unified_blocks_no_entries(self):
        """Test create_unified_blocks with no entries."""
        result = create_unified_blocks([])
        assert result == []

    def test_create_unified_blocks_single_active_block(self):
        """Test create_unified_blocks with single entry."""
        from par_cc_usage.models import UnifiedEntry, TokenUsage
        from datetime import datetime, timezone

        # Create a single unified entry
        now = datetime.now(timezone.utc)
        entry = UnifiedEntry(
            timestamp=now,
            project_name="test_project",
            session_id="session_1",
            model="sonnet",
            full_model_name="claude-3-5-sonnet-latest",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            tools_used=set(),
            tool_use_count=0,
            cost_usd=0.0,
            version="1.0"
        )

        result = create_unified_blocks([entry])
        assert len(result) == 1
        assert result[0].start_time.minute == 0  # Should be floored to hour
        assert result[0].start_time.second == 0
        assert result[0].start_time.microsecond == 0

    # TODO: Add more comprehensive unified block tests with multiple entries
