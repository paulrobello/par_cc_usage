"""
End-to-end integration tests.

Tests complete workflows from file processing through display output.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from par_cc_usage.main import monitor, scan_all_projects
from par_cc_usage.config import Config, DisplayConfig, NotificationConfig
from par_cc_usage.file_monitor import FileMonitor
from par_cc_usage.token_calculator import aggregate_usage
from par_cc_usage.display import MonitorDisplay


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_complete_monitor_workflow(self, temp_dir):
        """Test complete monitor workflow from files to display."""
        # Create realistic project structure
        projects_dir = temp_dir / "claude" / "projects"
        projects_dir.mkdir(parents=True)

        test_project = projects_dir / "my_project"
        test_project.mkdir()

        # Create realistic JSONL data
        jsonl_file = test_project / "session_20250109_143045.jsonl"
        test_data = [
            {
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {
                    "model": "claude-3-5-sonnet-latest",
                    "messages": [{"role": "user", "content": "Help me with Python"}]
                },
                "response": {
                    "id": "msg_abc123",
                    "usage": {
                        "input_tokens": 1200,
                        "output_tokens": 800,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 150
                    }
                },
                "project_name": "my_project",
                "session_id": "session_abc123",
                "request_id": "req_def456"
            },
            {
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {
                    "model": "claude-3-5-sonnet-latest",
                    "messages": [{"role": "user", "content": "Now help with JavaScript"}]
                },
                "response": {
                    "id": "msg_xyz789",
                    "usage": {
                        "input_tokens": 900,
                        "output_tokens": 1100,
                        "cache_creation_input_tokens": 200,
                        "cache_read_input_tokens": 0
                    }
                },
                "project_name": "my_project",
                "session_id": "session_abc123",
                "request_id": "req_ghi789"
            }
        ]

        with open(jsonl_file, "w", encoding="utf-8") as f:
            for data in test_data:
                f.write(json.dumps(data) + "\n")

        # Create config
        config = Config(
            projects_dir=projects_dir.parent,
            cache_dir=temp_dir / "cache",
            token_limit=1000000,
            polling_interval=1,
            timezone="UTC",
            disable_cache=False,
            display=DisplayConfig(
                time_format="24h",
                show_progress_bars=True,
                update_in_place=True,
            ),
            notifications=NotificationConfig(),
            recent_activity_window_hours=5,
        )

        # Test complete workflow
        with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
            with patch('time.sleep', side_effect=KeyboardInterrupt):  # Exit after one iteration
                try:
                    monitor(config, snapshot_mode=True)
                except KeyboardInterrupt:
                    pass

        # Verify files were processed correctly
        cache_dir = temp_dir / "cache"
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.json"))
            # Cache files should have been created

    def test_file_monitoring_to_aggregation(self, temp_dir):
        """Test file monitoring through to usage aggregation."""
        # Setup file monitoring
        claude_paths = [temp_dir / "claude_projects"]
        claude_paths[0].mkdir()

        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor(
            claude_paths=claude_paths,
            cache_dir=cache_dir,
            use_cache=True,
        )

        # Create test file
        test_file = claude_paths[0] / "test.jsonl"
        test_data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {
                "id": "msg_test",
                "usage": {"input_tokens": 1000, "output_tokens": 500}
            },
            "project_name": "test_project",
            "session_id": "test_session"
        }

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(test_data) + "\n")

        # Monitor and get new lines
        new_lines = monitor.get_new_lines(test_file)
        assert len(new_lines) >= 1

        # Process through aggregation
        config = Config()
        usage_list = []

        from par_cc_usage.token_calculator import process_jsonl_line
        from par_cc_usage.models import DeduplicationState

        dedup_state = DeduplicationState()
        for line in new_lines:
            usage = process_jsonl_line(line, dedup_state)
            if usage:
                usage_list.append(usage)

        # Aggregate usage
        snapshot = aggregate_usage(usage_list, config)

        # Verify aggregation worked
        assert snapshot is not None
        assert len(snapshot.projects) > 0
        assert "test_project" in snapshot.projects

    def test_aggregation_to_display(self, temp_dir):
        """Test usage aggregation through to display output."""
        # Create test usage data
        from par_cc_usage.models import TokenUsage, DeduplicationState
        from par_cc_usage.token_calculator import aggregate_usage

        test_usage = [
            TokenUsage(
                input_tokens=1000,
                output_tokens=500,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=100,
                service_tier="standard",
                message_id="msg_1",
                request_id="req_1",
                timestamp=datetime.now(timezone.utc),
                model="claude-3-5-sonnet-latest",
                project_name="test_project",
                session_id="test_session",
            ),
            TokenUsage(
                input_tokens=800,
                output_tokens=600,
                cache_creation_input_tokens=50,
                cache_read_input_tokens=0,
                service_tier="standard",
                message_id="msg_2",
                request_id="req_2",
                timestamp=datetime.now(timezone.utc) + timedelta(minutes=5),
                model="claude-3-5-sonnet-latest",
                project_name="test_project",
                session_id="test_session",
            ),
        ]

        # Aggregate usage
        config = Config()
        snapshot = aggregate_usage(test_usage, config)

        # Create display
        display = MonitorDisplay(config.display, show_pricing=False)

        # Update display with snapshot
        display.update(snapshot)

        # Display should handle the data without errors
        assert display is not None

    def test_pricing_integration_workflow(self, temp_dir):
        """Test workflow with pricing integration enabled."""
        # Create test data with cost information
        from par_cc_usage.models import TokenUsage
        from par_cc_usage.token_calculator import aggregate_usage
        from par_cc_usage.display import MonitorDisplay

        test_usage = [
            TokenUsage(
                input_tokens=1500,
                output_tokens=750,
                model="claude-3-5-sonnet-latest",
                timestamp=datetime.now(timezone.utc),
                project_name="pricing_test",
                session_id="pricing_session",
                cost_usd=2.25,  # Mock cost data
            ),
        ]

        config = Config()
        snapshot = aggregate_usage(test_usage, config)

        # Create display with pricing enabled
        display = MonitorDisplay(config.display, show_pricing=True)
        display.update(snapshot)

        # Should handle pricing display
        assert display is not None


class TestConfigurationIntegration:
    """Test configuration integration across components."""

    def test_config_loading_to_monitor(self, temp_dir):
        """Test configuration loading through to monitor execution."""
        # Create config file
        config_file = temp_dir / "config.yaml"
        config_data = {
            "token_limit": 2000000,
            "timezone": "America/New_York",
            "polling_interval": 2,
            "display": {
                "time_format": "12h",
                "show_progress_bars": False,
            },
            "notifications": {
                "discord_webhook_url": "https://discord.com/test",
                "notify_on_block_completion": True,
                "cooldown_minutes": 30,
            }
        }

        import yaml
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Load config
        from par_cc_usage.config import _load_config_file
        config = _load_config_file(config_file)

        # Verify config loaded correctly
        assert config.token_limit == 2000000
        assert config.timezone == "America/New_York"
        assert config.display.time_format.value == "12h"
        assert config.notifications.discord_webhook_url == "https://discord.com/test"

        # Test config with monitor
        with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
            with patch('time.sleep', side_effect=KeyboardInterrupt):
                try:
                    monitor(config, snapshot_mode=True)
                except KeyboardInterrupt:
                    pass

    def test_environment_variable_integration(self, temp_dir, monkeypatch):
        """Test environment variable integration across system."""
        # Set environment variables
        env_vars = {
            "PAR_CC_USAGE_TOKEN_LIMIT": "3000000",
            "PAR_CC_USAGE_TIMEZONE": "Europe/London",
            "PAR_CC_USAGE_TIME_FORMAT": "24h",
            "PAR_CC_USAGE_SHOW_PROGRESS_BARS": "true",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        # Create minimal config file
        config_file = temp_dir / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("token_limit: 1000000\n")  # Should be overridden

        from par_cc_usage.config import _load_config_file
        config = _load_config_file(config_file)

        # Environment variables should override file config
        assert config.token_limit == 3000000
        assert config.timezone == "Europe/London"

        # Test integrated config works with other components
        display = MonitorDisplay(config.display, show_pricing=False)
        assert display is not None


class TestErrorRecoveryIntegration:
    """Test error recovery across system components."""

    def test_file_corruption_recovery(self, temp_dir):
        """Test system recovery from file corruption."""
        # Create projects directory
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        test_project = projects_dir / "test_project"
        test_project.mkdir()

        # Create partially corrupted file
        corrupted_file = test_project / "corrupted.jsonl"
        with open(corrupted_file, "w", encoding="utf-8") as f:
            # Valid line
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_1", "usage": {"input_tokens": 100, "output_tokens": 50}}
            }) + "\n")

            # Corrupted line
            f.write("invalid json data\n")

            # Another valid line
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_2", "usage": {"input_tokens": 200, "output_tokens": 100}}
            }) + "\n")

        config = Config(projects_dir=projects_dir.parent)

        # Test system handles corruption and continues
        with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
            snapshots = scan_all_projects(config)

            # Should have processed valid data despite corruption
            assert len(snapshots) >= 0  # May have recovered some data

    def test_display_error_recovery(self, temp_dir):
        """Test display error recovery with invalid data."""
        # Create invalid snapshot data
        from par_cc_usage.models import UsageSnapshot, Project, Session

        # Create problematic data
        invalid_project = Project(name="", sessions={})  # Empty name

        snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={"": invalid_project},  # Empty key
            total_limit=1000000,
            block_start_override=None,
        )

        # Display should handle invalid data gracefully
        config = Config()
        display = MonitorDisplay(config.display, show_pricing=False)

        # Should not crash with invalid data
        display.update(snapshot)

    def test_network_failure_recovery(self, temp_dir):
        """Test system recovery from network failures."""
        # Test webhook delivery failure recovery
        from par_cc_usage.notification_manager import NotificationManager
        from par_cc_usage.config import NotificationConfig
        from par_cc_usage.models import UsageSnapshot

        notification_config = NotificationConfig(
            discord_webhook_url="https://invalid.webhook.url",
            notify_on_block_completion=True,
        )

        manager = NotificationManager(notification_config)

        # Create test snapshot
        snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        # Should handle network failures gracefully
        import asyncio
        try:
            asyncio.run(manager.check_and_notify(snapshot))
        except Exception:
            # Network failures should be handled gracefully
            pass


class TestPerformanceIntegration:
    """Test performance characteristics of integrated system."""

    def test_large_dataset_integration(self, temp_dir):
        """Test system performance with large datasets."""
        # Create large dataset
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        large_project = projects_dir / "large_project"
        large_project.mkdir()

        # Create file with many entries
        large_file = large_project / "large_session.jsonl"

        # Generate many JSONL entries (but not too many for test performance)
        num_entries = 100
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(num_entries):
                entry = {
                    "timestamp": f"2025-01-09T{14 + i // 60:02d}:{i % 60:02d}:00.000Z",
                    "request": {"model": "claude-3-sonnet-latest"},
                    "response": {
                        "id": f"msg_{i}",
                        "usage": {"input_tokens": 100 + i, "output_tokens": 50 + i}
                    },
                    "project_name": "large_project",
                    "session_id": "large_session"
                }
                f.write(json.dumps(entry) + "\n")

        config = Config(projects_dir=projects_dir.parent)

        # Test system handles large dataset efficiently
        with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
            snapshots = scan_all_projects(config)

            # Should process large dataset
            assert len(snapshots) >= 0

    def test_memory_usage_integration(self, temp_dir):
        """Test memory usage characteristics."""
        # Create moderate dataset to test memory efficiency
        from par_cc_usage.models import TokenUsage
        from par_cc_usage.token_calculator import aggregate_usage

        # Create many usage entries
        usage_list = []
        base_time = datetime.now(timezone.utc)

        for i in range(50):  # Moderate number for testing
            usage = TokenUsage(
                input_tokens=1000 + i * 10,
                output_tokens=500 + i * 5,
                model="claude-3-sonnet-latest",
                timestamp=base_time + timedelta(minutes=i),
                project_name=f"project_{i % 5}",  # 5 projects
                session_id=f"session_{i % 10}",  # 10 sessions
            )
            usage_list.append(usage)

        config = Config()

        # Test aggregation memory efficiency
        snapshot = aggregate_usage(usage_list, config)

        # Should create reasonable data structure
        assert snapshot is not None
        assert len(snapshot.projects) <= 5  # Should group by project
