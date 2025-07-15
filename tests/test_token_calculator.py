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
    """Test unified block calculation functionality (simple approach)."""

    def test_create_unified_blocks_no_projects(self):
        """Test create_unified_blocks with no projects."""
        result = create_unified_blocks({})
        assert result is None

    def test_create_unified_blocks_no_active_blocks(self):
        """Test create_unified_blocks with inactive blocks still returns current hour-floored time."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        # Create a project with an inactive block (too old)
        project = Project(name="test_project")
        session = Session(session_id="session_1", project_name="test_project", model="sonnet")

        # Create a block that's not active (6+ hours since last activity)
        old_time = datetime.now(timezone.utc) - timedelta(hours=6)
        block = TokenBlock(
            start_time=old_time,
            end_time=old_time + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=old_time + timedelta(minutes=30),  # 6+ hours ago
        )

        session.blocks.append(block)
        project.sessions["session_1"] = session

        result = create_unified_blocks({"test_project": project})
        # Should return None since no active blocks exist
        assert result is None

    def test_create_unified_blocks_single_active_block(self):
        """Test create_unified_blocks returns current hour-floored time."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        # Create a project with an active block
        project = Project(name="test_project")
        session = Session(session_id="session_1", project_name="test_project", model="sonnet")

        # Create a block with recent activity (within 5 hours)
        block_start = datetime.now(timezone.utc) - timedelta(hours=2)
        block = TokenBlock(
            start_time=block_start,
            end_time=block_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=datetime.now(timezone.utc) - timedelta(minutes=30),  # Recent activity
        )

        session.blocks.append(block)
        project.sessions["session_1"] = session

        result = create_unified_blocks({"test_project": project})
        # Should return the block start time (ccusage behavior)
        expected = block_start
        assert result == expected

    def test_create_unified_blocks_multiple_active_blocks_returns_current_hour(self):
        """Test create_unified_blocks returns current hour-floored time with multiple blocks."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        project = Project(name="test_project")

        # Create two sessions with active blocks
        session1 = Session(session_id="session_1", project_name="test_project", model="sonnet")
        session2 = Session(session_id="session_2", project_name="test_project", model="opus")

        current_time = datetime.now(timezone.utc)

        # First block started 3 hours ago (earlier)
        block1_start = current_time - timedelta(hours=3)
        block1 = TokenBlock(
            start_time=block1_start,
            end_time=block1_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=current_time - timedelta(hours=1),  # Active: 1 hour ago
        )

        # Second block started 1 hour ago (later)
        block2_start = current_time - timedelta(hours=1)
        block2 = TokenBlock(
            start_time=block2_start,
            end_time=block2_start + timedelta(hours=5),
            session_id="session_2",
            project_name="test_project",
            model="opus",
            token_usage=TokenUsage(input_tokens=200, output_tokens=100),
            actual_end_time=current_time - timedelta(minutes=15),  # Active: 15 min ago
        )

        session1.blocks.append(block1)
        session2.blocks.append(block2)
        project.sessions["session_1"] = session1
        project.sessions["session_2"] = session2

        result = create_unified_blocks({"test_project": project})
        # Should return the earliest active block start time (ccusage behavior)
        expected = block1_start  # block1 started earlier
        assert result == expected

    def test_create_unified_blocks_inactive_vs_active(self):
        """Test create_unified_blocks returns current hour-floored time regardless of block activity."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        project = Project(name="test_project")
        session = Session(session_id="session_1", project_name="test_project", model="sonnet")

        current_time = datetime.now(timezone.utc)

        # First block: started earlier but inactive (no recent activity)
        inactive_block_start = current_time - timedelta(hours=4)
        inactive_block = TokenBlock(
            start_time=inactive_block_start,
            end_time=inactive_block_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=current_time - timedelta(hours=6),  # Inactive: 6+ hours ago
        )

        # Second block: started later but active
        active_block_start = current_time - timedelta(hours=2)
        active_block = TokenBlock(
            start_time=active_block_start,
            end_time=active_block_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=200, output_tokens=100),
            actual_end_time=current_time - timedelta(minutes=30),  # Active: 30 min ago
        )

        session.blocks.extend([inactive_block, active_block])
        project.sessions["session_1"] = session

        result = create_unified_blocks({"test_project": project})
        # Should return the start time of the active block (ccusage behavior)
        expected = active_block_start
        assert result == expected

    def test_create_unified_blocks_multiple_projects(self):
        """Test create_unified_blocks across multiple projects returns current hour-floored time."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        current_time = datetime.now(timezone.utc)

        # First project with later active block
        project1 = Project(name="project1")
        session1 = Session(session_id="session_1", project_name="project1", model="sonnet")

        block1_start = current_time - timedelta(hours=1)  # Started 1 hour ago
        block1 = TokenBlock(
            start_time=block1_start,
            end_time=block1_start + timedelta(hours=5),
            session_id="session_1",
            project_name="project1",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=current_time - timedelta(minutes=30),
        )

        # Second project with earlier active block
        project2 = Project(name="project2")
        session2 = Session(session_id="session_2", project_name="project2", model="opus")

        block2_start = current_time - timedelta(hours=3)  # Started 3 hours ago (earlier)
        block2 = TokenBlock(
            start_time=block2_start,
            end_time=block2_start + timedelta(hours=5),
            session_id="session_2",
            project_name="project2",
            model="opus",
            token_usage=TokenUsage(input_tokens=200, output_tokens=100),
            actual_end_time=current_time - timedelta(hours=1),  # Still active
        )

        session1.blocks.append(block1)
        session2.blocks.append(block2)
        project1.sessions["session_1"] = session1
        project2.sessions["session_2"] = session2

        projects = {"project1": project1, "project2": project2}
        result = create_unified_blocks(projects)

        # Should return the earliest active block start time (ccusage behavior)
        expected = block2_start  # block2 started earlier and is still active
        assert result == expected

    def test_create_unified_blocks_activity_boundary_cases(self):
        """Test create_unified_blocks returns current hour-floored time even with inactive blocks."""
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage
        from datetime import datetime, timedelta, timezone

        project = Project(name="test_project")
        session = Session(session_id="session_1", project_name="test_project", model="sonnet")

        current_time = datetime.now(timezone.utc)

        # Block with activity exactly at 5-hour boundary (should be inactive)
        block_start = current_time - timedelta(hours=2)
        block = TokenBlock(
            start_time=block_start,
            end_time=block_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
            actual_end_time=current_time - timedelta(hours=5, seconds=1),  # Just over 5 hours
        )

        session.blocks.append(block)
        project.sessions["session_1"] = session

        result = create_unified_blocks({"test_project": project})
        # Should return None since no active blocks exist (ccusage behavior)
        assert result is None
