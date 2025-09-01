"""Test configurable separator in status line."""

from unittest.mock import Mock

import pytest

from par_cc_usage.statusline_manager import StatusLineManager


def create_mock_config(separator=" - "):
    """Create a mock config with all required fields."""
    config = Mock()
    config.statusline_enabled = True
    config.statusline_date_format = "%Y-%m-%d"
    config.statusline_time_format = "%I:%M %p"
    config.statusline_git_clean_indicator = "✓"
    config.statusline_git_dirty_indicator = "*"
    config.statusline_progress_bar_length = 10
    config.statusline_progress_bar_colorize = False
    config.statusline_progress_bar_style = "basic"
    config.statusline_progress_bar_show_percent = False
    config.statusline_template = "{tokens}{sep}{messages}"
    config.statusline_separator = separator
    return config


def test_default_separator():
    """Test default separator is ' - '."""
    config = create_mock_config()
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    assert " - " in result
    assert "100K" in result
    assert "25" in result


def test_custom_separator_pipe():
    """Test custom separator with pipe."""
    config = create_mock_config(separator=" | ")
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    assert " | " in result
    assert " - " not in result
    assert "100K" in result
    assert "25" in result


def test_custom_separator_double_colon():
    """Test custom separator with double colon."""
    config = create_mock_config(separator=" :: ")
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    assert " :: " in result
    assert " - " not in result
    assert "100K" in result
    assert "25" in result


def test_custom_separator_bullet():
    """Test custom separator with bullet."""
    config = create_mock_config(separator=" • ")
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    assert " • " in result
    assert " - " not in result
    assert "100K" in result
    assert "25" in result


def test_separator_cleanup_with_empty_components():
    """Test that custom separators are cleaned up properly."""
    config = create_mock_config(separator=" | ")
    config.statusline_template = "{project}{sep}{tokens}"
    manager = StatusLineManager(config)

    # No project name - separator should be cleaned
    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        project_name=None,
    )

    # Should not have leading separator
    assert not result.startswith(" | ")
    assert not result.startswith("|")
    assert "100K" in result


def test_separator_with_multiline_template():
    """Test custom separator in multiline template."""
    config = create_mock_config(separator=" :: ")
    config.statusline_template = "{tokens}{sep}{messages}\\n{cost}{sep}{remaining_block_time}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        cost=1.50,
        time_remaining="2h 30m",
    )

    lines = result.split("\n")
    assert " :: " in lines[0]
    assert "100K" in lines[0]
    assert "25" in lines[0]
    assert " :: " in lines[1]
    assert "$1.50" in lines[1]
    assert "2h 30m" in lines[1]


def test_multiple_separator_cleanup():
    """Test that multiple consecutive custom separators are cleaned up."""
    config = create_mock_config(separator=" | ")
    # Template with potential for multiple separators
    config.statusline_template = "{project}{sep}{sep}{tokens}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        project_name="test",
    )

    # Should not have double separators
    assert " |  | " not in result
    assert " | | " not in result
    assert "[test]" in result
    assert " | " in result
    assert "100K" in result


def test_separator_in_template_variable():
    """Test that {sep} template variable uses configured separator."""
    config = create_mock_config(separator=" => ")
    config.statusline_template = "Tokens{sep}{tokens}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    assert "Tokens => " in result
    assert "100K" in result
