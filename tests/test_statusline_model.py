"""Test model template variable in status line."""

from unittest.mock import Mock, patch

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
    config.statusline_progress_bar_length = 10
    config.statusline_progress_bar_colorize = False
    config.statusline_progress_bar_style = "basic"
    config.statusline_progress_bar_show_percent = False
    config.statusline_template = "{model} - {tokens} - {messages}"
    return config


def test_model_in_template():
    """Test that model variable is preserved in template."""
    config = create_mock_config()
    config.statusline_template = "{model} | {tokens}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
    )

    # Model should be preserved as a placeholder
    assert "{model}" in result
    assert "100K" in result


def test_model_enrichment():
    """Test that model is properly enriched from Claude Code JSON."""
    config = create_mock_config()
    config.statusline_template = "{model} - {tokens}"
    manager = StatusLineManager(config)

    # Save a test status line with model placeholder
    test_status = "{model} - 🪙 100K"
    manager.save_status_line("test_session", test_status)

    # Simulate Claude Code request with model info
    session_json = {
        "session_id": "test_session",
        "model": {
            "id": "claude-opus-4-1",
            "display_name": "Opus"
        }
    }

    # Mock the load_status_line to return our test status
    with patch.object(manager, 'load_status_line', return_value=test_status):
        result = manager.get_status_line_for_request(session_json)

    # Model should be replaced with display_name
    assert "Opus" in result
    assert "{model}" not in result
    assert "100K" in result


def test_model_enrichment_with_session_tokens():
    """Test that model and session tokens are both enriched."""
    config = create_mock_config()
    config.statusline_template = "{model} - {tokens} - {session_tokens}/{session_tokens_total}"
    manager = StatusLineManager(config)

    # Save a test status line with both placeholders
    test_status = "{model} - 🪙 100K - {session_tokens}/{session_tokens_total}"
    manager.save_status_line("test_session", test_status)

    # Simulate Claude Code request with model info
    session_json = {
        "session_id": "test_session",
        "model": {
            "id": "claude-sonnet-3-5",
            "display_name": "Sonnet"
        }
    }

    # Mock the session token extraction
    with patch.object(manager, 'load_status_line', return_value=test_status):
        with patch.object(manager, '_get_session_tokens', return_value=(50000, 200000, 150000)):
            result = manager.get_status_line_for_request(session_json)

    # Both model and session tokens should be replaced
    assert "Sonnet" in result
    assert "50K" in result
    assert "200K" in result
    assert "{model}" not in result
    assert "{session_tokens}" not in result


def test_model_missing_in_json():
    """Test graceful handling when model is not in JSON."""
    config = create_mock_config()
    config.statusline_template = "{model} - {tokens}"
    manager = StatusLineManager(config)

    # Save a test status line with model placeholder
    test_status = "{model} - 🪙 100K"
    manager.save_status_line("test_session", test_status)

    # Simulate Claude Code request without model info
    session_json = {
        "session_id": "test_session"
    }

    with patch.object(manager, 'load_status_line', return_value=test_status):
        result = manager.get_status_line_for_request(session_json)

    # Model should be replaced with empty string
    assert "{model}" not in result
    assert "100K" in result
    # The separator should be cleaned up
    assert result.strip().startswith("🪙")


def test_model_with_multiline_template():
    """Test model variable in multiline template."""
    config = create_mock_config()
    config.statusline_template = "{model}\\n{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Save a test status line
    test_status = "{model}\n🪙 100K - 💬 25"
    manager.save_status_line("test_session", test_status)

    # Simulate Claude Code request with model info
    session_json = {
        "session_id": "test_session",
        "model": {
            "id": "claude-opus-4-1",
            "display_name": "Opus"
        }
    }

    with patch.object(manager, 'load_status_line', return_value=test_status):
        result = manager.get_status_line_for_request(session_json)

    # Model should be on first line
    lines = result.split("\n")
    assert lines[0] == "Opus"
    assert "100K" in lines[1]
    assert "25" in lines[1]


def test_model_not_replaced_when_not_in_template():
    """Test that model enrichment is skipped when not in template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Save a test status line without model
    test_status = "🪙 100K - 💬 25"
    manager.save_status_line("test_session", test_status)

    # Simulate Claude Code request with model info
    session_json = {
        "session_id": "test_session",
        "model": {
            "id": "claude-opus-4-1",
            "display_name": "Opus"
        }
    }

    with patch.object(manager, 'load_status_line', return_value=test_status):
        result = manager.get_status_line_for_request(session_json)

    # Result should be unchanged since model wasn't in template
    assert result == test_status
    assert "Opus" not in result
