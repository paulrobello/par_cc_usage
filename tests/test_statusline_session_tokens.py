"""Test session token tracking in status line."""

import subprocess
from unittest.mock import Mock, patch

from par_cc_usage.statusline_manager import StatusLineManager


def create_mock_config():
    """Create a mock config with all required fields."""
    config = Mock()
    config.statusline_enabled = True
    config.statusline_date_format = "%Y-%m-%d"
    config.statusline_time_format = "%I:%M %p"
    config.statusline_git_clean_indicator = "✓"
    config.statusline_git_dirty_indicator = "*"
    config.statusline_progress_bar_length = 10
    config.statusline_progress_bar_colorize = False  # Default to False for tests
    config.statusline_progress_bar_style = "basic"  # Default to basic style
    config.statusline_progress_bar_show_percent = False  # Default to False for tests
    return config


def test_session_tokens_extraction():
    """Test extraction of session tokens from JSONL file."""
    from pathlib import Path

    config = create_mock_config()
    manager = StatusLineManager(config)

    # Mock the subprocess call to jq
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="150000\n",  # 150K tokens used
        )

        # Mock _find_session_file to return a valid path
        with patch.object(manager, "_find_session_file", return_value=Path("/tmp/test-session-id.jsonl")):
            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                tokens_used, max_tokens, tokens_remaining = manager._get_session_tokens("test-session-id")

                assert tokens_used == 150000
                assert max_tokens == 200000  # Default max
                assert tokens_remaining == 50000


def test_session_tokens_no_session():
    """Test when no session ID is provided."""
    config = create_mock_config()
    manager = StatusLineManager(config)

    tokens_used, max_tokens, tokens_remaining = manager._get_session_tokens(None)

    assert tokens_used == 0
    assert max_tokens == 0
    assert tokens_remaining == 0


def test_session_tokens_file_not_found():
    """Test when session file doesn't exist."""
    config = create_mock_config()
    manager = StatusLineManager(config)

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        tokens_used, max_tokens, tokens_remaining = manager._get_session_tokens("test-session-id")

        assert tokens_used == 0
        assert max_tokens == 0
        assert tokens_remaining == 0


def test_progress_bar_creation():
    """Test progress bar creation."""
    config = create_mock_config()
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test empty progress bar
    bar = manager._create_progress_bar(0, 100)
    assert bar == "[░░░░░░░░░░]"

    # Test half-filled progress bar
    bar = manager._create_progress_bar(50, 100)
    assert bar == "[█████░░░░░]"

    # Test full progress bar
    bar = manager._create_progress_bar(100, 100)
    assert bar == "[██████████]"

    # Test with custom length
    bar = manager._create_progress_bar(30, 100, length=5)
    assert bar == "[█░░░░]"

    # Test with zero max value
    bar = manager._create_progress_bar(50, 0)
    assert bar == "[░░░░░░░░░░]"


def test_template_with_session_tokens():
    """Test template with session token variables."""
    config = create_mock_config()
    config.statusline_template = "{session_tokens}/{session_tokens_total} ({session_tokens_percent})"
    manager = StatusLineManager(config)

    # Mock the session token extraction
    with patch.object(manager, '_get_session_tokens', return_value=(150000, 200000, 50000)):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            session_id="test-session-id"
        )

        assert "150K" in result  # No emoji anymore
        assert "200K" in result
        assert "75%" in result


def test_template_with_session_progress_bar():
    """Test template with session token progress bar."""
    config = create_mock_config()
    config.statusline_template = "{session_tokens_progress_bar} {session_tokens_remaining} left"
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Mock the session token extraction for 25% usage
    with patch.object(manager, '_get_session_tokens', return_value=(50000, 200000, 150000)):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            session_id="test-session-id"
        )

        assert "[██░░░░░░░░]" in result  # 25% filled
        assert "150K left" in result


def test_template_session_tokens_formatting():
    """Test formatting of session token values."""
    config = create_mock_config()
    config.statusline_template = "{session_tokens} / {session_tokens_total}"
    manager = StatusLineManager(config)

    # Test small values (< 1K)
    with patch.object(manager, '_get_session_tokens', return_value=(500, 1000, 500)):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            session_id="test-session-id"
        )
        assert "500 / 1K" in result  # 1000 is formatted as 1K, no emoji

    # Test K values (thousands)
    with patch.object(manager, '_get_session_tokens', return_value=(45678, 200000, 154322)):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            session_id="test-session-id"
        )
        assert "45K / 200K" in result  # No emoji

    # Test M values (millions)
    with patch.object(manager, '_get_session_tokens', return_value=(1500000, 2000000, 500000)):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            session_id="test-session-id"
        )
        assert "1.5M / 2.0M" in result  # No emoji


def test_template_without_session_id():
    """Test that session token variables are empty when no session_id."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - Session: {session_tokens}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        # No session_id provided
    )

    assert "100K" in result  # Regular tokens still have emoji
    assert "Session: " in result or "Session:" in result  # Empty session tokens


def test_custom_progress_bar_length():
    """Test custom progress bar length from config."""
    config = create_mock_config()
    config.statusline_progress_bar_length = 15
    manager = StatusLineManager(config)

    # Test with 60% usage
    bar = manager._create_progress_bar(60, 100)
    assert bar == "[█████████░░░░░░]"  # 9 filled, 6 empty (60% of 15)
    assert len(bar) == 17  # 15 chars + 2 brackets


def test_session_tokens_with_jq_error():
    """Test handling of jq command errors."""
    config = create_mock_config()
    manager = StatusLineManager(config)

    with patch("subprocess.run") as mock_run:
        # Simulate jq command failure
        mock_run.return_value = Mock(returncode=1, stdout="")

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            tokens_used, max_tokens, tokens_remaining = manager._get_session_tokens("test-session-id")

            assert tokens_used == 0
            assert max_tokens == 0
            assert tokens_remaining == 0


def test_session_tokens_with_timeout():
    """Test handling of subprocess timeout."""
    config = create_mock_config()
    manager = StatusLineManager(config)

    with patch("subprocess.run") as mock_run:
        # Simulate timeout
        mock_run.side_effect = subprocess.TimeoutExpired("jq", 1)

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            tokens_used, max_tokens, tokens_remaining = manager._get_session_tokens("test-session-id")

            assert tokens_used == 0
            assert max_tokens == 0
            assert tokens_remaining == 0


def test_colorized_progress_bar():
    """Test colorized progress bar based on utilization."""
    config = create_mock_config()
    config.statusline_progress_bar_colorize = True
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test green color (< 50%)
    bar = manager._create_progress_bar(25, 100)
    assert "\033[92m" in bar  # Bright Green color code
    assert "██" in bar  # 25% filled
    assert "\033[39m" in bar  # Reset foreground color

    # Test yellow color (50-79%)
    bar = manager._create_progress_bar(60, 100)
    assert "\033[93m" in bar  # Bright Yellow color code
    assert "██████" in bar  # 60% filled

    # Test red color (>= 80%)
    bar = manager._create_progress_bar(90, 100)
    assert "\033[91m" in bar  # Bright Red color code
    assert "█████████" in bar  # 90% filled


def test_non_colorized_progress_bar():
    """Test that progress bar has no colors when colorize is disabled."""
    config = create_mock_config()
    config.statusline_progress_bar_colorize = False
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test various percentages without colors
    bar = manager._create_progress_bar(25, 100)
    assert "\033[" not in bar  # No color codes
    assert bar == "[██░░░░░░░░]"

    bar = manager._create_progress_bar(60, 100)
    assert "\033[" not in bar
    assert bar == "[██████░░░░]"

    bar = manager._create_progress_bar(90, 100)
    assert "\033[" not in bar
    assert bar == "[█████████░]"


def test_colorized_progress_bar_edge_cases():
    """Test colorized progress bar at boundary values."""
    config = create_mock_config()
    config.statusline_progress_bar_colorize = True
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test exactly at boundaries
    # 49% should be green
    bar = manager._create_progress_bar(49, 100)
    assert "\033[92m" in bar  # Bright Green

    # 50% should be yellow
    bar = manager._create_progress_bar(50, 100)
    assert "\033[93m" in bar  # Bright Yellow

    # 79% should be yellow
    bar = manager._create_progress_bar(79, 100)
    assert "\033[93m" in bar  # Bright Yellow

    # 80% should be red
    bar = manager._create_progress_bar(80, 100)
    assert "\033[91m" in bar  # Bright Red

    # 100% should be red
    bar = manager._create_progress_bar(100, 100)
    assert "\033[91m" in bar  # Bright Red
    assert "[" in bar and "]" in bar  # Has brackets


def test_rich_progress_bar_style():
    """Test Rich-style progress bar rendering."""
    config = create_mock_config()
    config.statusline_progress_bar_style = "rich"
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test empty progress bar
    bar = manager._create_progress_bar(0, 100)
    assert "[" in bar and "]" in bar
    assert "╺" in bar  # Rich empty character

    # Test half-filled progress bar
    bar = manager._create_progress_bar(50, 100)
    assert "[" in bar and "]" in bar
    assert "━" in bar  # Rich filled character
    assert "╺" in bar  # Rich empty character

    # Test full progress bar
    bar = manager._create_progress_bar(100, 100)
    assert "[" in bar and "]" in bar
    assert "━" in bar  # All filled with Rich character
    assert "╺" not in bar  # No empty parts


def test_rich_progress_bar_with_colors():
    """Test Rich-style progress bar with colorization."""
    config = create_mock_config()
    config.statusline_progress_bar_style = "rich"
    config.statusline_progress_bar_colorize = True
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test green color (< 50%)
    bar = manager._create_progress_bar(25, 100)
    assert "\033[92m" in bar  # ANSI bright green color code
    assert "━" in bar

    # Test yellow color (50-79%)
    bar = manager._create_progress_bar(60, 100)
    assert "\033[93m" in bar  # ANSI bright yellow color code
    assert "━" in bar

    # Test red color (>= 80%)
    bar = manager._create_progress_bar(90, 100)
    assert "\033[91m" in bar  # ANSI bright red color code
    assert "━" in bar


def test_progress_bar_style_switching():
    """Test switching between basic and rich progress bar styles."""
    config = create_mock_config()
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Test basic style (default)
    config.statusline_progress_bar_style = "basic"
    bar = manager._create_progress_bar(50, 100)
    assert "█" in bar  # Basic filled character
    assert "░" in bar  # Basic empty character

    # Test rich style
    config.statusline_progress_bar_style = "rich"
    bar = manager._create_progress_bar(50, 100)
    assert "━" in bar  # Rich filled character
    assert "╺" in bar  # Rich empty character


def test_progress_bar_with_percent_basic():
    """Test basic progress bar with percentage display."""
    config = create_mock_config()
    config.statusline_progress_bar_style = "basic"
    config.statusline_progress_bar_show_percent = True
    config.statusline_progress_bar_length = 10  # Will be 13 with percent
    manager = StatusLineManager(config)

    # Test 0%
    bar = manager._create_progress_bar(0, 100)
    assert "  0%" in bar
    assert "░" in bar

    # Test 50%
    bar = manager._create_progress_bar(50, 100)
    assert " 50%" in bar
    assert "█" in bar
    assert "░" in bar

    # Test 100%
    bar = manager._create_progress_bar(100, 100)
    assert "100%" in bar
    assert "█" in bar


def test_progress_bar_with_percent_rich():
    """Test Rich progress bar with percentage display."""
    config = create_mock_config()
    config.statusline_progress_bar_style = "rich"
    config.statusline_progress_bar_show_percent = True
    config.statusline_progress_bar_length = 10  # Will be 13 with percent
    manager = StatusLineManager(config)

    # Test 0%
    bar = manager._create_progress_bar(0, 100)
    assert "  0%" in bar
    assert "╺" in bar

    # Test 50%
    bar = manager._create_progress_bar(50, 100)
    assert " 50%" in bar
    assert "━" in bar
    assert "╺" in bar

    # Test 100%
    bar = manager._create_progress_bar(100, 100)
    assert "100%" in bar
    assert "━" in bar


def test_progress_bar_with_percent_and_colors():
    """Test progress bar with percentage and colors."""
    config = create_mock_config()
    config.statusline_progress_bar_style = "basic"
    config.statusline_progress_bar_show_percent = True
    config.statusline_progress_bar_colorize = True
    config.statusline_progress_bar_length = 10  # Will be 13 with percent
    manager = StatusLineManager(config)

    # Test green (25%)
    bar = manager._create_progress_bar(25, 100)
    assert " 25%" in bar
    assert "\033[92m" in bar  # Bright Green color

    # Test yellow (60%)
    bar = manager._create_progress_bar(60, 100)
    assert " 60%" in bar
    assert "\033[93m" in bar  # Bright Yellow color

    # Test red (90%)
    bar = manager._create_progress_bar(90, 100)
    assert " 90%" in bar
    assert "\033[91m" in bar  # Bright Red color


def test_progress_bar_auto_width_adjustment():
    """Test that progress bar width is automatically adjusted when showing percent."""
    config = create_mock_config()
    config.statusline_progress_bar_length = 10
    manager = StatusLineManager(config)

    # Without percent display
    config.statusline_progress_bar_show_percent = False
    bar_no_percent = manager._create_progress_bar(50, 100)

    # With percent display
    config.statusline_progress_bar_show_percent = True
    bar_with_percent = manager._create_progress_bar(50, 100)

    # The bar with percent should have the percentage text in it
    assert " 50%" in bar_with_percent
    # The bar without percent should not
    assert "50%" not in bar_no_percent
