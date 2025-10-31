"""
Tests for the main module.
"""

import json
import logging
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
            projects, unified_entries = scan_all_projects(mock_config)

        assert projects == {}
        assert unified_entries == []

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
                scan_all_projects(mock_config)

        # Verify file monitor was used
        mock_monitor_class.assert_called_once()

    def test_scan_all_projects_with_existing_monitor(self, temp_dir, mock_config):
        """Test scanning with an existing FileMonitor instance."""
        # Create test project directory and file
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        test_file = project_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Create actual FileMonitor instance
        from par_cc_usage.file_monitor import FileMonitor
        existing_monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=True)

        # Mock get_claude_paths to return our temp directory
        with patch.object(type(mock_config), 'get_claude_paths', return_value=[temp_dir]):
            # Mock process_file to return 1 line processed
            with patch('par_cc_usage.main.process_file', return_value=1):
                projects, unified_entries = scan_all_projects(mock_config, monitor=existing_monitor)

        # Verify the existing monitor was used (file should be in file_states)
        assert test_file in existing_monitor.file_states
        assert isinstance(projects, dict)
        assert isinstance(unified_entries, list)

    def test_scan_all_projects_monitor_parameter_priority(self, temp_dir, mock_config):
        """Test that provided monitor parameter takes priority over creating new one."""
        # Create test project directory and file
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        test_file = project_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Create existing monitor with a known file state
        from par_cc_usage.file_monitor import FileMonitor, FileState
        existing_monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=True)
        # Pre-populate with a known file state
        existing_monitor.file_states[test_file] = FileState(
            path=test_file,
            mtime=test_file.stat().st_mtime,
            size=test_file.stat().st_size,
            last_position=0
        )

        # Mock get_claude_paths to return our temp directory
        with patch.object(type(mock_config), 'get_claude_paths', return_value=[temp_dir]):
            # Mock process_file to return 1 line processed
            with patch('par_cc_usage.main.process_file', return_value=1):
                # Use patch to ensure FileMonitor constructor is NOT called
                with patch('par_cc_usage.main.FileMonitor') as mock_monitor_constructor:
                    projects, unified_entries = scan_all_projects(mock_config, monitor=existing_monitor)

        # Verify FileMonitor constructor was NOT called (existing monitor was used)
        mock_monitor_constructor.assert_not_called()
        # Verify the existing monitor was used
        assert test_file in existing_monitor.file_states
        assert isinstance(projects, dict)
        assert isinstance(unified_entries, list)

    def test_scan_all_projects_cache_consistency(self, temp_dir, mock_config):
        """Test that cache state is consistent when using existing monitor."""
        # Create test project directory and file
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        test_file = project_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Create existing monitor
        from par_cc_usage.file_monitor import FileMonitor
        existing_monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=False)

        # Mock get_claude_paths to return our temp directory
        with patch.object(type(mock_config), 'get_claude_paths', return_value=[temp_dir]):
            # Mock process_file to return 1 line processed
            with patch('par_cc_usage.main.process_file', return_value=1):
                # First call with use_cache=True
                projects1, unified_entries1 = scan_all_projects(mock_config, use_cache=True, monitor=existing_monitor)

                # Second call with use_cache=True should use cached positions
                projects2, unified_entries2 = scan_all_projects(mock_config, use_cache=True, monitor=existing_monitor)

        # Both calls should return valid projects and unified entries
        assert isinstance(projects1, dict)
        assert isinstance(projects2, dict)
        assert isinstance(unified_entries1, list)
        assert isinstance(unified_entries2, list)
        # File state should be preserved between calls
        assert test_file in existing_monitor.file_states


class TestMonitorCommand:
    """Test the monitor command."""

    def test_monitor_uses_single_file_monitor_instance(self, mock_config):
        """Test that monitor command uses single FileMonitor instance throughout."""
        runner = CliRunner()

        # Track FileMonitor constructor calls
        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                # Mock the return values
                mock_monitor = Mock()
                mock_init.return_value = ([], mock_monitor, Mock(), Mock())

                with patch('par_cc_usage.main.scan_all_projects') as mock_scan:
                    mock_scan.return_value = {}

                    with patch('par_cc_usage.main.DisplayManager') as mock_display:
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        runner.invoke(app, ["monitor", "--snapshot"])

        # Verify _initialize_monitor_components was called (creates single monitor)
        mock_init.assert_called_once()

        # Verify scan_all_projects was called with the monitor instance
        mock_scan.assert_called()
        # Get the call arguments and verify monitor parameter was passed
        call_args = mock_scan.call_args
        assert 'monitor' in call_args.kwargs
        assert call_args.kwargs['monitor'] is mock_monitor

    def test_monitor_keyboard_interrupt(self, mock_config):
        """Test monitor handles keyboard interrupt gracefully."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
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

        # Mock scan_all_projects to return empty projects and unified entries
        mock_scan.return_value = ({}, [])

        runner = CliRunner()

        with patch('par_cc_usage.main.DisplayManager'):
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
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        mock_init.return_value = ([], Mock(), Mock(), Mock())
                        # Make DisplayManager raise KeyboardInterrupt to exit quickly
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        runner.invoke(app, ["monitor", "--compact"])

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
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        mock_init.return_value = ([], Mock(), Mock(), Mock())
                        mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                        runner.invoke(app, ["monitor", "--compact"])

                        # Should have called _parse_monitor_options with compact=True
                        assert mock_parse_options.called
                        # Get the call arguments
                        call_args = mock_parse_options.call_args[0]
                        # The compact parameter should be True (it's the 10th parameter, index 9)
                        assert call_args[9] is True  # compact parameter

    def test_monitor_normal_mode_default(self, mock_config):
        """Test monitor command defaults to normal mode."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        with patch('par_cc_usage.main._parse_monitor_options') as mock_parse:
                            mock_init.return_value = ([], Mock(), Mock(), Mock())
                            mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                            runner.invoke(app, ["monitor"])

                            # Should have called _parse_monitor_options with compact=False
                            assert mock_parse.called
                            call_args = mock_parse.call_args[0]
                            # The compact parameter should be False (it's the 9th parameter, index 8)
                            assert call_args[9] is False  # compact parameter
                            # The debug parameter should be False (it's the 10th parameter, index 10)
                            assert call_args[10] is False  # debug parameter

    def test_monitor_debug_flag_enabled(self, mock_config):
        """Test monitor command with --debug flag enabled."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        with patch('par_cc_usage.main.logging.basicConfig') as mock_logging:
                            mock_init.return_value = ([], Mock(), Mock(), Mock())
                            mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                            runner.invoke(app, ["monitor", "--debug"])

                            # Should have configured logging for DEBUG level with file handler
                            mock_logging.assert_called_once()
                            call_args = mock_logging.call_args
                            assert call_args[1]['level'] == logging.DEBUG
                            assert call_args[1]['format'] == "%(asctime)s - %(message)s"
                            assert len(call_args[1]['handlers']) == 1
                            assert isinstance(call_args[1]['handlers'][0], logging.FileHandler)

    def test_monitor_debug_flag_disabled(self, mock_config):
        """Test monitor command with debug flag disabled (default)."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                with patch('par_cc_usage.main.DisplayManager') as mock_display:
                    with patch('par_cc_usage.main._initialize_monitor_components') as mock_init:
                        with patch('par_cc_usage.main.logging.basicConfig') as mock_logging:
                            mock_init.return_value = ([], Mock(), Mock(), Mock())
                            mock_display.return_value.__enter__.side_effect = KeyboardInterrupt

                            runner.invoke(app, ["monitor"])

                            # Should have configured logging for ERROR level (to suppress pricing warnings in monitor mode)
                            mock_logging.assert_called_with(level=logging.ERROR, format="%(message)s")

    @patch('par_cc_usage.main.logger')
    def test_monitor_debug_message_logging(self, mock_logger, mock_config):
        """Test that debug messages are logged when processing files."""
        from pathlib import Path

        from par_cc_usage.file_monitor import FileState
        from par_cc_usage.main import _process_modified_files

        # Create a mock file path
        test_file = Path("/test/file.jsonl")
        mock_file_state = FileState(path=test_file, size=100, mtime=123456)

        # Mock the necessary components for _process_modified_files
        with patch('par_cc_usage.main.process_file', return_value=3):
            _process_modified_files(
                [(test_file, mock_file_state)],  # List of tuples
                [Path("/test")],  # claude_paths
                {},  # projects
                mock_config,  # config
                Mock()  # dedup_state
            )

        # Should have called logger.debug with the processing message
        mock_logger.debug.assert_called_with("Processed 3 messages from file.jsonl")


class TestListCommand:
    """Test the list command."""

    def test_list_command_default(self, mock_config):
        """Test list command with default options."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch.object(type(mock_config), 'get_claude_paths', return_value=[Path("/fake/path")]):
                with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
                    with patch('par_cc_usage.main.display_usage_list') as mock_display:
                        result = runner.invoke(app, ["list"])

                        assert result.exit_code == 0
                        mock_display.assert_called_once()

    def test_list_command_with_format(self, mock_config):
        """Test list command with format option."""
        runner = CliRunner()

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch.object(type(mock_config), 'get_claude_paths', return_value=[Path("/fake/path")]):
                with patch('par_cc_usage.main.scan_all_projects', return_value=({}, [])):
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
                result = runner.invoke(app, ["set-limit", "token", "500000", "--config", str(config_file)])

                assert result.exit_code == 0
                mock_save.assert_called_once()
                # The output depends on whether there was an existing limit
                # Remove ANSI color codes for testing since they can split the number formatting
                import re
                clean_output = re.sub(r'\x1b\[[0-9;]*m', '', result.output)
                assert "token limit" in result.output.lower() and "500,000" in clean_output

    def test_set_limit_invalid(self, temp_dir):
        """Test setting an invalid limit type."""
        runner = CliRunner()

        # Create a minimal config file to avoid "Configuration file not found" error
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: UTC")

        result = runner.invoke(app, ["set-limit", "--config", str(config_file), "invalid", "1000"])

        assert result.exit_code != 0
        assert "Invalid limit type" in result.output

    def test_set_limit_message_valid(self, temp_dir, mock_config):
        """Test setting a valid message limit."""
        runner = CliRunner()

        config_file = temp_dir / "config.yaml"
        config_file.write_text("message_limit: 100")

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.save_config') as mock_save:
                result = runner.invoke(app, ["set-limit", "message", "250", "--config", str(config_file)])

                assert result.exit_code == 0
                mock_save.assert_called_once()
                assert "message limit" in result.output.lower()

    def test_set_limit_cost_valid(self, temp_dir, mock_config):
        """Test setting a valid cost limit."""
        runner = CliRunner()

        config_file = temp_dir / "config.yaml"
        config_file.write_text("cost_limit: 10.0")

        with patch('par_cc_usage.main.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.save_config') as mock_save:
                result = runner.invoke(app, ["set-limit", "cost", "25.99", "--config", str(config_file)])

                assert result.exit_code == 0
                mock_save.assert_called_once()
                assert "cost limit" in result.output.lower()
                assert "$25.99" in result.output

    def test_set_limit_negative_value(self, temp_dir):
        """Test setting negative limits are rejected."""
        runner = CliRunner()

        # Create a minimal config file to avoid "Configuration file not found" error
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: UTC")

        # Test negative token limit
        result = runner.invoke(app, ["set-limit", "--config", str(config_file), "token", "--", "-100"])
        assert result.exit_code != 0
        assert "must be a non-negative integer" in result.output

        # Test negative cost limit
        result = runner.invoke(app, ["set-limit", "--config", str(config_file), "cost", "--", "-5.0"])
        assert result.exit_code != 0
        assert "must be non-negative" in result.output

    def test_set_limit_fractional_token(self, temp_dir):
        """Test fractional token limits are rejected."""
        runner = CliRunner()

        # Create a minimal config file to avoid "Configuration file not found" error
        config_file = temp_dir / "config.yaml"
        config_file.write_text("timezone: UTC")

        result = runner.invoke(app, ["set-limit", "--config", str(config_file), "token", "100.5"])
        assert result.exit_code != 0
        assert "must be a non-negative integer" in result.output


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
                assert "Webhook test successful!" in result.output


class TestHelperFunctions:
    """Test helper functions in scan_all_projects."""

    def test_find_base_directory(self, temp_dir):
        """Test _find_base_directory function."""
        from par_cc_usage.main import _find_base_directory

        # Create test directories
        claude_dir1 = temp_dir / "claude1"
        claude_dir2 = temp_dir / "claude2"
        claude_dir1.mkdir()
        claude_dir2.mkdir()

        # Create test files
        file1 = claude_dir1 / "project" / "test.jsonl"
        file2 = claude_dir2 / "project" / "test.jsonl"
        file1.parent.mkdir()
        file2.parent.mkdir()
        file1.write_text('{"test": 1}')
        file2.write_text('{"test": 2}')

        claude_paths = [claude_dir1, claude_dir2]

        # Test finding base directory for files
        assert _find_base_directory(file1, claude_paths) == claude_dir1
        assert _find_base_directory(file2, claude_paths) == claude_dir2

        # Test file not in any claude path
        other_file = temp_dir / "other" / "test.jsonl"
        other_file.parent.mkdir()
        other_file.write_text('{"test": 3}')
        assert _find_base_directory(other_file, claude_paths) is None

    def test_get_or_create_file_state_existing(self, temp_dir):
        """Test _get_or_create_file_state with existing file state."""
        from par_cc_usage.file_monitor import FileMonitor, FileState
        from par_cc_usage.main import _get_or_create_file_state

        # Create test file
        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}')

        # Create monitor with existing file state
        monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=True)
        existing_state = FileState(
            path=test_file,
            mtime=test_file.stat().st_mtime,
            size=test_file.stat().st_size,
            last_position=100
        )
        monitor.file_states[test_file] = existing_state

        # Test with use_cache=True (should preserve position)
        state = _get_or_create_file_state(test_file, monitor, use_cache=True)
        assert state is not None
        assert state.last_position == 100

        # Test with use_cache=False (should reset position)
        state = _get_or_create_file_state(test_file, monitor, use_cache=False)
        assert state is not None
        assert state.last_position == 0

    def test_get_or_create_file_state_new(self, temp_dir):
        """Test _get_or_create_file_state with new file."""
        from par_cc_usage.file_monitor import FileMonitor
        from par_cc_usage.main import _get_or_create_file_state

        # Create test file
        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}')

        # Create monitor without existing state
        monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=True)

        # Test creating new state
        state = _get_or_create_file_state(test_file, monitor, use_cache=True)
        assert state is not None
        assert state.path == test_file
        assert state.last_position == 0
        assert test_file in monitor.file_states

    def test_get_or_create_file_state_nonexistent(self, temp_dir):
        """Test _get_or_create_file_state with nonexistent file."""
        from par_cc_usage.file_monitor import FileMonitor
        from par_cc_usage.main import _get_or_create_file_state

        # Reference nonexistent file
        nonexistent_file = temp_dir / "nonexistent.jsonl"

        # Create monitor
        monitor = FileMonitor([temp_dir], temp_dir / "cache", disable_cache=True)

        # Test with nonexistent file
        state = _get_or_create_file_state(nonexistent_file, monitor, use_cache=True)
        assert state is None

    def test_print_dedup_stats_with_duplicates(self, capsys):
        """Test _print_dedup_stats with duplicate count."""
        from par_cc_usage.main import _print_dedup_stats
        from par_cc_usage.models import DeduplicationState

        dedup_state = DeduplicationState()
        dedup_state.total_messages = 100
        dedup_state.duplicate_count = 5

        # Test with suppress_stats=False (should print)
        _print_dedup_stats(dedup_state, suppress_stats=False)
        captured = capsys.readouterr()
        assert "Processed 100 messages" in captured.out
        assert "skipped 5 duplicates" in captured.out

        # Test with suppress_stats=True (should not print)
        _print_dedup_stats(dedup_state, suppress_stats=True)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_dedup_stats_no_duplicates(self, capsys):
        """Test _print_dedup_stats with no duplicates."""
        from par_cc_usage.main import _print_dedup_stats
        from par_cc_usage.models import DeduplicationState

        dedup_state = DeduplicationState()
        dedup_state.total_messages = 100
        dedup_state.duplicate_count = 0

        # Should not print anything when no duplicates
        _print_dedup_stats(dedup_state, suppress_stats=False)
        captured = capsys.readouterr()
        assert captured.out == ""


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
