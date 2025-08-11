"""Basic tests for status line functionality."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from par_cc_usage.statusline_manager import StatusLineManager


class TestStatusLineBasic:
    """Basic tests for StatusLineManager."""

    def test_format_status_line_tokens_only(self):
        """Test formatting with just tokens."""
        config = Mock()
        manager = StatusLineManager(config)

        result = manager.format_status_line(tokens=5000, messages=10)
        assert "🪙 5K" in result  # Format is 5K not 5.0K
        assert "💬 10" in result
        assert "💰" not in result  # No cost
        assert "⏱️" not in result  # No time

    def test_format_status_line_with_limits(self):
        """Test formatting with limits."""
        config = Mock()
        manager = StatusLineManager(config)

        result = manager.format_status_line(
            tokens=5000,
            messages=10,
            token_limit=10000,
            message_limit=20
        )
        assert "🪙 5K/10K (50%)" in result  # Format is 5K not 5.0K
        assert "💬 10/20" in result

    def test_format_status_line_with_cost(self):
        """Test formatting with cost."""
        config = Mock()
        manager = StatusLineManager(config)

        result = manager.format_status_line(
            tokens=5000,
            messages=10,
            cost=1.50,
            cost_limit=5.00
        )
        assert "💰 $1.50/$5.00" in result

    def test_format_status_line_with_time(self):
        """Test formatting with time remaining."""
        config = Mock()
        manager = StatusLineManager(config)

        result = manager.format_status_line(
            tokens=5000,
            messages=10,
            time_remaining="2h 30m"
        )
        assert "⏱️ 2h 30m" in result

    def test_calculate_time_remaining_future(self):
        """Test time remaining calculation for future time."""
        config = Mock()
        manager = StatusLineManager(config)

        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=2, minutes=30)

        result = manager._calculate_time_remaining(future)
        # Result should be approximately 2h 30m (might be slightly less due to execution time)
        assert result is not None
        assert "h" in result or "m" in result

    def test_calculate_time_remaining_past(self):
        """Test time remaining calculation for past time."""
        config = Mock()
        manager = StatusLineManager(config)

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)

        result = manager._calculate_time_remaining(past)
        assert result is None

    def test_calculate_time_remaining_minutes_only(self):
        """Test time remaining when less than an hour."""
        config = Mock()
        manager = StatusLineManager(config)

        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=45)

        result = manager._calculate_time_remaining(future)
        assert result is not None
        assert "m" in result
        assert "h" not in result

    def test_save_and_load_status_line(self, tmp_path):
        """Test saving and loading status lines to/from disk."""
        config = Mock()
        manager = StatusLineManager(config)

        # Mock the path functions
        test_path = tmp_path / "test_session.txt"

        with patch("par_cc_usage.statusline_manager.get_statusline_file_path", return_value=test_path):
            # Save a status line
            status_line = "🪙 100K - 💬 50 - 💰 $10.00"
            manager.save_status_line("test_session", status_line)

            # Verify file was created
            assert test_path.exists()
            assert test_path.read_text() == status_line

            # Load the status line back
            loaded = manager.load_status_line("test_session")
            assert loaded == status_line

    def test_get_status_line_for_request_disabled(self):
        """Test that disabled status line returns empty string."""
        config = Mock()
        config.statusline_enabled = False
        manager = StatusLineManager(config)

        result = manager.get_status_line_for_request({"sessionId": "test"})
        assert result == ""

    def test_get_status_line_for_request_grand_total_mode(self):
        """Test grand total mode always returns grand total."""
        config = Mock()
        config.statusline_enabled = True
        config.statusline_use_grand_total = True
        manager = StatusLineManager(config)

        with patch.object(manager, "load_status_line") as mock_load:
            mock_load.return_value = "grand_total_line"

            result = manager.get_status_line_for_request({"sessionId": "any_session"})
            assert result == "grand_total_line"
            mock_load.assert_called_once_with("grand_total")

    def test_get_status_line_for_request_session_mode(self):
        """Test session mode returns session-specific line."""
        config = Mock()
        config.statusline_enabled = True
        config.statusline_use_grand_total = False
        manager = StatusLineManager(config)

        with patch.object(manager, "load_status_line") as mock_load:
            mock_load.side_effect = lambda x: "session_line" if x == "test_session" else None

            result = manager.get_status_line_for_request({"sessionId": "test_session"})
            assert result == "session_line"

    def test_get_status_line_for_request_fallback(self):
        """Test fallback to grand total when session not found."""
        config = Mock()
        config.statusline_enabled = True
        config.statusline_use_grand_total = False
        manager = StatusLineManager(config)

        with patch.object(manager, "load_status_line") as mock_load:
            mock_load.side_effect = lambda x: "grand_total_line" if x == "grand_total" else None

            result = manager.get_status_line_for_request({"sessionId": "unknown_session"})
            assert result == "grand_total_line"

    def test_update_status_lines_disabled(self):
        """Test that update does nothing when disabled."""
        config = Mock()
        config.statusline_enabled = False
        manager = StatusLineManager(config)

        usage_snapshot = Mock()

        with patch.object(manager, "save_status_line") as mock_save:
            manager.update_status_lines(usage_snapshot)
            mock_save.assert_not_called()
