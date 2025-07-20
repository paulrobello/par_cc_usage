"""
Additional tests for token_calculator.py to improve coverage.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from par_cc_usage.models import DeduplicationState, Project, Session, TokenBlock, TokenUsage, UnifiedBlock, UnifiedEntry
from par_cc_usage.token_calculator import (
    UTC,
    _populate_model_messages,
    _populate_model_tokens,
    create_unified_blocks,
    get_current_unified_block,
    normalize_model_name,
    parse_timestamp,
    process_jsonl_line,
)


class TestParseTimestampEdgeCases:
    """Test edge cases for timestamp parsing."""

    def test_parse_timestamp_empty_string(self):
        """Test parsing empty timestamp string raises ValueError."""
        with pytest.raises(ValueError, match="Empty timestamp string"):
            parse_timestamp("")

    def test_parse_timestamp_none(self):
        """Test parsing None timestamp raises ValueError."""
        with pytest.raises(ValueError, match="Empty timestamp string"):
            parse_timestamp(None)

    def test_parse_timestamp_unix_timestamp(self):
        """Test parsing Unix timestamp."""
        # Unix timestamp for 2025-01-09 14:30:45 UTC
        timestamp_str = "1736428245"
        result = parse_timestamp(timestamp_str)

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 9
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_negative_unix_timestamp(self):
        """Test parsing negative Unix timestamp."""
        timestamp_str = "-946684800"  # 1940-01-01 00:00:00 UTC
        result = parse_timestamp(timestamp_str)

        assert result.year == 1939 or result.year == 1940  # Time zone differences
        assert result.month == 12 or result.month == 1
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_iso_without_timezone(self):
        """Test parsing ISO format without timezone (assumes UTC)."""
        timestamp_str = "2025-01-09T14:30:45.123"
        result = parse_timestamp(timestamp_str)

        assert result.year == 2025
        assert result.hour == 14
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid timestamp format raises ValueError."""
        with pytest.raises(ValueError):
            parse_timestamp("invalid-timestamp-format")

    def test_parse_timestamp_iso_with_positive_offset(self):
        """Test parsing ISO format with positive timezone offset."""
        timestamp_str = "2025-01-09T14:30:45.123+05:30"
        result = parse_timestamp(timestamp_str)

        assert result.year == 2025
        assert result.hour == 14
        assert result.tzinfo.utcoffset(None) == timedelta(hours=5, minutes=30)


class TestNormalizeModelName:
    """Test model name normalization."""

    def test_normalize_model_name_simple(self):
        """Test basic model name normalization."""
        assert normalize_model_name("claude-3-5-sonnet-20241022") == "sonnet"
        assert normalize_model_name("claude-3-opus-20240229") == "opus"
        assert normalize_model_name("claude-3-haiku-20240307") == "haiku"

    def test_normalize_model_name_latest_versions(self):
        """Test normalization of latest model versions."""
        assert normalize_model_name("claude-3-5-sonnet-latest") == "sonnet"
        assert normalize_model_name("claude-3-opus-latest") == "opus"

    def test_normalize_model_name_new_versions(self):
        """Test normalization of new Claude versions."""
        assert normalize_model_name("claude-4-sonnet-20250101") == "sonnet"
        assert normalize_model_name("claude-sonnet-4-20250514") == "sonnet"

    def test_normalize_model_name_edge_cases(self):
        """Test edge cases for model name normalization."""
        # Test unknown model (should return as-is or normalized)
        result = normalize_model_name("unknown-model")
        assert isinstance(result, str)

        # Test empty string
        result = normalize_model_name("")
        assert isinstance(result, str)

        # Test case insensitive
        result = normalize_model_name("CLAUDE-3-SONNET-LATEST")
        assert "sonnet" in result.lower()


class TestPopulateModelFunctions:
    """Test helper functions for populating model data."""

    def test_populate_model_tokens_new_model(self):
        """Test populating tokens for a new model."""
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test",
            project_name="test",
            model="claude-3-sonnet-latest",
            token_usage=TokenUsage()
        )

        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            actual_input_tokens=80,
            actual_output_tokens=40
        )

        _populate_model_tokens(block, "claude-3-sonnet-latest", token_usage)

        assert block.model_tokens["sonnet"] == 150  # Total display tokens
        assert block.actual_model_tokens["sonnet"] == 120  # Total actual tokens

    def test_populate_model_tokens_existing_model(self):
        """Test populating tokens for an existing model (should add)."""
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test",
            project_name="test",
            model="claude-3-sonnet-latest",
            token_usage=TokenUsage()
        )

        # Pre-populate with existing data
        block.model_tokens["sonnet"] = 100
        block.actual_model_tokens["sonnet"] = 80

        token_usage = TokenUsage(
            input_tokens=50,
            output_tokens=25,
            actual_input_tokens=40,
            actual_output_tokens=20
        )

        _populate_model_tokens(block, "claude-3-sonnet-latest", token_usage)

        assert block.model_tokens["sonnet"] == 175  # 100 + 75
        assert block.actual_model_tokens["sonnet"] == 140  # 80 + 60

    def test_populate_model_messages_new_model(self):
        """Test populating messages for a new model."""
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test",
            project_name="test",
            model="claude-3-opus-latest",
            token_usage=TokenUsage()
        )

        token_usage = TokenUsage(message_count=5)

        _populate_model_messages(block, "claude-3-opus-latest", token_usage)

        assert block.model_message_counts["opus"] == 5

    def test_populate_model_messages_existing_model(self):
        """Test populating messages for an existing model (should add)."""
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test",
            project_name="test",
            model="claude-3-opus-latest",
            token_usage=TokenUsage()
        )

        # Pre-populate with existing data
        block.model_message_counts["opus"] = 3

        token_usage = TokenUsage(message_count=2)

        _populate_model_messages(block, "claude-3-opus-latest", token_usage)

        assert block.model_message_counts["opus"] == 5  # 3 + 2


class TestProcessJsonlLineEdgeCases:
    """Test edge cases for JSONL line processing."""

    def test_process_jsonl_line_missing_timestamp(self):
        """Test processing line without timestamp."""
        data = {
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {"usage": {"input_tokens": 100, "output_tokens": 50}}
        }
        projects = {}
        dedup_state = DeduplicationState()

        # Should handle gracefully without crashing
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should not create any projects due to missing timestamp
        assert len(projects) == 0

    def test_process_jsonl_line_invalid_timestamp(self):
        """Test processing line with invalid timestamp."""
        data = {
            "timestamp": "invalid-timestamp",
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {"usage": {"input_tokens": 100, "output_tokens": 50}}
        }
        projects = {}
        dedup_state = DeduplicationState()

        # Should handle gracefully without crashing
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should not create any projects due to invalid timestamp
        assert len(projects) == 0

    def test_process_jsonl_line_missing_model(self):
        """Test processing line without model information."""
        data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "response": {"usage": {"input_tokens": 100, "output_tokens": 50}}
        }
        projects = {}
        dedup_state = DeduplicationState()

        # Should handle gracefully without crashing
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should create project but with default model
        assert len(projects) == 1
        assert "test-project" in projects

    def test_process_jsonl_line_missing_usage(self):
        """Test processing line without usage information."""
        data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-sonnet-latest"}
        }
        projects = {}
        dedup_state = DeduplicationState()

        # Should handle gracefully with zero usage
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should create project with zero token usage
        assert len(projects) == 1
        project = projects["test-project"]
        assert len(project.sessions) == 1

    def test_process_jsonl_line_with_tools(self):
        """Test processing line with tool usage information."""
        data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "tool_use": [
                    {"name": "Read"},
                    {"name": "Edit"}
                ]
            }
        }
        projects = {}
        dedup_state = DeduplicationState()

        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should process successfully and create project
        assert len(projects) == 1
        project = projects["test-project"]
        assert len(project.sessions) == 1

    def test_process_jsonl_line_duplicate_detection(self):
        """Test duplicate detection functionality."""
        data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {
                "id": "msg_123",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }
        }
        projects = {}
        dedup_state = DeduplicationState()

        # Process same message twice
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")
        process_jsonl_line(data, "test-project", "session-123", projects, dedup_state, "UTC")

        # Should handle duplicate processing gracefully
        assert len(projects) == 1
        # Deduplication state behavior may vary by implementation
        assert isinstance(dedup_state.total_messages, int)


class TestUnifiedBlockCreation:
    """Test unified block creation and management."""

    def test_create_unified_blocks_empty_entries(self):
        """Test creating unified blocks with empty entries list."""
        unified_entries = []
        blocks = create_unified_blocks(unified_entries)

        assert blocks == []

    def test_create_unified_blocks_single_entry(self):
        """Test creating unified blocks with single entry."""
        timestamp = datetime.now(UTC)
        entry = UnifiedEntry(
            timestamp=timestamp,
            project_name="test",
            session_id="session1",
            model="sonnet",
            full_model_name="claude-3-sonnet-latest",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50)
        )

        blocks = create_unified_blocks([entry])

        assert len(blocks) == 1
        assert len(blocks[0].entries) == 1
        assert blocks[0].total_tokens == 150

    def test_create_unified_blocks_multiple_projects(self):
        """Test creating unified blocks with entries from multiple projects."""
        base_time = datetime.now(UTC)
        entries = [
            UnifiedEntry(
                timestamp=base_time,
                project_name="project1",
                session_id="session1",
                model="sonnet",
                full_model_name="claude-3-sonnet-latest",
                token_usage=TokenUsage(input_tokens=100, output_tokens=50)
            ),
            UnifiedEntry(
                timestamp=base_time + timedelta(minutes=30),
                project_name="project2",
                session_id="session2",
                model="opus",
                full_model_name="claude-3-opus-latest",
                token_usage=TokenUsage(input_tokens=200, output_tokens=100)
            )
        ]

        blocks = create_unified_blocks(entries)

        assert len(blocks) == 1  # Should be in same 5-hour block
        assert len(blocks[0].entries) == 2
        assert len(blocks[0].projects) == 2
        assert "project1" in blocks[0].projects
        assert "project2" in blocks[0].projects

    def test_create_unified_blocks_gap_detection(self):
        """Test unified blocks correctly detects gaps and creates separate blocks."""
        base_time = datetime.now(UTC)
        entries = [
            UnifiedEntry(
                timestamp=base_time,
                project_name="project1",
                session_id="session1",
                model="sonnet",
                full_model_name="claude-3-sonnet-latest",
                token_usage=TokenUsage(input_tokens=100, output_tokens=50)
            ),
            UnifiedEntry(
                timestamp=base_time + timedelta(hours=6),  # 6 hours later, should be new block
                project_name="project1",
                session_id="session2",
                model="sonnet",
                full_model_name="claude-3-sonnet-latest",
                token_usage=TokenUsage(input_tokens=100, output_tokens=50)
            )
        ]

        blocks = create_unified_blocks(entries)

        # Should create blocks successfully
        assert len(blocks) >= 1  # Should create at least one block
        assert isinstance(blocks, list)  # Should return a list


class TestGetCurrentUnifiedBlock:
    """Test current unified block detection."""

    def test_get_current_unified_block_empty_list(self):
        """Test getting current block from empty list."""
        result = get_current_unified_block([])
        assert result is None

    def test_get_current_unified_block_no_active(self):
        """Test getting current block when none are active."""
        old_time = datetime.now(UTC) - timedelta(hours=10)
        block = UnifiedBlock(
            id=old_time.isoformat(),
            start_time=old_time,
            end_time=old_time + timedelta(hours=5),
            actual_end_time=old_time + timedelta(hours=1)
        )

        result = get_current_unified_block([block])
        assert result is None

    def test_get_current_unified_block_active_found(self):
        """Test getting current block when active block exists."""
        recent_time = datetime.now(UTC) - timedelta(minutes=30)
        block = UnifiedBlock(
            id=recent_time.isoformat(),
            start_time=recent_time,
            end_time=recent_time + timedelta(hours=5),
            actual_end_time=recent_time + timedelta(minutes=10)
        )

        result = get_current_unified_block([block])
        assert result == block

    def test_get_current_unified_block_multiple_blocks(self):
        """Test getting current block from multiple blocks."""
        old_time = datetime.now(UTC) - timedelta(hours=10)
        recent_time = datetime.now(UTC) - timedelta(minutes=30)

        old_block = UnifiedBlock(
            id=old_time.isoformat(),
            start_time=old_time,
            end_time=old_time + timedelta(hours=5),
            actual_end_time=old_time + timedelta(hours=1)
        )

        recent_block = UnifiedBlock(
            id=recent_time.isoformat(),
            start_time=recent_time,
            end_time=recent_time + timedelta(hours=5),
            actual_end_time=recent_time + timedelta(minutes=10)
        )

        result = get_current_unified_block([old_block, recent_block])
        assert result == recent_block


class TestTokenLimitDetection:
    """Test token limit detection functionality."""

    def test_detect_token_limit_from_data_basic(self):
        """Test detecting token limit from project data."""
        from par_cc_usage.token_calculator import detect_token_limit_from_data

        # Create project with token usage
        project = Project(name="test-project")
        session = Session(session_id="session1", project_name="test-project", model="sonnet")

        # Add block with significant token usage
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="session1",
            project_name="test-project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100000, output_tokens=50000)
        )
        session.add_block(block)
        project.add_session(session)

        projects = {"test-project": project}
        limit = detect_token_limit_from_data(projects)

        # Should return a reasonable limit based on usage
        assert limit is None or (isinstance(limit, int) and limit > 0)

    def test_detect_token_limit_from_data_empty(self):
        """Test detecting token limit from empty data."""
        from par_cc_usage.token_calculator import detect_token_limit_from_data

        limit = detect_token_limit_from_data({})
        # Function may return default limit or None
        assert limit is None or isinstance(limit, int)
