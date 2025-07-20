"""Tests for auto-scaling functionality."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import pytest

from par_cc_usage.config import Config, update_max_encountered_values, update_max_encountered_values_async
from par_cc_usage.models import Project, Session, TokenBlock, TokenUsage, UsageSnapshot


class TestAutoScaling:
    """Test auto-scaling functionality."""

    def test_update_max_encountered_values_new_block_maximum(self):
        """Test updating max encountered values when new block maximum is found."""
        config = Config()

        # Create a usage snapshot with higher values than defaults
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="opus")

        # Create a token block with high values
        token_usage = TokenUsage(
            input_tokens=100_000,
            output_tokens=50_000,
            message_count=10
        )

        start_time = datetime.now()
        block = TokenBlock(
            start_time=start_time,
            end_time=start_time + timedelta(hours=5),
            session_id="test-session",
            project_name="test-project",
            model="opus",
            token_usage=token_usage,
            message_count=10,
            cost_usd=25.50
        )
        # Set model_tokens to simulate adjusted tokens
        block.model_tokens = {"opus": 750_000}  # 150k * 5x multiplier

        session.add_block(block)
        project.add_session(session)

        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock unified block methods to return high values
        with patch.object(usage_snapshot, 'unified_block_tokens', return_value=750_000):
            with patch.object(usage_snapshot, 'unified_block_messages', return_value=10):
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                    config_file = Path(tmp.name)

                    # Call the function
                    result = update_max_encountered_values(config, usage_snapshot, config_file)

                    # Verify it returned True (config was updated)
                    assert result is True

                    # Verify the max values were updated (sync function only updates tokens and messages)
                    assert config.max_unified_block_tokens_encountered == 750_000  # adjusted tokens
                    assert config.max_unified_block_messages_encountered == 10
                    # Cost updates require async function - sync function doesn't update cost
                    assert config.max_unified_block_cost_encountered == 0.0  # unchanged by sync function

                    # Clean up
                    config_file.unlink()

    def test_update_max_encountered_values_no_change(self):
        """Test that no config update occurs when values are not higher."""
        config = Config()
        # Set high initial values
        # Set high initial values for unified block fields
        config.max_unified_block_tokens_encountered = 1_000_000
        config.max_unified_block_messages_encountered = 100
        config.max_unified_block_cost_encountered = 100.0

        # Create a usage snapshot with lower values
        project = Project(name="test-project")
        session = Session(session_id="test-session", project_name="test-project", model="opus")

        token_usage = TokenUsage(
            input_tokens=10_000,
            output_tokens=5_000,
            message_count=5
        )

        start_time = datetime.now()
        block = TokenBlock(
            start_time=start_time,
            end_time=start_time + timedelta(hours=5),
            session_id="test-session",
            project_name="test-project",
            model="opus",
            token_usage=token_usage,
            message_count=5,
            cost_usd=2.50
        )
        block.model_tokens = {"opus": 75_000}  # 15k * 5x multiplier

        session.add_block(block)
        project.add_session(session)

        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock unified block methods to return lower values
        with patch.object(usage_snapshot, 'unified_block_tokens', return_value=75_000):
            with patch.object(usage_snapshot, 'unified_block_messages', return_value=5):
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                    config_file = Path(tmp.name)

                    # Call the function
                    result = update_max_encountered_values(config, usage_snapshot, config_file)

                    # Verify it returned False (no config update)
                    assert result is False

                    # Verify the max values were not changed
                    assert config.max_unified_block_tokens_encountered == 1_000_000
                    assert config.max_unified_block_messages_encountered == 100
                    assert config.max_unified_block_cost_encountered == 100.0
                    assert config.max_unified_block_tokens_encountered == 1_000_000
                    assert config.max_unified_block_messages_encountered == 100

                    # Clean up
                    config_file.unlink()

    def test_auto_scale_token_limit_exceeded(self):
        """Test that token limit is auto-scaled when exceeded."""
        config = Config()
        config.token_limit = 100_000  # Set initial limit

        # Create usage snapshot with unified tokens exceeding limit
        project = Project(name="test-project")
        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock unified block methods to return values exceeding limit
        with patch.object(usage_snapshot, 'unified_block_tokens', return_value=150_000):
            with patch.object(usage_snapshot, 'unified_block_messages', return_value=10):
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                    config_file = Path(tmp.name)

                    # Call the function
                    result = update_max_encountered_values(config, usage_snapshot, config_file)

                    # Verify it returned True (config was updated)
                    assert result is True

                    # Verify the token limit was auto-scaled with 20% buffer
                    expected_limit = int(150_000 * 1.2)  # 180,000
                    assert config.token_limit == expected_limit

                    # Clean up
                    config_file.unlink()

    def test_auto_scale_message_limit_exceeded(self):
        """Test that message limit is auto-scaled when exceeded."""
        config = Config()
        config.message_limit = 20  # Set initial limit

        # Create usage snapshot with unified messages exceeding limit
        project = Project(name="test-project")
        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock unified block methods to return values exceeding limit
        with patch.object(usage_snapshot, 'unified_block_tokens', return_value=50_000):
            with patch.object(usage_snapshot, 'unified_block_messages', return_value=30):
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                    config_file = Path(tmp.name)

                    # Call the function
                    result = update_max_encountered_values(config, usage_snapshot, config_file)

                    # Verify it returned True (config was updated)
                    assert result is True

                    # Verify the message limit was auto-scaled with 20% buffer
                    expected_limit = int(30 * 1.2)  # 36
                    assert config.message_limit == expected_limit

                    # Clean up
                    config_file.unlink()

    def test_auto_scale_no_limit_set(self):
        """Test that no auto-scaling occurs when limits are not set."""
        config = Config()
        config.token_limit = None
        config.message_limit = None

        # Create usage snapshot with high values
        project = Project(name="test-project")
        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock unified block methods to return high values
        with patch.object(usage_snapshot, 'unified_block_tokens', return_value=500_000):
            with patch.object(usage_snapshot, 'unified_block_messages', return_value=50):
                with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                    config_file = Path(tmp.name)

                    # Call the function
                    result = update_max_encountered_values(config, usage_snapshot, config_file)

                    # Verify it returned True (max values were updated)
                    assert result is True

                    # Verify limits remained None (no auto-scaling)
                    assert config.token_limit is None
                    assert config.message_limit is None

                    # But max encountered values should be updated
                    assert config.max_unified_block_tokens_encountered == 500_000
                    assert config.max_unified_block_messages_encountered == 50

                    # Clean up
                    config_file.unlink()

    @pytest.mark.asyncio
    async def test_update_max_encountered_values_async_with_cost(self):
        """Test async function that includes cost calculation."""
        config = Config()

        # Create usage snapshot
        project = Project(name="test-project")
        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock the async cost calculation
        mock_cost = 15.75
        with patch.object(usage_snapshot, 'get_unified_block_total_cost', return_value=mock_cost):
            with patch.object(usage_snapshot, 'unified_block_tokens', return_value=100_000):
                with patch.object(usage_snapshot, 'unified_block_messages', return_value=10):
                    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                        config_file = Path(tmp.name)

                        # Call the async function
                        result = await update_max_encountered_values_async(config, usage_snapshot, config_file)

                        # Verify it returned True (config was updated)
                        assert result is True

                        # Verify the max cost was updated
                        assert config.max_unified_block_cost_encountered == mock_cost

                        # Clean up
                        config_file.unlink()

    @pytest.mark.asyncio
    async def test_update_max_encountered_values_async_cost_error(self):
        """Test async function gracefully handles cost calculation errors."""
        config = Config()

        # Create usage snapshot
        project = Project(name="test-project")
        usage_snapshot = UsageSnapshot(
            timestamp=datetime.now(),
            projects={"test-project": project}
        )

        # Mock the async cost calculation to raise an error
        with patch.object(usage_snapshot, 'get_unified_block_total_cost', side_effect=Exception("Cost calc error")):
            with patch.object(usage_snapshot, 'unified_block_tokens', return_value=100_000):
                with patch.object(usage_snapshot, 'unified_block_messages', return_value=10):
                    with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as tmp:
                        config_file = Path(tmp.name)

                        # Call the async function
                        result = await update_max_encountered_values_async(config, usage_snapshot, config_file)

                        # Verify it still returned True (sync updates succeeded)
                        assert result is True

                        # Verify the max values were still updated (sync part)
                        assert config.max_unified_block_tokens_encountered == 100_000
                        assert config.max_unified_block_messages_encountered == 10

                        # But cost should remain default (error was handled)
                        assert config.max_unified_block_cost_encountered == 0.0

                        # Clean up
                        config_file.unlink()
