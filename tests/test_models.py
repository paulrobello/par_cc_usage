"""
Tests for the models module.
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock, patch

from par_cc_usage.models import (
    DeduplicationState,
    Project,
    Session,
    TokenBlock,
    TokenUsage,
    UsageSnapshot,
)


class TestTokenUsage:
    """Test the TokenUsage model."""

    def test_creation_minimal(self):
        """Test creating a minimal TokenUsage instance."""
        usage = TokenUsage()

        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0
        assert usage.service_tier == "standard"

    def test_creation_with_values(self, sample_timestamp):
        """Test creating a TokenUsage instance with values."""
        usage = TokenUsage(
            input_tokens=100,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=20,
            output_tokens=50,
            service_tier="premium",
            message_id="msg_123",
            request_id="req_456",
            timestamp=sample_timestamp,
            model="claude-3-opus-latest",
        )

        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.model == "claude-3-opus-latest"

    def test_total_input_property(self):
        """Test total_input property calculation."""
        usage = TokenUsage(
            input_tokens=100,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=30,
        )

        assert usage.total_input == 150  # 100 + 20 + 30

    def test_total_output_property(self):
        """Test total_output property."""
        usage = TokenUsage(output_tokens=200)
        assert usage.total_output == 200

    def test_total_property(self):
        """Test total property calculation."""
        usage = TokenUsage(
            input_tokens=100,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=30,
            output_tokens=200,
        )

        assert usage.total == 350  # 150 + 200

    def test_adjusted_total(self):
        """Test adjusted_total with multiplier."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)

        assert usage.adjusted_total(1.0) == 150
        assert usage.adjusted_total(5.0) == 750

    def test_addition_operator(self):
        """Test adding two TokenUsage instances."""
        usage1 = TokenUsage(
            input_tokens=100,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=20,
            output_tokens=50,
            cost_usd=0.01,
        )

        usage2 = TokenUsage(
            input_tokens=200,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=30,
            output_tokens=100,
            cost_usd=0.02,
        )

        result = usage1 + usage2

        assert result.input_tokens == 300
        assert result.cache_creation_input_tokens == 30
        assert result.cache_read_input_tokens == 50
        assert result.output_tokens == 150
        assert result.cost_usd == 0.03

    def test_get_unique_hash(self):
        """Test unique hash generation."""
        usage1 = TokenUsage(message_id="msg_123", request_id="req_456")
        assert usage1.get_unique_hash() == "msg_123:req_456"

        usage2 = TokenUsage()
        assert usage2.get_unique_hash() == "no-message-id:no-request-id"



class TestTokenBlock:
    """Test the TokenBlock model."""

    def test_creation(self, sample_timestamp):
        """Test creating a TokenBlock instance."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)

        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage,
        )

        assert block.start_time == sample_timestamp
        assert block.end_time == sample_timestamp + timedelta(hours=5)
        assert block.session_id == "session_123"
        assert block.project_name == "test_project"
        assert block.model == "claude-3-opus-latest"

    def test_is_active_property(self, sample_timestamp):
        """Test is_active property."""
        usage = TokenUsage()

        # Active block
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        # Mock current time to be within the block
        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone
            assert active_block.is_active is True

    def test_is_active_gap_block(self, sample_timestamp):
        """Test that gap blocks are never active."""
        usage = TokenUsage()

        gap_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage,
            is_gap=True,
        )

        assert gap_block.is_active is False

    def test_model_multiplier_property(self):
        """Test model_multiplier property."""
        usage = TokenUsage()
        now = datetime.now(UTC)

        opus_block = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=5),
            session_id="s1",
            project_name="p1",
            model="claude-3-opus-latest",
            token_usage=usage,
        )
        assert opus_block.model_multiplier == 5.0

        sonnet_block = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=5),
            session_id="s1",
            project_name="p1",
            model="claude-3-5-sonnet-latest",
            token_usage=usage,
        )
        assert sonnet_block.model_multiplier == 1.0

    def test_adjusted_tokens_property(self):
        """Test adjusted_tokens property."""
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        now = datetime.now(UTC)

        # With model_tokens
        block1 = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=5),
            session_id="s1",
            project_name="p1",
            model="claude-3-opus-latest",
            token_usage=usage,
            model_tokens={"opus": 7500, "sonnet": 2000},
        )
        assert block1.adjusted_tokens == 9500

        # Without model_tokens (fallback)
        block2 = TokenBlock(
            start_time=now,
            end_time=now + timedelta(hours=5),
            session_id="s1",
            project_name="p1",
            model="claude-3-opus-latest",
            token_usage=usage,
            model_tokens={},
        )
        assert block2.adjusted_tokens == 7500  # 1500 * 5



class TestSession:
    """Test the Session model."""

    def test_creation(self, sample_timestamp):
        """Test creating a Session instance."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        assert session.session_id == "session_123"
        assert session.project_name == "test_project"
        assert session.model == "claude-3-opus-latest"
        assert session.blocks == []

    def test_total_tokens_property(self, sample_timestamp):
        """Test total_tokens property."""
        blocks = []
        for i in range(3):
            usage = TokenUsage(input_tokens=500, output_tokens=500)
            block = TokenBlock(
                start_time=sample_timestamp + timedelta(hours=i * 5),
                end_time=sample_timestamp + timedelta(hours=(i + 1) * 5),
                session_id="session_123",
                project_name="test_project",
                model="claude-3-5-sonnet-latest",
                token_usage=usage,
                model_tokens={"sonnet": 1000},
            )
            blocks.append(block)

        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            blocks=blocks,
        )

        assert session.total_tokens == 3000  # 3 blocks * 1000 tokens

    def test_add_block(self, sample_timestamp):
        """Test adding a block to session."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        usage = TokenUsage(input_tokens=100, output_tokens=50)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage,
            cost_usd=0.05,
        )

        session.add_block(block)

        assert len(session.blocks) == 1
        assert session.first_seen == sample_timestamp
        assert session.last_seen == sample_timestamp
        assert session.total_cost_usd == 0.05

    def test_latest_block_property(self, sample_timestamp):
        """Test latest_block property."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        # Add blocks with different start times
        times = [sample_timestamp, sample_timestamp + timedelta(hours=2), sample_timestamp + timedelta(hours=1)]
        blocks = []
        for _i, start_time in enumerate(times):
            usage = TokenUsage(input_tokens=100, output_tokens=50)
            block = TokenBlock(
                start_time=start_time,
                end_time=start_time + timedelta(hours=5),
                session_id="session_123",
                project_name="test_project",
                model="claude-3-opus-latest",
                token_usage=usage,
            )
            blocks.append(block)
            session.add_block(block)

        # Should return the block with latest start time
        latest = session.latest_block
        assert latest is not None
        assert latest.start_time == sample_timestamp + timedelta(hours=2)

    def test_latest_block_empty(self):
        """Test latest_block with no blocks."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        assert session.latest_block is None

    def test_active_block_property(self, sample_timestamp):
        """Test active_block property."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        # Add inactive block
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage1,
        )

        # Add active block
        usage2 = TokenUsage(input_tokens=200, output_tokens=100)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        session.blocks = [inactive_block, active_block]

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            assert session.active_block == active_block

    def test_active_block_none(self, sample_timestamp):
        """Test active_block when no active blocks."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        # Add only inactive block
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage,
        )
        session.blocks = [inactive_block]

        assert session.active_block is None

    def test_active_tokens_property(self, sample_timestamp):
        """Test active_tokens property in Session."""
        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        # Add active block
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        # Add inactive block
        usage2 = TokenUsage(input_tokens=200, output_tokens=100)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage2,
        )

        session.blocks = [active_block, inactive_block]

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should only count active block tokens (150 * 5 = 750)
            assert session.active_tokens == 750


class TestProject:
    """Test the Project model."""

    def test_creation(self):
        """Test creating a Project instance."""
        project = Project(name="test_project")

        assert project.name == "test_project"
        assert project.sessions == {}

    def test_total_tokens_property(self):
        """Test total_tokens property across sessions."""
        project = Project(name="test_project")

        # Add sessions with blocks
        for i in range(2):
            session = Session(
                session_id=f"session_{i}",
                project_name="test_project",
                model="claude-3-5-sonnet-latest",
            )

            # Add a block with tokens
            usage = TokenUsage(input_tokens=500, output_tokens=500)
            block = TokenBlock(
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC) + timedelta(hours=5),
                session_id=f"session_{i}",
                project_name="test_project",
                model="claude-3-5-sonnet-latest",
                token_usage=usage,
                model_tokens={"sonnet": 1000},
            )
            session.blocks.append(block)
            project.sessions[f"session_{i}"] = session

        assert project.total_tokens == 2000  # 2 sessions * 1000 tokens

    def test_active_tokens_property_project(self, sample_timestamp):
        """Test active_tokens property in Project."""
        project = Project(name="test_project")

        # Add session with active and inactive blocks
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Active block
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 1000},
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        # Inactive block
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            model_tokens={"sonnet": 500},
        )

        session.blocks = [active_block, inactive_block]
        project.sessions["session_1"] = session

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            assert project.active_tokens == 1000  # Only active block

    def test_active_sessions_property(self, sample_timestamp):
        """Test active_sessions property."""
        project = Project(name="test_project")

        # Active session
        active_session = Session(
            session_id="active_session",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="active_session",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )
        active_session.blocks = [active_block]

        # Inactive session
        inactive_session = Session(
            session_id="inactive_session",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="inactive_session",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
        )
        inactive_session.blocks = [inactive_block]

        project.sessions = {
            "active_session": active_session,
            "inactive_session": inactive_session,
        }

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            active_sessions = project.active_sessions
            assert len(active_sessions) == 1
            assert active_sessions[0].session_id == "active_session"

    def test_add_session(self):
        """Test add_session method."""
        project = Project(name="test_project")

        session = Session(
            session_id="session_123",
            project_name="test_project",
            model="claude-3-opus-latest",
        )

        project.add_session(session)

        assert "session_123" in project.sessions
        assert project.sessions["session_123"] == session

    def test_get_unified_block_tokens_with_unified_start(self, sample_timestamp):
        """Test get_unified_block_tokens with unified start time."""
        project = Project(name="test_project")

        # Create session with multiple blocks
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
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
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = unified_start + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should only return tokens from block1 (matching start time)
            assert project.get_unified_block_tokens(unified_start) == 1000  # 500 + 500

    def test_get_unified_block_tokens_no_unified_start(self, sample_timestamp):
        """Test get_unified_block_tokens with no unified start time."""
        project = Project(name="test_project")

        # Create session with active block
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        usage = TokenUsage(input_tokens=500, output_tokens=500)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        session.blocks = [block]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should return active tokens when no unified start
            assert project.get_unified_block_tokens(None) == 1000

    def test_get_unified_block_models_with_unified_start(self, sample_timestamp):
        """Test get_unified_block_models with unified start time."""
        project = Project(name="test_project")

        # Create session with multiple blocks and models
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
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
        )
        block1.models_used = {"claude-3-5-sonnet-latest", "claude-3-opus-latest"}

        # Block with different start time
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),
            end_time=unified_start + timedelta(hours=11),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-haiku-latest",
            token_usage=usage2,
            actual_end_time=unified_start + timedelta(hours=7),
        )
        block2.models_used = {"claude-3-haiku-latest"}

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = unified_start + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should only return models from block1 (matching start time)
            models = project.get_unified_block_models(unified_start)
            assert models == {"claude-3-5-sonnet-latest", "claude-3-opus-latest"}

    def test_get_unified_block_models_no_unified_start(self, sample_timestamp):
        """Test get_unified_block_models with no unified start time."""
        project = Project(name="test_project")

        # Create session with active blocks
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )
        block1.models_used = {"claude-3-5-sonnet-latest"}

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=2),
        )
        block2.models_used = {"claude-3-opus-latest"}

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=1, minutes=30)
            mock_dt.timezone = timezone

            # Should return models from all active blocks when no unified start
            models = project.get_unified_block_models(None)
            assert models == {"claude-3-5-sonnet-latest", "claude-3-opus-latest"}

    def test_get_unified_block_latest_activity_with_unified_start(self, sample_timestamp):
        """Test get_unified_block_latest_activity with unified start time."""
        project = Project(name="test_project")

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        unified_start = sample_timestamp

        # Block matching unified start time with earlier activity
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=unified_start + timedelta(hours=1),
        )

        # Another block matching unified start time with later activity
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=unified_start + timedelta(hours=3),
        )

        # Block with different start time
        usage3 = TokenUsage(input_tokens=200, output_tokens=200)
        block3 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),
            end_time=unified_start + timedelta(hours=11),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage3,
            actual_end_time=unified_start + timedelta(hours=7),
        )

        session.blocks = [block1, block2, block3]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = unified_start + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should return latest activity from blocks matching start time
            latest_activity = project.get_unified_block_latest_activity(unified_start)
            assert latest_activity == unified_start + timedelta(hours=3)

    def test_get_unified_block_latest_activity_no_unified_start(self, sample_timestamp):
        """Test get_unified_block_latest_activity with no unified start time."""
        project = Project(name="test_project")

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Active block with earlier activity
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        # Active block with later activity
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=sample_timestamp + timedelta(hours=3),
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should return latest activity from all active blocks
            latest_activity = project.get_unified_block_latest_activity(None)
            assert latest_activity == sample_timestamp + timedelta(hours=3)

    def test_get_unified_block_latest_activity_no_activity(self, sample_timestamp):
        """Test get_unified_block_latest_activity with no activity."""
        project = Project(name="test_project")

        # Empty project
        assert project.get_unified_block_latest_activity(sample_timestamp) is None
        assert project.get_unified_block_latest_activity(None) is None



class TestDeduplicationState:
    """Test the DeduplicationState model."""

    def test_creation(self):
        """Test creating a DeduplicationState instance."""
        state = DeduplicationState()

        assert state.processed_hashes == set()
        assert state.duplicate_count == 0
        assert state.total_messages == 0

    def test_is_duplicate_new_hash(self):
        """Test is_duplicate with a new hash."""
        state = DeduplicationState()

        result = state.is_duplicate("hash_123")

        assert result is False
        assert "hash_123" in state.processed_hashes
        assert state.total_messages == 1
        assert state.duplicate_count == 0

    def test_is_duplicate_existing_hash(self):
        """Test is_duplicate with an existing hash."""
        state = DeduplicationState()

        # Add hash first time
        state.is_duplicate("hash_123")

        # Add same hash second time
        result = state.is_duplicate("hash_123")

        assert result is True
        assert state.total_messages == 1  # Should not increment
        assert state.duplicate_count == 1

    def test_unique_messages_property(self):
        """Test unique_messages property."""
        state = DeduplicationState()

        # Add unique hashes
        state.is_duplicate("hash_1")
        state.is_duplicate("hash_2")

        # Add duplicate
        state.is_duplicate("hash_1")

        # Add another unique
        state.is_duplicate("hash_3")

        assert state.unique_messages == 2  # total_messages (3) - duplicate_count (1)
        assert state.total_messages == 3
        assert state.duplicate_count == 1


class TestUsageSnapshot:
    """Test the UsageSnapshot model."""

    def test_creation(self, sample_timestamp):
        """Test creating a UsageSnapshot instance."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            total_limit=500000,
        )

        assert snapshot.timestamp == sample_timestamp
        assert snapshot.projects == {}
        assert snapshot.total_limit == 500000

    def test_total_tokens_property(self, sample_timestamp):
        """Test total_tokens property."""
        # Create projects with tokens
        project1 = Project(name="project1")
        project2 = Project(name="project2")

        # Add sessions with blocks
        for project, base_tokens in [(project1, 1000), (project2, 2000)]:
            session = Session(
                session_id=f"session_{project.name}",
                project_name=project.name,
                model="claude-3-5-sonnet-latest",
            )

            usage = TokenUsage(input_tokens=base_tokens // 2, output_tokens=base_tokens // 2)
            block = TokenBlock(
                start_time=sample_timestamp,
                end_time=sample_timestamp + timedelta(hours=5),
                session_id=session.session_id,
                project_name=project.name,
                model="claude-3-5-sonnet-latest",
                token_usage=usage,
                model_tokens={"sonnet": base_tokens},
            )
            session.blocks.append(block)
            project.sessions[session.session_id] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={"project1": project1, "project2": project2},
        )

        assert snapshot.total_tokens == 3000  # 1000 + 2000

    def test_active_tokens_property(self, sample_timestamp):
        """Test active_tokens property."""
        # Create projects with active and inactive blocks
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Add active block
        active_usage = TokenUsage(input_tokens=500, output_tokens=500)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=active_usage,
            model_tokens={"sonnet": 1000},
            actual_end_time=sample_timestamp + timedelta(hours=1),  # Still active
        )

        # Add inactive block (no actual_end_time)
        inactive_usage = TokenUsage(input_tokens=300, output_tokens=300)
        inactive_block = TokenBlock(
            start_time=sample_timestamp - timedelta(hours=10),
            end_time=sample_timestamp - timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=inactive_usage,
            model_tokens={"sonnet": 600},
        )

        session.blocks = [active_block, inactive_block]
        project.sessions["session_1"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),  # Current time within active block
            projects={"test_project": project},
        )

        # Mock current time to be within active block
        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone
            assert snapshot.active_tokens == 1000  # Only the active block

    def test_active_projects_property(self, sample_timestamp):
        """Test active_projects property."""
        # Create project with active session
        active_project = Project(name="active_project")
        active_session = Session(
            session_id="active_session",
            project_name="active_project",
            model="claude-3-5-sonnet-latest",
        )

        active_usage = TokenUsage(input_tokens=500, output_tokens=500)
        active_block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="active_session",
            project_name="active_project",
            model="claude-3-5-sonnet-latest",
            token_usage=active_usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )
        active_session.blocks = [active_block]
        active_project.sessions["active_session"] = active_session

        # Create project with no active sessions
        inactive_project = Project(name="inactive_project")

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"active_project": active_project, "inactive_project": inactive_project},
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone
            active_projects = snapshot.active_projects
            assert len(active_projects) == 1
            assert active_projects[0].name == "active_project"

    def test_active_session_count_property(self, sample_timestamp):
        """Test active_session_count property."""
        project = Project(name="test_project")

        # Add two active sessions
        for i in range(2):
            session = Session(
                session_id=f"session_{i}",
                project_name="test_project",
                model="claude-3-5-sonnet-latest",
            )

            usage = TokenUsage(input_tokens=500, output_tokens=500)
            block = TokenBlock(
                start_time=sample_timestamp,
                end_time=sample_timestamp + timedelta(hours=5),
                session_id=f"session_{i}",
                project_name="test_project",
                model="claude-3-5-sonnet-latest",
                token_usage=usage,
                actual_end_time=sample_timestamp + timedelta(hours=1),
            )
            session.blocks = [block]
            project.sessions[f"session_{i}"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone
            assert snapshot.active_session_count == 2

    def test_tokens_by_model(self, sample_timestamp):
        """Test tokens_by_model method."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Block with model_tokens
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 800, "opus": 1200},
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        # Block without model_tokens (fallback)
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage2,
            model_tokens={},  # Empty - will use fallback
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        session.blocks = [block1, block2]
        project.sessions["session_1"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            tokens = snapshot.tokens_by_model()
            assert tokens["sonnet"] == 800
            assert tokens["opus"] == 1200
            assert tokens["claude-3-opus-latest"] == 2500  # 500 * 5 (opus multiplier)

    def test_unified_block_tokens(self, sample_timestamp):
        """Test unified_block_tokens method."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Block matching unified start time
        unified_start = sample_timestamp
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 1000},
            actual_end_time=unified_start + timedelta(hours=1),
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
            model_tokens={"sonnet": 500},
            actual_end_time=unified_start + timedelta(hours=7),
        )

        session.blocks = [block1, block2]
        project.sessions["session_1"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
            block_start_override=unified_start,  # Set override
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should only return tokens from block1 (matching start time)
            assert snapshot.unified_block_tokens() == 1000

    def test_unified_block_tokens_by_model(self, sample_timestamp):
        """Test unified_block_tokens_by_model method."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        unified_start = sample_timestamp

        # Block with model_tokens matching unified start
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 800, "opus": 200},
            actual_end_time=unified_start + timedelta(hours=1),
        )

        # Block without model_tokens matching unified start
        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-opus-latest",
            token_usage=usage2,
            model_tokens={},  # Will use fallback
            actual_end_time=unified_start + timedelta(hours=1),
        )

        session.blocks = [block1, block2]
        project.sessions["session_1"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
            block_start_override=unified_start,
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            tokens = snapshot.unified_block_tokens_by_model()
            assert tokens["sonnet"] == 800
            assert tokens["opus"] == 200
            assert tokens["claude-3-opus-latest"] == 2500  # fallback

    def test_add_project(self, sample_timestamp):
        """Test add_project method."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
        )

        project = Project(name="test_project")
        snapshot.add_project(project)

        assert "test_project" in snapshot.projects
        assert snapshot.projects["test_project"] == project

    def test_unified_block_start_time_with_override(self, sample_timestamp):
        """Test unified_block_start_time with override."""
        override_time = sample_timestamp + timedelta(hours=3)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
            block_start_override=override_time,
        )

        assert snapshot.unified_block_start_time == override_time

    def test_unified_block_start_time_no_active_blocks(self, sample_timestamp):
        """Test unified_block_start_time with no active blocks."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
        )

        assert snapshot.unified_block_start_time is None

    @patch("par_cc_usage.config.load_config")
    def test_unified_block_start_time_smart_strategy(self, mock_load_config, sample_timestamp):
        """Test unified_block_start_time with smart strategy."""
        # Mock config
        mock_config = Mock()
        mock_config.recent_activity_window_hours = 2
        mock_load_config.return_value = mock_config

        project = Project(name="test_project")

        session1 = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        session2 = Session(
            session_id="session_2",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        current_time = sample_timestamp + timedelta(hours=4)

        # Block with recent activity and more tokens
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)  # 1000 total
        block1 = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=current_time - timedelta(minutes=30),  # Recent activity
        )

        # Block with old activity but fewer tokens
        usage2 = TokenUsage(input_tokens=100, output_tokens=100)  # 200 total
        block2 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_2",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=current_time - timedelta(hours=3),  # Old activity
        )

        session1.blocks = [block1]
        session2.blocks = [block2]
        project.sessions["session_1"] = session1
        project.sessions["session_2"] = session2

        snapshot = UsageSnapshot(
            timestamp=current_time,
            projects={"test_project": project},
        )

        with patch("par_cc_usage.token_calculator.datetime") as mock_dt:
            mock_dt.now.return_value = current_time
            mock_dt.timezone = timezone

            # Should return start time of the active block (block1) - ccusage behavior
            # Only block1 is active (recent activity), block2 is inactive (old activity)
            expected_start = sample_timestamp  # block1 start time
            assert snapshot.unified_block_start_time == expected_start

    def test_unified_block_end_time(self, sample_timestamp):
        """Test unified_block_end_time property."""
        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        usage = TokenUsage(input_tokens=500, output_tokens=500)
        block = TokenBlock(
            start_time=sample_timestamp,
            end_time=sample_timestamp + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage,
            actual_end_time=sample_timestamp + timedelta(hours=1),
        )

        session.blocks = [block]
        project.sessions["session_1"] = session

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
        )

        current_time = sample_timestamp + timedelta(hours=2)
        with patch("par_cc_usage.token_calculator.datetime") as mock_dt:
            mock_dt.now.return_value = current_time
            mock_dt.timezone = timezone

            # Should return the active block start time + 5 hours (ccusage behavior)
            expected_start = sample_timestamp  # Block start time
            expected_end = expected_start + timedelta(hours=5)
            assert snapshot.unified_block_end_time == expected_end

    def test_unified_block_end_time_no_start(self, sample_timestamp):
        """Test unified_block_end_time when no start time."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
        )

        assert snapshot.unified_block_end_time is None

    def test_unified_block_tokens_no_unified_start(self, sample_timestamp):
        """Test unified_block_tokens when no unified start time."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
        )

        assert snapshot.unified_block_tokens() == 0

    def test_unified_block_tokens_by_model_no_unified_start(self, sample_timestamp):
        """Test unified_block_tokens_by_model when no unified start time."""
        snapshot = UsageSnapshot(
            timestamp=sample_timestamp,
            projects={},
        )

        assert snapshot.unified_block_tokens_by_model() == {}

    def test_unified_block_tokens_overlap_logic_multiple_projects(self, sample_timestamp):
        """Test that unified block tokens correctly include overlapping blocks from multiple projects."""
        unified_start = sample_timestamp

        # Create Project 1 with block starting exactly at unified start
        project1 = Project(name="project1")
        session1 = Session(
            session_id="session_1",
            project_name="project1",
            model="claude-3-5-sonnet-latest",
        )

        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=unified_start,
            end_time=unified_start + timedelta(hours=5),
            session_id="session_1",
            project_name="project1",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 1000},
            actual_end_time=unified_start + timedelta(hours=2),
        )
        session1.add_block(block1)
        project1.add_session(session1)

        # Create Project 2 with block starting 1 hour into unified block (overlaps)
        project2 = Project(name="project2")
        session2 = Session(
            session_id="session_2",
            project_name="project2",
            model="claude-3-opus-latest",
        )

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=unified_start + timedelta(hours=1),  # Overlaps with unified block
            end_time=unified_start + timedelta(hours=6),
            session_id="session_2",
            project_name="project2",
            model="claude-3-opus-latest",
            token_usage=usage2,
            model_tokens={"opus": 2500},
            actual_end_time=unified_start + timedelta(hours=3),
        )
        session2.add_block(block2)
        project2.add_session(session2)

        # Create Project 3 with block starting after unified block ends (no overlap)
        project3 = Project(name="project3")
        session3 = Session(
            session_id="session_3",
            project_name="project3",
            model="claude-3-haiku-latest",
        )

        usage3 = TokenUsage(input_tokens=200, output_tokens=100)
        block3 = TokenBlock(
            start_time=unified_start + timedelta(hours=6),  # No overlap
            end_time=unified_start + timedelta(hours=11),
            session_id="session_3",
            project_name="project3",
            model="claude-3-haiku-latest",
            token_usage=usage3,
            model_tokens={"haiku": 300},
            actual_end_time=unified_start + timedelta(hours=7),
        )
        session3.add_block(block3)
        project3.add_session(session3)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"project1": project1, "project2": project2, "project3": project3},
            block_start_override=unified_start,
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Should include tokens from project1 and project2 (overlapping), exclude project3
            total_tokens = snapshot.unified_block_tokens()
            assert total_tokens == 3500  # 1000 + 2500

            # Test by-model breakdown
            tokens_by_model = snapshot.unified_block_tokens_by_model()
            expected_models = {"sonnet": 1000, "opus": 2500}
            assert tokens_by_model == expected_models

    def test_unified_block_tokens_edge_case_overlap(self, sample_timestamp):
        """Test edge cases for block overlap detection."""
        unified_start = sample_timestamp

        project = Project(name="test_project")
        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        # Block that starts just before unified block ends but is inactive (old activity)
        usage1 = TokenUsage(input_tokens=100, output_tokens=100)
        block1 = TokenBlock(
            start_time=unified_start + timedelta(hours=4, minutes=59),  # 1 minute before end
            end_time=unified_start + timedelta(hours=9, minutes=59),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            model_tokens={"sonnet": 200},
            actual_end_time=unified_start - timedelta(hours=6),  # 6+ hours ago = inactive
        )

        # Block that ends just after unified block starts
        usage2 = TokenUsage(input_tokens=50, output_tokens=50)
        block2 = TokenBlock(
            start_time=unified_start - timedelta(hours=1),  # Starts before unified
            end_time=unified_start + timedelta(hours=4),  # Ends during unified block
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            model_tokens={"sonnet": 100},
            actual_end_time=unified_start + timedelta(hours=1),
        )

        session.blocks = [block1, block2]
        project.add_session(session)

        snapshot = UsageSnapshot(
            timestamp=sample_timestamp + timedelta(hours=2),
            projects={"test_project": project},
            block_start_override=unified_start,
        )

        with patch("par_cc_usage.models.datetime") as mock_dt:
            mock_dt.now.return_value = sample_timestamp + timedelta(hours=2)
            mock_dt.timezone = timezone

            # Only block2 should be included as it's active and overlaps
            total_tokens = snapshot.unified_block_tokens()
            assert total_tokens == 100  # Only block2 (block1 is not active)

            tokens_by_model = snapshot.unified_block_tokens_by_model()
            assert tokens_by_model == {"sonnet": 100}  # Only block2

    def test_project_block_overlaps_unified_window_helper(self, sample_timestamp):
        """Test the _block_overlaps_unified_window helper method."""
        project = Project(name="test_project")
        unified_start = sample_timestamp

        # Mock block that overlaps
        overlapping_block = Mock()
        overlapping_block.start_time = unified_start + timedelta(hours=1)
        overlapping_block.actual_end_time = unified_start + timedelta(hours=3)
        overlapping_block.end_time = unified_start + timedelta(hours=6)

        assert project._block_overlaps_unified_window(overlapping_block, unified_start) is True

        # Mock block that doesn't overlap (starts after unified ends)
        non_overlapping_block = Mock()
        non_overlapping_block.start_time = unified_start + timedelta(hours=6)
        non_overlapping_block.actual_end_time = unified_start + timedelta(hours=7)
        non_overlapping_block.end_time = unified_start + timedelta(hours=11)

        assert project._block_overlaps_unified_window(non_overlapping_block, unified_start) is False

        # Mock block that starts before but ends during unified window
        early_overlapping_block = Mock()
        early_overlapping_block.start_time = unified_start - timedelta(hours=2)
        early_overlapping_block.actual_end_time = unified_start + timedelta(hours=1)
        early_overlapping_block.end_time = unified_start + timedelta(hours=3)

        assert project._block_overlaps_unified_window(early_overlapping_block, unified_start) is True

    @patch("par_cc_usage.config.load_config")
    def test_smart_strategy_no_recent_activity(self, mock_load_config, sample_timestamp):
        """Test smart strategy when no blocks have recent activity."""
        # Mock config
        mock_config = Mock()
        mock_config.recent_activity_window_hours = 1  # Very short window
        mock_load_config.return_value = mock_config

        project = Project(name="test_project")

        session1 = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        session2 = Session(
            session_id="session_2",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
        )

        current_time = sample_timestamp + timedelta(hours=5)

        # All blocks have old activity (beyond window)
        usage1 = TokenUsage(input_tokens=500, output_tokens=500)
        block1 = TokenBlock(
            start_time=sample_timestamp + timedelta(hours=1),  # Later start
            end_time=sample_timestamp + timedelta(hours=6),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage1,
            actual_end_time=current_time - timedelta(hours=3),  # Old activity
        )

        usage2 = TokenUsage(input_tokens=300, output_tokens=200)
        block2 = TokenBlock(
            start_time=sample_timestamp,  # Earlier start
            end_time=sample_timestamp + timedelta(hours=6),  # Extend end time
            session_id="session_2",
            project_name="test_project",
            model="claude-3-5-sonnet-latest",
            token_usage=usage2,
            actual_end_time=current_time - timedelta(hours=2),  # Old activity
        )

        session1.blocks = [block1]
        session2.blocks = [block2]
        project.sessions["session_1"] = session1
        project.sessions["session_2"] = session2

        snapshot = UsageSnapshot(
            timestamp=current_time,
            projects={"test_project": project},
        )

        with patch("par_cc_usage.token_calculator.datetime") as mock_dt:
            mock_dt.now.return_value = current_time
            mock_dt.timezone = timezone

            # Should return the earliest active block start time (ccusage behavior)
            # block1 is active (activity 3h ago, current < end), block2 is inactive (current == end)
            expected_start = sample_timestamp + timedelta(hours=1)  # block1 started later but is the only active one
            assert snapshot.unified_block_start_time == expected_start
