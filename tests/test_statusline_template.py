"""Test the status line template functionality."""

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
    return config


def test_template_basic_single_line():
    """Test basic single-line template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"

    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        cost=0.0,
        token_limit=500000,
        message_limit=50,
    )

    assert "🪙 100K/500K (20%)" in result
    assert "💬 25/50" in result
    assert " - " in result


def test_template_multi_line():
    """Test multi-line template with newline."""
    config = create_mock_config()
    config.statusline_template = "{tokens}\\n{messages}\\n{cost}"

    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        cost=1.50,
        token_limit=500000,
        message_limit=50,
        cost_limit=5.00,
    )

    lines = result.split("\n")
    assert len(lines) == 3
    assert "🪙 100K/500K (20%)" in lines[0]
    assert "💬 25/50" in lines[1]
    assert "💰 $1.50/$5.00" in lines[2]


def test_template_with_project():
    """Test template with project name."""
    config = create_mock_config()
    config.statusline_template = "{project}{sep}{tokens}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        project_name="my-project",
        token_limit=500000,
    )

    assert "[my-project]" in result
    assert "🪙 100K/500K (20%)" in result
    assert " - " in result


def test_template_custom_order():
    """Test template with custom component order."""
    config = create_mock_config()
    config.statusline_template = "{messages} | {tokens} | {remaining_block_time}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        time_remaining="2h 30m",
        token_limit=500000,
        message_limit=50,
    )

    # Check order is correct
    assert result.index("💬") < result.index("🪙")
    assert result.index("🪙") < result.index("⏱️")
    assert "|" in result  # Custom separator used


def test_template_missing_components():
    """Test template with some components missing."""
    config = create_mock_config()
    config.statusline_template = "{project}{sep}{cost}{sep}{remaining_block_time}"
    manager = StatusLineManager(config)

    # No project, no cost (cost=0), no time
    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        cost=0.0,
        project_name=None,
        time_remaining=None,
    )

    # Should be empty or very minimal since all components are missing
    assert result == ""


def test_template_with_all_components():
    """Test template with all components present."""
    config = create_mock_config()
    config.statusline_template = "{project}{sep}{tokens}{sep}{messages}{sep}{cost}{sep}{remaining_block_time}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=250000,
        messages=30,
        cost=2.50,
        token_limit=500000,
        message_limit=50,
        cost_limit=10.00,
        time_remaining="1h 45m",
        project_name="test-project",
    )

    assert "[test-project]" in result
    assert "🪙 250K/500K (50%)" in result
    assert "💬 30/50" in result
    assert "💰 $2.50/$10.00" in result
    assert "⏱️ 1h 45m" in result


def test_template_default_fallback():
    """Test fallback to default template when template is empty."""
    config = create_mock_config()
    config.statusline_template = ""  # Empty template
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        token_limit=500000,
        message_limit=50,
    )

    # Should use default template
    assert "🪙 100K/500K (20%)" in result
    assert "💬 25/50" in result


def test_template_complex_multiline():
    """Test complex multi-line template."""
    config = create_mock_config()
    config.statusline_template = "Project: {project}\\nUsage: {tokens} | {messages}\\nCost: {cost} | Time left: {remaining_block_time}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=300000,
        messages=40,
        cost=3.75,
        token_limit=500000,
        message_limit=50,
        cost_limit=10.00,
        time_remaining="45m",
        project_name="complex-app",
    )

    lines = result.split("\n")
    assert len(lines) == 3
    assert "Project: [complex-app]" in lines[0]
    assert "Usage: 🪙 300K/500K (60%) | 💬 40/50" in lines[1]
    assert "Cost: 💰 $3.75/$10.00 | Time left: ⏱️ 45m" in lines[2]


def test_template_separator_cleanup():
    """Test that multiple/trailing separators are cleaned up."""
    config = create_mock_config()
    config.statusline_template = "{project}{sep}{sep}{tokens}{sep}{sep}{messages}{sep}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        project_name="test",
        token_limit=500000,
        message_limit=50,
    )

    # Should not have multiple consecutive separators or trailing separators
    assert " -  - " not in result
    assert not result.endswith(" - ")
    assert not result.startswith(" - ")


def test_template_unknown_variables():
    """Test that unknown template variables are gracefully handled."""
    config = create_mock_config()
    config.statusline_template = "{tokens}{sep}{unknown_var}{sep}{another_unknown}"
    manager = StatusLineManager(config)

    result = manager.format_status_line_from_template(
        tokens=100000,
        messages=25,
        token_limit=500000,
        message_limit=50,
    )

    # Should contain the unknown variable placeholders
    assert "[unknown_var: unknown_var]" in result
    assert "[unknown_var: another_unknown]" in result
    assert "🪙 100K/500K (20%)" in result


def test_template_with_git_variables():
    """Test template with git branch and status variables."""
    config = create_mock_config()
    config.statusline_template = "{git_branch}{sep}{git_status}{sep}{tokens}"
    manager = StatusLineManager(config)

    # Mock the git info method to avoid actual git calls
    with patch.object(manager, '_get_git_info', return_value=("main", "✓")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            token_limit=500000,
            message_limit=50,
        )

        assert "main" in result
        assert "✓" in result
        assert "🪙 100K/500K (20%)" in result


def test_template_git_dirty_status():
    """Test template with dirty git status."""
    config = create_mock_config()
    config.statusline_template = "Branch: {git_branch} Status: {git_status}"
    manager = StatusLineManager(config)

    # Mock dirty git status
    with patch.object(manager, '_get_git_info', return_value=("feature/new", "*")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        assert "Branch: feature/new" in result
        assert "Status: *" in result


def test_template_no_git_repo():
    """Test template when not in a git repository."""
    config = create_mock_config()
    config.statusline_template = "{git_branch}{sep}{git_status}{sep}{tokens}"
    manager = StatusLineManager(config)

    # Mock no git repo (empty strings)
    with patch.object(manager, '_get_git_info', return_value=("", "")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            token_limit=500000,
            message_limit=50,
        )

        # Git components should be empty, separator cleanup should handle it
        assert "🪙 100K/500K (20%)" in result
        # Should not have trailing/leading separators from empty git fields
        assert not result.startswith(" - ")
        assert not result.endswith(" - ")


def test_template_custom_git_indicators():
    """Test template with custom git status indicators."""
    config = create_mock_config()
    config.statusline_template = "{git_branch} {git_status} - {tokens}"
    manager = StatusLineManager(config)

    # Test with clean status
    with patch.object(manager, '_get_git_info', return_value=("main", "✅")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
            token_limit=500000,
            message_limit=50,
        )

        assert "main ✅" in result
        assert "🪙 100K/500K (20%)" in result


def test_template_text_git_indicators():
    """Test template with text-based git status indicators."""
    config = create_mock_config()
    config.statusline_template = "Branch: {git_branch} ({git_status})"
    manager = StatusLineManager(config)

    # Test with dirty status
    with patch.object(manager, '_get_git_info', return_value=("feature/new", "modified")):
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        assert "Branch: feature/new (modified)" in result
