"""Data models for par_cc_usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class TokenUsage:
    """Token usage data from Claude Code sessions."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    service_tier: str = "standard"
    # New fields from findings.md
    version: str | None = None
    message_id: str | None = None
    request_id: str | None = None
    cost_usd: float | None = None
    is_api_error: bool = False
    timestamp: datetime | None = None
    model: str | None = None  # Full model name (e.g., "claude-sonnet-4-20250514")
    # Tool usage tracking
    tools_used: list[str] = field(default_factory=list)  # List of tool names used in this message
    tool_use_count: int = 0  # Total number of tool calls in this message
    # Interruption tracking
    was_interrupted: bool = False  # Whether this message was interrupted by user

    @property
    def total_input(self) -> int:
        """Calculate total input tokens."""
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def total_output(self) -> int:
        """Calculate total output tokens."""
        return self.output_tokens

    @property
    def total(self) -> int:
        """Calculate total tokens."""
        return self.total_input + self.total_output

    def adjusted_total(self, multiplier: float = 1.0) -> int:
        """Calculate adjusted total with model multiplier."""
        return int(self.total * multiplier)

    def __add__(self, other: object) -> TokenUsage:
        """Add two TokenUsage instances together."""
        if not isinstance(other, TokenUsage):
            return NotImplemented
        # Combine tool lists and remove duplicates
        combined_tools = list(set(self.tools_used + other.tools_used))

        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            service_tier=self.service_tier,
            # Preserve cost by summing
            cost_usd=(self.cost_usd or 0) + (other.cost_usd or 0) if self.cost_usd or other.cost_usd else None,
            # Combine tool usage
            tools_used=combined_tools,
            tool_use_count=self.tool_use_count + other.tool_use_count,
            # Interruption tracking (True if either was interrupted)
            was_interrupted=self.was_interrupted or other.was_interrupted,
        )

    def get_unique_hash(self) -> str:
        """Get unique hash for deduplication."""
        message_id = self.message_id or "no-message-id"
        request_id = self.request_id or "no-request-id"
        return f"{message_id}:{request_id}"


@dataclass
class TokenBlock:
    """A 5-hour token block for rate limiting."""

    start_time: datetime
    end_time: datetime
    session_id: str
    project_name: str
    model: str
    token_usage: TokenUsage
    messages_processed: int = 0
    models_used: set[str] = field(default_factory=set[str])
    full_model_names: set[str] = field(default_factory=set[str])  # Full model names for pricing
    model_tokens: dict[str, int] = field(default_factory=dict[str, int])  # Per-model adjusted tokens
    # New fields from findings.md
    actual_end_time: datetime | None = None  # Last activity in block
    is_gap: bool = False  # True if this is a gap block between sessions
    block_id: str | None = None  # Unique block identifier
    cost_usd: float = 0.0  # Total cost for this block
    versions: list[str] = field(default_factory=list[str])  # Claude Code versions used
    # Tool usage tracking
    tools_used: set[str] = field(default_factory=set[str])  # Unique tools used in this block
    total_tool_calls: int = 0  # Total number of tool calls in this block
    tool_call_counts: dict[str, int] = field(default_factory=dict[str, int])  # Per-tool call counts
    # Interruption tracking
    total_interruptions: int = 0  # Total number of interruptions in this block
    interruptions_by_model: dict[str, int] = field(default_factory=dict[str, int])  # Per-model interruption counts

    @property
    def is_active(self) -> bool:
        """Check if this block is currently active for billing purposes.

        A block is active if:
        1. It's not a gap block
        2. Time since last activity < 5 hours (session duration)
        3. Current time is not before the block's start time
        """
        if self.is_gap:
            return False

        now = datetime.now(self.start_time.tzinfo)

        # Check if current time is before the block's start time
        if now < self.start_time:
            return False

        # Check time since last activity
        last_activity = self.actual_end_time or self.start_time
        time_since_activity = (now - last_activity).total_seconds()
        session_duration_seconds = 5 * 3600  # 5 hours in seconds

        return time_since_activity < session_duration_seconds

    @property
    def model_multiplier(self) -> float:
        """Get the model multiplier based on model name."""
        if "opus" in self.model.lower():
            return 5.0
        return 1.0

    @property
    def adjusted_tokens(self) -> int:
        """Get adjusted token count from per-model totals."""
        if self.model_tokens:
            return sum(self.model_tokens.values())
        else:
            # Fallback to old method for backward compatibility
            return self.token_usage.adjusted_total(self.model_multiplier)

    @property
    def all_models_display(self) -> str:
        """Get display string for all models used in this block."""
        from .token_calculator import get_model_display_name

        if self.models_used:
            # Get unique display names
            display_names = {get_model_display_name(m) for m in self.models_used}
            return ", ".join(sorted(display_names))
        else:
            # Fallback to single model
            return get_model_display_name(self.model)


@dataclass
class Session:
    """A Claude Code session with its blocks."""

    session_id: str
    project_name: str
    model: str
    blocks: list[TokenBlock] = field(default_factory=list[TokenBlock])
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    session_start: datetime | None = None  # First message timestamp for block calculation
    # New fields from findings.md
    project_path: str | None = None  # Full project path (for multi-directory support)
    total_cost_usd: float = 0.0  # Total cost across all blocks
    processed_message_ids: set[str] = field(default_factory=set[str])  # For deduplication

    @property
    def latest_block(self) -> TokenBlock | None:
        """Get the most recent block."""
        if not self.blocks:
            return None
        return max(self.blocks, key=lambda b: b.start_time)

    @property
    def active_block(self) -> TokenBlock | None:
        """Get the currently active block."""
        for block in self.blocks:
            if block.is_active:
                return block
        return None

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all blocks."""
        return sum(block.adjusted_tokens for block in self.blocks)

    @property
    def active_tokens(self) -> int:
        """Calculate tokens in active blocks only."""
        return sum(block.adjusted_tokens for block in self.blocks if block.is_active)

    def add_block(self, block: TokenBlock) -> None:
        """Add a block to the session."""
        self.blocks.append(block)
        if not self.first_seen or block.start_time < self.first_seen:
            self.first_seen = block.start_time
        if not self.last_seen or block.start_time > self.last_seen:
            self.last_seen = block.start_time
        # Update total cost
        self.total_cost_usd += block.cost_usd


@dataclass
class Project:
    """A Claude Code project with its sessions."""

    name: str
    sessions: dict[str, Session] = field(default_factory=dict[str, Session])

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all sessions."""
        return sum(session.total_tokens for session in self.sessions.values())

    @property
    def active_tokens(self) -> int:
        """Calculate tokens in active sessions only."""
        return sum(session.active_tokens for session in self.sessions.values())

    @property
    def active_sessions(self) -> list[Session]:
        """Get sessions with active blocks."""
        return [session for session in self.sessions.values() if session.active_block is not None]

    def add_session(self, session: Session) -> None:
        """Add a session to the project."""
        self.sessions[session.session_id] = session

    def _block_overlaps_unified_window(self, block: Any, unified_start: datetime) -> bool:
        """Check if a block overlaps with the unified block time window."""

        unified_end = unified_start + timedelta(hours=5)
        block_end = block.actual_end_time or block.end_time

        # Block is included if it overlaps with the unified block time window
        return (
            block.start_time < unified_end  # Block starts before unified block ends
            and block_end > unified_start  # Block ends after unified block starts
        )

    def get_unified_block_tokens(self, unified_start: datetime | None) -> int:
        """Get project tokens for the unified block time window."""
        if unified_start is None:
            return self.active_tokens

        total_tokens = 0
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    total_tokens += block.adjusted_tokens
        return total_tokens

    def get_unified_block_models(self, unified_start: datetime | None) -> set[str]:
        """Get models used in the unified block time window."""
        if unified_start is None:
            models = set()
            for session in self.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        models.update(block.models_used)
            return models

        models = set()
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    models.update(block.models_used)
        return models

    def get_unified_block_tools(self, unified_start: datetime | None) -> set[str]:
        """Get tools used in the unified block time window."""
        if unified_start is None:
            tools = set()
            for session in self.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        tools.update(block.tools_used)
            return tools

        tools = set()
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    tools.update(block.tools_used)
        return tools

    def get_unified_block_tool_calls(self, unified_start: datetime | None) -> int:
        """Get total tool calls in the unified block time window."""
        if unified_start is None:
            total_calls = 0
            for session in self.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        total_calls += block.total_tool_calls
            return total_calls

        total_calls = 0
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    total_calls += block.total_tool_calls
        return total_calls

    def get_unified_block_latest_activity(self, unified_start: datetime | None) -> datetime | None:
        """Get the latest activity time for this project in the unified block window."""
        if unified_start is None:
            latest_activity = None
            for session in self.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        activity_time = block.actual_end_time or block.start_time
                        if latest_activity is None or activity_time > latest_activity:
                            latest_activity = activity_time
            return latest_activity

        latest_activity = None
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    activity_time = block.actual_end_time or block.start_time
                    if latest_activity is None or activity_time > latest_activity:
                        latest_activity = activity_time
        return latest_activity


@dataclass
class UsageSnapshot:
    """A snapshot of usage across all projects."""

    timestamp: datetime
    projects: dict[str, Project] = field(default_factory=dict[str, Project])
    total_limit: int | None = None
    block_start_override: datetime | None = None

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all projects."""
        return sum(project.total_tokens for project in self.projects.values())

    @property
    def active_tokens(self) -> int:
        """Calculate tokens in active blocks only."""
        return sum(project.active_tokens for project in self.projects.values())

    @property
    def active_projects(self) -> list[Project]:
        """Get projects with active sessions."""
        return [project for project in self.projects.values() if project.active_sessions]

    @property
    def active_session_count(self) -> int:
        """Get total count of active sessions."""
        return sum(len(project.active_sessions) for project in self.projects.values())

    def tokens_by_model(self) -> dict[str, int]:
        """Get token usage grouped by model from all active blocks."""
        model_tokens: dict[str, int] = {}

        for project in self.projects.values():
            for session in project.sessions.values():
                # Sum tokens from all active blocks
                for block in session.blocks:
                    if block.is_active:
                        if block.model_tokens:
                            # Use per-model token tracking if available
                            for model, tokens in block.model_tokens.items():
                                if model not in model_tokens:
                                    model_tokens[model] = 0
                                model_tokens[model] += tokens
                        else:
                            # Fallback to old method for backward compatibility
                            model = block.model
                            if model not in model_tokens:
                                model_tokens[model] = 0
                            model_tokens[model] += block.adjusted_tokens

        return model_tokens

    def unified_block_tokens(self) -> int:
        """Get tokens only from blocks that overlap with the unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return 0

        total = 0
        for project in self.projects.values():
            total += project.get_unified_block_tokens(unified_start)
        return total

    def unified_block_tokens_by_model(self) -> dict[str, int]:
        """Get token usage by model only from blocks overlapping with unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return {}

        model_tokens: dict[str, int] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        if block.model_tokens:
                            # Use per-model token tracking if available
                            for model, tokens in block.model_tokens.items():
                                if model not in model_tokens:
                                    model_tokens[model] = 0
                                model_tokens[model] += tokens
                        else:
                            # Fallback to old method
                            model = block.model
                            if model not in model_tokens:
                                model_tokens[model] = 0
                            model_tokens[model] += block.adjusted_tokens
        return model_tokens

    def unified_block_tool_usage(self) -> dict[str, int]:
        """Get tool usage counts only from blocks overlapping with unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return {}

        tool_counts: dict[str, int] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        for tool, count in block.tool_call_counts.items():
                            if tool not in tool_counts:
                                tool_counts[tool] = 0
                            tool_counts[tool] += count
        return tool_counts

    def unified_block_total_tool_calls(self) -> int:
        """Get total tool calls only from blocks overlapping with unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return 0

        total = 0
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        total += block.total_tool_calls
        return total

    def interruptions_by_model(self) -> dict[str, int]:
        """Get interruption counts grouped by model from all active blocks."""
        model_interruptions: dict[str, int] = {}

        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        for model, count in block.interruptions_by_model.items():
                            if model not in model_interruptions:
                                model_interruptions[model] = 0
                            model_interruptions[model] += count

        return model_interruptions

    def unified_block_interruptions_by_model(self) -> dict[str, int]:
        """Get interruption counts by model only from blocks overlapping with unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return {}

        model_interruptions: dict[str, int] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        for model, count in block.interruptions_by_model.items():
                            if model not in model_interruptions:
                                model_interruptions[model] = 0
                            model_interruptions[model] += count
        return model_interruptions

    async def get_unified_block_cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model only from blocks overlapping with unified block time window."""
        from .pricing import calculate_token_cost

        unified_start = self.unified_block_start_time
        if not unified_start:
            return {}

        model_costs: dict[str, float] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        # Calculate cost for each full model name in the block
                        for full_model in block.full_model_names:
                            if full_model not in model_costs:
                                model_costs[full_model] = 0.0

                            # Calculate cost based on token usage
                            usage = block.token_usage
                            cost = await calculate_token_cost(
                                full_model,
                                usage.input_tokens,
                                usage.output_tokens,
                                usage.cache_creation_input_tokens,
                                usage.cache_read_input_tokens,
                            )
                            model_costs[full_model] += cost.total_cost

        return model_costs

    async def get_unified_block_total_cost(self) -> float:
        """Get total cost only from blocks overlapping with unified block time window."""
        model_costs = await self.get_unified_block_cost_by_model()
        return sum(model_costs.values())

    async def get_total_cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model from all active blocks."""
        from .pricing import calculate_token_cost

        model_costs: dict[str, float] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        # Calculate cost for each full model name in the block
                        for full_model in block.full_model_names:
                            if full_model not in model_costs:
                                model_costs[full_model] = 0.0

                            # Calculate cost based on token usage
                            usage = block.token_usage
                            cost = await calculate_token_cost(
                                full_model,
                                usage.input_tokens,
                                usage.output_tokens,
                                usage.cache_creation_input_tokens,
                                usage.cache_read_input_tokens,
                            )
                            model_costs[full_model] += cost.total_cost

        return model_costs

    async def get_total_cost(self) -> float:
        """Get total cost from all active blocks."""
        model_costs = await self.get_total_cost_by_model()
        return sum(model_costs.values())

    def total_interruptions(self) -> int:
        """Get total interruptions across all active blocks."""
        total = 0
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        total += block.total_interruptions
        return total

    def unified_block_total_interruptions(self) -> int:
        """Get total interruptions only from blocks overlapping with unified block time window."""
        unified_start = self.unified_block_start_time
        if not unified_start:
            return 0

        total = 0
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and project._block_overlaps_unified_window(block, unified_start):
                        total += block.total_interruptions
        return total

    def add_project(self, project: Project) -> None:
        """Add a project to the snapshot."""
        self.projects[project.name] = project

    @property
    def unified_block_start_time(self) -> datetime | None:
        """Get the unified billing block start time.

        Uses entry-level aggregation to determine the correct unified block,
        or returns the override if provided.

        This implements a straightforward approach:
        aggregate all activity across sessions first, then determine the unified block
        based on the most recent activity.

        Returns:
            Unified block start time or None if no active entries
        """
        # Use override if provided
        if self.block_start_override:
            return self.block_start_override

        # Use the unified block calculation from token_calculator
        # This implements entry-level aggregation for token usage
        from .token_calculator import create_unified_blocks

        return create_unified_blocks(self.projects)

    @property
    def unified_block_end_time(self) -> datetime | None:
        """Get the unified billing block end time.

        Returns the end time of the currently active billing block (start + 5 hours).

        Returns:
            Block end time or None if no active blocks
        """
        start_time = self.unified_block_start_time
        if start_time is None:
            return None

        return start_time + timedelta(hours=5)


@dataclass
class DeduplicationState:
    """Track deduplication state across file processing."""

    processed_hashes: set[str] = field(default_factory=set[str])
    duplicate_count: int = 0
    total_messages: int = 0

    def is_duplicate(self, hash_value: str) -> bool:
        """Check if a message hash has been seen before."""
        if hash_value in self.processed_hashes:
            self.duplicate_count += 1
            return True
        self.processed_hashes.add(hash_value)
        self.total_messages += 1
        return False

    @property
    def unique_messages(self) -> int:
        """Get count of unique messages processed."""
        return self.total_messages - self.duplicate_count
