"""Test conditional data fetching in status line based on template."""

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
    config.statusline_progress_bar_colorize = False
    config.statusline_progress_bar_style = "basic"
    config.statusline_progress_bar_show_percent = False
    return config


def test_git_info_not_fetched_when_not_in_template():
    """Test that git info is not fetched when not in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Mock subprocess.run to track if it's called
    with patch("subprocess.run") as mock_run:
        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # Git command should not have been called
        assert not any(
            "git" in str(call[0][0]) if call[0] else False
            for call in mock_run.call_args_list
        )

        # Result should not contain git info
        assert "✓" not in result
        assert "*" not in result


def test_git_info_fetched_when_in_template():
    """Test that git info is fetched when in the template."""
    from pathlib import Path

    config = create_mock_config()
    config.statusline_template = "{tokens} - {git_branch} {git_status}"
    manager = StatusLineManager(config)

    # Mock subprocess.run for git commands
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="main\n",
            stderr="",
        )

        # Mock _get_project_path_from_session to return a valid path
        mock_project_path = Path("/tmp/test_project")
        with patch.object(manager, "_get_project_path_from_session", return_value=mock_project_path):
            # Mock _find_git_root to return the project path (indicating .git exists)
            with patch.object(manager, "_find_git_root", return_value=mock_project_path):
                result = manager.format_status_line_from_template(
                    tokens=100000,
                    messages=25,
                    session_id="test-session-123",
                )

                # Git command should have been called
                assert any(
                    "git" in str(call[0][0]) if call[0] else False
                    for call in mock_run.call_args_list
                )

                # Result should contain branch name
                assert "main" in result


def test_session_tokens_not_fetched_when_not_in_template():
    """Test that session tokens are not fetched when not in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Mock subprocess.run to track if jq is called
    with patch("subprocess.run") as mock_run:
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            manager.format_status_line_from_template(
                tokens=100000,
                messages=25,
                session_id="test-session-id",
            )

            # jq command should not have been called
            assert not any(
                "jq" in str(call[0][0]) if call[0] else False
                for call in mock_run.call_args_list
            )


def test_session_tokens_fetched_when_in_template():
    """Test that session tokens are fetched when in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {session_tokens}/{session_tokens_total}"
    manager = StatusLineManager(config)

    # Mock subprocess.run for jq command
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="150000\n",
        )

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            result = manager.format_status_line_from_template(
                tokens=100000,
                messages=25,
                session_id="test-session-id",
            )

            # jq command should have been called
            assert any(
                "jq" in str(call[0][0]) if call[0] else False
                for call in mock_run.call_args_list
            )

            # Result should contain session tokens
            assert "150K" in result
            assert "200K" in result  # Default max


def test_date_time_not_fetched_when_not_in_template():
    """Test that date/time is not computed when not in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Mock datetime to check if it's accessed
    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        # Set up a mock that tracks if now() is called
        mock_now = Mock()
        mock_datetime.now = Mock(return_value=mock_now)

        manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # datetime.now() should not have been called
        mock_datetime.now.assert_not_called()


def test_date_time_fetched_when_in_template():
    """Test that date/time is computed when in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {date} {current_time}"
    manager = StatusLineManager(config)

    # Mock datetime
    from datetime import datetime
    test_time = datetime(2024, 3, 15, 14, 30, 0)

    with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
        mock_datetime.now.return_value = test_time
        mock_datetime.strftime = datetime.strftime

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # datetime.now() should have been called
        mock_datetime.now.assert_called()

        # Result should contain formatted date and time
        assert "2024-03-15" in result
        assert "02:30 PM" in result


def test_hostname_not_fetched_when_not_in_template():
    """Test that hostname is not fetched when not in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Mock socket.gethostname
    with patch("socket.gethostname") as mock_gethostname:
        manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # gethostname should not have been called
        mock_gethostname.assert_not_called()


def test_hostname_fetched_when_in_template():
    """Test that hostname is fetched when in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {hostname}"
    manager = StatusLineManager(config)

    # Mock socket.gethostname
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-machine"

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # gethostname should have been called
        mock_gethostname.assert_called()

        # Result should contain hostname
        assert "test-machine" in result


def test_username_not_fetched_when_not_in_template():
    """Test that username is not fetched when not in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {messages}"
    manager = StatusLineManager(config)

    # Mock os.getenv
    with patch("os.getenv") as mock_getenv:
        manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # getenv should not have been called for USER or USERNAME
        assert not any(
            call[0][0] in ["USER", "USERNAME"]
            for call in mock_getenv.call_args_list
        )


def test_username_fetched_when_in_template():
    """Test that username is fetched when in the template."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {username}"
    manager = StatusLineManager(config)

    # Mock os.getenv
    with patch("os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda x: "testuser" if x == "USER" else None

        result = manager.format_status_line_from_template(
            tokens=100000,
            messages=25,
        )

        # getenv should have been called for USER
        mock_getenv.assert_any_call("USER")

        # Result should contain username
        assert "testuser" in result


def test_multiple_conditional_fetches():
    """Test that multiple components are conditionally fetched correctly."""
    config = create_mock_config()
    # Template with only tokens and session tokens
    config.statusline_template = "{tokens} - {session_tokens}/{session_tokens_total}"
    manager = StatusLineManager(config)

    # Mock various system calls
    with patch("subprocess.run") as mock_run:
        with patch("socket.gethostname") as mock_gethostname:
            with patch("os.getenv") as mock_getenv:
                with patch("par_cc_usage.statusline_manager.datetime") as mock_datetime:
                    with patch("pathlib.Path.exists") as mock_exists:
                        mock_exists.return_value = True
                        mock_run.return_value = Mock(returncode=0, stdout="150000\n")

                        manager.format_status_line_from_template(
                            tokens=100000,
                            messages=25,
                            session_id="test-session-id",
                        )

                        # Only jq should have been called (for session tokens)
                        assert any(
                            "jq" in str(call[0][0]) if call[0] else False
                            for call in mock_run.call_args_list
                        )

                        # Git should not have been called
                        assert not any(
                            "git" in str(call[0][0]) if call[0] else False
                            for call in mock_run.call_args_list
                        )

                        # System info should not have been fetched
                        mock_gethostname.assert_not_called()
                        mock_datetime.now.assert_not_called()
                        assert not any(
                            call[0][0] in ["USER", "USERNAME"]
                            for call in mock_getenv.call_args_list
                        )


def test_session_progress_bar_conditional_fetch():
    """Test that session progress bar triggers session token fetch."""
    config = create_mock_config()
    config.statusline_template = "{tokens} - {session_tokens_progress_bar}"
    manager = StatusLineManager(config)

    # Mock subprocess.run for jq command
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="50000\n",  # 25% of 200K
        )

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            result = manager.format_status_line_from_template(
                tokens=100000,
                messages=25,
                session_id="test-session-id",
            )

            # jq command should have been called
            assert any(
                "jq" in str(call[0][0]) if call[0] else False
                for call in mock_run.call_args_list
            )

            # Result should contain progress bar
            assert "[" in result
            assert "]" in result
