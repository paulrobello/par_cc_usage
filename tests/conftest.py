"""
Pytest configuration and shared fixtures for PAR CC Usage tests.
"""

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from par_cc_usage.config import Config, DisplayConfig, NotificationConfig
from par_cc_usage.models import (
    Project,
    Session,
    TokenBlock,
    TokenUsage,
    UsageSnapshot,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock configuration with test paths."""
    return Config(
        projects_dir=temp_dir / "claude" / "projects",
        cache_dir=temp_dir / "cache",
        token_limit=1000000,
        polling_interval=1,
        timezone="UTC",
        disable_cache=False,
        display=DisplayConfig(
            time_format="24h",
            show_progress_bars=True,
            show_active_sessions=True,
            update_in_place=True,
            refresh_interval=1,
            project_name_prefixes=["-Users-", "-home-"],
        ),
        notifications=NotificationConfig(
            discord_webhook_url=None,
            notify_on_block_completion=False,
            cooldown_minutes=60,
        ),
        recent_activity_window_hours=5,
    )


@pytest.fixture
def sample_timestamp():
    """Provide a consistent timestamp for testing."""
    return datetime(2025, 1, 9, 14, 30, 45, tzinfo=UTC)


@pytest.fixture
def sample_token_usage(sample_timestamp):
    """Create a sample TokenUsage instance."""
    return TokenUsage(
        input_tokens=1000,
        cache_creation_input_tokens=50,
        cache_read_input_tokens=100,
        output_tokens=500,
        service_tier="standard",
        message_id="msg_123",
        request_id="req_456",
        timestamp=sample_timestamp,
        model="claude-3-5-sonnet-latest",
    )


@pytest.fixture
def sample_token_block(sample_timestamp):
    """Create a sample TokenBlock instance."""
    usage = TokenUsage(
        input_tokens=1000,
        output_tokens=500,
        model="claude-3-opus-latest",
        timestamp=sample_timestamp,
    )

    block = TokenBlock(
        start_time=sample_timestamp,
        end_time=sample_timestamp + timedelta(hours=5),
        session_id="session_123",
        project_name="test_project",
        model="claude-3-opus-latest",
        token_usage=usage,
        messages_processed=1,
        models_used={"claude-3-opus-latest"},
        model_tokens={"opus": 7500},  # 1500 * 5
        actual_end_time=sample_timestamp + timedelta(minutes=30),
    )
    return block


@pytest.fixture
def sample_session(sample_timestamp, sample_token_block):
    """Create a sample Session instance."""
    session = Session(
        session_id="session_123",
        project_name="test_project",
        model="claude-3-opus-latest",
        blocks=[sample_token_block],
        first_seen=sample_timestamp,
        last_seen=sample_timestamp + timedelta(hours=1),
        session_start=sample_timestamp,
    )
    return session


@pytest.fixture
def sample_project(sample_session):
    """Create a sample Project instance."""
    project = Project(
        name="test_project",
        sessions={"session_123": sample_session},
    )
    return project


@pytest.fixture
def sample_usage_snapshot(sample_timestamp, sample_project):
    """Create a sample UsageSnapshot instance."""
    return UsageSnapshot(
        timestamp=sample_timestamp,
        projects={"test_project": sample_project},
        total_limit=1000000,
        block_start_override=None,
    )


@pytest.fixture
def sample_jsonl_lines():
    """Provide sample JSONL lines for testing."""
    return [
        json.dumps({
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {
                "model": "claude-3-5-sonnet-latest",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            "response": {
                "id": "msg_123",
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": 50,
                    "cache_read_input_tokens": 100,
                },
            },
            "project_name": "test_project",
            "session_id": "session_123",
            "request_id": "req_456",
        }),
        json.dumps({
            "timestamp": "2025-01-09T14:35:00.000Z",
            "request": {
                "model": "claude-3-opus-latest",
                "messages": [{"role": "user", "content": "Test opus"}],
            },
            "response": {
                "id": "msg_789",
                "usage": {
                    "input_tokens": 2000,
                    "output_tokens": 1000,
                },
            },
            "project_name": "test_project",
            "session_id": "session_123",
            "request_id": "req_789",
        }),
    ]


@pytest.fixture
def mock_datetime(sample_timestamp):
    """Mock datetime to return consistent timestamps."""
    with patch("par_cc_usage.models.datetime") as mock_dt:
        mock_dt.now.return_value = sample_timestamp
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield mock_dt


@pytest.fixture
def mock_file_monitor(temp_dir):
    """Create a mock FileMonitor for testing."""
    from par_cc_usage.file_monitor import FileMonitor

    monitor = FileMonitor(
        claude_paths=[temp_dir / "claude_projects"],
        cache_dir=temp_dir / "cache",
        use_cache=True,
    )
    return monitor


@pytest.fixture
def mock_discord_webhook():
    """Mock Discord webhook for testing."""
    with patch("par_cc_usage.discord_webhook.requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def timezone_aware_datetime():
    """Helper fixture for timezone-aware datetime testing."""
    def _make_aware(dt: datetime, tz: str = "UTC") -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=ZoneInfo(tz))
        return dt.astimezone(ZoneInfo(tz))
    return _make_aware


@pytest.fixture
def sample_jsonl_file(temp_dir, sample_jsonl_lines):
    """Create a sample JSONL file for testing."""
    jsonl_path = temp_dir / "test_project.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for line in sample_jsonl_lines:
            f.write(line + "\n")
    return jsonl_path


# Environment variable fixtures
@pytest.fixture
def clean_env(monkeypatch):
    """Remove all PAR_CC_USAGE environment variables."""
    env_vars = [k for k in os.environ if k.startswith("PAR_CC_USAGE_")]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def mock_env_vars(monkeypatch, clean_env):
    """Set mock environment variables for testing."""
    test_vars = {
        "PAR_CC_USAGE_TOKEN_LIMIT": "2000000",
        "PAR_CC_USAGE_POLLING_INTERVAL": "5",
        "PAR_CC_USAGE_TIME_FORMAT": "12h",
        "PAR_CC_USAGE_TIMEZONE": "America/New_York",
        "PAR_CC_USAGE_DISCORD_WEBHOOK_URL": "https://discord.com/test",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
    yield test_vars


@pytest.fixture
def deduplication_state():
    """Create a DeduplicationState for testing."""
    # Check if DeduplicationState exists in models
    try:
        from par_cc_usage.models import DeduplicationState
        return DeduplicationState()
    except ImportError:
        # Return a mock if it doesn't exist
        class MockDeduplicationState:
            def __init__(self):
                self.seen_hashes = set()

            def add(self, hash_value):
                if hash_value is None:
                    return True
                if hash_value in self.seen_hashes:
                    return False
                self.seen_hashes.add(hash_value)
                return True

            def contains(self, hash_value):
                return hash_value in self.seen_hashes

        return MockDeduplicationState()


# Helper functions for tests
def create_token_usage(
    timestamp: datetime | None = None,
    model: str = "claude-3-5-sonnet-latest",
    input_tokens: int = 100,
    output_tokens: int = 50,
    message_id: str | None = None,
    request_id: str | None = None,
) -> TokenUsage:
    """Helper to create TokenUsage instances for tests."""
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        service_tier="standard",
        message_id=message_id or f"msg_{timestamp.timestamp() if timestamp else 'test'}",
        request_id=request_id or f"req_{timestamp.timestamp() if timestamp else 'test'}",
        timestamp=timestamp,
        model=model,
    )


def create_block_with_tokens(
    start_time: datetime,
    session_id: str,
    project_name: str,
    token_count: int = 1000,
    model: str = "sonnet",
    duration_hours: float = 5.0,
) -> TokenBlock:
    """Helper to create a TokenBlock with specified tokens."""
    end_time = start_time + timedelta(hours=duration_hours)
    multiplier = 5 if model == "opus" else 1

    usage = TokenUsage(
        input_tokens=token_count // 2,
        output_tokens=token_count // 2,
        model=f"claude-3-{model}-latest" if model in ["opus", "sonnet", "haiku"] else model,
        timestamp=start_time,
    )

    block = TokenBlock(
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        project_name=project_name,
        model=usage.model,
        token_usage=usage,
        model_tokens={model: token_count * multiplier},
        actual_end_time=start_time + timedelta(hours=1),
    )
    return block
