"""Test the new status line template variables."""

import os
import socket
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from par_cc_usage.statusline_manager import StatusLineManager


def create_mock_config():
    """Create a mock config with all required fields."""
    config = Mock()
    config.statusline_separator = " - "
    config.statusline_enabled = True
    config.statusline_date_format = "%Y-%m-%d"
    config.statusline_time_format = "%I:%M %p"
    config.statusline_git_clean_indicator = "✓"
    config.statusline_git_dirty_indicator = "*"
    return config


def test_template_with_username():
    """Test template with username variable."""
    config = create_mock_config()
    config.statusline_template = "{username} - {tokens}"
    manager = StatusLineManager(config)

    with patch.dict(os.environ, {"USER": "testuser"}):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            token_limit=500000,
        )

    assert "testuser" in result
    assert "🪙 100K/500K (20%)" in result


def test_template_with_hostname():
    """Test template with hostname variable."""
    config = create_mock_config()
    config.statusline_template = "{hostname} | {messages}"
    manager = StatusLineManager(config)

    with patch("socket.gethostname", return_value="test-machine"):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            message_limit=50,
        )

    assert "test-machine" in result
    assert "💬 25/50" in result


def test_template_with_date():
    """Test template with date variable."""
    config = create_mock_config()
    config.statusline_template = "{date} - {tokens}"
    manager = StatusLineManager(config)

    # Mock datetime to have consistent test
    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.strftime = datetime.strftime

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            token_limit=500000,
        )

    assert "2024-01-15" in result
    assert "🪙 100K/500K (20%)" in result


def test_template_with_current_time():
    """Test template with current_time variable."""
    config = create_mock_config()
    config.statusline_template = "{current_time} | {messages}"
    manager = StatusLineManager(config)

    # Mock datetime to have consistent test
    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.strftime = datetime.strftime

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            message_limit=50,
        )

    assert "02:30 PM" in result
    assert "💬 25/50" in result


def test_template_with_custom_date_format():
    """Test template with custom date format."""
    config = create_mock_config()
    config.statusline_template = "{date}"
    config.statusline_date_format = "%d/%m/%Y"  # Custom format
    manager = StatusLineManager(config)

    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.strftime = datetime.strftime

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

    assert "15/01/2024" in result


def test_template_with_24hr_time_format():
    """Test template with 24-hour time format."""
    config = create_mock_config()
    config.statusline_template = "{current_time}"
    config.statusline_time_format = "%H:%M"  # 24-hour format
    manager = StatusLineManager(config)

    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 0)
        mock_datetime.strftime = datetime.strftime

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

    assert "14:30" in result


def test_template_with_all_new_variables():
    """Test template with all new variables combined."""
    config = create_mock_config()
    config.statusline_template = "{username}@{hostname} [{date} {current_time}]\\n{tokens} - {messages}"
    manager = StatusLineManager(config)

    with patch.dict(os.environ, {"USER": "testuser"}):
        with patch("socket.gethostname", return_value="test-machine"):
            with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 0)
                mock_datetime.strftime = datetime.strftime

                result = manager.format_status_line_from_template(
                    tokens=100000,
                    messages=25,
                    token_limit=500000,
                    message_limit=50,
                )

    lines = result.split("\n")
    assert len(lines) == 2
    assert "testuser@test-machine [2024-01-15 02:30 PM]" in lines[0]
    assert "🪙 100K/500K (20%) - 💬 25/50" in lines[1]


def test_template_fallback_for_missing_username():
    """Test that missing username falls back to 'unknown'."""
    config = create_mock_config()
    config.statusline_template = "{username}"
    manager = StatusLineManager(config)

    with patch.dict(os.environ, {}, clear=True):  # Clear all env vars
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

    assert "unknown" in result


def test_template_fallback_for_hostname_error():
    """Test that hostname error falls back to 'unknown'."""
    config = create_mock_config()
    config.statusline_template = "{hostname}"
    manager = StatusLineManager(config)

    with patch("socket.gethostname", side_effect=Exception("Network error")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

    assert "unknown" in result
