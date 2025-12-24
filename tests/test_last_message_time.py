"""Tests for last message timer functionality in status line."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from par_cc_usage.config import Config
from par_cc_usage.statusline_manager import StatusLineManager


class TestLastMessageTimer:
    """Test last message timer functionality."""

    @pytest.fixture
    def config(self) -> Config:
        """Create a test configuration."""
        return Config()

    @pytest.fixture
    def manager(self, config: Config) -> StatusLineManager:
        """Create a status line manager."""
        return StatusLineManager(config)

    def create_session_file(self, minutes_ago: int = 5) -> Path:
        """Create a temporary session file with a timestamp.

        Args:
            minutes_ago: How many minutes ago the message was sent

        Returns:
            Path to the temporary session file
        """
        # Use timezone-aware datetime
        time_ago = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        timestamp_str = time_ago.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_file = Path(f.name)

            mock_entry = {
                "timestamp": timestamp_str,
                "sessionId": "test-session-123",
                "type": "assistant",
                "message": {"usage": {"input_tokens": 100, "output_tokens": 50}},
            }

            f.write(json.dumps(mock_entry) + "\n")

        return session_file

    def test_extract_last_message_timestamp(self, manager: StatusLineManager) -> None:
        """Test extracting timestamp from session file."""
        session_file = self.create_session_file(minutes_ago=5)

        try:
            timestamp = manager._extract_last_message_timestamp(session_file)

            assert timestamp is not None, "Should extract timestamp"
            assert isinstance(timestamp, datetime), "Should be a datetime object"

            # Check it's approximately 5 minutes ago (within 2 minutes tolerance)
            now = datetime.now(timezone.utc)
            diff = (now - timestamp).total_seconds()
            assert 180 <= diff <= 420, f"Should be ~5 minutes ago, got {diff} seconds"
        finally:
            session_file.unlink()

    def test_extract_last_message_timestamp_nonexistent(self, manager: StatusLineManager) -> None:
        """Test extracting timestamp from nonexistent file."""
        nonexistent = Path("/nonexistent/session.jsonl")
        timestamp = manager._extract_last_message_timestamp(nonexistent)
        assert timestamp is None, "Should return None for nonexistent file"

    def test_extract_last_message_timestamp_from_last_line(self, manager: StatusLineManager) -> None:
        """Test that timestamp is extracted from the LAST line of the file."""
        # Create a session file with multiple entries, each with different timestamps
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_file = Path(f.name)

            # First entry: 10 minutes ago
            time_1 = datetime.now(timezone.utc) - timedelta(minutes=10)
            timestamp_str_1 = time_1.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            entry_1 = {
                "timestamp": timestamp_str_1,
                "sessionId": "test-session-123",
                "type": "user",
                "message": {"content": "First message"},
            }
            f.write(json.dumps(entry_1) + "\n")

            # Second entry: 5 minutes ago
            time_2 = datetime.now(timezone.utc) - timedelta(minutes=5)
            timestamp_str_2 = time_2.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            entry_2 = {
                "timestamp": timestamp_str_2,
                "sessionId": "test-session-123",
                "type": "assistant",
                "message": {"content": "Second message"},
            }
            f.write(json.dumps(entry_2) + "\n")

            # Third entry: 1 minute ago (LAST/MOST RECENT)
            time_3 = datetime.now(timezone.utc) - timedelta(minutes=1)
            timestamp_str_3 = time_3.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            entry_3 = {
                "timestamp": timestamp_str_3,
                "sessionId": "test-session-123",
                "type": "assistant",
                "message": {"content": "Most recent message"},
            }
            f.write(json.dumps(entry_3) + "\n")

        try:
            timestamp = manager._extract_last_message_timestamp(session_file)

            assert timestamp is not None, "Should extract timestamp from last line"

            # The extracted timestamp should match the LAST entry (1 minute ago)
            # Check it's approximately 1 minute ago (within 30 seconds tolerance)
            now = datetime.now(timezone.utc)
            diff = (now - timestamp).total_seconds()
            assert 30 <= diff <= 90, f"Should be ~1 minute ago (last line), got {diff} seconds"

            # Also verify it's NOT 10 minutes ago (first line) or 5 minutes ago (second line)
            assert not (540 <= diff <= 660), "Should not be from first line (10 min ago)"
            assert not (240 <= diff <= 360), "Should not be from second line (5 min ago)"
        finally:
            session_file.unlink()

    def test_format_last_message_timestamp_recent(self, manager: StatusLineManager) -> None:
        """Test formatting timestamp for recent messages."""
        # Use current time for predictable formatting
        now = datetime.now(timezone.utc)
        time_str = manager._format_last_message_timestamp(now)

        assert time_str is not None
        # Should be in HH:MM AM/PM format
        import re
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_str), f"Should be HH:MM AM/PM format, got: {time_str}"

    def test_format_last_message_timestamp_specific_time(self, manager: StatusLineManager) -> None:
        """Test formatting a specific timestamp."""
        # Create a specific time: 2:30 PM UTC
        specific_time = datetime(2025, 1, 9, 14, 30, 0, tzinfo=timezone.utc)
        time_str = manager._format_last_message_timestamp(specific_time)

        assert time_str is not None
        # The exact format depends on local timezone, but should contain time components
        import re
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_str), f"Should be HH:MM AM/PM format, got: {time_str}"
        # Verify it shows actual time, not elapsed time (no "ago" or duration markers)
        assert "ago" not in time_str.lower(), "Should show actual time, not elapsed time"
        assert "min" not in time_str.lower(), "Should show actual time, not elapsed time"
        assert "hour" not in time_str.lower(), "Should show actual time, not elapsed time"

    def test_format_last_message_timestamp_morning(self, manager: StatusLineManager) -> None:
        """Test formatting morning timestamp."""
        # Create a morning time: 8:42 AM UTC
        morning_time = datetime(2025, 1, 9, 8, 42, 0, tzinfo=timezone.utc)
        time_str = manager._format_last_message_timestamp(morning_time)

        assert time_str is not None
        import re
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_str), f"Should be HH:MM AM/PM format, got: {time_str}"

    def test_format_last_message_timestamp_evening(self, manager: StatusLineManager) -> None:
        """Test formatting evening timestamp."""
        # Create an evening time: 8:42 PM UTC
        evening_time = datetime(2025, 1, 9, 20, 42, 0, tzinfo=timezone.utc)
        time_str = manager._format_last_message_timestamp(evening_time)

        assert time_str is not None
        import re
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_str), f"Should be HH:MM AM/PM format, got: {time_str}"

    def test_format_last_message_timestamp_naive(self, manager: StatusLineManager) -> None:
        """Test formatting timezone-naive timestamp (should handle gracefully)."""
        # Create a naive datetime (no timezone info)
        naive_time = datetime(2025, 1, 9, 12, 0, 0)
        time_str = manager._format_last_message_timestamp(naive_time)

        assert time_str is not None
        import re
        assert re.match(r"\d{2}:\d{2} (AM|PM)", time_str), f"Should be HH:MM AM/PM format, got: {time_str}"

    def test_template_integration(self, manager: StatusLineManager) -> None:
        """Test integration with template system."""
        session_file = self.create_session_file(minutes_ago=3)

        try:
            # Mock the session file lookup
            original_find = manager._find_session_file
            manager._find_session_file = lambda _: session_file

            # Test template with last_message_time variable
            template = "{last_message_time}"
            components = manager._prepare_last_message_time_component(template, "test-session-123")

            assert "last_message_time" in components
            assert components["last_message_time"] != "", "Should have a value"
            assert "📝" in components["last_message_time"], "Should include 📝 emoji"

            # Verify format: should be "📝 HH:MM AM/PM"
            import re
            assert re.search(r"📝 \d{2}:\d{2} (AM|PM)", components["last_message_time"]), \
                f"Should be '📝 HH:MM AM/PM' format, got: {components['last_message_time']}"

            # Restore original method
            manager._find_session_file = original_find
        finally:
            session_file.unlink()

    def test_template_without_variable(self, manager: StatusLineManager) -> None:
        """Test that component is empty when variable not in template."""
        template = "{tokens}{sep}{messages}"
        components = manager._prepare_last_message_time_component(template, "test-session-123")

        assert components["last_message_time"] == "", "Should be empty when not in template"

    def test_template_without_session_id(self, manager: StatusLineManager) -> None:
        """Test that component is empty without session ID."""
        template = "{last_message_time}"
        components = manager._prepare_last_message_time_component(template, None)

        assert components["last_message_time"] == "", "Should be empty without session ID"

    def test_full_status_line_with_timer(self, manager: StatusLineManager) -> None:
        """Test full status line generation with timer."""
        session_file = self.create_session_file(minutes_ago=10)

        try:
            # Mock the session file lookup
            original_find = manager._find_session_file
            manager._find_session_file = lambda _: session_file

            # Generate status line with custom template
            manager.config.statusline_template = "{project}{sep}{tokens}{sep}{last_message_time}"
            status_line = manager.format_status_line_from_template(
                tokens=1000,
                messages=5,
                cost=0.50,
                project_name="test-project",
                session_id="test-session-123",
            )

            assert "📝" in status_line, "Should include timer emoji"
            # Should show actual time (HH:MM AM/PM format), not elapsed time
            import re
            assert re.search(r"\d{2}:\d{2} (AM|PM)", status_line), f"Should show time in HH:MM AM/PM format, got: {status_line}"
            assert "test-project" in status_line, "Should include project name"

            # Restore original method
            manager._find_session_file = original_find
        finally:
            session_file.unlink()


class TestLastMessageTimerEdgeCases:
    """Test edge cases for last message timer."""

    @pytest.fixture
    def config(self) -> Config:
        """Create a test configuration."""
        return Config()

    @pytest.fixture
    def manager(self, config: Config) -> StatusLineManager:
        """Create a status line manager."""
        return StatusLineManager(config)

    def test_invalid_timestamp_format(self, manager: StatusLineManager) -> None:
        """Test handling of invalid timestamp format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_file = Path(f.name)

            # Invalid timestamp format
            mock_entry = {
                "timestamp": "invalid-timestamp",
                "sessionId": "test-session-123",
            }

            f.write(json.dumps(mock_entry) + "\n")

        try:
            timestamp = manager._extract_last_message_timestamp(session_file)
            assert timestamp is None, "Should return None for invalid timestamp"
        finally:
            session_file.unlink()

    def test_empty_session_file(self, manager: StatusLineManager) -> None:
        """Test handling of empty session file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_file = Path(f.name)
            # Write nothing

        try:
            timestamp = manager._extract_last_message_timestamp(session_file)
            assert timestamp is None, "Should return None for empty file"
        finally:
            session_file.unlink()

    def test_malformed_json(self, manager: StatusLineManager) -> None:
        """Test handling of malformed JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            session_file = Path(f.name)
            f.write("{invalid json content\n")

        try:
            timestamp = manager._extract_last_message_timestamp(session_file)
            # Should handle gracefully (jq will fail, result will be None)
            assert timestamp is None, "Should return None for malformed JSON"
        finally:
            session_file.unlink()
