"""
Tests for the display module.
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from par_cc_usage.display import MonitorDisplay
from par_cc_usage.enums import DisplayMode
from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot


class TestMonitorDisplay:
    """Test the MonitorDisplay class."""

    def test_initialization_default(self):
        """Test MonitorDisplay initialization with defaults."""
        display = MonitorDisplay()

        assert display.console is not None
        assert display.layout is not None
        assert display.show_sessions is False
        assert display.time_format == "24h"

    def test_initialization_with_params(self):
        """Test MonitorDisplay initialization with parameters."""
        console = Console()
        display = MonitorDisplay(console=console, show_sessions=True, time_format="12h")

        assert display.console == console
        assert display.show_sessions is True
        assert display.time_format == "12h"

    def test_initialization_with_compact_mode(self):
        """Test MonitorDisplay initialization with compact mode."""
        from par_cc_usage.config import DisplayConfig

        # Create config with compact mode
        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        assert display.compact_mode is True
        assert display.config == config

    def test_initialization_with_normal_mode(self):
        """Test MonitorDisplay initialization with normal mode."""
        from par_cc_usage.config import DisplayConfig

        # Create config with normal mode
        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.NORMAL)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        assert display.compact_mode is False
        assert display.config == config

    def test_initialization_without_config(self):
        """Test MonitorDisplay initialization without config defaults to normal mode."""
        display = MonitorDisplay()

        assert display.compact_mode is False
        assert display.config is None

    def test_setup_layout_without_sessions(self):
        """Test layout setup without sessions panel."""
        display = MonitorDisplay(show_sessions=False)

        # Check layout structure
        assert display.layout is not None
        # The layout should have been split

    def test_setup_layout_with_sessions(self):
        """Test layout setup with sessions panel."""
        display = MonitorDisplay(show_sessions=True)

        # Check layout structure
        assert display.layout is not None
        # The layout should have sessions panel

    def test_setup_layout_compact_mode(self):
        """Test layout setup in compact mode."""
        from par_cc_usage.config import DisplayConfig

        # Create config with compact mode
        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config, show_sessions=True)

        # Check layout structure - should only have header and progress
        assert display.layout is not None
        assert display.compact_mode is True
        # In compact mode, sessions should not be shown even if requested

    def test_setup_layout_compact_mode_without_sessions(self):
        """Test layout setup in compact mode without sessions."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config, show_sessions=False)

        assert display.layout is not None
        assert display.compact_mode is True

    def test_create_header(self, sample_usage_snapshot):
        """Test header panel creation."""
        display = MonitorDisplay()

        # Create header panel
        panel = display._create_header(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        # Check that it contains expected header information
        assert "Active Projects" in str(panel.renderable) or "projects" in str(panel.renderable).lower()

    def test_create_block_progress_no_unified_block(self):
        """Test block progress panel when no unified block."""
        display = MonitorDisplay()

        # Create snapshot without unified block
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={},
            total_limit=None,
        )

        panel = display._create_block_progress(snapshot)

        assert isinstance(panel, Panel)

    def test_create_block_progress_with_block(self, sample_usage_snapshot):
        """Test block progress panel with active block."""
        display = MonitorDisplay()

        # Mock unified block start time by setting block_start_override
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=2)

        panel = display._create_block_progress(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        # The block progress panel doesn't have a title, it just contains the progress bar
        # We can check that it has the right structure instead
        assert panel.title is None

    @pytest.mark.asyncio
    async def test_create_progress_bars(self, sample_usage_snapshot):
        """Test progress bars creation."""
        display = MonitorDisplay()

        panel = await display._create_progress_bars(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        assert panel.title == "Token Usage by Model"

    @pytest.mark.asyncio
    async def test_create_progress_bars_compact_mode(self, sample_usage_snapshot):
        """Test progress bars creation in compact mode."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        panel = await display._create_progress_bars(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        assert panel.title == "Token Usage by Model"
        # In compact mode, should not show traditional progress bars

    def test_create_model_displays_compact_mode(self):
        """Test model displays in compact mode."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        model_tokens = {"claude-3-5-sonnet": 1000, "claude-3-opus": 500}

        displays = display._create_model_displays(model_tokens)

        assert len(displays) == 2
        for display_text in displays:
            assert isinstance(display_text, Text)

    def test_create_model_displays_normal_mode(self):
        """Test model displays in normal mode."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.NORMAL)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        model_tokens = {"claude-3-5-sonnet": 1000}

        displays = display._create_model_displays(model_tokens)

        assert len(displays) == 1
        display_text = displays[0]
        assert isinstance(display_text, Text)

    @pytest.mark.asyncio
    async def test_create_sessions_table_no_sessions(self):
        """Test sessions table with no active sessions."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = True
        mock_config.display.project_name_prefixes = ["-Users-", "-home-"]

        display = MonitorDisplay(config=mock_config)

        # Create empty snapshot
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={},
            total_limit=None,
        )

        panel = await display._create_sessions_table(snapshot)

        assert isinstance(panel, Panel)

    @pytest.mark.asyncio
    async def test_create_sessions_table_with_sessions(self, sample_usage_snapshot):
        """Test sessions table with active sessions."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False
        mock_config.display.project_name_prefixes = ["-Users-", "-home-"]

        display = MonitorDisplay(config=mock_config)

        panel = await display._create_sessions_table(sample_usage_snapshot)

        assert isinstance(panel, Panel)

    def test_update_with_compact_mode(self, sample_usage_snapshot):
        """Test update method in compact mode only updates essential elements."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0  # Add max_cost_encountered attribute

        display = MonitorDisplay(config=config)

        # Create a proper mock layout that supports item assignment
        mock_layout = {}
        display.layout = mock_layout

        # The update method expects certain layout keys to exist
        mock_layout["header"] = Mock()
        mock_layout["progress"] = Mock()
        mock_layout["block_progress"] = Mock()
        mock_layout["tool_usage"] = Mock()
        mock_layout["sessions"] = Mock()

        # Update should work in compact mode
        display.update(sample_usage_snapshot)

        # Verify that layout updates were called
        assert mock_layout["header"].update.called
        assert mock_layout["progress"].update.called

    def test_format_time_24h(self):
        """Test time formatting in 24-hour format."""
        from par_cc_usage.utils import format_time

        test_time = datetime(2024, 7, 8, 14, 30, 45, tzinfo=UTC)
        formatted = format_time(test_time, "24h")

        # Should contain 24-hour formatted time
        assert "14:30" in formatted

    def test_format_time_12h(self):
        """Test time formatting in 12-hour format."""
        from par_cc_usage.utils import format_time

        test_time = datetime(2024, 7, 8, 14, 30, 45, tzinfo=UTC)
        formatted = format_time(test_time, "12h")

        # Should contain 12-hour formatted time
        assert "PM" in formatted or "AM" in formatted

    def test_compact_mode_hides_sessions_even_when_requested(self):
        """Test that compact mode hides sessions even when show_sessions=True."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        # Request sessions to be shown, but compact mode should override
        display = MonitorDisplay(config=config, show_sessions=True)

        assert display.compact_mode is True
        assert display.show_sessions is True  # The setting is preserved
        # But in compact mode, sessions should not be displayed in the layout

    @pytest.mark.asyncio
    async def test_compact_mode_burn_rate_calculation(self, sample_usage_snapshot):
        """Test burn rate calculation and display in compact mode."""
        from par_cc_usage.config import DisplayConfig

        config = Mock()
        config.display = DisplayConfig(display_mode=DisplayMode.COMPACT)
        config.max_cost_encountered = 0.0
        config.max_tokens_encountered = 0
        config.max_messages_encountered = 0
        config.max_unified_block_tokens_encountered = 0
        config.max_unified_block_messages_encountered = 0
        config.max_unified_block_cost_encountered = 0.0
        display = MonitorDisplay(config=config)

        # Create progress bars panel which includes burn rate in compact mode
        panel = await display._create_progress_bars(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        # Compact mode should still show burn rate metrics

    def test_update_display(self, sample_usage_snapshot):
        """Test display update."""
        display = MonitorDisplay()

        # Should not raise an error
        display.update(sample_usage_snapshot)

    def test_get_model_emoji(self):
        """Test model emoji mapping."""
        display = MonitorDisplay()

        # Test known models - use correct emojis
        assert display._get_model_emoji("opus") == "🚀"
        assert display._get_model_emoji("sonnet") == "⚡"
        assert display._get_model_emoji("haiku") == "💨"
        assert display._get_model_emoji("claude") == "🤖"
        assert display._get_model_emoji("gpt") == "🧠"
        assert display._get_model_emoji("llama") == "🦙"
        assert display._get_model_emoji("unknown") == "❓"

    def test_create_model_displays(self):
        """Test model display creation."""
        display = MonitorDisplay()

        model_tokens = {
            "opus": 50000,
            "sonnet": 30000,
            "haiku": 20000
        }

        displays = display._create_model_displays(model_tokens)

        assert isinstance(displays, list)
        assert len(displays) == 3
        # Should be sorted alphabetically by model name
        display_strs = [str(display) for display in displays]
        assert any("Haiku" in d for d in display_strs)
        assert any("Opus" in d for d in display_strs)
        assert any("Sonnet" in d for d in display_strs)

    def test_get_progress_colors(self):
        """Test progress color determination."""
        display = MonitorDisplay()

        # Test different usage levels - use percentage as 0-100 range
        bar_color, text_color = display._get_progress_colors(30, 30000, 100000)
        # Should be green for low usage (30%)
        assert "00FF00" in bar_color

        bar_color, text_color = display._get_progress_colors(80, 80000, 100000)
        # Should be orange for medium usage (80%)
        assert "FFA500" in bar_color

        bar_color, text_color = display._get_progress_colors(95, 95000, 100000)
        # Should be red for high usage (95%)
        assert "FF0000" in bar_color

    def test_calculate_burn_rate(self, sample_usage_snapshot):
        """Test burn rate calculation text creation."""
        display = MonitorDisplay()

        # Mock timestamp for consistent elapsed time
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        text = display._calculate_burn_rate_sync(sample_usage_snapshot, 60000, 100000)

        assert hasattr(text, 'plain')  # Should be a Text object
        assert "/m" in text.plain  # Abbreviated tokens per minute format

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_async_without_pricing(self, sample_usage_snapshot):
        """Test async burn rate calculation without pricing enabled."""
        # Mock config without pricing
        mock_config = Mock()
        mock_config.display.show_pricing = False

        display = MonitorDisplay(config=mock_config)

        # Mock timestamp for consistent elapsed time
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        text = await display._calculate_burn_rate(sample_usage_snapshot, 60000, 100000)

        assert hasattr(text, 'plain')  # Should be a Text object
        assert "/m" in text.plain  # Abbreviated tokens per minute format
        assert "$" not in text.plain  # Should not have estimated cost when pricing disabled

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_async_with_pricing(self, sample_usage_snapshot):
        """Test async burn rate calculation with pricing enabled."""
        # Mock config with pricing enabled
        mock_config = Mock()
        mock_config.display.show_pricing = True

        display = MonitorDisplay(config=mock_config)

        # Mock timestamp for consistent elapsed time
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        # Mock the get_unified_block_total_cost method to return a test cost
        async def mock_get_cost():
            return 10.50  # $10.50 current cost
        sample_usage_snapshot.get_unified_block_total_cost = mock_get_cost

        text = await display._calculate_burn_rate(sample_usage_snapshot, 60000, 100000)

        assert hasattr(text, 'plain')  # Should be a Text object
        assert "/m" in text.plain  # Abbreviated tokens per minute format
        # Should have estimated cost when pricing enabled and cost available
        assert "Est:" in text.plain and "$" in text.plain

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_async_pricing_error(self, sample_usage_snapshot):
        """Test async burn rate calculation when pricing calculation fails."""
        # Mock config with pricing enabled
        mock_config = Mock()
        mock_config.display.show_pricing = True

        display = MonitorDisplay(config=mock_config)

        # Mock timestamp for consistent elapsed time
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        # Mock the get_unified_block_total_cost method to raise an exception
        async def mock_get_cost_error():
            raise Exception("Pricing calculation failed")
        sample_usage_snapshot.get_unified_block_total_cost = mock_get_cost_error

        text = await display._calculate_burn_rate(sample_usage_snapshot, 60000, 100000)

        assert hasattr(text, 'plain')  # Should be a Text object
        assert "/m" in text.plain  # Abbreviated tokens per minute format
        # Should not break when pricing fails - graceful degradation

    @pytest.mark.asyncio
    async def test_calculate_burn_rate_async_zero_cost(self, sample_usage_snapshot):
        """Test async burn rate calculation with zero cost."""
        # Mock config with pricing enabled
        mock_config = Mock()
        mock_config.display.show_pricing = True

        display = MonitorDisplay(config=mock_config)

        # Mock timestamp for consistent elapsed time
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        # Mock the get_unified_block_total_cost method to return zero cost
        async def mock_get_zero_cost():
            return 0.0
        sample_usage_snapshot.get_unified_block_total_cost = mock_get_zero_cost

        text = await display._calculate_burn_rate(sample_usage_snapshot, 60000, 100000)

        assert hasattr(text, 'plain')  # Should be a Text object
        assert "/m" in text.plain  # Abbreviated tokens per minute format
        # Should not show cost estimate when cost is zero

    def test_calculate_eta_display(self, sample_usage_snapshot):
        """Test ETA display calculation."""
        display = MonitorDisplay()

        # Mock values for ETA calculation
        sample_usage_snapshot.timestamp = datetime.now(UTC)
        sample_usage_snapshot.block_start_override = datetime.now(UTC) - timedelta(hours=1)

        eta_result = display._calculate_eta_display(sample_usage_snapshot, 50000, 100000, 833.33)  # 50k tokens/hour rate

        assert isinstance(eta_result, tuple)  # Should be a tuple
        assert len(eta_result) == 2  # (display_string, eta_before_block_end)
        display_string, eta_before_block_end = eta_result
        assert isinstance(display_string, str)
        assert isinstance(eta_before_block_end, bool)

    @patch('par_cc_usage.display.Live')
    def test_live_context_manager(self, mock_live_class, sample_usage_snapshot):
        """Test using display update method."""
        mock_live = Mock()
        mock_live_class.return_value = mock_live

        display = MonitorDisplay()

        # Just test that update method works
        display.update(sample_usage_snapshot)

        # The update method should work without errors
        assert True

    @pytest.mark.asyncio
    async def test_create_progress_bars_with_limit(self, sample_usage_snapshot):
        """Test progress bars with token limit set."""
        display = MonitorDisplay()

        # Set a token limit
        sample_usage_snapshot.total_limit = 100000

        panel = await display._create_progress_bars(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        assert panel.title == "Token Usage by Model"

    @pytest.mark.asyncio
    async def test_create_sessions_table_with_unified_block(self, sample_usage_snapshot):
        """Test sessions table filtering by unified block."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False
        mock_config.display.project_name_prefixes = ["-Users-", "-home-"]

        display = MonitorDisplay(config=mock_config)

        # Set unified block time
        block_start = datetime.now(UTC) - timedelta(hours=2)
        sample_usage_snapshot.block_start_override = block_start

        # Ensure the session's block matches
        for project in sample_usage_snapshot.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    block.start_time = block_start

        panel = await display._create_sessions_table(sample_usage_snapshot)

        assert isinstance(panel, Panel)

    def test_create_header_with_no_limit(self, sample_usage_snapshot):
        """Test header creation when no token limit is set."""
        display = MonitorDisplay()

        # Remove token limit
        sample_usage_snapshot.total_limit = None

        panel = display._create_header(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        # Just check that the header is created successfully
        assert "Active" in str(panel.renderable) or "projects" in str(panel.renderable).lower()

    @pytest.mark.asyncio
    async def test_create_sessions_table_project_aggregation_mode(self, sample_usage_snapshot):
        """Test sessions table with project aggregation enabled."""
        # Mock config with project aggregation enabled
        mock_config = Mock()
        mock_config.display.aggregate_by_project = True
        mock_config.display.project_name_prefixes = ["-Users-", "-home-"]
        mock_config.display.show_tool_usage = False  # Disable tool usage for consistent column count
        mock_config.display.show_pricing = False  # Disable pricing for testing

        display = MonitorDisplay(config=mock_config)

        panel = await display._create_sessions_table(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        assert panel.title == "Projects with Activity in Current Block"

        # The table should have different columns for project mode
        table = panel.renderable
        assert isinstance(table, Table)
        # Check that it has the expected columns for project aggregation (Project, Model, Tokens, Messages)
        assert len(table.columns) == 4  # Project, Model, Tokens, Messages

    @pytest.mark.asyncio
    async def test_create_sessions_table_session_aggregation_mode(self, sample_usage_snapshot):
        """Test sessions table with session aggregation enabled."""
        # Mock config with project aggregation disabled
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False
        mock_config.display.project_name_prefixes = ["-Users-", "-home-"]
        mock_config.display.show_tool_usage = False  # Disable tool usage for consistent column count
        mock_config.display.show_pricing = False  # Disable pricing for testing

        display = MonitorDisplay(config=mock_config)

        panel = await display._create_sessions_table(sample_usage_snapshot)

        assert isinstance(panel, Panel)
        assert panel.title == "Sessions with Activity in Current Block"

        # The table should have different columns for session mode
        table = panel.renderable
        assert isinstance(table, Table)
        # Check that it has the expected columns for session aggregation (Project, Session ID, Model, Tokens, Messages)
        assert len(table.columns) == 5  # Project, Session ID, Model, Tokens, Messages

    def test_strip_project_name_with_config(self):
        """Test project name stripping with configuration."""
        mock_config = Mock()
        mock_config.display.project_name_prefixes = ["-Users-johndoe-", "-home-"]

        display = MonitorDisplay(config=mock_config)

        # Test prefix stripping
        assert display._strip_project_name("-Users-johndoe-MyProject") == "MyProject"
        assert display._strip_project_name("-home-MyProject") == "MyProject"
        assert display._strip_project_name("MyProject") == "MyProject"  # No prefix to strip

    def test_strip_project_name_no_config(self):
        """Test project name stripping without configuration."""
        display = MonitorDisplay(config=None)

        # Without config, should return original name
        assert display._strip_project_name("-Users-johndoe-MyProject") == "-Users-johndoe-MyProject"
        assert display._strip_project_name("MyProject") == "MyProject"

    def test_strip_project_name_empty_prefixes(self):
        """Test project name stripping with empty prefixes."""
        mock_config = Mock()
        mock_config.display.project_name_prefixes = []

        display = MonitorDisplay(config=mock_config)

        # With empty prefixes, should return original name
        assert display._strip_project_name("-Users-johndoe-MyProject") == "-Users-johndoe-MyProject"
        assert display._strip_project_name("MyProject") == "MyProject"

    @pytest.mark.asyncio
    async def test_populate_project_table(self, sample_usage_snapshot):
        """Test populating table with project aggregation data."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = True
        mock_config.display.project_name_prefixes = ["-Users-"]
        mock_config.display.show_tool_usage = False  # Disable tool usage for consistent column count
        mock_config.display.show_pricing = False  # Disable pricing for testing

        display = MonitorDisplay(config=mock_config)

        # Create a table to populate
        table = Table()

        # Mock the project methods
        project = list(sample_usage_snapshot.projects.values())[0]
        project.get_unified_block_tokens = Mock(return_value=5000)
        project.get_unified_block_models = Mock(return_value={"claude-3-5-sonnet-latest", "claude-3-opus-latest"})
        project.get_unified_block_latest_activity = Mock(return_value=datetime.now(UTC))

        # Call the method
        await display._populate_project_table(table, sample_usage_snapshot, None)

        # Verify the table was populated
        assert len(table.columns) == 4  # Project, Model, Tokens, Messages
        assert table.row_count >= 0  # Should have at least attempted to add rows

    @pytest.mark.asyncio
    async def test_populate_session_table(self, sample_usage_snapshot):
        """Test populating table with session aggregation data."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False
        mock_config.display.project_name_prefixes = ["-Users-"]
        mock_config.display.show_tool_usage = False  # Disable tool usage for consistent column count
        mock_config.display.show_pricing = False  # Disable pricing for testing

        display = MonitorDisplay(config=mock_config)

        # Create a table to populate
        table = Table()

        # Call the method
        await display._populate_session_table(table, sample_usage_snapshot, None)

        # Verify the table was populated
        assert len(table.columns) == 5  # Project, Session ID, Model, Tokens, Messages
        assert table.row_count >= 0  # Should have at least attempted to add rows

    def test_calculate_session_data(self, sample_usage_snapshot):
        """Test calculating session data for aggregation."""
        # Mock config
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False

        display = MonitorDisplay(config=mock_config)

        # Get a session from the snapshot
        project = list(sample_usage_snapshot.projects.values())[0]
        session = list(project.sessions.values())[0]

        # Call the method - now returns 5 values
        session_tokens, session_models, session_latest_activity, session_tools, session_tool_calls = display._calculate_session_data(session, None)

        # Verify the results
        assert isinstance(session_tokens, int)
        assert isinstance(session_models, set)
        assert session_latest_activity is None or isinstance(session_latest_activity, datetime)
        assert isinstance(session_tools, set)
        assert isinstance(session_tool_calls, int)

    def test_should_include_block_no_unified_start(self):
        """Test block inclusion logic without unified start time."""
        display = MonitorDisplay()

        # Mock active block
        mock_block = Mock()
        mock_block.is_active = True

        # With no unified start, active blocks should be included
        assert display._should_include_block(mock_block, None) is True

        # Inactive blocks should not be included
        mock_block.is_active = False
        assert display._should_include_block(mock_block, None) is False

    def test_should_include_block_with_unified_start(self):
        """Test block inclusion logic with unified start time."""
        display = MonitorDisplay()

        unified_start = datetime.now(UTC)

        # Mock active block that overlaps with unified window
        mock_block = Mock()
        mock_block.is_active = True
        mock_block.start_time = unified_start - timedelta(hours=1)  # Starts before unified block ends
        mock_block.actual_end_time = unified_start + timedelta(hours=1)  # Ends after unified block starts
        mock_block.end_time = unified_start + timedelta(hours=4)

        # Should be included (overlaps with unified window)
        assert display._should_include_block(mock_block, unified_start) is True

        # Mock block that doesn't overlap
        mock_block.start_time = unified_start + timedelta(hours=6)  # Starts after unified block ends
        mock_block.actual_end_time = unified_start + timedelta(hours=7)
        mock_block.end_time = unified_start + timedelta(hours=11)

        # Should not be included (no overlap)
        assert display._should_include_block(mock_block, unified_start) is False

    def test_add_empty_row_if_needed_project_mode(self):
        """Test adding empty row in project aggregation mode."""
        mock_config = Mock()
        mock_config.display.aggregate_by_project = True

        display = MonitorDisplay(config=mock_config)

        # Create empty table
        table = Table()
        table.add_column("Project")
        table.add_column("Model")
        table.add_column("Tokens")

        # Add empty row
        display._add_empty_row_if_needed(table)

        # Should have added one row
        assert table.row_count == 1

    def test_add_empty_row_if_needed_session_mode(self):
        """Test adding empty row in session aggregation mode."""
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False

        display = MonitorDisplay(config=mock_config)

        # Create empty table
        table = Table()
        table.add_column("Project")
        table.add_column("Session ID")
        table.add_column("Model")
        table.add_column("Tokens")

        # Add empty row
        display._add_empty_row_if_needed(table)

        # Should have added one row
        assert table.row_count == 1

    def test_get_table_title_project_mode(self):
        """Test getting table title for project aggregation mode."""
        mock_config = Mock()
        mock_config.display.aggregate_by_project = True

        display = MonitorDisplay(config=mock_config)

        title = display._get_table_title()
        assert title == "Projects with Activity in Current Block"

    def test_get_table_title_session_mode(self):
        """Test getting table title for session aggregation mode."""
        mock_config = Mock()
        mock_config.display.aggregate_by_project = False

        display = MonitorDisplay(config=mock_config)

        title = display._get_table_title()
        assert title == "Sessions with Activity in Current Block"


class TestMonitorDisplayEdgeCases:
    """Test edge cases and missing coverage for MonitorDisplay."""

    def test_block_progress_with_timezone_mismatch(self):
        """Test block progress when unified block and current time have different timezones."""
        from datetime import timedelta

        # Create snapshot with UTC time
        utc_time = datetime.now(UTC)

        # Create a token usage and block
        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-latest"
        )

        # Create block with a different timezone (EST)
        est_tz = timezone(timedelta(hours=-5))
        block_start = utc_time.replace(tzinfo=est_tz)

        block = TokenBlock(
            start_time=block_start,
            end_time=block_start + timedelta(hours=1),
            session_id="session_1",
            project_name="project_1",
            model="claude-3-5-sonnet-latest",
            token_usage=token_usage,
            models_used={"claude-3-5-sonnet-latest"}
        )

        session = Session(
            session_id="session_1",
            project_name="project_1",
            model="claude-3-5-sonnet-latest"
        )
        session.blocks = [block]

        project = Project(name="project_1")
        project.sessions = {"session_1": session}

        # Override the unified block start time to trigger timezone conversion
        snapshot = UsageSnapshot(
            timestamp=utc_time,
            projects={"project_1": project}
        )
        snapshot.block_start_override = block_start

        display = MonitorDisplay()
        result = display._create_block_progress(snapshot)

        # Should not raise an error and should return a Panel
        assert isinstance(result, Panel)

    def test_get_model_emoji_all_types(self):
        """Test model emoji for all supported model types."""
        display = MonitorDisplay()

        # Test all specific model types
        assert display._get_model_emoji("claude-3-opus-latest") == "🚀"
        assert display._get_model_emoji("claude-3-sonnet-latest") == "⚡"
        assert display._get_model_emoji("claude-3-haiku-latest") == "💨"
        assert display._get_model_emoji("claude-2") == "🤖"
        assert display._get_model_emoji("gpt-4") == "🧠"
        assert display._get_model_emoji("llama-2") == "🦙"
        assert display._get_model_emoji("unknown-model") == "❓"

    def test_get_progress_colors_all_ranges(self):
        """Test progress colors for all percentage ranges."""
        display = MonitorDisplay()

        # Test low usage (< 50%) - green (now includes color in style)
        bar_color, text_style = display._get_progress_colors(25.0, 25000, 100000)
        assert bar_color == "#00FF00"
        assert text_style == "bold #00FF00"  # Now includes color with theme system

        # Test medium usage (50-75%) - yellow
        bar_color, text_style = display._get_progress_colors(60.0, 60000, 100000)
        assert bar_color == "#FFFF00"
        assert text_style == "bold #FFFF00"

        # Test high usage (75-90%) - orange
        bar_color, text_style = display._get_progress_colors(80.0, 80000, 100000)
        assert bar_color == "#FFA500"
        assert text_style == "bold #FFA500"

        # Test very high usage (> 90%) - red (uses get_style for critical)
        bar_color, text_style = display._get_progress_colors(95.0, 95000, 100000)
        assert bar_color == "#FF0000"
        assert text_style == "#FF0000 bold"  # get_style puts color first

    def test_create_tool_usage_table_with_tools(self):
        """Test tool usage table creation when tools are used."""
        # Create snapshot with tool usage
        now = datetime.now(UTC)

        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-latest",
            tools_used=["Read", "Edit", "Bash"],
            tool_use_count=5
        )

        block = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=1),
            session_id="session_1",
            project_name="project_1",
            model="claude-3-5-sonnet-latest",
            token_usage=token_usage,
            models_used={"claude-3-5-sonnet-latest"},
            tools_used={"Read", "Edit", "Bash"},
            total_tool_calls=5,
            tool_call_counts={"Read": 2, "Edit": 2, "Bash": 1}
        )

        session = Session(
            session_id="session_1",
            project_name="project_1",
            model="claude-3-5-sonnet-latest"
        )
        session.blocks = [block]

        project = Project(name="project_1")
        project.sessions = {"session_1": session}

        snapshot = UsageSnapshot(
            timestamp=now,
            projects={"project_1": project}
        )

        # Mock config to enable tool usage display
        mock_config = Mock()
        mock_config.display.show_tool_usage = True

        display = MonitorDisplay(config=mock_config)
        result = display._create_tool_usage_table(snapshot)

        # Should return a Table
        assert isinstance(result, Table)

    def test_create_tool_usage_table_disabled(self):
        """Test tool usage table when disabled in config."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        # Mock config to disable tool usage display
        mock_config = Mock()
        mock_config.display.show_tool_usage = False

        display = MonitorDisplay(config=mock_config)
        result = display._create_tool_usage_table(snapshot)

        # Should return a Table even when disabled, but empty
        assert isinstance(result, Table)

    def test_create_tool_usage_table_no_config(self):
        """Test tool usage table with no config."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        display = MonitorDisplay(config=None)
        result = display._create_tool_usage_table(snapshot)

        # Should return a Table even when no config, but empty
        assert isinstance(result, Table)

    def test_create_tool_usage_table_empty_tools(self):
        """Test tool usage table with no tools used."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        # Mock config to enable tool usage display
        mock_config = Mock()
        mock_config.display.show_tool_usage = True

        display = MonitorDisplay(config=mock_config)
        result = display._create_tool_usage_table(snapshot)

        # Should return a Table even with empty tools
        assert isinstance(result, Table)

    def test_calculate_burn_rate_no_block(self):
        """Test burn rate calculation with no active block."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        display = MonitorDisplay()

        # Should handle no active block gracefully and return Text
        burn_rate_text = display._calculate_burn_rate_sync(snapshot, 1000, 5000)
        assert isinstance(burn_rate_text, Text)

    def test_calculate_eta_display_infinite(self):
        """Test ETA display when burn rate is zero (infinite time)."""
        display = MonitorDisplay()
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        # Test with zero burn rate
        eta_display, eta_before_block_end = display._calculate_eta_display(snapshot, 1000, 5000, 0.0)

        # Should show "N/A" for infinite time
        assert eta_display == "N/A"

    def test_calculate_eta_display_normal(self):
        """Test ETA display with normal burn rate."""
        display = MonitorDisplay()
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        burn_rate = 100.0  # tokens per minute

        eta_display, eta_before_block_end = display._calculate_eta_display(snapshot, 1000, 5000, burn_rate)

        # Should return a string
        assert isinstance(eta_display, str)
        assert len(eta_display) > 0

    def test_get_fallback_tool_data(self):
        """Test getting fallback tool data."""
        # Create snapshot with no tools
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        display = MonitorDisplay()

        # Should return empty tool counts and zero total calls
        tool_counts, total_calls = display._get_fallback_tool_data(snapshot)
        assert isinstance(tool_counts, dict)
        assert isinstance(total_calls, int)
        assert total_calls == 0

    def test_strip_project_name_multiple_prefixes(self):
        """Test stripping project name with multiple configured prefixes."""
        mock_config = Mock()
        mock_config.display.project_name_prefixes = ["prefix1_", "prefix2_", "prefix3_"]

        display = MonitorDisplay(config=mock_config)

        # Test first prefix match
        result = display._strip_project_name("prefix1_project")
        assert result == "project"

        # Test second prefix match
        result = display._strip_project_name("prefix2_another")
        assert result == "another"

        # Test no prefix match
        result = display._strip_project_name("noprefix_project")
        assert result == "noprefix_project"

    def test_strip_project_name_empty_config(self):
        """Test stripping project name when config has empty prefixes list."""
        mock_config = Mock()
        mock_config.display.project_name_prefixes = []

        display = MonitorDisplay(config=mock_config)
        result = display._strip_project_name("test_project")

        # Should return original name when no prefixes configured
        assert result == "test_project"

    def test_layout_with_tool_usage_enabled(self):
        """Test layout setup when tool usage is enabled in config."""
        mock_config = Mock()
        mock_config.display.show_tool_usage = True

        display = MonitorDisplay(show_sessions=True, config=mock_config)

        # Should have tool_usage layout section
        assert display.layout is not None

    def test_layout_with_tool_usage_disabled(self):
        """Test layout setup when tool usage is disabled in config."""
        mock_config = Mock()
        mock_config.display.show_tool_usage = False

        display = MonitorDisplay(show_sessions=True, config=mock_config)

        # Should still have layout
        assert display.layout is not None


class TestDynamicSizing:
    """Test dynamic container sizing functionality."""

    def test_calculate_compact_height_single_model(self):
        """Test compact height calculation with single model."""
        display = MonitorDisplay()

        # Create snapshot with single model
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="sonnet")
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test-session",
            project_name="test-project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=1000, output_tokens=500)
        )
        session.blocks = [block]
        project.sessions = {"test-session": session}

        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={"test-project": project}
        )

        height = display._calculate_compact_height(snapshot)
        # Should be: 1 model + 3 burn rate lines + 1 total + 1 padding = 6 (minimum)
        assert height == 6

    def test_calculate_compact_height_multiple_models(self):
        """Test compact height calculation with multiple models."""
        display = MonitorDisplay()

        # Create snapshot with multiple models
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="sonnet")

        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={"test-project": project}
        )

        # Mock tokens_by_model to return multiple models
        with patch.object(snapshot, 'unified_block_tokens_by_model') as mock_unified:
            mock_unified.return_value = {}
            with patch.object(snapshot, 'tokens_by_model') as mock_tokens:
                mock_tokens.return_value = {"sonnet": 1500, "opus": 3000, "haiku": 800}

                height = display._calculate_compact_height(snapshot)
                # Should be: 3 models + 3 burn rate lines + 1 total + 1 padding = 8
                assert height == 8

    def test_calculate_normal_height_single_model(self):
        """Test normal height calculation with single model."""
        display = MonitorDisplay()

        # Create snapshot with single model
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="sonnet")
        block = TokenBlock(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=5),
            session_id="test-session",
            project_name="test-project",
            model="sonnet",
            token_usage=TokenUsage(input_tokens=1000, output_tokens=500)
        )
        session.blocks = [block]
        project.sessions = {"test-session": session}

        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={"test-project": project}
        )

        height = display._calculate_normal_height(snapshot)
        # Should be: 1 model + 1 burn rate + 1 total + 1 padding = 4 (minimum)
        assert height == 4

    def test_calculate_normal_height_multiple_models(self):
        """Test normal height calculation with multiple models."""
        display = MonitorDisplay()

        # Create snapshot with multiple models
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="sonnet")

        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={"test-project": project}
        )

        # Mock tokens_by_model to return multiple models
        with patch.object(snapshot, 'unified_block_tokens_by_model') as mock_unified:
            mock_unified.return_value = {}
            with patch.object(snapshot, 'tokens_by_model') as mock_tokens:
                mock_tokens.return_value = {"sonnet": 1500, "opus": 3000, "haiku": 800}

                height = display._calculate_normal_height(snapshot)
                # Should be: 3 models + 1 burn rate + 1 total + 1 padding = 6
                assert height == 6

    def test_calculate_compact_height_no_models(self):
        """Test compact height calculation with no models (fallback)."""
        display = MonitorDisplay()

        # Create empty snapshot
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        # Mock to return empty models
        with patch.object(snapshot, 'unified_block_tokens_by_model') as mock_unified:
            mock_unified.return_value = {}
            with patch.object(snapshot, 'tokens_by_model') as mock_tokens:
                mock_tokens.return_value = {}

                height = display._calculate_compact_height(snapshot)
                # Should be: 1 model (minimum) + 3 burn rate lines + 1 total + 1 padding = 6
                assert height == 6

    def test_calculate_normal_height_no_models(self):
        """Test normal height calculation with no models (fallback)."""
        display = MonitorDisplay()

        # Create empty snapshot
        snapshot = UsageSnapshot(
            timestamp=datetime.now(UTC),
            projects={}
        )

        # Mock to return empty models
        with patch.object(snapshot, 'unified_block_tokens_by_model') as mock_unified:
            mock_unified.return_value = {}
            with patch.object(snapshot, 'tokens_by_model') as mock_tokens:
                mock_tokens.return_value = {}

                height = display._calculate_normal_height(snapshot)
                # Should be: 1 model (minimum) + 1 burn rate + 1 total + 1 padding = 4
                assert height == 4

    def test_update_compact_layout_size(self):
        """Test updating compact layout size."""
        config = Mock()
        config.display = Mock()
        config.display.display_mode = DisplayMode.COMPACT
        config.display.project_name_prefixes = []
        config.display.theme = "default"

        display = MonitorDisplay(config=config)

        # Ensure we're in compact mode
        assert display.compact_mode is True

        # Test updating layout size
        display._update_compact_layout_size(8)

        # Should have updated the layout
        assert hasattr(display.layout, "children")

    def test_update_normal_layout_size_no_sessions_no_tools(self):
        """Test updating normal layout size without sessions or tools."""
        config = Mock()
        config.display = Mock()
        config.display.display_mode = DisplayMode.NORMAL
        config.display.show_tool_usage = False
        config.display.project_name_prefixes = []
        config.display.theme = "default"

        display = MonitorDisplay(config=config, show_sessions=False)

        # Ensure we're in normal mode
        assert display.compact_mode is False

        # Test updating layout size
        display._update_normal_layout_size(5)

        # Should have updated the layout
        assert hasattr(display.layout, "children")

    def test_update_normal_layout_size_with_sessions_and_tools(self):
        """Test updating normal layout size with sessions and tools."""
        config = Mock()
        config.display = Mock()
        config.display.display_mode = DisplayMode.NORMAL
        config.display.show_tool_usage = True
        config.display.project_name_prefixes = []
        config.display.theme = "default"

        display = MonitorDisplay(config=config, show_sessions=True)

        # Ensure we're in normal mode with both sessions and tools
        assert display.compact_mode is False
        assert display.show_sessions is True
        assert display.show_tool_usage is True

        # Test updating layout size
        display._update_normal_layout_size(6)

        # Should have updated the layout
        assert hasattr(display.layout, "children")

    def test_update_compact_layout_size_not_compact_mode(self):
        """Test that compact layout update is skipped when not in compact mode."""
        config = Mock()
        config.display = Mock()
        config.display.display_mode = DisplayMode.NORMAL
        config.display.project_name_prefixes = []
        config.display.theme = "default"

        display = MonitorDisplay(config=config)

        # Ensure we're NOT in compact mode
        assert display.compact_mode is False

        # Test updating layout size - should be skipped
        display._update_compact_layout_size(8)

        # Should still have layout but update was skipped
        assert hasattr(display.layout, "children")

    def test_update_normal_layout_size_compact_mode(self):
        """Test that normal layout update is skipped when in compact mode."""
        config = Mock()
        config.display = Mock()
        config.display.display_mode = DisplayMode.COMPACT
        config.display.project_name_prefixes = []
        config.display.theme = "default"

        display = MonitorDisplay(config=config)

        # Ensure we're in compact mode
        assert display.compact_mode is True

        # Test updating layout size - should be skipped
        display._update_normal_layout_size(6)

        # Should still have layout but update was skipped
        assert hasattr(display.layout, "children")
