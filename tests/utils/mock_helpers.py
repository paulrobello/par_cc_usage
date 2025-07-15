"""
Mock helpers for testing.

This module provides standardized mock utilities for testing PAR CC Usage components.
"""

from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from par_cc_usage.models import (
    TokenUsage,
    TokenBlock,
    Session,
    Project,
    UsageSnapshot,
)
from par_cc_usage.config import Config, DisplayConfig, NotificationConfig


class MockFileMonitor:
    """Mock FileMonitor for testing."""

    def __init__(self, claude_paths: List[str], cache_dir: str, use_cache: bool = True):
        self.claude_paths = claude_paths
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        self._file_states = {}

    def get_new_lines(self, file_path: str) -> List[str]:
        """Mock getting new lines from a file."""
        # Return empty list by default
        return []

    def update_file_state(self, file_path: str, position: int):
        """Mock updating file state."""
        self._file_states[str(file_path)] = position


class MockWebhookClient:
    """Mock WebhookClient for testing."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.sent_webhooks = []

    async def send_webhook(self, payload: Any) -> bool:
        """Mock sending webhook."""
        self.sent_webhooks.append(payload)
        return True  # Always succeed by default


class MockPricingCache:
    """Mock PricingCache for testing."""

    def __init__(self):
        self._cache = {}
        self.api_calls = []

    async def get_pricing(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Mock getting pricing data."""
        self.api_calls.append(model_name)

        # Return mock pricing for known models
        if "sonnet" in model_name.lower():
            return {
                "input_cost_per_token": 0.003,
                "output_cost_per_token": 0.015,
                "supports_vision": False,
                "litellm_provider": "anthropic",
                "mode": "chat",
            }
        elif "opus" in model_name.lower():
            return {
                "input_cost_per_token": 0.015,
                "output_cost_per_token": 0.075,
                "supports_vision": True,
                "litellm_provider": "anthropic",
                "mode": "chat",
            }
        elif "haiku" in model_name.lower():
            return {
                "input_cost_per_token": 0.00025,
                "output_cost_per_token": 0.00125,
                "supports_vision": False,
                "litellm_provider": "anthropic",
                "mode": "chat",
            }

        return None  # Unknown model


class MockDisplay:
    """Mock Display for testing."""

    def __init__(self, display_config: DisplayConfig, show_pricing: bool = False):
        self.display_config = display_config
        self.show_pricing = show_pricing
        self.updates = []

    def update(self, snapshot: Optional[UsageSnapshot]):
        """Mock display update."""
        self.updates.append(snapshot)


def create_mock_config(
    token_limit: int = 1000000,
    timezone: str = "UTC",
    polling_interval: float = 1.0,
    projects_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    **kwargs
) -> Config:
    """Create a mock configuration for testing."""
    return Config(
        projects_dir=projects_dir or "/mock/projects",
        cache_dir=cache_dir or "/mock/cache",
        token_limit=token_limit,
        polling_interval=polling_interval,
        timezone=timezone,
        disable_cache=kwargs.get("disable_cache", False),
        display=DisplayConfig(
            time_format=kwargs.get("time_format", "24h"),
            show_progress_bars=kwargs.get("show_progress_bars", True),
            show_active_sessions=kwargs.get("show_active_sessions", True),
            update_in_place=kwargs.get("update_in_place", True),
            refresh_interval=kwargs.get("refresh_interval", 1),
            project_name_prefixes=kwargs.get("project_name_prefixes", []),
        ),
        notifications=NotificationConfig(
            discord_webhook_url=kwargs.get("discord_webhook_url"),
            notify_on_block_completion=kwargs.get("notify_on_block_completion", False),
            cooldown_minutes=kwargs.get("cooldown_minutes", 60),
        ),
        recent_activity_window_hours=kwargs.get("recent_activity_window_hours", 5),
    )


def create_mock_usage(
    timestamp: Optional[datetime] = None,
    model: str = "claude-3-5-sonnet-latest",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    project_name: str = "mock_project",
    session_id: str = "mock_session",
    message_id: Optional[str] = None,
    request_id: Optional[str] = None,
    cost_usd: Optional[float] = None,
) -> TokenUsage:
    """Create a mock TokenUsage instance."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        service_tier="standard",
        message_id=message_id or f"msg_{timestamp.timestamp()}",
        request_id=request_id or f"req_{timestamp.timestamp()}",
        timestamp=timestamp,
        model=model,
        project_name=project_name,
        session_id=session_id,
        cost_usd=cost_usd,
    )


def create_mock_block(
    start_time: Optional[datetime] = None,
    session_id: str = "mock_session",
    project_name: str = "mock_project",
    model: str = "claude-3-5-sonnet-latest",
    token_count: int = 1500,
    duration_hours: float = 5.0,
    cost_usd: Optional[float] = None,
) -> TokenBlock:
    """Create a mock TokenBlock instance."""
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    end_time = start_time + timedelta(hours=duration_hours)

    # Create mock usage
    usage = create_mock_usage(
        timestamp=start_time,
        model=model,
        input_tokens=token_count // 2,
        output_tokens=token_count // 2,
        project_name=project_name,
        session_id=session_id,
    )

    # Determine model type and multiplier
    model_type = "sonnet"
    multiplier = 1
    if "opus" in model.lower():
        model_type = "opus"
        multiplier = 5
    elif "haiku" in model.lower():
        model_type = "haiku"
        multiplier = 1

    return TokenBlock(
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        project_name=project_name,
        model=model,
        token_usage=usage,
        model_tokens={model_type: token_count * multiplier},
        actual_end_time=start_time + timedelta(hours=1),
        cost_usd=cost_usd,
    )


def create_mock_session(
    session_id: str = "mock_session",
    project_name: str = "mock_project",
    model: str = "claude-3-5-sonnet-latest",
    num_blocks: int = 3,
    start_time: Optional[datetime] = None,
) -> Session:
    """Create a mock Session instance."""
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    blocks = []
    for i in range(num_blocks):
        block_start = start_time + timedelta(hours=i * 2)
        block = create_mock_block(
            start_time=block_start,
            session_id=session_id,
            project_name=project_name,
            model=model,
            token_count=1000 + i * 100,
        )
        blocks.append(block)

    return Session(
        session_id=session_id,
        project_name=project_name,
        model=model,
        blocks=blocks,
        first_seen=start_time,
        last_seen=start_time + timedelta(hours=num_blocks * 2),
        session_start=start_time,
    )


def create_mock_project(
    name: str = "mock_project",
    num_sessions: int = 2,
    start_time: Optional[datetime] = None,
) -> Project:
    """Create a mock Project instance."""
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    sessions = {}
    for i in range(num_sessions):
        session_id = f"session_{i}"
        session = create_mock_session(
            session_id=session_id,
            project_name=name,
            start_time=start_time + timedelta(hours=i * 6),
        )
        sessions[session_id] = session

    return Project(name=name, sessions=sessions)


def create_mock_snapshot(
    num_projects: int = 2,
    total_limit: int = 1000000,
    timestamp: Optional[datetime] = None,
    block_start_override: Optional[datetime] = None,
) -> UsageSnapshot:
    """Create a mock UsageSnapshot instance."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    projects = {}
    for i in range(num_projects):
        project_name = f"project_{i}"
        project = create_mock_project(
            name=project_name,
            start_time=timestamp - timedelta(hours=i * 2),
        )
        projects[project_name] = project

    return UsageSnapshot(
        timestamp=timestamp,
        projects=projects,
        total_limit=total_limit,
        block_start_override=block_start_override,
    )


class MockAsyncContext:
    """Mock async context manager for testing."""

    def __init__(self, return_value: Any):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_mock_aiohttp_response(
    status: int = 200,
    text: str = "",
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Mock:
    """Create a mock aiohttp response."""
    response = Mock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    response.headers = headers or {}

    if json_data is not None:
        response.json = AsyncMock(return_value=json_data)
    else:
        response.json = AsyncMock(side_effect=ValueError("No JSON data"))

    return response


def create_mock_file_system(temp_dir_path: str) -> Dict[str, Any]:
    """Create a mock file system structure for testing."""
    from pathlib import Path

    base_path = Path(temp_dir_path)

    # Create directory structure
    structure = {
        "claude": {
            "projects": {
                "project_1": {
                    "session_1.jsonl": "mock_jsonl_content",
                    "session_2.jsonl": "mock_jsonl_content",
                },
                "project_2": {
                    "session_3.jsonl": "mock_jsonl_content",
                },
            }
        },
        "cache": {},
        "config.yaml": "mock_config_content",
    }

    return structure


# Error simulation utilities
class MockNetworkError(Exception):
    """Mock network error for testing."""
    pass


class MockTimeoutError(Exception):
    """Mock timeout error for testing."""
    pass


class MockPermissionError(PermissionError):
    """Mock permission error for testing."""
    pass


def simulate_network_failure():
    """Simulate network failure."""
    raise MockNetworkError("Simulated network failure")


def simulate_timeout():
    """Simulate timeout."""
    raise MockTimeoutError("Simulated timeout")


def simulate_permission_denied():
    """Simulate permission denied."""
    raise MockPermissionError("Simulated permission denied")


# Performance testing utilities
class MockPerformanceTimer:
    """Mock performance timer for testing."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None

    def start(self):
        """Start timing."""
        import time
        self.start_time = time.time()

    def stop(self):
        """Stop timing."""
        import time
        self.end_time = time.time()
        if self.start_time:
            self.duration = self.end_time - self.start_time

    def get_duration(self) -> float:
        """Get duration in seconds."""
        return self.duration or 0.0


class MockMemoryTracker:
    """Mock memory tracker for testing."""

    def __init__(self):
        self.initial_memory = None
        self.current_memory = None

    def start(self):
        """Start memory tracking."""
        self.initial_memory = self._get_memory_usage()

    def check(self):
        """Check current memory usage."""
        self.current_memory = self._get_memory_usage()

    def get_increase(self) -> float:
        """Get memory increase in MB."""
        if self.initial_memory and self.current_memory:
            return self.current_memory - self.initial_memory
        return 0.0

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback estimation
            import sys
            return sys.getsizeof({}) / 1024 / 1024
