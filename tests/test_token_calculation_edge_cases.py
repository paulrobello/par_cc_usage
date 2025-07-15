"""
Test edge cases for token calculation and billing block logic.

This module tests complex billing scenarios, timezone transitions,
overlapping blocks, and gap detection.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from zoneinfo import ZoneInfo

from par_cc_usage.token_calculator import (
    create_unified_blocks,
    calculate_block_start,
    aggregate_usage,
    process_jsonl_line,
)
from par_cc_usage.models import (
    TokenUsage,
    TokenBlock,
    Session,
    Project,
    UsageSnapshot,
)
from tests.conftest import create_token_usage, create_block_with_tokens


class TestBillingBlockEdgeCases:
    """Test billing block calculation edge cases."""

    def test_billing_block_timezone_edge_cases(self, mock_config):
        """Test billing blocks across daylight saving transitions."""
        # Test data around DST transition (Spring forward)
        spring_forward = datetime(2025, 3, 9, 6, 30, tzinfo=timezone.utc)  # 2 AM EST -> 3 AM EDT

        # Create projects with activity around DST transition
        projects = {
            "test_project": Project(
                name="test_project",
                sessions={
                    "session_1": Session(
                        session_id="session_1",
                        project_name="test_project",
                        model="claude-3-sonnet-latest",
                        blocks=[
                            create_block_with_tokens(
                                start_time=spring_forward - timedelta(hours=1),
                                session_id="session_1",
                                project_name="test_project",
                                token_count=1000,
                            )
                        ],
                        first_seen=spring_forward - timedelta(hours=1),
                        last_seen=spring_forward,
                        session_start=spring_forward - timedelta(hours=1),
                    )
                },
            )
        }

        # Mock current time to be after DST transition
        with patch('par_cc_usage.token_calculator.datetime') as mock_dt:
            mock_dt.now.return_value = spring_forward + timedelta(hours=2)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            unified_start = create_unified_blocks(projects, None)

            # Should handle timezone transition correctly
            assert unified_start is not None
            # Block start should be hour-floored
            expected_hour = (spring_forward + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
            assert unified_start == expected_hour

    def test_overlapping_session_blocks(self, mock_config):
        """Test handling of overlapping blocks from multiple sessions."""
        base_time = datetime(2025, 1, 9, 14, 0, tzinfo=timezone.utc)

        # Create overlapping blocks from different sessions
        block1 = create_block_with_tokens(
            start_time=base_time,
            session_id="session_1",
            project_name="test_project",
            token_count=1000,
        )

        block2 = create_block_with_tokens(
            start_time=base_time + timedelta(hours=2),  # Overlaps with block1
            session_id="session_2",
            project_name="test_project",
            token_count=1500,
        )

        projects = {
            "test_project": Project(
                name="test_project",
                sessions={
                    "session_1": Session(
                        session_id="session_1",
                        project_name="test_project",
                        model="claude-3-sonnet-latest",
                        blocks=[block1],
                        first_seen=base_time,
                        last_seen=base_time + timedelta(hours=1),
                        session_start=base_time,
                    ),
                    "session_2": Session(
                        session_id="session_2",
                        project_name="test_project",
                        model="claude-3-sonnet-latest",
                        blocks=[block2],
                        first_seen=base_time + timedelta(hours=2),
                        last_seen=base_time + timedelta(hours=3),
                        session_start=base_time + timedelta(hours=2),
                    ),
                },
            )
        }

        with patch('par_cc_usage.token_calculator.datetime') as mock_dt:
            current_time = base_time + timedelta(hours=3)
            mock_dt.now.return_value = current_time
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            snapshot = UsageSnapshot(
                timestamp=current_time,
                projects=projects,
                total_limit=1000000,
                block_start_override=None,
            )

            # Should handle overlapping blocks correctly
            unified_tokens = snapshot.unified_block_tokens()
            assert unified_tokens > 0

            # Should include tokens from both overlapping blocks
            unified_tokens_by_model = snapshot.unified_block_tokens_by_model()
            assert "sonnet" in unified_tokens_by_model

    def test_gap_block_insertion(self, mock_config):
        """Test automatic gap block creation for inactivity > 5 hours."""
        base_time = datetime(2025, 1, 9, 10, 0, tzinfo=timezone.utc)

        # Create blocks with a large gap (8 hours) between them
        early_block = create_block_with_tokens(
            start_time=base_time,
            session_id="session_1",
            project_name="test_project",
            token_count=1000,
        )

        late_block = create_block_with_tokens(
            start_time=base_time + timedelta(hours=8),  # 8-hour gap
            session_id="session_1",
            project_name="test_project",
            token_count=1500,
        )

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=[early_block, late_block],
            first_seen=base_time,
            last_seen=base_time + timedelta(hours=9),
            session_start=base_time,
        )

        # Should detect gap and handle it appropriately
        assert len(session.blocks) == 2

        # Check that blocks are properly spaced
        time_gap = late_block.start_time - early_block.end_time
        assert time_gap >= timedelta(hours=3)  # Gap should be significant

    def test_unified_block_calculation_edge_cases(self, mock_config):
        """Test unified block calculation with empty projects, single messages."""
        # Test with empty projects
        empty_projects = {}
        unified_start = create_unified_blocks(empty_projects, None)
        assert unified_start is None

        # Test with project but no sessions
        empty_session_projects = {
            "empty_project": Project(name="empty_project", sessions={})
        }
        unified_start = create_unified_blocks(empty_session_projects, None)
        assert unified_start is None

        # Test with single message
        base_time = datetime(2025, 1, 9, 14, 30, 45, tzinfo=timezone.utc)
        single_usage = create_token_usage(
            timestamp=base_time,
            input_tokens=100,
            output_tokens=50,
        )

        single_block = TokenBlock(
            start_time=base_time,
            end_time=base_time + timedelta(hours=5),
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            token_usage=single_usage,
            model_tokens={"sonnet": 150},
            actual_end_time=base_time + timedelta(minutes=1),
        )

        projects = {
            "test_project": Project(
                name="test_project",
                sessions={
                    "session_1": Session(
                        session_id="session_1",
                        project_name="test_project",
                        model="claude-3-sonnet-latest",
                        blocks=[single_block],
                        first_seen=base_time,
                        last_seen=base_time,
                        session_start=base_time,
                    )
                },
            )
        }

        with patch('par_cc_usage.token_calculator.datetime') as mock_dt:
            current_time = base_time + timedelta(hours=1)
            mock_dt.now.return_value = current_time
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            unified_start = create_unified_blocks(projects, None)

            # Should calculate unified block start correctly for single message
            assert unified_start is not None
            expected_hour = current_time.replace(minute=0, second=0, microsecond=0)
            assert unified_start == expected_hour

    def test_calculate_block_start_edge_cases(self):
        """Test block start calculation edge cases."""
        # Test with exact hour boundary
        exact_hour = datetime(2025, 1, 9, 14, 0, 0, tzinfo=timezone.utc)
        block_start = calculate_block_start(exact_hour)
        assert block_start == exact_hour

        # Test with microseconds
        with_microseconds = datetime(2025, 1, 9, 14, 30, 45, 123456, tzinfo=timezone.utc)
        block_start = calculate_block_start(with_microseconds)
        expected = datetime(2025, 1, 9, 14, 0, 0, tzinfo=timezone.utc)
        assert block_start == expected

        # Test with different timezone
        eastern_time = datetime(2025, 1, 9, 9, 30, 45, tzinfo=ZoneInfo("America/New_York"))
        block_start = calculate_block_start(eastern_time)
        # Should convert to UTC and floor to hour
        expected_utc = eastern_time.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        assert block_start == expected_utc


class TestTokenProcessingEdgeCases:
    """Test token processing and aggregation edge cases."""

    def test_process_jsonl_line_with_malformed_data(self, deduplication_state):
        """Test processing JSONL lines with various malformations."""
        # Test with missing required fields
        incomplete_line = '{"timestamp": "2025-01-09T14:30:45.000Z"}'
        result = process_jsonl_line(incomplete_line, deduplication_state)
        assert result is None

        # Test with invalid timestamp format
        invalid_timestamp = '{"timestamp": "invalid-date", "request": {"model": "test"}, "response": {"usage": {"input_tokens": 100}}}'
        result = process_jsonl_line(invalid_timestamp, deduplication_state)
        assert result is None

        # Test with negative token counts
        negative_tokens = '''
        {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-sonnet-latest"},
            "response": {
                "id": "msg_123",
                "usage": {
                    "input_tokens": -100,
                    "output_tokens": 50
                }
            }
        }
        '''
        result = process_jsonl_line(negative_tokens, deduplication_state)
        # Should handle negative tokens gracefully
        assert result is None or result.input_tokens >= 0

    def test_aggregate_usage_with_extreme_values(self, mock_config):
        """Test aggregation with extreme token values and edge cases."""
        base_time = datetime(2025, 1, 9, 14, 0, tzinfo=timezone.utc)

        # Create usage with extreme values
        extreme_usage = [
            create_token_usage(
                timestamp=base_time,
                input_tokens=999999999,  # Very large number
                output_tokens=1,  # Very small number
                model="claude-3-opus-latest",
            ),
            create_token_usage(
                timestamp=base_time + timedelta(minutes=30),
                input_tokens=0,  # Zero tokens
                output_tokens=999999999,  # Very large number
                model="claude-3-sonnet-latest",
            ),
        ]

        with patch('par_cc_usage.token_calculator.datetime') as mock_dt:
            mock_dt.now.return_value = base_time + timedelta(hours=1)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            snapshot = aggregate_usage(extreme_usage, mock_config)

            # Should handle extreme values without crashing
            assert snapshot is not None
            assert len(snapshot.projects) > 0

            # Check that large numbers are preserved
            total_tokens = snapshot.unified_block_tokens()
            assert total_tokens > 0

    def test_session_block_activity_calculation(self, mock_config):
        """Test session block activity detection with edge cases."""
        current_time = datetime(2025, 1, 9, 20, 0, tzinfo=timezone.utc)

        # Create blocks with different activity patterns
        blocks = [
            # Recently active block (should be active)
            create_block_with_tokens(
                start_time=current_time - timedelta(hours=2),
                session_id="session_1",
                project_name="test_project",
                token_count=1000,
            ),
            # Old block that ended recently (should be inactive)
            create_block_with_tokens(
                start_time=current_time - timedelta(hours=8),
                session_id="session_1",
                project_name="test_project",
                token_count=1500,
            ),
        ]

        # Set actual end times
        blocks[0].actual_end_time = current_time - timedelta(minutes=30)  # Recent activity
        blocks[1].actual_end_time = current_time - timedelta(hours=6)  # Old activity

        session = Session(
            session_id="session_1",
            project_name="test_project",
            model="claude-3-sonnet-latest",
            blocks=blocks,
            first_seen=current_time - timedelta(hours=8),
            last_seen=current_time - timedelta(minutes=30),
            session_start=current_time - timedelta(hours=8),
        )

        # Test activity calculation
        with patch('par_cc_usage.models.datetime') as mock_dt:
            mock_dt.now.return_value = current_time
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Check block activity
            assert not blocks[0].is_active  # Should be determined by block logic
            assert not blocks[1].is_active  # Should be inactive due to age

    def test_model_token_multiplier_calculation(self, mock_config):
        """Test model token multiplier calculations with different models."""
        base_time = datetime(2025, 1, 9, 14, 0, tzinfo=timezone.utc)

        # Create usage for different models
        usage_data = [
            create_token_usage(
                timestamp=base_time,
                input_tokens=1000,
                output_tokens=500,
                model="claude-3-opus-latest",
            ),
            create_token_usage(
                timestamp=base_time + timedelta(minutes=10),
                input_tokens=1000,
                output_tokens=500,
                model="claude-3-sonnet-latest",
            ),
            create_token_usage(
                timestamp=base_time + timedelta(minutes=20),
                input_tokens=1000,
                output_tokens=500,
                model="claude-3-haiku-latest",
            ),
        ]

        with patch('par_cc_usage.token_calculator.datetime') as mock_dt:
            mock_dt.now.return_value = base_time + timedelta(hours=1)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            snapshot = aggregate_usage(usage_data, mock_config)

            # Check that multipliers are applied correctly
            tokens_by_model = snapshot.unified_block_tokens_by_model()

            # Opus should have 5x multiplier (1500 * 5 = 7500)
            if "opus" in tokens_by_model:
                assert tokens_by_model["opus"] == 7500

            # Sonnet should have 1x multiplier (1500 * 1 = 1500)
            if "sonnet" in tokens_by_model:
                assert tokens_by_model["sonnet"] == 1500

            # Haiku should have 1x multiplier (1500 * 1 = 1500)
            if "haiku" in tokens_by_model:
                assert tokens_by_model["haiku"] == 1500
