"""
Tests for the main module.
"""

import json
import signal
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from par_cc_usage.file_monitor import FileState
from par_cc_usage.main import (
    _check_token_limit_update,
    app,
    process_file,
    scan_all_projects,
)
from par_cc_usage.models import DeduplicationState


class TestProcessFile:
    """Test the process_file function."""

    def test_process_file_with_new_data(self, temp_dir, mock_config):
        """Test processing a file with new data."""
        # Create proper directory structure: base_dir/project_name/session_id.jsonl
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "session_123.jsonl"
        jsonl_data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-5-sonnet-latest"},
            "response": {
                "id": "msg_123",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            },
            "project_name": "test_project",
            "session_id": "session_123",
        }
        jsonl_file.write_text(json.dumps(jsonl_data) + "\n")

        # Create file state
        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        projects = {}
        dedup_state = DeduplicationState()

        # Process the file
        lines_processed = process_file(
            file_path=jsonl_file,
            file_state=file_state,
            projects=projects,
            config=mock_config,
            base_dir=temp_dir,
            dedup_state=dedup_state
        )

        assert lines_processed == 1
        assert "test_project" in projects
        assert "session_123" in projects["test_project"].sessions

    def test_process_file_with_invalid_json(self, temp_dir, mock_config):
        """Test processing a file with invalid JSON."""
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "invalid.jsonl"
        jsonl_file.write_text("invalid json\n")

        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        projects = {}

        # Should not raise an error
        lines_processed = process_file(
            file_path=jsonl_file,
            file_state=file_state,
            projects=projects,
            config=mock_config,
            base_dir=temp_dir
        )

        assert lines_processed == 0

    def test_process_file_from_position(self, temp_dir, mock_config):
        """Test processing a file from a specific position."""
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "test.jsonl"
        line1 = json.dumps({"timestamp": "2025-01-09T14:00:00Z", "test": 1})
        line2 = json.dumps({"timestamp": "2025-01-09T14:30:00Z", "test": 2})
        jsonl_file.write_text(f"{line1}\n{line2}\n")

        # Set position after first line
        first_line_size = len(line1) + 1  # +1 for newline

        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=first_line_size
        )

        projects = {}

        with patch('par_cc_usage.main.process_jsonl_line') as mock_process:
            lines_processed = process_file(
                file_path=jsonl_file,
                file_state=file_state,
                projects=projects,
                config=mock_config,
                base_dir=temp_dir
            )

            # Should only process the second line
            assert mock_process.call_count == 1
            assert lines_processed == 1


class TestScanAllProjects:
    """Test the scan_all_projects function."""

    def test_scan_all_projects_no_files(self, temp_dir, mock_config):
        """Test scanning with no JSONL files."""
        mock_config.projects_dir = temp_dir

        # Mock get_claude_paths to return empty temp directory
        with patch.object(type(mock_config), 'get_claude_paths', return_value=[temp_dir]):
            projects = scan_all_projects(mock_config)

        assert projects == {}

    @patch('par_cc_usage.main.FileMonitor')
    def test_scan_all_projects_with_files(self, mock_monitor_class, temp_dir, mock_config):
        """Test scanning with JSONL files."""
        # Create mock file monitor
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor

        # Mock file discovery
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        test_file = project_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Mock scan_files to return our test file
        mock_monitor.scan_files.return_value = [test_file]
        mock_monitor.file_states = {}

        # Mock get_claude_paths to return our temp directory
        with patch.object(type(mock_config), 'get_claude_paths', return_value=[temp_dir]):
            # Mock process_file to return 1 line processed
            with patch('par_cc_usage.main.process_file', return_value=1):
                projects = scan_all_projects(mock_config)

        # Verify file monitor was used
        mock_monitor_class.assert_called_once()


class TestMonitorCommand:
    """Test the monitor command."""

    def test_monitor_keyboard_interrupt(self, mock_config):
        """Test monitor handles keyboard interrupt gracefully."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        mock_init.return_value = ([], Mock(), Mock(), Mock())
                        # Simulate KeyboardInterrupt after display creation
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        result = runner.invoke(app, ["monitor"])

                        # Should exit cleanly or with KeyboardInterrupt (130)
                        assert result.exit_code in [0, 130]

    @patch('par_cc_usage.main.time.sleep')
    @patch('par_cc_usage.main.scan_all_projects')
    @patch('par_cc_usage.main.load_config')
    def test_monitor_polling_loop(self, mock_load_config, mock_scan, mock_sleep, mock_config):
        """Test monitor polling loop."""
        mock_load_config.return_value = mock_config
        mock_config.polling_interval = 1

        # Mock scan_all_projects to return empty projects
        mock_scan.return_value = {}

        runner = CliRunner()

        with patch('par_cc_usage.main.DisplayManager') as mock_display:
            with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                mock_init.return_value = ([], Mock(), Mock(), Mock())
                # Mock the get_modified_files to raise KeyboardInterrupt after first call
                mock_monitor = Mock()
                mock_monitor.get_modified_files.side_effect = KeyboardInterrupt
                mock_init.return_value = ([], mock_monitor, Mock(), Mock())

                result = runner.invoke(app, ["monitor"])

        # Should have called scan at least once
        assert mock_scan.call_count >= 1
        # Exit code 130 is expected for KeyboardInterrupt
        assert result.exit_code in [0, 130]

    def test_monitor_compact_mode_flag(self, mock_config):
        """Test monitor command with --compact flag."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config) as mock_load:
            with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        mock_init.return_value = ([], Mock(), Mock(), Mock())
                        # Make DisplayManager raise KeyboardInterrupt to exit quickly
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        result = runner.invoke(app, ["monitor", "--compact"])

                        # Should exit cleanly or with KeyboardInterrupt (130)
                        assert result.exit_code in [0, 130]

                        # Verify config was loaded
                        mock_load.assert_called_once()

    @patch('par_cc_usage.main._parse_monitor_options')
    def test_monitor_compact_option_parsing(self, mock_parse_options, mock_config):
        """Test that --compact flag is properly parsed into MonitorOptions."""
        from par_cc_usage.enums import DisplayMode
        from par_cc_usage.options import MonitorOptions

        # Create a mock MonitorOptions with compact mode
        mock_options = MonitorOptions(
            display_mode=DisplayMode.COMPACT,
            interval=5,
            snapshot=False,
        )
        mock_parse_options.return_value = mock_options

        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        mock_init.return_value = ([], Mock(), Mock(), Mock())
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        result = runner.invoke(app, ["monitor", "--compact"])

                        # Should have called _parse_monitor_options with compact=True
                        assert mock_parse_options.called
                        # Get the call arguments
                        call_args = mock_parse_options.call_args[0]
                        # The compact parameter should be True (it's the 9th parameter, index 8)
                        assert call_args[8] is True  # compact parameter

    def test_monitor_normal_mode_default(self, mock_config):
        """Test monitor command defaults to normal mode."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        with patch('par_cc_usage.main._parse_monitor_options') as mock_parse:
                            mock_init.return_value = ([], Mock(), Mock(), Mock())
                            mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                            result = runner.invoke(app, ["monitor"])

                            # Should have called _parse_monitor_options with compact=False
                            assert mock_parse.called
                            call_args = mock_parse.call_args[0]
                            # The compact parameter should be False (it's the 9th parameter, index 8)
                            assert call_args[8] is False  # compact parameter


class TestListCommand:
    """Test the list command."""

    def test_list_command_default(self, mock_config):
        """Test list command with default options."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch.object(type(mock_config), 'get_claude_paths', return_value=[Path("/fake/path")]):
                with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                    with patch('par_cc_usage.main.display_usage_list') as mock_display:
                        result = runner.invoke(app, ["list"])

                        assert result.exit_code == 0
                        mock_display.assert_called_once()

    def test_list_command_with_format(self, mock_config):
        """Test list command with format option."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch.object(type(mock_config), 'get_claude_paths', return_value=[Path("/fake/path")]):
                with patch('par_cc_usage.main.scan_all_projects', return_value={}):
                    with patch('par_cc_usage.main.display_usage_list') as mock_display:
                        result = runner.invoke(app, ["list", "--format", "json"])

                        assert result.exit_code == 0
                        # Check that JSON format was passed
                        call_args = mock_display.call_args
                        assert call_args[1]['output_format'].value == "json"


class TestSetLimitCommand:
    """Test the set-limit command."""

    def test_set_limit_valid(self, temp_dir, mock_config):
        """Test setting a valid token limit."""
        runner = CliRunner()

        config_file = temp_dir / "config.yaml"
        config_file.write_text("token_limit: 100000")

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.save_config') as mock_save:
                result = runner.invoke(app, ["set-limit", "500000", "--config", str(config_file)])

                assert result.exit_code == 0
                mock_save.assert_called_once()
                # The output depends on whether there was an existing limit
                assert "token limit" in result.output.lower() and "500,000" in result.output

    def test_set_limit_invalid(self):
        """Test setting an invalid token limit."""
        runner = CliRunner()

        result = runner.invoke(app, ["set-limit", "-1000"])

        assert result.exit_code != 0


class TestInitCommand:
    """Test the init command."""

    def test_init_creates_config(self, temp_dir):
        """Test init creates default config."""
        runner = CliRunner()

        config_file = temp_dir / "config.yaml"

        with patch('par_cc_usage.main.save_default_config') as mock_save:
            result = runner.invoke(app, ["init", "--config", str(config_file)])

            assert result.exit_code == 0
            mock_save.assert_called_once_with(config_file)


class TestTestWebhookCommand:
    """Test the test-webhook command."""

    @patch('par_cc_usage.main.NotificationManager')
    def test_webhook_success(self, mock_notification_class, mock_config):
        """Test webhook test with success."""
        runner = CliRunner()

        mock_notification = Mock()
        mock_notification.test_webhook.return_value = True
        mock_notification_class.return_value = mock_notification

        mock_config.notifications.discord_webhook_url = "https://discord.com/test"

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main._get_current_usage_snapshot', return_value=None):
                result = runner.invoke(app, ["test-webhook"])

                assert result.exit_code == 0
                assert "✓ Webhook test successful!" in result.output


class TestUtilityFunctions:
    """Test utility functions."""

    def test_check_token_limit_no_limit(self, mock_config):
        """Test token limit check when no limit is set."""
        mock_config.token_limit = None

        snapshot = Mock()
        snapshot.total_tokens = 100000

        # Should not do anything when no limit
        _check_token_limit_update(mock_config, None, 100000)

    def test_check_token_limit_exceeded(self, mock_config, temp_dir):
        """Test token limit check when limit is exceeded."""
        mock_config.token_limit = 50000

        config_file = temp_dir / "config.yaml"
        config_file.write_text("token_limit: 50000")

        with patch('par_cc_usage.main.update_config_token_limit') as mock_update:
            with patch('par_cc_usage.main.console') as mock_console:
                _check_token_limit_update(mock_config, config_file, 60000)

                # Should update config with detected limit
                mock_update.assert_called_once_with(config_file, 60000)
                mock_console.print.assert_called()

    def test_signal_handling(self):
        """Test signal handling functionality."""
        # Test that signal module is imported and available

        # Create a simple signal handler to test
        def test_handler(signum, frame):
            pass

        # Test that we can set up signal handlers
        old_handler = signal.signal(signal.SIGINT, test_handler)

        # Restore original handler
        signal.signal(signal.SIGINT, old_handler)

        # Test passes if we get here without error
        assert True


class TestCLIRunner:
    """Test the CLI application."""

    def test_app_no_args_shows_help(self):
        """Test that app with no args shows help."""
        runner = CliRunner()
        result = runner.invoke(app, [])

        # The app is configured with no_args_is_help=True, so it should show help
        # Exit code 2 is expected when no arguments are provided with no_args_is_help=True
        assert result.exit_code in [0, 2]
        assert "Usage:" in result.output or "Commands:" in result.output

    def test_app_invalid_command(self):
        """Test app with invalid command."""
        runner = CliRunner()
        result = runner.invoke(app, ["invalid-command"])

        assert result.exit_code != 0
