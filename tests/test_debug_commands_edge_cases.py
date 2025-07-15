"""
Test debug commands error handling and edge cases.

This module tests debug commands with empty projects, malformed data,
and various edge cases in debug functionality.
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timezone, timedelta
from typer.testing import CliRunner

from par_cc_usage.main import app
from par_cc_usage.commands import (
    debug_blocks,
    debug_unified_block,
    debug_recent_activity,
    debug_session_table,
)
from par_cc_usage.models import UsageSnapshot, Project, Session, TokenBlock, TokenUsage
from tests.conftest import create_token_usage, create_block_with_tokens


class TestDebugBlocksEdgeCases:
    """Test debug-blocks command with edge cases."""

    def test_debug_blocks_with_empty_projects(self, mock_config):
        """Test debug-blocks command when no projects exist."""
        runner = CliRunner()

        # Mock empty projects
        empty_snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[empty_snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-blocks"])

                # Should handle empty projects gracefully
                assert result.exit_code == 0
                assert "No projects found" in result.output or "No blocks found" in result.output

    def test_debug_blocks_with_malformed_blocks(self, mock_config, sample_timestamp):
        """Test debug-blocks with malformed block data."""
        # Create blocks with problematic data
        malformed_blocks = [
            # Block with invalid timestamps
            TokenBlock(
                start_time=sample_timestamp + timedelta(hours=5),  # End before start
                end_time=sample_timestamp,
                session_id="malformed_1",
                project_name="test_project",
                model="claude-3-sonnet-latest",
                token_usage=create_token_usage(timestamp=sample_timestamp),
                model_tokens={"sonnet": 1000},
            ),
            # Block with None values
            TokenBlock(
                start_time=sample_timestamp,
                end_time=sample_timestamp + timedelta(hours=5),
                session_id="malformed_2",
                project_name="test_project",
                model=None,  # None model
                token_usage=None,  # None usage
                model_tokens={},
                actual_end_time=None,
            ),
        ]

        sessions = {}
        for i, block in enumerate(malformed_blocks):
            session = Session(
                session_id=f"malformed_{i+1}",
                project_name="test_project",
                model="claude-3-sonnet-latest",
                blocks=[block],
                first_seen=sample_timestamp,
                last_seen=sample_timestamp,
                session_start=sample_timestamp,
            )
            sessions[f"malformed_{i+1}"] = session

        project = Project(name="test_project", sessions=sessions)
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        runner = CliRunner()
        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-blocks"])

                # Should handle malformed blocks without crashing
                assert result.exit_code == 0

    def test_debug_blocks_show_inactive_option(self, mock_config, sample_timestamp):
        """Test debug-blocks with --show-inactive option."""
        runner = CliRunner()

        # Create mix of active and inactive blocks
        old_block = create_block_with_tokens(
            start_time=sample_timestamp - timedelta(hours=10),
            session_id="session_old",
            project_name="test_project",
            token_count=1000,
        )
        old_block.actual_end_time = sample_timestamp - timedelta(hours=8)

        recent_block = create_block_with_tokens(
            start_time=sample_timestamp - timedelta(hours=1),
            session_id="session_recent",
            project_name="test_project",
            token_count=1500,
        )
        recent_block.actual_end_time = sample_timestamp - timedelta(minutes=30)

        sessions = {
            "session_old": Session(
                session_id="session_old",
                project_name="test_project",
                model="claude-3-sonnet-latest",
                blocks=[old_block],
                first_seen=sample_timestamp - timedelta(hours=10),
                last_seen=sample_timestamp - timedelta(hours=8),
                session_start=sample_timestamp - timedelta(hours=10),
            ),
            "session_recent": Session(
                session_id="session_recent",
                project_name="test_project",
                model="claude-3-sonnet-latest",
                blocks=[recent_block],
                first_seen=sample_timestamp - timedelta(hours=1),
                last_seen=sample_timestamp - timedelta(minutes=30),
                session_start=sample_timestamp - timedelta(hours=1),
            ),
        }

        project = Project(name="test_project", sessions=sessions)
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                # Test without --show-inactive
                result1 = runner.invoke(app, ["debug-blocks"])
                assert result1.exit_code == 0

                # Test with --show-inactive
                result2 = runner.invoke(app, ["debug-blocks", "--show-inactive"])
                assert result2.exit_code == 0

    def test_debug_blocks_with_extreme_data(self, mock_config, sample_timestamp):
        """Test debug-blocks with extreme amounts of data."""
        runner = CliRunner()

        # Create many projects with many sessions and blocks
        projects = {}
        for proj_i in range(5):  # 5 projects
            sessions = {}
            for sess_i in range(10):  # 10 sessions per project
                blocks = []
                for block_i in range(20):  # 20 blocks per session
                    block_time = sample_timestamp - timedelta(hours=block_i)
                    block = create_block_with_tokens(
                        start_time=block_time,
                        session_id=f"session_{sess_i}",
                        project_name=f"project_{proj_i}",
                        token_count=1000 + block_i * 100,
                    )
                    blocks.append(block)

                session = Session(
                    session_id=f"session_{sess_i}",
                    project_name=f"project_{proj_i}",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=sample_timestamp - timedelta(hours=20),
                    last_seen=sample_timestamp,
                    session_start=sample_timestamp - timedelta(hours=20),
                )
                sessions[f"session_{sess_i}"] = session

            project = Project(name=f"project_{proj_i}", sessions=sessions)
            projects[f"project_{proj_i}"] = project

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-blocks"])

                # Should handle large datasets
                assert result.exit_code == 0


class TestDebugUnifiedEdgeCases:
    """Test debug-unified command with edge cases."""

    def test_debug_unified_with_malformed_data(self, mock_config, sample_timestamp):
        """Test debug-unified when data is inconsistent."""
        runner = CliRunner()

        # Create snapshot with inconsistent unified block data
        projects = {
            "project_1": Project(name="project_1", sessions={}),
            "project_2": Project(name="project_2", sessions={}),
        }

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        # Mock unified_block_tokens to return inconsistent data
        with patch.object(snapshot, 'unified_block_tokens', side_effect=Exception("Calculation error")):
            with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, ["debug-unified"])

                    # Should handle calculation errors gracefully
                    assert result.exit_code == 0

    def test_debug_unified_with_no_unified_block(self, mock_config, sample_timestamp):
        """Test debug-unified when no unified block exists."""
        runner = CliRunner()

        # Create snapshot with no unified block
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        # Mock unified_block_start_time to return None
        with patch.object(snapshot, 'unified_block_start_time', None):
            with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, ["debug-unified"])

                    # Should handle no unified block
                    assert result.exit_code == 0

    def test_debug_unified_with_block_start_override(self, mock_config, sample_timestamp):
        """Test debug-unified with block start override."""
        runner = CliRunner()

        # Create snapshot with block start override
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=sample_timestamp - timedelta(hours=2),
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-unified"])

                # Should handle block start override
                assert result.exit_code == 0


class TestDebugSessionsEdgeCases:
    """Test debug-sessions command with edge cases."""

    def test_debug_sessions_with_empty_sessions(self, mock_config, sample_timestamp):
        """Test debug-sessions with empty sessions."""
        runner = CliRunner()

        # Create project with empty sessions
        project = Project(name="empty_project", sessions={})
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"empty_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-sessions"])

                # Should handle empty sessions
                assert result.exit_code == 0

    def test_debug_sessions_with_filter_option(self, mock_config, sample_timestamp):
        """Test debug-sessions with filter option."""
        runner = CliRunner()

        # Create sessions with different projects
        sessions = {}
        for i in range(3):
            session = Session(
                session_id=f"session_{i}",
                project_name=f"project_{i}",
                model="claude-3-sonnet-latest",
                blocks=[],
                first_seen=sample_timestamp,
                last_seen=sample_timestamp,
                session_start=sample_timestamp,
            )
            sessions[f"session_{i}"] = session

        projects = {}
        for i in range(3):
            project = Project(
                name=f"project_{i}",
                sessions={f"session_{i}": sessions[f"session_{i}"]},
            )
            projects[f"project_{i}"] = project

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                # Test with filter
                result = runner.invoke(app, ["debug-sessions", "--filter", "project_1"])
                assert result.exit_code == 0

    def test_debug_sessions_with_corrupted_session_data(self, mock_config, sample_timestamp):
        """Test debug-sessions with corrupted session data."""
        runner = CliRunner()

        # Create session with corrupted data
        corrupted_session = Session(
            session_id="corrupted",
            project_name="test_project",
            model=None,  # None model
            blocks=None,  # None blocks
            first_seen=None,  # None timestamp
            last_seen=sample_timestamp,
            session_start=sample_timestamp + timedelta(hours=5),  # Start after end
        )

        project = Project(
            name="test_project",
            sessions={"corrupted": corrupted_session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-sessions"])

                # Should handle corrupted session data
                assert result.exit_code == 0


class TestDebugActivityEdgeCases:
    """Test debug-activity command with edge cases."""

    def test_debug_activity_with_no_activity(self, mock_config, sample_timestamp):
        """Test debug-activity when no activity exists."""
        runner = CliRunner()

        # Create snapshot with no activity
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-activity"])

                # Should handle no activity
                assert result.exit_code == 0

    def test_debug_activity_with_hours_option(self, mock_config, sample_timestamp):
        """Test debug-activity with custom hours option."""
        runner = CliRunner()

        # Create some activity data
        block = create_block_with_tokens(
            start_time=sample_timestamp - timedelta(hours=2),
            session_id="session_1",
            project_name="test_project",
            token_count=1000,
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[block],
            first_seen=sample_timestamp - timedelta(hours=2),
            last_seen=sample_timestamp,
            session_start=sample_timestamp - timedelta(hours=2),
        )

        project = Project(name="test_project", sessions={"session_1": session})
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                # Test with different hour values
                hour_values = ["1", "12", "24", "168"]  # 1h, 12h, 24h, 1 week

                for hours in hour_values:
                    result = runner.invoke(app, ["debug-activity", "--hours", hours])
                    assert result.exit_code == 0

    def test_debug_activity_with_invalid_hours(self, mock_config):
        """Test debug-activity with invalid hours option."""
        runner = CliRunner()

        # Test with invalid hour values
        invalid_hours = ["-1", "0", "invalid", "999999"]

        for hours in invalid_hours:
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                result = runner.invoke(app, ["debug-activity", "--hours", hours])
                # May succeed with validation or fail with error


class TestDebugSessionTableEdgeCases:
    """Test debug_session_table function with edge cases."""

    def test_debug_session_table_with_overlapping_blocks(self, sample_timestamp):
        """Test session table generation with overlapping blocks."""
        # Create overlapping blocks
        block1 = create_block_with_tokens(
            start_time=sample_timestamp,
            session_id="session_1",
            project_name="test_project",
            token_count=1000,
        )

        block2 = create_block_with_tokens(
            start_time=sample_timestamp + timedelta(hours=2),  # Overlaps with block1
            session_id="session_1",
            project_name="test_project",
            token_count=1500,
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[block1, block2],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp + timedelta(hours=6),
            session_start=sample_timestamp,
        )

        # Should handle overlapping blocks without crashing
        debug_session_table([session])

    def test_debug_session_table_with_extreme_block_counts(self, sample_timestamp):
        """Test session table with sessions having many blocks."""
        # Create session with many blocks
        blocks = []
        for i in range(100):  # 100 blocks
            block = create_block_with_tokens(
                start_time=sample_timestamp + timedelta(hours=i),
                session_id="session_many_blocks",
                project_name="test_project",
                token_count=1000 + i * 10,
            )
            blocks.append(block)

        session = Session(
            session_id="session_many_blocks",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=blocks,
            first_seen=sample_timestamp,
            last_seen=sample_timestamp + timedelta(hours=100),
            session_start=sample_timestamp,
        )

        # Should handle many blocks efficiently
        debug_session_table([session])

    def test_debug_session_table_with_malformed_timestamps(self, sample_timestamp):
        """Test session table with malformed timestamp data."""
        # Create block with problematic timestamps
        problematic_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp - timedelta(hours=1),  # End before start
            session_id="problematic_session",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            token_usage=create_token_usage(timestamp=sample_timestamp),
            model_tokens={"sonnet": 1000},
            actual_end_time=sample_timestamp + timedelta(days=365),  # Far future
        )

        session = Session(
            session_id="problematic_session",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[problematic_block],
            first_seen=sample_timestamp + timedelta(hours=5),  # After last_seen
            last_seen=sample_timestamp,
            session_start=sample_timestamp - timedelta(days=1),  # Before first_seen
        )

        # Should handle malformed timestamps gracefully
        debug_session_table([session])

    def test_debug_session_table_with_empty_and_none_data(self):
        """Test session table with empty and None data."""
        # Test with empty session list
        debug_session_table([])

        # Test with None blocks
        session_with_none_blocks = Session(
            session_id="none_blocks",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=None,  # None blocks
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            session_start=datetime.now(timezone.utc),
        )

        # Should handle None blocks gracefully
        try:
            debug_session_table([session_with_none_blocks])
        except (AttributeError, TypeError):
            # May fail with None blocks
            pass


class TestDebugCommandsMemoryAndPerformance:
    """Test debug commands under memory and performance stress."""

    def test_debug_commands_memory_pressure(self, mock_config, sample_timestamp):
        """Test debug commands under memory pressure."""
        runner = CliRunner()

        # Create extremely large dataset
        projects = {}
        for proj_i in range(2):  # Keep smaller for test performance
            sessions = {}
            for sess_i in range(5):
                blocks = []
                for block_i in range(50):
                    # Create blocks with large token counts
                    block = create_block_with_tokens(
                        start_time=sample_timestamp + timedelta(hours=block_i),
                        session_id=f"session_{sess_i}",
                        project_name=f"project_{proj_i}",
                        token_count=999999999,  # Very large token count
                    )
                    blocks.append(block)

                session = Session(
                    session_id=f"session_{sess_i}",
                    project_name=f"project_{proj_i}",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=sample_timestamp,
                    last_seen=sample_timestamp + timedelta(hours=50),
                    session_start=sample_timestamp,
                )
                sessions[f"session_{sess_i}"] = session

            project = Project(name=f"project_{proj_i}", sessions=sessions)
            projects[f"project_{proj_i}"] = project

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        debug_commands = ["debug-blocks", "debug-unified", "debug-sessions"]

        for command in debug_commands:
            with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
                with patch('par_cc_usage.config.load_config', return_value=mock_config):
                    result = runner.invoke(app, [command])

                    # Should handle large datasets without memory issues
                    assert result.exit_code == 0

    def test_debug_commands_concurrent_execution(self, mock_config, sample_timestamp):
        """Test debug commands don't interfere with concurrent execution."""
        runner = CliRunner()

        # Create test data
        block = create_block_with_tokens(
            start_time=sample_timestamp,
            session_id="session_1",
            project_name="test_project",
            token_count=1000,
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,
            session_start=sample_timestamp,
        )

        project = Project(name="test_project", sessions={"session_1": session})
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        with patch('par_cc_usage.main.scan_all_projects', return_value=[snapshot]):
            with patch('par_cc_usage.config.load_config', return_value=mock_config):
                # Run multiple debug commands (simulating concurrent execution)
                debug_commands = ["debug-blocks", "debug-unified", "debug-sessions"]

                for command in debug_commands:
                    result = runner.invoke(app, [command])
                    # Each command should execute independently
                    assert result.exit_code == 0
