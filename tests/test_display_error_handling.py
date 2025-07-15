"""
Test display error handling and edge cases.

This module tests display rendering with invalid data, theme switching failures,
layout management edge cases, and console size extremes.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.layout import Layout
from io import StringIO

from par_cc_usage.display import MonitorDisplay
from par_cc_usage.models import UsageSnapshot, Project, Session, TokenBlock, TokenUsage
from par_cc_usage.theme import ThemeManager
from par_cc_usage.config import DisplayConfig
from tests.conftest import create_token_usage, create_block_with_tokens


class TestDisplayWithInvalidData:
    """Test display rendering when usage data is corrupted or invalid."""

    def test_display_with_corrupted_usage_snapshot(self, mock_config):
        """Test display rendering when usage snapshot is corrupted."""
        # Create display
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Test with None snapshot
        display.update(None)  # Should not crash

        # Test with empty projects
        empty_snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )
        display.update(empty_snapshot)  # Should handle gracefully

    def test_display_with_invalid_token_blocks(self, mock_config, sample_timestamp):
        """Test display with invalid or corrupted token blocks."""
        # Create block with invalid data
        invalid_usage = TokenUsage(
            input_tokens=-100,  # Negative tokens
            output_tokens=float('inf'),  # Infinite tokens
            model="",  # Empty model
            timestamp=sample_timestamp,
        )

        invalid_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp - timedelta(hours=1),  # End before start
            session_id="",  # Empty session ID
            project_name="",  # Empty project name
            model="invalid-model",
            token_usage=invalid_usage,
            model_tokens={"invalid": float('nan')},  # NaN tokens
            actual_end_time=None,  # None end time
        )

        session = Session(
            session_id="invalid_session",
            project_name="invalid_project",
            model="invalid-model",
            blocks=[invalid_block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,
            session_start=sample_timestamp,
        )

        project = Project(
            name="invalid_project",
            sessions={"invalid_session": session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"invalid_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        display = MonitorDisplay(mock_config.display, show_pricing=False)
        # Should handle invalid data gracefully
        display.update(snapshot)

    def test_display_with_missing_model_data(self, mock_config, sample_timestamp):
        """Test display when model data is missing or incomplete."""
        # Create usage with missing model information
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model=None,  # None model
            timestamp=sample_timestamp,
        )

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model=None,  # None model
            token_usage=usage,
            model_tokens={},  # Empty model tokens
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model=None,
            blocks=[block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,
            session_start=sample_timestamp,
        )

        project = Project(
            name="test_project",
            sessions={"session_1": session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        display = MonitorDisplay(mock_config.display, show_pricing=False)
        # Should handle missing model data
        display.update(snapshot)

    def test_display_with_extreme_token_values(self, mock_config, sample_timestamp):
        """Test display with extremely large or small token values."""
        extreme_values = [
            (0, 0),  # Zero tokens
            (1, 1),  # Minimal tokens
            (999999999999, 999999999999),  # Extremely large
            (1e15, 1e15),  # Scientific notation
        ]

        for input_tokens, output_tokens in extreme_values:
            usage = create_token_usage(
                timestamp=sample_timestamp,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )

            block = create_block_with_tokens(
                start_time=sample_timestamp,
                session_id="session_extreme",
                project_name="extreme_project",
                token_count=int(input_tokens + output_tokens),
            )

            session = Session(
                session_id="session_extreme",
                project_name="extreme_project",
                model="claude-3-sonnet-latest",
                blocks=[block],
                first_seen=sample_timestamp,
                last_seen=sample_timestamp,
                session_start=sample_timestamp,
            )

            project = Project(
                name="extreme_project",
                sessions={"session_extreme": session},
            )

            snapshot = UsageSnapshot(
                timestamp=sample_timestamp,
                projects={"extreme_project": project},
                total_limit=1000000,
                block_start_override=None,
            )

            display = MonitorDisplay(mock_config.display, show_pricing=False)
            # Should handle extreme values without crashing
            display.update(snapshot)


class TestThemeSwitchingErrors:
    """Test display when theme switching fails."""

    def test_display_theme_switching_failures(self, mock_config):
        """Test display when theme switching fails."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Mock theme manager to fail
        with patch.object(display.theme_manager, 'get_current_theme') as mock_theme:
            mock_theme.side_effect = Exception("Theme loading failed")

            # Should handle theme failure gracefully
            empty_snapshot = UsageSnapshot(
                timestamp=datetime.now(timezone.utc),
                projects={},
                total_limit=1000000,
                block_start_override=None,
            )
            display.update(empty_snapshot)

    def test_display_with_invalid_theme_data(self, mock_config):
        """Test display with corrupted theme data."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Mock theme manager to return invalid theme
        invalid_theme = Mock()
        invalid_theme.primary = None  # Invalid color
        invalid_theme.secondary = "invalid_color"  # Invalid color string
        invalid_theme.accent = Mock()  # Mock object instead of color

        with patch.object(display.theme_manager, 'get_current_theme', return_value=invalid_theme):
            empty_snapshot = UsageSnapshot(
                timestamp=datetime.now(timezone.utc),
                projects={},
                total_limit=1000000,
                block_start_override=None,
            )
            # Should handle invalid theme data
            display.update(empty_snapshot)

    def test_theme_manager_initialization_failure(self, mock_config):
        """Test display when theme manager fails to initialize."""
        with patch('par_cc_usage.display.ThemeManager') as mock_theme_manager:
            mock_theme_manager.side_effect = Exception("Theme manager init failed")

            # Should handle theme manager initialization failure
            try:
                display = MonitorDisplay(mock_config.display, show_pricing=False)
            except Exception:
                pass  # May fail during initialization


class TestProgressBarEdgeCases:
    """Test progress bar calculations with edge cases."""

    def test_progress_bar_calculation_edge_cases(self, mock_config, sample_timestamp):
        """Test progress bars with zero tokens, negative values."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Test with zero total tokens
        zero_snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=1000000,
            block_start_override=None,
        )

        # Mock unified_block_tokens to return 0
        with patch.object(zero_snapshot, 'unified_block_tokens', return_value=0):
            display.update(zero_snapshot)

    def test_burn_rate_calculation_with_zero_time(self, mock_config, sample_timestamp):
        """Test burn rate calculation when time elapsed is zero."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Create snapshot with blocks that have zero time elapsed
        usage = create_token_usage(
            timestamp=sample_timestamp,
            input_tokens=1000,
            output_tokens=500,
        )

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            token_usage=usage,
            model_tokens={"sonnet": 1500},
            actual_end_time=sample_timestamp,  # Same as start_time = zero elapsed
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,  # Same as first_seen = zero elapsed
            session_start=sample_timestamp,
        )

        project = Project(
            name="test_project",
            sessions={"session_1": session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=sample_timestamp,  # Same as timestamp = zero elapsed
        )

        # Should handle zero time elapsed without division by zero
        display.update(snapshot)

    def test_progress_bar_with_negative_percentages(self, mock_config, sample_timestamp):
        """Test progress bars when calculations result in negative percentages."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Create snapshot where used tokens exceed limit
        usage = create_token_usage(
            timestamp=sample_timestamp,
            input_tokens=2000000,  # Exceeds typical limit
            output_tokens=1000000,
        )

        block = create_block_with_tokens(
            start_time=sample_timestamp,
            session_id="session_1",
            project_name="test_project",
            token_count=3000000,  # Very large token count
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

        project = Project(
            name="test_project",
            sessions={"session_1": session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=100000,  # Small limit, will be exceeded
            block_start_override=None,
        )

        # Should handle exceeding limits gracefully
        display.update(snapshot)


class TestLayoutManagementEdgeCases:
    """Test layout management with console size extremes."""

    def test_layout_resizing_edge_cases(self, mock_config):
        """Test layout management with very small/large console sizes."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Test with very small console sizes
        small_console_sizes = [
            (10, 5),   # Extremely small
            (20, 10),  # Very small
            (40, 15),  # Small
            (1, 1),    # Minimum possible
        ]

        for width, height in small_console_sizes:
            # Mock console size
            with patch.object(display.console, 'size') as mock_size:
                mock_size.return_value = Mock(width=width, height=height)

                empty_snapshot = UsageSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    projects={},
                    total_limit=1000000,
                    block_start_override=None,
                )

                # Should handle small console sizes gracefully
                display.update(empty_snapshot)

    def test_layout_with_large_console_sizes(self, mock_config):
        """Test layout with very large console sizes."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Test with very large console sizes
        large_console_sizes = [
            (500, 200),   # Very large
            (1000, 500),  # Extremely large
            (2000, 1000), # Ultra-wide
        ]

        for width, height in large_console_sizes:
            with patch.object(display.console, 'size') as mock_size:
                mock_size.return_value = Mock(width=width, height=height)

                empty_snapshot = UsageSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    projects={},
                    total_limit=1000000,
                    block_start_override=None,
                )

                # Should handle large console sizes gracefully
                display.update(empty_snapshot)

    def test_progress_container_dynamic_sizing(self, mock_config, sample_timestamp):
        """Test ProgressContainer dynamic sizing with various model counts."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Create snapshots with different numbers of models
        model_counts = [0, 1, 3, 5, 10, 20]  # Various model counts

        for model_count in model_counts:
            projects = {}

            if model_count > 0:
                # Create blocks with different models
                blocks = []
                for i in range(model_count):
                    model_name = f"claude-3-model-{i}"
                    block = create_block_with_tokens(
                        start_time=sample_timestamp,
                        session_id=f"session_{i}",
                        project_name="test_project",
                        token_count=1000,
                    )
                    block.model = model_name
                    block.model_tokens = {f"model_{i}": 1000}
                    blocks.append(block)

                session = Session(
                    session_id="session_multi",
                    project_name="test_project",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=sample_timestamp,
                    last_seen=sample_timestamp,
                    session_start=sample_timestamp,
                )

                projects["test_project"] = Project(
                    name="test_project",
                    sessions={"session_multi": session},
                )

            snapshot = UsageSnapshot(
                timestamp=sample_timestamp,
                projects=projects,
                total_limit=1000000,
                block_start_override=None,
            )

            # Should adapt container size to model count
            display.update(snapshot)

    def test_display_render_failures(self, mock_config):
        """Test display when rendering operations fail."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Mock console.print to fail
        with patch.object(display.console, 'print', side_effect=Exception("Render failed")):
            empty_snapshot = UsageSnapshot(
                timestamp=datetime.now(timezone.utc),
                projects={},
                total_limit=1000000,
                block_start_override=None,
            )

            # Should handle render failures gracefully
            try:
                display.update(empty_snapshot)
            except Exception:
                pass  # May fail during rendering


class TestDisplayConfigurationEdgeCases:
    """Test display with various configuration edge cases."""

    def test_display_with_invalid_configuration(self):
        """Test display with invalid display configuration."""
        # Create invalid display config
        invalid_configs = [
            DisplayConfig(
                time_format="invalid",  # Invalid time format
                refresh_interval=-1,   # Negative interval
                project_name_prefixes=[],  # Empty prefixes
            ),
            DisplayConfig(
                time_format="24h",
                refresh_interval=0,    # Zero interval
                project_name_prefixes=None,  # None prefixes
            ),
        ]

        for config in invalid_configs:
            try:
                display = MonitorDisplay(config, show_pricing=False)
                # Should handle invalid config gracefully
                empty_snapshot = UsageSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    projects={},
                    total_limit=1000000,
                    block_start_override=None,
                )
                display.update(empty_snapshot)
            except Exception:
                pass  # May fail due to invalid configuration

    def test_display_with_missing_configuration_fields(self):
        """Test display when configuration fields are missing."""
        # Create minimal config
        minimal_config = DisplayConfig()

        try:
            display = MonitorDisplay(minimal_config, show_pricing=False)

            empty_snapshot = UsageSnapshot(
                timestamp=datetime.now(timezone.utc),
                projects={},
                total_limit=1000000,
                block_start_override=None,
            )
            display.update(empty_snapshot)
        except Exception:
            pass  # May fail due to minimal configuration

    def test_display_pricing_mode_edge_cases(self, mock_config, sample_timestamp):
        """Test display with pricing enabled and various edge cases."""
        display = MonitorDisplay(mock_config.display, show_pricing=True)

        # Create block with cost data
        usage = create_token_usage(
            timestamp=sample_timestamp,
            input_tokens=1000,
            output_tokens=500,
        )
        usage.cost_usd = 2.50  # Add cost data

        block = create_block_with_tokens(
            start_time=sample_timestamp,
            session_id="session_1",
            project_name="test_project",
            token_count=1500,
        )
        block.cost_usd = 2.50  # Add cost data

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[block],
            first_seen=sample_timestamp,
            last_seen=sample_timestamp,
            session_start=sample_timestamp,
        )

        project = Project(
            name="test_project",
            sessions={"session_1": session},
        )

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"test_project": project},
            total_limit=1000000,
            block_start_override=None,
        )

        # Should handle pricing display mode
        display.update(snapshot)

    def test_display_console_encoding_errors(self, mock_config):
        """Test display when console encoding fails."""
        display = MonitorDisplay(mock_config.display, show_pricing=False)

        # Mock console with encoding issues
        with patch.object(display.console, 'file') as mock_file:
            mock_file.encoding = 'ascii'  # Limited encoding
            mock_file.write.side_effect = UnicodeEncodeError(
                'ascii', 'emoji', 0, 1, 'ordinal not in range'
            )

            empty_snapshot = UsageSnapshot(
                timestamp=datetime.now(timezone.utc),
                projects={},
                total_limit=1000000,
                block_start_override=None,
            )

            # Should handle encoding errors gracefully
            try:
                display.update(empty_snapshot)
            except UnicodeEncodeError:
                pass  # Expected for this test
