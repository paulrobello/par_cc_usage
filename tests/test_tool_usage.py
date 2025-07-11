"""
Tests for tool usage tracking functionality.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot
from par_cc_usage.token_calculator import _update_block_tool_usage, extract_token_usage, extract_tool_usage


class TestToolUsageExtraction:
    """Test tool usage extraction from JSONL data."""

    def test_extract_tool_usage_no_content(self):
        """Test extracting tool usage from message with no content."""
        message_data = {}
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == []
        assert tool_use_count == 0

    def test_extract_tool_usage_empty_content(self):
        """Test extracting tool usage from message with empty content."""
        message_data = {"content": []}
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == []
        assert tool_use_count == 0

    def test_extract_tool_usage_no_tool_use_blocks(self):
        """Test extracting tool usage from message with no tool_use blocks."""
        message_data = {
            "content": [
                {"type": "text", "text": "Hello world"},
                {"type": "image", "source": {"type": "base64", "data": "..."}}
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == []
        assert tool_use_count == 0

    def test_extract_tool_usage_single_tool(self):
        """Test extracting tool usage with a single tool call."""
        message_data = {
            "content": [
                {"type": "text", "text": "I'll help you with that."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Read",
                    "input": {"file_path": "/path/to/file.py"}
                }
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == ["Read"]
        assert tool_use_count == 1

    def test_extract_tool_usage_multiple_tools(self):
        """Test extracting tool usage with multiple tool calls."""
        message_data = {
            "content": [
                {"type": "text", "text": "Let me analyze this code."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Read",
                    "input": {"file_path": "/path/to/file.py"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_124",
                    "name": "Edit",
                    "input": {"file_path": "/path/to/file.py", "old_string": "old", "new_string": "new"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_125",
                    "name": "Bash",
                    "input": {"command": "python test.py"}
                }
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == ["Read", "Edit", "Bash"]
        assert tool_use_count == 3

    def test_extract_tool_usage_duplicate_tools(self):
        """Test extracting tool usage with duplicate tool names."""
        message_data = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Read",
                    "input": {"file_path": "/path/to/file1.py"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_124",
                    "name": "Read",
                    "input": {"file_path": "/path/to/file2.py"}
                }
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == ["Read", "Read"]
        assert tool_use_count == 2

    def test_extract_tool_usage_tool_without_name(self):
        """Test extracting tool usage from tool_use block without name."""
        message_data = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "input": {"file_path": "/path/to/file.py"}
                }
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == []
        assert tool_use_count == 0

    def test_extract_tool_usage_invalid_content_format(self):
        """Test extracting tool usage with invalid content format."""
        message_data = {"content": "not a list"}
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == []
        assert tool_use_count == 0

    def test_extract_tool_usage_mixed_content(self):
        """Test extracting tool usage with mixed content types."""
        message_data = {
            "content": [
                {"type": "text", "text": "Let me help you."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Grep",
                    "input": {"pattern": "function.*def", "path": "."}
                },
                {"type": "text", "text": "Found some functions."},
                {
                    "type": "tool_use",
                    "id": "toolu_124",
                    "name": "Write",
                    "input": {"file_path": "/path/to/new_file.py", "content": "print('hello')"}
                }
            ]
        }
        tools_used, tool_use_count = extract_tool_usage(message_data)

        assert tools_used == ["Grep", "Write"]
        assert tool_use_count == 2


class TestTokenUsageWithTools:
    """Test TokenUsage model with tool tracking."""

    def test_token_usage_creation_with_tools(self, sample_timestamp):
        """Test creating TokenUsage with tool information."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=["Read", "Edit", "Bash"],
            tool_use_count=3,
            timestamp=sample_timestamp
        )

        assert usage.tools_used == ["Read", "Edit", "Bash"]
        assert usage.tool_use_count == 3
        assert usage.total == 150

    def test_token_usage_addition_with_tools(self):
        """Test adding TokenUsage instances with tool information."""
        usage1 = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=["Read", "Edit"],
            tool_use_count=2
        )

        usage2 = TokenUsage(
            input_tokens=200,
            output_tokens=100,
            tools_used=["Bash", "Read"],
            tool_use_count=2
        )

        result = usage1 + usage2

        assert result.input_tokens == 300
        assert result.output_tokens == 150
        assert set(result.tools_used) == {"Read", "Edit", "Bash"}
        assert result.tool_use_count == 4

    def test_token_usage_addition_duplicate_tools(self):
        """Test adding TokenUsage instances with duplicate tools."""
        usage1 = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=["Read", "Edit"],
            tool_use_count=2
        )

        usage2 = TokenUsage(
            input_tokens=200,
            output_tokens=100,
            tools_used=["Read", "Edit"],
            tool_use_count=2
        )

        result = usage1 + usage2

        # Should remove duplicates but preserve counts
        assert set(result.tools_used) == {"Read", "Edit"}
        assert result.tool_use_count == 4

    def test_extract_token_usage_with_tools(self, sample_timestamp):
        """Test extract_token_usage function includes tool information."""
        data = {
            "timestamp": sample_timestamp.isoformat(),
            "version": "1.0.0",
            "requestId": "req_123"
        }

        message_data = {
            "id": "msg_456",
            "model": "claude-3-5-sonnet-20241022",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "service_tier": "standard"
            },
            "content": [
                {"type": "text", "text": "I'll help with that."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Read",
                    "input": {"file_path": "/test.py"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_124",
                    "name": "Edit",
                    "input": {"file_path": "/test.py", "old_string": "old", "new_string": "new"}
                }
            ]
        }

        token_usage = extract_token_usage(data, message_data)

        assert token_usage is not None
        assert token_usage.input_tokens == 100
        assert token_usage.output_tokens == 50
        assert token_usage.tools_used == ["Read", "Edit"]
        assert token_usage.tool_use_count == 2
        assert token_usage.model == "sonnet"


class TestTokenBlockWithTools:
    """Test TokenBlock model with tool tracking."""

    def test_token_block_creation_with_tools(self, sample_timestamp):
        """Test creating TokenBlock with tool information."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=["Read", "Edit"],
            tool_use_count=2
        )

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage,
            tools_used={"Read", "Edit", "Bash"},
            total_tool_calls=5,
            tool_call_counts={"Read": 2, "Edit": 1, "Bash": 2}
        )

        assert block.tools_used == {"Read", "Edit", "Bash"}
        assert block.total_tool_calls == 5
        assert block.tool_call_counts == {"Read": 2, "Edit": 1, "Bash": 2}

    def test_update_block_tool_usage(self, sample_timestamp):
        """Test _update_block_tool_usage function."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=["Read", "Edit", "Read"],
            tool_use_count=3
        )

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=TokenUsage(),
            tools_used={"Bash"},
            total_tool_calls=1,
            tool_call_counts={"Bash": 1}
        )

        _update_block_tool_usage(block, usage)

        assert block.tools_used == {"Bash", "Read", "Edit"}
        assert block.total_tool_calls == 4  # 1 + 3
        # Counter correctly counts: Read appears 2 times, Edit appears 1 time
        assert block.tool_call_counts == {"Bash": 1, "Read": 2, "Edit": 1}

    def test_update_block_tool_usage_empty_tools(self, sample_timestamp):
        """Test _update_block_tool_usage with no tools."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            tools_used=[],
            tool_use_count=0
        )

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=TokenUsage()
        )

        _update_block_tool_usage(block, usage)

        assert block.tools_used == set()
        assert block.total_tool_calls == 0
        assert block.tool_call_counts == {}


class TestProjectWithTools:
    """Test Project model with tool tracking methods."""

    def test_get_unified_block_tools_with_unified_start(self, sample_timestamp):
        """Test get_unified_block_tools with unified start time."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest"
        )

        unified_start = sample_timestamp

        # Block matching unified start time
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=unified_start + timedelta(hours=1),
            tools_used={"Read", "Edit", "Bash"}
        )

        # Block with different start time
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),
            end_time=unified_start + timedelta(hours=11),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=unified_start + timedelta(hours=7),
            tools_used={"Grep", "Write"}
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = unified_start + timedelta(hours=2)
            mock_dt.timezone.utc = UTC

            # Should only return tools from block1 (overlapping with unified start)
            tools = project.get_unified_block_tools(unified_start)
            assert tools == {"Read", "Edit", "Bash"}

    def test_get_unified_block_tools_no_unified_start(self, sample_timestamp):
        """Test get_unified_block_tools with no unified start time."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest"
        )

        # Active blocks with different tools
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            tools_used={"Read", "Edit"}
        )

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=2),
            tools_used={"Bash", "Write"}
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone.utc = UTC

            # Should return tools from all active blocks when no unified start
            tools = project.get_unified_block_tools(None)
            assert tools == {"Read", "Edit", "Bash", "Write"}

    def test_get_unified_block_tool_calls_with_unified_start(self, sample_timestamp):
        """Test get_unified_block_tool_calls with unified start time."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest"
        )

        unified_start = sample_timestamp

        # Block matching unified start time
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=unified_start + timedelta(hours=1),
            total_tool_calls=5
        )

        # Block with different start time
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),
            end_time=unified_start + timedelta(hours=11),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=unified_start + timedelta(hours=7),
            total_tool_calls=3
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = unified_start + timedelta(hours=2)
            mock_dt.timezone.utc = UTC

            # Should only return tool calls from block1 (overlapping with unified start)
            tool_calls = project.get_unified_block_tool_calls(unified_start)
            assert tool_calls == 5

    def test_get_unified_block_tool_calls_no_unified_start(self, sample_timestamp):
        """Test get_unified_block_tool_calls with no unified start time."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest"
        )

        # Active blocks with tool calls
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            total_tool_calls=5
        )

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=2),
            total_tool_calls=3
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone.utc = UTC

            # Should return tool calls from all active blocks when no unified start
            tool_calls = project.get_unified_block_tool_calls(None)
            assert tool_calls == 8  # 5 + 3

    def test_get_unified_block_tools_empty_project(self, sample_timestamp):
        """Test tool methods with empty project."""
        project = Project(name="test_project")

        assert project.get_unified_block_tools(sample_timestamp) == set()
        assert project.get_unified_block_tools(None) == set()
        assert project.get_unified_block_tool_calls(sample_timestamp) == 0
        assert project.get_unified_block_tool_calls(None) == 0


class TestDisplayConfigToolUsage:
    """Test display configuration for tool usage."""

    def test_display_config_tool_usage_default(self):
        """Test that show_tool_usage defaults to False."""
        from par_cc_usage.config import DisplayConfig

        config = DisplayConfig()
        assert config.show_tool_usage is False

    def test_display_config_tool_usage_enabled(self):
        """Test enabling tool usage display."""
        from par_cc_usage.config import DisplayConfig

        config = DisplayConfig(show_tool_usage=True)
        assert config.show_tool_usage is True

    def test_config_loading_with_tool_usage(self):
        """Test loading configuration with tool usage setting."""
        from par_cc_usage.config import Config, DisplayConfig

        config = Config(
            display=DisplayConfig(show_tool_usage=True)
        )
        assert config.display.show_tool_usage is True


class TestToolUsageTableDisplay:
    """Test the 3-column tool usage table display."""

    def test_create_tool_usage_table_disabled(self, sample_timestamp):
        """Test tool usage table when disabled."""
        from par_cc_usage.config import Config, DisplayConfig
        from par_cc_usage.display import MonitorDisplay
        from par_cc_usage.models import UsageSnapshot

        config = Config(display=DisplayConfig(show_tool_usage=False))
        display = MonitorDisplay(config=config)
        snapshot = UsageSnapshot(timestamp=sample_timestamp)

        table = display._create_tool_usage_table(snapshot)

        # Should have a single column with disabled message
        assert table.columns[0].header == "Status"
        # Table should have one row with disabled message
        assert len(table.rows) == 1

    def test_create_tool_usage_table_empty(self, sample_timestamp):
        """Test tool usage table with no tools."""
        from par_cc_usage.config import Config, DisplayConfig
        from par_cc_usage.display import MonitorDisplay
        from par_cc_usage.models import UsageSnapshot

        config = Config(display=DisplayConfig(show_tool_usage=True))
        display = MonitorDisplay(config=config)
        snapshot = UsageSnapshot(timestamp=sample_timestamp)

        table = display._create_tool_usage_table(snapshot)

        # Should have a single column with empty message
        assert table.columns[0].header == "Status"
        # Table should have one row with empty message
        assert len(table.rows) == 1

    def test_create_tool_usage_table_with_tools(self, sample_timestamp):
        """Test tool usage table with tools in dynamic layout."""
        from datetime import timedelta
        from unittest.mock import patch

        from par_cc_usage.config import Config, DisplayConfig
        from par_cc_usage.display import MonitorDisplay
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot

        config = Config(display=DisplayConfig(show_tool_usage=True))
        display = MonitorDisplay(config=config)

        # Create test data with multiple tools
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="sonnet"
        )

        # Create a block with 5 tools (should use single column)
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            tools_used={"Read", "Edit", "Bash", "Write", "Grep"},
            tool_call_counts={"Read": 10, "Edit": 8, "Bash": 6, "Write": 4, "Grep": 2},
            total_tool_calls=30
        )

        session.blocks = [block]
        project.add_session(session)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=1),
            projects={"test_project": project}
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone.utc = sample_timestamp.tzinfo

            table = display._create_tool_usage_table(snapshot)

            # Fixed 3-column layout (6 columns total: 3 tool + 3 count)
            assert len(table.columns) == 6

            # Should have 3 rows: 2 tool rows + 1 total row (5 tools / 3 cols = 2 rows)
            assert len(table.rows) == 3

            # Basic functionality test - table should be created
            assert table is not None
            assert hasattr(table, 'columns')
            assert hasattr(table, 'rows')

    def test_tool_distribution_algorithm(self, sample_timestamp):
        """Test that tools are properly distributed with dynamic column layout."""
        from datetime import timedelta
        from unittest.mock import patch

        from par_cc_usage.config import Config, DisplayConfig
        from par_cc_usage.display import MonitorDisplay
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot

        config = Config(display=DisplayConfig(show_tool_usage=True))
        display = MonitorDisplay(config=config)

        # Create test data with exactly 18 tools (should use 3 columns)
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="sonnet"
        )

        tools = {f"Tool{i:02d}": 20-i for i in range(18)}  # 18 tools with decreasing counts
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            tools_used=set(tools.keys()),
            tool_call_counts=tools,
            total_tool_calls=sum(tools.values())
        )

        session.blocks = [block]
        project.add_session(session)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=1),
            projects={"test_project": project}
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone.utc = sample_timestamp.tzinfo

            table = display._create_tool_usage_table(snapshot)

            # Fixed 3-column layout (6 columns total: 3 tool + 3 count)
            assert len(table.columns) == 6

            # Should have 7 rows: 6 tool rows + 1 total row (18 tools / 3 cols = 6 rows per col)
            assert len(table.rows) == 7

            # Check that table has tool content by examining rows
            assert table.row_count > 0

            # Basic verification that table structure is correct
            assert table is not None

    def test_tool_limit_40_tools(self, sample_timestamp):
        """Test that table limits to 24 tools (8 rows × 3 columns) with fixed 3-column layout."""
        from datetime import timedelta
        from unittest.mock import patch

        from par_cc_usage.config import Config, DisplayConfig
        from par_cc_usage.display import MonitorDisplay
        from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot

        config = Config(display=DisplayConfig(show_tool_usage=True))
        display = MonitorDisplay(config=config)

        # Create test data with 40 tools (should use 5 columns, limited to max_rows * 5 = 40 tools)
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="sonnet"
        )

        tools = {f"Tool{i:02d}": 40-i for i in range(40)}  # 40 tools with decreasing counts
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            tools_used=set(tools.keys()),
            tool_call_counts=tools,
            total_tool_calls=sum(tools.values())
        )

        session.blocks = [block]
        project.add_session(session)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=1),
            projects={"test_project": project}
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone.utc = sample_timestamp.tzinfo

            table = display._create_tool_usage_table(snapshot)

            # Fixed 3-column layout (6 columns total: 3 tool + 3 count)
            assert len(table.columns) == 6

            # Should have 9 rows: 8 tool rows + 1 total row (24 tools max / 3 cols = 8 rows per col)
            assert len(table.rows) == 9

            # Should display tools properly arranged
            assert len(table.rows) >= 2  # At least some tool rows + total row

            # Basic verification that table structure is correct
            assert table is not None
            assert table.row_count > 0


class TestToolUsageIntegration:
    """Integration tests for tool usage tracking."""

    def test_end_to_end_tool_tracking(self, sample_timestamp):
        """Test complete tool tracking from JSONL to display."""
        # Create sample JSONL data with tool usage
        data = {
            "timestamp": sample_timestamp.isoformat(),
            "version": "1.0.0",
            "requestId": "req_123"
        }

        message_data = {
            "id": "msg_456",
            "model": "claude-3-5-sonnet-20241022",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "service_tier": "standard"
            },
            "content": [
                {"type": "text", "text": "I'll help you analyze this code."},
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Read",
                    "input": {"file_path": "/test.py"}
                },
                {
                    "type": "tool_use",
                    "id": "toolu_124",
                    "name": "Grep",
                    "input": {"pattern": "def.*:", "path": "/test.py"}
                }
            ]
        }

        # Extract token usage with tools
        token_usage = extract_token_usage(data, message_data)
        assert token_usage is not None
        assert token_usage.tools_used == ["Read", "Grep"]
        assert token_usage.tool_use_count == 2

        # Create block and update with tool usage
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="sonnet",
            token_usage=TokenUsage()
        )

        _update_block_tool_usage(block, token_usage)

        assert block.tools_used == {"Read", "Grep"}
        assert block.total_tool_calls == 2
        assert block.tool_call_counts == {"Read": 1, "Grep": 1}

        # Test project-level aggregation
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="sonnet",
            blocks=[block]
        )

        project = Project(name="test_project")
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1)
            mock_dt.timezone.utc = UTC

            unified_tools = project.get_unified_block_tools(sample_timestamp)
            unified_tool_calls = project.get_unified_block_tool_calls(sample_timestamp)

            assert unified_tools == {"Read", "Grep"}
            assert unified_tool_calls == 2

    def test_tool_usage_aggregation_multiple_blocks(self, sample_timestamp):
        """Test tool usage aggregation across multiple blocks."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="sonnet"
        )

        # Block 1 with Read and Edit tools
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
            tools_used={"Read", "Edit"},
            total_tool_calls=3,
            tool_call_counts={"Read": 2, "Edit": 1}
        )

        # Block 2 with Bash and Read tools (overlapping with unified window)
        usage2 = TokenUsage(input_tokens=150, output_tokens=75)
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=2),
            end_time=sample_timestamp + timedelta(hours=7),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=3),
            tools_used={"Bash", "Read"},
            total_tool_calls=2,
            tool_call_counts={"Bash": 1, "Read": 1}
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2, minutes=30)
            mock_dt.timezone.utc = UTC

            # Both blocks should overlap with unified window starting at sample_timestamp
            unified_tools = project.get_unified_block_tools(sample_timestamp)
            unified_tool_calls = project.get_unified_block_tool_calls(sample_timestamp)

            assert unified_tools == {"Read", "Edit", "Bash"}
            assert unified_tool_calls == 5  # 3 + 2


class TestUsageSnapshotToolUsage:
    """Test UsageSnapshot tool usage methods."""

    def test_unified_block_tool_usage(self, sample_timestamp):
        """Test unified_block_tool_usage method."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="sonnet"
        )

        unified_start = sample_timestamp

        # Block overlapping with unified start
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage1,
            actual_end_time=unified_start + timedelta(hours=1),
            tools_used={"Read", "Edit"},
            tool_call_counts={"Read": 3, "Edit": 2},
            total_tool_calls=5
        )

        # Block overlapping with unified window (starts 2 hours into unified block)
        usage2 = TokenUsage(input_tokens=75, output_tokens=25)
        block2 = TokenBlock(
            start_time=unified_start + timedelta(hours=2),
            end_time=unified_start + timedelta(hours=7),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage2,
            actual_end_time=unified_start + timedelta(hours=3),
            tools_used={"Bash", "Read"},
            tool_call_counts={"Bash": 1, "Read": 2},
            total_tool_calls=3
        )

        # Block not overlapping (starts after unified block ends)
        usage3 = TokenUsage(input_tokens=50, output_tokens=25)
        block3 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),
            end_time=unified_start + timedelta(hours=11),
            session_id="session_1",
            project_name="test_project",
            model="sonnet",
            token_usage=usage3,
            actual_end_time=unified_start + timedelta(hours=7),
            tools_used={"Write"},
            tool_call_counts={"Write": 4},
            total_tool_calls=4
        )

        session.blocks = [block1, block2, block3]
        project.add_session(session)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
            block_start_override=unified_start
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2, minutes=30)
            mock_dt.timezone.utc = UTC

            # Should aggregate tool counts from blocks 1 and 2 (overlapping with unified block)
            tool_usage = snapshot.unified_block_tool_usage()
            assert tool_usage == {"Read": 5, "Edit": 2, "Bash": 1}  # Read: 3+2, Edit: 2, Bash: 1

            # Should sum total tool calls from overlapping blocks
            total_calls = snapshot.unified_block_total_tool_calls()
            assert total_calls == 8  # 5 + 3

    def test_unified_block_tool_usage_no_unified_start(self, sample_timestamp):
        """Test tool usage methods when no unified start time."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={}
        )

        assert snapshot.unified_block_tool_usage() == {}
        assert snapshot.unified_block_total_tool_calls() == 0

    def test_unified_block_tool_usage_empty_projects(self, sample_timestamp):
        """Test tool usage methods with empty projects."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            block_start_override=sample_timestamp
        )

        assert snapshot.unified_block_tool_usage() == {}
        assert snapshot.unified_block_total_tool_calls() == 0


# Integration with existing fixtures
@pytest.fixture
def sample_timestamp():
    """Provide a sample timestamp for testing."""
    return datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
