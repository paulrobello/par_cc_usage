"""
Tests for the list_command module.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, mock_open, patch
import tempfile
import json
import csv
import asyncio

import pytest
from rich.console import Console

from par_cc_usage.enums import OutputFormat, SortBy, TimeFormat
from par_cc_usage.list_command import ListDisplay, display_usage_list
from par_cc_usage.models import UsageSnapshot, Project, Session, TokenBlock, TokenUsage


class TestListCommand:
    """Test the list_command functionality."""

    def test_display_usage_list_no_data(self, capsys):
        """Test display with no data."""
        # Create empty snapshot
        snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={},
            total_limit=None,
        )

        console = Console()
        # Should not raise an error even with no data
        asyncio.run(display_usage_list(
            snapshot=snapshot,
            output_format=OutputFormat.TABLE,
            console=console
        ))

    def test_display_usage_list_table_format(self, sample_usage_snapshot, capsys):
        """Test display with table format."""
        console = Console()
        asyncio.run(display_usage_list(
            snapshot=sample_usage_snapshot,
            output_format=OutputFormat.TABLE,
            console=console
        ))

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_display_usage_list_csv_format(self, sample_usage_snapshot, capsys):
        """Test display with CSV format."""
        console = Console()
        asyncio.run(display_usage_list(
            snapshot=sample_usage_snapshot,
            output_format=OutputFormat.CSV,
            console=console
        ))

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_display_usage_list_json_format(self, sample_usage_snapshot, capsys):
        """Test display with JSON format."""
        import json

        console = Console()
        asyncio.run(display_usage_list(
            snapshot=sample_usage_snapshot,
            output_format=OutputFormat.JSON,
            console=console
        ))

        captured = capsys.readouterr()
        # Should be valid JSON
        try:
            data = json.loads(captured.out)
            assert isinstance(data, (dict, list))  # Can be either dict or list
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.CSV.value == "csv"

    def test_sort_by_enum(self):
        """Test SortBy enum values."""
        assert SortBy.TOKENS.value == "tokens"
        assert SortBy.TIME.value == "time"
        assert SortBy.PROJECT.value == "project"
        assert SortBy.SESSION.value == "session"
        assert SortBy.MODEL.value == "model"


class TestListDisplay:
    """Test the ListDisplay class methods."""

    @pytest.fixture
    def list_display(self):
        """Create a ListDisplay instance for testing."""
        return ListDisplay(time_format=TimeFormat.TWENTY_FOUR_HOUR)

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        now = datetime.now(timezone.utc)

        # Create token usage
        token_usage1 = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-latest"
        )
        token_usage2 = TokenUsage(
            input_tokens=200,
            output_tokens=100,
            model="claude-3-opus-latest"
        )

        # Create blocks
        block1 = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=1),
            session_id="session_1",
            project_name="project_a",
            model="claude-3-5-sonnet-latest",
            token_usage=token_usage1,
            models_used={"claude-3-5-sonnet-latest"},
            messages_processed=5
        )
        block2 = TokenBlock(
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=3),
            session_id="session_2",
            project_name="project_b",
            model="claude-3-opus-latest",
            token_usage=token_usage2,
            models_used={"claude-3-opus-latest"},
            messages_processed=3
        )

        # Create sessions
        session1 = Session(
            session_id="session_1",
            project_name="project_a",
            model="claude-3-5-sonnet-latest"
        )
        session1.blocks = [block1]

        session2 = Session(
            session_id="session_2",
            project_name="project_b",
            model="claude-3-opus-latest"
        )
        session2.blocks = [block2]

        # Create projects
        project_a = Project(name="project_a")
        project_a.sessions = {"session_1": session1}

        project_b = Project(name="project_b")
        project_b.sessions = {"session_2": session2}

        # Create snapshot
        snapshot = UsageSnapshot(
            timestamp=now,
            projects={"project_a": project_a, "project_b": project_b},
            total_limit=1000
        )

        return snapshot, [(project_a, session1, block1), (project_b, session2, block2)]

    def test_initialization_default(self):
        """Test ListDisplay initialization with defaults."""
        display = ListDisplay()
        assert display.console is not None
        assert display.time_format == "24h"

    def test_initialization_with_console(self):
        """Test ListDisplay initialization with custom console."""
        console = Console()
        display = ListDisplay(console=console, time_format="12h")
        assert display.console is console
        assert display.time_format == "12h"

    def test_get_all_blocks(self, list_display, sample_data):
        """Test getting all blocks from snapshot."""
        snapshot, expected_blocks = sample_data
        blocks = list_display.get_all_blocks(snapshot)

        assert len(blocks) == 2
        assert all(len(block_tuple) == 3 for block_tuple in blocks)  # (project, session, block)

    def test_get_all_blocks_empty_snapshot(self, list_display):
        """Test getting blocks from empty snapshot."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={}
        )
        blocks = list_display.get_all_blocks(snapshot)
        assert blocks == []

    def test_sort_blocks_by_project(self, list_display, sample_data):
        """Test sorting blocks by project name."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)
        sorted_blocks = list_display.sort_blocks(blocks, SortBy.PROJECT)

        # Should be sorted by project name (project_a, project_b)
        assert sorted_blocks[0][0].name == "project_a"
        assert sorted_blocks[1][0].name == "project_b"

    def test_sort_blocks_by_session(self, list_display, sample_data):
        """Test sorting blocks by session ID."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)
        sorted_blocks = list_display.sort_blocks(blocks, SortBy.SESSION)

        # Should be sorted by session ID (session_1, session_2)
        assert sorted_blocks[0][1].session_id == "session_1"
        assert sorted_blocks[1][1].session_id == "session_2"

    def test_sort_blocks_by_tokens(self, list_display, sample_data):
        """Test sorting blocks by token count (descending)."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)
        sorted_blocks = list_display.sort_blocks(blocks, SortBy.TOKENS)

        # Should be sorted by tokens descending (opus has more tokens due to 5x multiplier)
        assert sorted_blocks[0][2].adjusted_tokens >= sorted_blocks[1][2].adjusted_tokens

    def test_sort_blocks_by_time(self, list_display, sample_data):
        """Test sorting blocks by time (descending)."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)
        sorted_blocks = list_display.sort_blocks(blocks, SortBy.TIME)

        # Should be sorted by time descending (newest first)
        assert sorted_blocks[0][2].start_time >= sorted_blocks[1][2].start_time

    def test_sort_blocks_by_model(self, list_display, sample_data):
        """Test sorting blocks by model name."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)
        sorted_blocks = list_display.sort_blocks(blocks, SortBy.MODEL)

        # Should be sorted by model name alphabetically
        model_names = [block[2].model for block in sorted_blocks]
        assert model_names == sorted(model_names)

    def test_sort_blocks_unknown_sort_by(self, list_display, sample_data):
        """Test sorting with unknown sort_by value returns original order."""
        snapshot, _ = sample_data
        blocks = list_display.get_all_blocks(snapshot)

        # Use a string that's not a valid SortBy enum
        sorted_blocks = list_display.sort_blocks(blocks, "unknown")

        # Should return blocks in original order
        assert sorted_blocks == blocks

    def test_display_table_with_data(self, sample_data):
        """Test table display with data."""
        snapshot, _ = sample_data
        console = Console(file=Mock())  # Capture output
        display = ListDisplay(console=console)

        # Should not raise an error
        asyncio.run(display.display_table(snapshot, SortBy.TOKENS))

        # Verify console.print was called
        assert console.file.write.called

    def test_display_table_empty_data(self):
        """Test table display with empty data."""
        snapshot = UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            projects={}
        )
        console = Console(file=Mock())
        display = ListDisplay(console=console)

        # Should not raise an error
        asyncio.run(display.display_table(snapshot, SortBy.TOKENS))

        # Verify console.print was called (even for empty table)
        assert console.file.write.called

    def test_export_json_to_file(self, sample_data):
        """Test JSON export to file."""
        snapshot, _ = sample_data
        console = Console(file=Mock())
        display = ListDisplay(console=console)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = Path(f.name)

        try:
            asyncio.run(display.export_json(snapshot, output_file, SortBy.TOKENS))

            # Verify file was created and contains valid JSON
            assert output_file.exists()
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert 'timestamp' in data
            assert 'blocks' in data
            assert len(data['blocks']) == 2

        finally:
            if output_file.exists():
                output_file.unlink()

    def test_export_csv_to_file(self, sample_data):
        """Test CSV export to file."""
        snapshot, _ = sample_data
        console = Console(file=Mock())
        display = ListDisplay(console=console)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = Path(f.name)

        try:
            asyncio.run(display.export_csv(snapshot, output_file, SortBy.TOKENS))

            # Verify file was created and contains valid CSV
            assert output_file.exists()
            with open(output_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Should have header + 2 data rows
            assert len(rows) == 3
            assert 'Project' in rows[0]  # Header row

        finally:
            if output_file.exists():
                output_file.unlink()


class TestDisplayUsageListFunction:
    """Test the display_usage_list function edge cases."""

    @pytest.fixture
    def sample_snapshot(self):
        """Create a simple snapshot for testing."""
        now = datetime.now(timezone.utc)

        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="claude-3-5-sonnet-latest"
        )

        block = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=1),
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

        return UsageSnapshot(
            timestamp=now,
            projects={"project_1": project}
        )

    def test_display_json_to_console(self, sample_snapshot, capsys):
        """Test JSON output to console (no file)."""
        console = Console()
        asyncio.run(display_usage_list(
            snapshot=sample_snapshot,
            output_format=OutputFormat.JSON,
            sort_by=SortBy.TOKENS,
            output_file=None,
            console=console
        ))

        captured = capsys.readouterr()
        # Should contain JSON output
        assert len(captured.out) > 0

    def test_display_csv_without_output_file(self, sample_snapshot, capsys):
        """Test CSV format without output file shows error."""
        console = Console()
        asyncio.run(display_usage_list(
            snapshot=sample_snapshot,
            output_format=OutputFormat.CSV,
            sort_by=SortBy.TOKENS,
            output_file=None,
            console=console
        ))

        captured = capsys.readouterr()
        # Should show error message
        assert "CSV format requires --output option" in captured.out

    def test_display_json_with_output_file(self, sample_snapshot):
        """Test JSON export with output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = Path(f.name)

        try:
            console = Console(file=Mock())
            asyncio.run(display_usage_list(
                snapshot=sample_snapshot,
                output_format=OutputFormat.JSON,
                sort_by=SortBy.TIME,
                output_file=output_file,
                console=console
            ))

            # Verify file was created
            assert output_file.exists()

        finally:
            if output_file.exists():
                output_file.unlink()

    def test_display_csv_with_output_file(self, sample_snapshot):
        """Test CSV export with output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = Path(f.name)

        try:
            console = Console(file=Mock())
            asyncio.run(display_usage_list(
                snapshot=sample_snapshot,
                output_format=OutputFormat.CSV,
                sort_by=SortBy.PROJECT,
                output_file=output_file,
                console=console
            ))

            # Verify file was created
            assert output_file.exists()

        finally:
            if output_file.exists():
                output_file.unlink()

    def test_display_with_different_sort_options(self, sample_snapshot):
        """Test display with all different sort options."""
        console = Console(file=Mock())

        # Test all sort options
        for sort_by in [SortBy.PROJECT, SortBy.SESSION, SortBy.TOKENS, SortBy.TIME, SortBy.MODEL]:
            asyncio.run(display_usage_list(
                snapshot=sample_snapshot,
                output_format=OutputFormat.TABLE,
                sort_by=sort_by,
                console=console,
                time_format="12h"
            ))

            # Should not raise any errors
            assert console.file.write.called

    def test_display_with_12h_time_format(self, sample_snapshot):
        """Test display with 12h time format."""
        console = Console(file=Mock())
        asyncio.run(display_usage_list(
            snapshot=sample_snapshot,
            output_format=OutputFormat.TABLE,
            sort_by=SortBy.TOKENS,
            console=console,
            time_format="12h"
        ))

        # Should not raise any errors
        assert console.file.write.called


class TestCostCalculationHierarchy:
    """Test the cost calculation hierarchy and native cost support."""

    def create_token_block_with_native_cost(self, block_cost: float | None = None, usage_cost: float | None = None) -> TokenBlock:
        """Create a token block with optional native cost data."""
        # Create token usage
        token_usage = TokenUsage(
            input_tokens=1000,
            cache_creation_input_tokens=500,
            cache_read_input_tokens=200,
            output_tokens=300,
            cost_usd=usage_cost,
        )

        # Create token block
        block = TokenBlock(
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=5),
            session_id="test-session",
            project_name="test-project",
            model="claude-3-sonnet-20240229",
            token_usage=token_usage,
            cost_usd=block_cost if block_cost is not None else 0.0,
        )

        return block

    def test_validate_native_cost_valid_values(self):
        """Test that valid native cost values are accepted."""
        display = ListDisplay(show_pricing=True)

        # Valid costs should return True
        assert display._validate_native_cost(0.01) == True
        assert display._validate_native_cost(1.0) == True
        assert display._validate_native_cost(10.5) == True
        assert display._validate_native_cost(999.99) == True

    def test_validate_native_cost_invalid_values(self):
        """Test that invalid native cost values are rejected."""
        display = ListDisplay(show_pricing=True)

        # Invalid costs should return False
        assert display._validate_native_cost(None) == False
        assert display._validate_native_cost(0.0) == False
        assert display._validate_native_cost(-1.0) == False
        assert display._validate_native_cost(1500.0) == False  # Suspiciously high

    def test_get_cost_source_block_native(self):
        """Test cost source detection for block native cost."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(block_cost=5.50)

        assert display._get_cost_source(block) == "block_native"

    def test_get_cost_source_usage_native(self):
        """Test cost source detection for usage native cost."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(usage_cost=3.25)

        assert display._get_cost_source(block) == "usage_native"

    def test_get_cost_source_litellm_calculated(self):
        """Test cost source detection for LiteLLM calculated cost."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost()

        assert display._get_cost_source(block) == "litellm_calculated"

    def test_get_cost_source_priority_block_over_usage(self):
        """Test that block native cost takes priority over usage native cost."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(block_cost=5.50, usage_cost=3.25)

        assert display._get_cost_source(block) == "block_native"

    @pytest.mark.asyncio
    async def test_calculate_block_cost_block_native_priority(self):
        """Test that block native cost is used when available."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(block_cost=5.50)

        cost = await display._calculate_block_cost(block)
        assert cost == 5.50

    @pytest.mark.asyncio
    async def test_calculate_block_cost_usage_native_fallback(self):
        """Test that usage native cost is used when block cost not available."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(usage_cost=3.25)

        cost = await display._calculate_block_cost(block)
        assert cost == 3.25

    @pytest.mark.asyncio
    async def test_calculate_block_cost_litellm_fallback(self):
        """Test that LiteLLM calculation is used when no native cost available."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost()

        # Mock the calculate_token_cost function
        with patch('par_cc_usage.list_command.calculate_token_cost') as mock_calc:
            from par_cc_usage.pricing import TokenCost
            mock_calc.return_value = TokenCost(total_cost=2.75)

            cost = await display._calculate_block_cost(block)
            assert cost == 2.75
            mock_calc.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_block_cost_invalid_native_fallback(self):
        """Test that invalid native cost falls back to LiteLLM calculation."""
        display = ListDisplay(show_pricing=True)
        block = self.create_token_block_with_native_cost(block_cost=-1.0, usage_cost=0.0)

        # Mock the calculate_token_cost function
        with patch('par_cc_usage.list_command.calculate_token_cost') as mock_calc:
            from par_cc_usage.pricing import TokenCost
            mock_calc.return_value = TokenCost(total_cost=2.75)

            cost = await display._calculate_block_cost(block)
            assert cost == 2.75
            mock_calc.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_block_cost_pricing_disabled(self):
        """Test that cost calculation returns 0 when pricing is disabled."""
        display = ListDisplay(show_pricing=False)
        block = self.create_token_block_with_native_cost(block_cost=5.50)

        cost = await display._calculate_block_cost(block)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_cost_hierarchy_priority_order(self):
        """Test the complete cost calculation priority order."""
        display = ListDisplay(show_pricing=True)

        # Test 1: Block cost takes highest priority
        block1 = self.create_token_block_with_native_cost(block_cost=10.0, usage_cost=5.0)
        cost1 = await display._calculate_block_cost(block1)
        assert cost1 == 10.0

        # Test 2: Usage cost when block cost not available
        block2 = self.create_token_block_with_native_cost(usage_cost=5.0)
        cost2 = await display._calculate_block_cost(block2)
        assert cost2 == 5.0

        # Test 3: LiteLLM fallback when no native cost
        block3 = self.create_token_block_with_native_cost()
        with patch('par_cc_usage.list_command.calculate_token_cost') as mock_calc:
            from par_cc_usage.pricing import TokenCost
            mock_calc.return_value = TokenCost(total_cost=2.5)

            cost3 = await display._calculate_block_cost(block3)
            assert cost3 == 2.5
            mock_calc.assert_called_once()
