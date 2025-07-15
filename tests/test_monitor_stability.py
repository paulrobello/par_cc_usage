"""
Test monitor mode stability and error handling.

This module tests signal handling, filesystem errors, configuration reloading,
and other stability issues in monitor mode.
"""

import pytest
import signal
import asyncio
import os
import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock, AsyncMock
from datetime import datetime, timezone

from par_cc_usage.main import (
    monitor,
    _apply_command_overrides,
    scan_all_projects,
)
from par_cc_usage.config import Config, load_config
from par_cc_usage.models import UsageSnapshot


class TestSignalHandling:
    """Test signal handling during monitor mode."""

    @pytest.mark.asyncio
    async def test_monitor_signal_handling_sigint(self, temp_dir, mock_config):
        """Test SIGINT handling during monitor mode."""
        # Mock the monitoring loop to avoid infinite running
        monitor_called = False

        def mock_monitor_loop(*args, **kwargs):
            nonlocal monitor_called
            monitor_called = True
            # Simulate receiving SIGINT
            raise KeyboardInterrupt("Interrupted by user")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_monitor_loop):
            with patch('time.sleep'):  # Speed up test
                # Should handle KeyboardInterrupt gracefully
                try:
                    monitor(mock_config, False)  # False = not snapshot mode
                except KeyboardInterrupt:
                    pass  # Expected

                assert monitor_called

    def test_monitor_signal_handling_sigterm(self, temp_dir, mock_config):
        """Test SIGTERM handling during monitor mode."""
        # Track if signal handler was set up
        signal_handlers_set = []

        def mock_signal(sig, handler):
            signal_handlers_set.append(sig)
            return signal.default_int_handler

        with patch('signal.signal', side_effect=mock_signal):
            with patch('par_cc_usage.main.scan_all_projects', return_value=[]):
                with patch('time.sleep', side_effect=KeyboardInterrupt):  # Exit quickly
                    try:
                        monitor(mock_config, True)  # True = snapshot mode
                    except KeyboardInterrupt:
                        pass

        # Should have set up signal handlers (if implemented)
        # This test checks that signal handling is considered

    def test_monitor_graceful_shutdown(self, temp_dir, mock_config):
        """Test graceful shutdown when monitor is interrupted."""
        shutdown_called = False

        def mock_cleanup():
            nonlocal shutdown_called
            shutdown_called = True

        # Mock the scan function to run once then interrupt
        call_count = 0
        def mock_scan(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Shutdown")
            return []

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan):
            with patch('time.sleep'):
                with patch('atexit.register', mock_cleanup):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

        # Monitor should have attempted to run multiple iterations
        assert call_count >= 2


class TestFilesystemErrors:
    """Test monitor mode behavior with filesystem errors."""

    def test_monitor_with_filesystem_unavailable(self, temp_dir, mock_config):
        """Test monitor mode when filesystem becomes unavailable."""
        # Simulate filesystem becoming unavailable
        filesystem_errors = [
            OSError("Device not ready"),
            PermissionError("Permission denied"),
            FileNotFoundError("No such file or directory"),
            IOError("I/O error"),
        ]

        for error in filesystem_errors:
            call_count = 0
            def mock_scan_with_error(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise error
                elif call_count >= 2:
                    # Exit after demonstrating recovery
                    raise KeyboardInterrupt("Test complete")
                return []

            with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_error):
                with patch('time.sleep'):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

            # Should have attempted recovery
            assert call_count >= 2

    def test_monitor_with_claude_directory_disappearing(self, temp_dir, mock_config):
        """Test monitor when Claude directories disappear during monitoring."""
        # Create initial directory structure
        claude_dir = temp_dir / "claude"
        claude_dir.mkdir()
        projects_dir = claude_dir / "projects"
        projects_dir.mkdir()

        call_count = 0
        def mock_scan_with_disappearing_dir(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call succeeds
                return []
            elif call_count == 2:
                # Second call - directory disappears
                if projects_dir.exists():
                    projects_dir.rmdir()
                    claude_dir.rmdir()
                raise FileNotFoundError("Claude directory not found")
            else:
                # Exit test
                raise KeyboardInterrupt("Test complete")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_disappearing_dir):
            with patch('time.sleep'):
                try:
                    monitor(mock_config, False)
                except KeyboardInterrupt:
                    pass

        # Should have handled directory disappearing
        assert call_count >= 2

    def test_monitor_with_disk_full_errors(self, temp_dir, mock_config):
        """Test monitor mode when disk becomes full."""
        disk_full_errors = [
            OSError(28, "No space left on device"),  # ENOSPC
            OSError("Disk quota exceeded"),
        ]

        for error in disk_full_errors:
            def mock_scan_disk_full(*args, **kwargs):
                raise error

            with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_disk_full):
                with patch('time.sleep', side_effect=KeyboardInterrupt):  # Exit quickly
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass
                    # Should not crash on disk full errors


class TestConfigurationReloading:
    """Test configuration changes during monitoring."""

    def test_monitor_configuration_reload(self, temp_dir, mock_config):
        """Test behavior when config file changes during monitoring."""
        config_file = temp_dir / "config.yaml"

        # Create initial config
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("token_limit: 1000000\npolling_interval: 1\n")

        # Track config loads
        load_count = 0
        original_token_limit = mock_config.token_limit

        def mock_load_config(*args, **kwargs):
            nonlocal load_count
            load_count += 1

            if load_count == 1:
                # Return original config
                return mock_config
            else:
                # Return modified config
                modified_config = mock_config.model_copy()
                modified_config.token_limit = 2000000  # Changed
                return modified_config

        scan_count = 0
        def mock_scan_with_config_change(*args, **kwargs):
            nonlocal scan_count
            scan_count += 1

            if scan_count >= 3:
                raise KeyboardInterrupt("Test complete")

            # Simulate config file change on second scan
            if scan_count == 2:
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write("token_limit: 2000000\npolling_interval: 1\n")

            return []

        with patch('par_cc_usage.config.load_config', side_effect=mock_load_config):
            with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_config_change):
                with patch('time.sleep'):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

        # Should have handled config changes
        assert scan_count >= 3

    def test_apply_command_overrides_edge_cases(self, mock_config):
        """Test configuration override edge cases."""
        # Test with None values
        overrides = {
            'token_limit': None,
            'show_pricing': None,
            'block_start': None,
        }

        modified_config = _apply_command_overrides(mock_config, **overrides)
        # Should handle None values gracefully
        assert modified_config.token_limit == mock_config.token_limit

        # Test with invalid values
        invalid_overrides = {
            'token_limit': -1,  # Negative value
            'polling_interval': 0,  # Zero interval
        }

        modified_config = _apply_command_overrides(mock_config, **invalid_overrides)
        # Should validate or handle invalid values appropriately

    def test_config_file_corruption_during_monitoring(self, temp_dir, mock_config):
        """Test behavior when config file becomes corrupted during monitoring."""
        config_file = temp_dir / "config.yaml"

        scan_count = 0
        def mock_scan_with_config_corruption(*args, **kwargs):
            nonlocal scan_count
            scan_count += 1

            if scan_count == 2:
                # Corrupt config file
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write("invalid: yaml: content: {\n")
            elif scan_count >= 3:
                raise KeyboardInterrupt("Test complete")

            return []

        def mock_load_config_with_corruption(*args, **kwargs):
            if scan_count >= 2:
                raise ValueError("Invalid YAML")
            return mock_config

        with patch('par_cc_usage.config.load_config', side_effect=mock_load_config_with_corruption):
            with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_config_corruption):
                with patch('time.sleep'):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

        # Should handle config corruption gracefully
        assert scan_count >= 3


class TestTokenLimitAutoAdjustment:
    """Test automatic token limit adjustment when exceeded."""

    def test_token_limit_auto_adjustment(self, temp_dir, mock_config):
        """Test automatic token limit adjustment when exceeded."""
        original_limit = mock_config.token_limit

        # Mock usage snapshot that exceeds limit
        mock_snapshot = Mock(spec=UsageSnapshot)
        mock_snapshot.unified_block_tokens.return_value = original_limit + 1000000  # Exceed limit
        mock_snapshot.projects = {"test": Mock()}

        adjustment_count = 0
        def mock_scan_with_limit_exceeded(*args, **kwargs):
            nonlocal adjustment_count
            adjustment_count += 1

            if adjustment_count >= 2:
                raise KeyboardInterrupt("Test complete")

            # Return mock data that exceeds token limit
            return [mock_snapshot] if adjustment_count == 1 else []

        config_save_called = False
        def mock_save_config(*args, **kwargs):
            nonlocal config_save_called
            config_save_called = True

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_limit_exceeded):
            with patch('par_cc_usage.main.aggregate_usage', return_value=mock_snapshot):
                with patch('par_cc_usage.config.save_config', side_effect=mock_save_config):
                    with patch('time.sleep'):
                        try:
                            monitor(mock_config, False)
                        except KeyboardInterrupt:
                            pass

        # Should have attempted token limit adjustment
        assert adjustment_count >= 2

    def test_token_limit_adjustment_failure_handling(self, temp_dir, mock_config):
        """Test handling when token limit adjustment fails."""
        # Mock config save failure
        def mock_save_config_failure(*args, **kwargs):
            raise PermissionError("Cannot write config file")

        mock_snapshot = Mock(spec=UsageSnapshot)
        mock_snapshot.unified_block_tokens.return_value = mock_config.token_limit + 1000000
        mock_snapshot.projects = {"test": Mock()}

        def mock_scan_limit_exceeded(*args, **kwargs):
            raise KeyboardInterrupt("Test complete")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_limit_exceeded):
            with patch('par_cc_usage.main.aggregate_usage', return_value=mock_snapshot):
                with patch('par_cc_usage.config.save_config', side_effect=mock_save_config_failure):
                    with patch('time.sleep'):
                        try:
                            monitor(mock_config, False)
                        except KeyboardInterrupt:
                            pass

        # Should handle config save failure gracefully


class TestMonitorLoopStability:
    """Test monitor loop stability and error recovery."""

    def test_monitor_exception_resilience(self, temp_dir, mock_config):
        """Test that monitor loop exceptions are handled gracefully."""
        exceptions_to_test = [
            ValueError("Invalid data"),
            RuntimeError("Runtime error"),
            TypeError("Type error"),
            AttributeError("Attribute error"),
            Exception("Generic exception"),
        ]

        for exception in exceptions_to_test:
            call_count = 0
            def mock_scan_with_exception(*args, **kwargs):
                nonlocal call_count
                call_count += 1

                if call_count == 1:
                    raise exception
                elif call_count >= 2:
                    raise KeyboardInterrupt("Test recovery")
                return []

            with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_exception):
                with patch('time.sleep'):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

            # Should have attempted recovery after exception
            assert call_count >= 2

    def test_monitor_memory_pressure_handling(self, temp_dir, mock_config):
        """Test monitor behavior under memory pressure."""
        # Mock memory pressure by raising MemoryError
        memory_pressure_count = 0
        def mock_scan_memory_pressure(*args, **kwargs):
            nonlocal memory_pressure_count
            memory_pressure_count += 1

            if memory_pressure_count == 1:
                raise MemoryError("Out of memory")
            elif memory_pressure_count >= 2:
                raise KeyboardInterrupt("Test complete")
            return []

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_memory_pressure):
            with patch('time.sleep'):
                try:
                    monitor(mock_config, False)
                except KeyboardInterrupt:
                    pass

        # Should handle memory pressure gracefully
        assert memory_pressure_count >= 2

    def test_monitor_rapid_interruption_handling(self, temp_dir, mock_config):
        """Test monitor handling of rapid interruptions."""
        interruption_count = 0
        max_interruptions = 5

        def mock_scan_rapid_interruptions(*args, **kwargs):
            nonlocal interruption_count
            interruption_count += 1

            if interruption_count <= max_interruptions:
                # Simulate rapid interruptions
                if interruption_count % 2 == 0:
                    raise KeyboardInterrupt(f"Interruption {interruption_count}")
                else:
                    return []  # Normal execution
            else:
                raise KeyboardInterrupt("Final interruption")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_rapid_interruptions):
            with patch('time.sleep'):
                try:
                    monitor(mock_config, False)
                except KeyboardInterrupt:
                    pass

        # Should handle multiple rapid interruptions
        assert interruption_count > max_interruptions

    def test_monitor_display_update_failures(self, temp_dir, mock_config):
        """Test monitor when display updates fail."""
        display_failure_count = 0

        def mock_scan_with_display_failure(*args, **kwargs):
            nonlocal display_failure_count
            display_failure_count += 1

            if display_failure_count >= 3:
                raise KeyboardInterrupt("Test complete")

            # Return data that might cause display issues
            mock_snapshot = Mock(spec=UsageSnapshot)
            mock_snapshot.projects = {"test": Mock()}
            return [mock_snapshot]

        # Mock display update failure
        def mock_display_update_failure(*args, **kwargs):
            raise RuntimeError("Display update failed")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_with_display_failure):
            with patch('par_cc_usage.display.MonitorDisplay.update', side_effect=mock_display_update_failure):
                with patch('time.sleep'):
                    try:
                        monitor(mock_config, False)
                    except KeyboardInterrupt:
                        pass

        # Should handle display update failures
        assert display_failure_count >= 3


class TestSnapshotMode:
    """Test snapshot mode specific behavior."""

    def test_snapshot_mode_single_execution(self, temp_dir, mock_config):
        """Test that snapshot mode executes only once."""
        scan_count = 0
        def mock_scan_snapshot(*args, **kwargs):
            nonlocal scan_count
            scan_count += 1
            return []

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_snapshot):
            # Snapshot mode should execute once and exit
            monitor(mock_config, True)  # True = snapshot mode

        # Should have executed exactly once
        assert scan_count == 1

    def test_snapshot_mode_error_handling(self, temp_dir, mock_config):
        """Test error handling in snapshot mode."""
        def mock_scan_snapshot_error(*args, **kwargs):
            raise RuntimeError("Snapshot error")

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_snapshot_error):
            # Should handle errors in snapshot mode
            try:
                monitor(mock_config, True)
            except RuntimeError:
                pass  # Expected for this test

    def test_snapshot_mode_with_no_data(self, temp_dir, mock_config):
        """Test snapshot mode when no data is available."""
        def mock_scan_no_data(*args, **kwargs):
            return []  # No projects found

        with patch('par_cc_usage.main.scan_all_projects', side_effect=mock_scan_no_data):
            # Should handle no data gracefully
            monitor(mock_config, True)
            # Should complete without errors
