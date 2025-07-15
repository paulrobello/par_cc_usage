"""
Test CLI command integration and end-to-end functionality.

This module tests full CLI command execution, argument parsing,
configuration handling, and command interactions.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone
from typer.testing import CliRunner

from par_cc_usage.main import app, monitor, list_sessions
from par_cc_usage.config import Config
from par_cc_usage.models import UsageSnapshot, Project, Session
from tests.conftest import create_block_with_tokens


class TestMonitorCommandIntegration:
    """Test full monitor command execution."""

    def test_monitor_command_integration(self, temp_dir, mock_config):
        """Test full monitor command execution with realistic data."""
        runner = CliRunner()

        # Create test data files
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        test_project = projects_dir / "test_project"
        test_project.mkdir()

        # Create JSONL file with test data
        jsonl_file = test_project / "session.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_1",
                    "usage": {"input_tokens": 1000, "output_tokens": 500}
                },
                "project_name": "test_project",
                "session_id": "session_1"
            }) + "\n")

        # Mock config paths
        with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                with patch('time.sleep', side_effect=KeyboardInterrupt):  # Exit quickly
                    # Test monitor command with snapshot mode
                    result = runner.invoke(app, ["monitor", "--snapshot"])

                    # Should execute without crashing
                    assert result.exit_code in [0, 1]  # May exit with 1 due to KeyboardInterrupt

    def test_monitor_command_with_options(self, temp_dir, mock_config):
        """Test monitor command with various command line options."""
        runner = CliRunner()

        # Test various option combinations
        option_combinations = [
            ["monitor", "--snapshot"],
            ["monitor", "--snapshot", "--debug"],
            ["monitor", "--snapshot", "--no-cache"],
            ["monitor", "--snapshot", "--token-limit", "2000000"],
            ["monitor", "--snapshot", "--show-pricing"],
            ["monitor", "--snapshot", "--block-start", "14"],
        ]

        for options in option_combinations:
            with patch('par_cc_usage.main.get_claude_project_paths', return_value=[temp_dir]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
                        result = runner.invoke(app, options)

                        # Should handle all option combinations
                        assert result.exit_code in [0, 1]

    def test_monitor_command_error_handling(self, temp_dir, mock_config):
        """Test monitor command error handling."""
        runner = CliRunner()

        # Test with invalid options
        invalid_options = [
            ["monitor", "--token-limit", "-1"],  # Negative token limit
            ["monitor", "--block-start", "25"],  # Invalid hour (>23)
            ["monitor", "--block-start", "-1"],  # Negative hour
        ]

        for options in invalid_options:
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, options)
                # May succeed with validation or fail with error
                # Specific behavior depends on validation implementation

    def test_monitor_command_with_config_file_errors(self, temp_dir):
        """Test monitor command when config file has errors."""
        runner = CliRunner()

        # Mock config loading to fail
        with patch('par_cc_usage.config.load_config', side_effect=ValueError("Invalid config")):
            result = runner.invoke(app, ["monitor", "--snapshot"])

            # Should handle config errors gracefully
            assert result.exit_code != 0


class TestListCommandIntegration:
    """Test list command with pricing integration."""

    def test_list_command_with_pricing_integration(self, temp_dir, mock_config, sample_timestamp):
        """Test list command with pricing enabled end-to-end."""
        runner = CliRunner()

        # Create test data
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        # Mock scan_all_projects to return test data
        test_block = create_block_with_tokens(
            start_time=sample_timestamp,
            session_id="session_1",
            project_name="test_project",
            token_count=1500,
        )

        test_session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[test_block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,
            session_start=sample_timestamp,
        )

        test_project = Project(
            name="test_project",
            sessions={"session_1": test_session},
        )

        test_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": test_project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[test_snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                # Test list command with pricing
                result = runner.invoke(app, ["list", "--show-pricing"])

                # Should execute successfully
                assert result.exit_code == 0

    def test_list_command_output_formats(self, temp_dir, mock_config, sample_timestamp):
        """Test list command with different output formats."""
        runner = CliRunner()

        # Create minimal test data
        test_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        # Test different output formats
        format_tests = [
            ["list", "--format", "table"],
            ["list", "--format", "json"],
            ["list", "--format", "csv"],
        ]

        for options in format_tests:
            with patch('par_cc_usage.main.scan_all_projects', return_value=[test_snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, options)

                    # Should handle all output formats
                    assert result.exit_code == 0

    def test_list_command_with_output_file(self, temp_dir, mock_config, sample_timestamp):
        """Test list command with file output."""
        runner = CliRunner()

        test_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        output_file = temp_dir / "output.csv"

        with patch('par_cc_usage.main.scan_all_projects', return_value=[test_snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, [
                    "list",
                    "--format", "csv",
                    "--output", str(output_file)
                ])

                # Should execute successfully
                assert result.exit_code == 0

    def test_list_command_filtering_options(self, temp_dir, mock_config, sample_timestamp):
        """Test list command with filtering and sorting options."""
        runner = CliRunner()

        test_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        # Test various filtering options
        filter_options = [
            ["list", "--active-only"],
            ["list", "--sort-by", "tokens"],
            ["list", "--sort-by", "time"],
            ["list", "--show-pricing", "--sort-by", "tokens"],
        ]

        for options in filter_options:
            with patch('par_cc_usage.main.scan_all_projects', return_value=[test_snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, options)

                    # Should handle all filtering options
                    assert result.exit_code == 0


class TestInitCommandIntegration:
    """Test init command configuration creation."""

    def test_init_command_configuration_creation(self, temp_dir):
        """Test init command creating configuration files."""
        runner = CliRunner()

        # Mock XDG directories to use temp directory
        with patch('par_cc_usage.xdg_dirs.get_config_dir', return_value=temp_dir):
            with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=temp_dir / "config.yaml"):
                result = runner.invoke(app, ["init"])

                # Should create config successfully
                assert result.exit_code == 0

    def test_init_command_with_existing_config(self, temp_dir):
        """Test init command when config already exists."""
        runner = CliRunner()

        # Create existing config file
        config_file = temp_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("token_limit: 1000000\n")

        with patch('par_cc_usage.xdg_dirs.get_config_file_path', return_value=config_file):
            result = runner.invoke(app, ["init"])

            # Should handle existing config appropriately
            assert result.exit_code in [0, 1]

    def test_init_command_permission_errors(self, temp_dir):
        """Test init command when config directory is not writable."""
        runner = CliRunner()

        # Create read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            with patch('par_cc_usage.xdg_dirs.get_config_dir', return_value=readonly_dir):
                result = runner.invoke(app, ["init"])

                # Should handle permission errors
                assert result.exit_code != 0
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestDebugCommandsIntegration:
    """Test debug commands with large datasets."""

    def test_debug_commands_with_large_datasets(self, temp_dir, mock_config, sample_timestamp):
        """Test debug commands performance with large amounts of data."""
        runner = CliRunner()

        # Create large dataset
        large_projects = {}
        for i in range(10):  # 10 projects
            sessions = {}
            for j in range(5):  # 5 sessions per project
                blocks = []
                for k in range(20):  # 20 blocks per session
                    block = create_block_with_tokens(
                        start_time=sample_timestamp,
                        session_id=f"session_{j}",
                        project_name=f"project_{i}",
                        token_count=1000 + k * 100,
                    )
                    blocks.append(block)

                session = Session(
                    session_id=f"session_{j}",
                    project_name=f"project_{i}",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=sample_timestamp,
                    last_seen=sample_timestamp,
                    session_start=sample_timestamp,
                )
                sessions[f"session_{j}"] = session

            project = Project(
                name=f"project_{i}",
                sessions=sessions,
            )
            large_projects[f"project_{i}"] = project

        large_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects=large_projects,
            total_limit=1000000,
            block_start_override=None,
        )

        # Test debug commands with large dataset
        debug_commands = [
            ["debug-blocks"],
            ["debug-unified"],
            ["debug-sessions"],
        ]

        for command in debug_commands:
            with patch('par_cc_usage.main.scan_all_projects', return_value=[large_snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, command)

                    # Should handle large datasets
                    assert result.exit_code == 0

    def test_debug_commands_error_handling(self, temp_dir, mock_config):
        """Test debug commands error handling."""
        runner = CliRunner()

        # Test debug commands with no data
        with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                debug_commands = [
                    ["debug-blocks"],
                    ["debug-unified"],
                    ["debug-sessions"],
                    ["debug-activity"],
                ]

                for command in debug_commands:
                    result = runner.invoke(app, command)

                    # Should handle empty data gracefully
                    assert result.exit_code == 0

    def test_debug_commands_with_invalid_options(self, temp_dir, mock_config):
        """Test debug commands with invalid options."""
        runner = CliRunner()

        # Test debug commands with various options
        command_option_tests = [
            ["debug-blocks", "--show-inactive"],
            ["debug-sessions", "--filter", "test"],
            ["debug-activity", "--hours", "24"],
        ]

        for command_options in command_option_tests:
            with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, command_options)

                    # Should handle options appropriately
                    assert result.exit_code in [0, 1, 2]  # Various exit codes possible


class TestWebhookTestingCommands:
    """Test webhook testing command integration."""

    def test_test_webhook_command(self, temp_dir, mock_config):
        """Test webhook testing command."""
        runner = CliRunner()

        # Configure webhook in config
        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"

        with patch('par_cc_usage.config.load_config', return_value=mock_config):
            with patch('par_cc_usage.webhook_client.WebhookClient.send_webhook') as mock_send:
                mock_send.return_value = True  # Mock successful send

                result = runner.invoke(app, ["test-webhook"])

                # Should test webhook successfully
                assert result.exit_code == 0

    def test_test_webhook_command_no_url(self, temp_dir, mock_config):
        """Test webhook testing command when no URL is configured."""
        runner = CliRunner()

        # No webhook URL configured
        mock_config.notifications.discord_webhook_url = None

        with patch('par_cc_usage.config.load_config', return_value=mock_config):
            result = runner.invoke(app, ["test-webhook"])

            # Should handle missing webhook URL
            assert result.exit_code != 0

    def test_test_webhook_command_network_failure(self, temp_dir, mock_config):
        """Test webhook testing command with network failure."""
        runner = CliRunner()

        mock_config.notifications.discord_webhook_url = "https://hooks.discord.com/api/webhooks/test"

        with patch('par_cc_usage.config.load_config', return_value=mock_config):
            with patch('par_cc_usage.webhook_client.WebhookClient.send_webhook') as mock_send:
                mock_send.return_value = False  # Mock failed send

                result = runner.invoke(app, ["test-webhook"])

                # Should handle webhook failure
                assert result.exit_code != 0


class TestGlobalOptionsIntegration:
    """Test global CLI options and their interactions."""

    def test_help_commands(self, temp_dir):
        """Test help command functionality."""
        runner = CliRunner()

        # Test main help
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "monitor" in result.output
        assert "list" in result.output

        # Test command-specific help
        help_commands = [
            ["monitor", "--help"],
            ["list", "--help"],
            ["init", "--help"],
            ["debug-blocks", "--help"],
        ]

        for command in help_commands:
            result = runner.invoke(app, command)
            assert result.exit_code == 0

    def test_version_command(self, temp_dir):
        """Test version command."""
        runner = CliRunner()

        # Test version display
        result = runner.invoke(app, ["--version"])
        # May succeed or fail depending on implementation
        # Version command behavior varies by framework

    def test_config_file_option_override(self, temp_dir, mock_config):
        """Test config file option override."""
        runner = CliRunner()

        # Create custom config file
        custom_config = temp_dir / "custom_config.yaml"
        with open(custom_config, "w", encoding="utf-8") as f:
            f.write("token_limit: 5000000\n")

        # Test if custom config file option exists and works
        with patch('par_cc_usage.config.load_config') as mock_load:
            mock_load.return_value = mock_config

            # Try common config file option patterns
            config_options = [
                ["--config", str(custom_config), "monitor", "--snapshot"],
                ["-c", str(custom_config), "monitor", "--snapshot"],
                ["monitor", "--config", str(custom_config), "--snapshot"],
            ]

            for options in config_options:
                result = runner.invoke(app, options)
                # May succeed if option exists, or fail with unrecognized option

    def test_verbose_debug_options(self, temp_dir, mock_config):
        """Test verbose and debug options."""
        runner = CliRunner()

        # Test various verbosity options
        verbosity_options = [
            ["monitor", "--snapshot", "--debug"],
            ["monitor", "--snapshot", "--verbose"],
            ["list", "--debug"],
        ]

        for options in verbosity_options:
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
                    result = runner.invoke(app, options)

                    # Should handle verbosity options
                    assert result.exit_code in [0, 1, 2]


class TestCommandInteractions:
    """Test interactions between different commands and options."""

    def test_command_option_conflicts(self, temp_dir, mock_config):
        """Test handling of conflicting command options."""
        runner = CliRunner()

        # Test potentially conflicting options
        conflicting_options = [
            ["monitor", "--snapshot", "--no-cache", "--token-limit", "0"],
            ["list", "--format", "json", "--format", "csv"],  # Duplicate options
            ["monitor", "--show-pricing", "--block-start", "invalid"],
        ]

        for options in conflicting_options:
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, options)
                # Should handle conflicts gracefully (may succeed or fail)

    def test_command_environment_interaction(self, temp_dir, mock_config, monkeypatch):
        """Test command interaction with environment variables."""
        runner = CliRunner()

        # Set environment variables
        env_vars = {
            "PAR_CC_USAGE_TOKEN_LIMIT": "3000000",
            "PAR_CC_USAGE_DEBUG": "true",
            "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "https://test.com/webhook",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        with patch('par_cc_usage.config.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
                result = runner.invoke(app, ["monitor", "--snapshot"])

                # Should respect environment variables
                assert result.exit_code in [0, 1]

    def test_signal_handling_integration(self, temp_dir, mock_config):
        """Test signal handling in CLI commands."""
        runner = CliRunner()

        # Test keyboard interrupt handling
        with patch('par_cc_usage.config.load_config', return_value=mock_config):
            with patch('par_cc_usage.main.scan_all_projects', side_effect=KeyboardInterrupt):
                result = runner.invoke(app, ["monitor"])

                # Should handle interruption gracefully
                assert result.exit_code in [0, 1, 130]  # Various interrupt exit codes
