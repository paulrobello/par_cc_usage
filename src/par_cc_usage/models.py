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
    # Message count tracking
    message_count: int = 1  # Number of messages (typically 1 per TokenUsage instance)
    # Actual token fields (for accurate pricing calculations)
    actual_input_tokens: int = 0
    actual_cache_creation_input_tokens: int = 0
    actual_cache_read_input_tokens: int = 0
    actual_output_tokens: int = 0

    @property
    def total_input(self) -> int:
        """Calculate total input tokens (display tokens)."""
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def total_output(self) -> int:
        """Calculate total output tokens (display tokens)."""
        return self.output_tokens

    @property
    def total(self) -> int:
        """Calculate total tokens (display tokens)."""
        return self.total_input + self.total_output

    @property
    def actual_total_input(self) -> int:
        """Calculate total actual input tokens (for pricing)."""
        return self.actual_input_tokens + self.actual_cache_creation_input_tokens + self.actual_cache_read_input_tokens

    @property
    def actual_total_output(self) -> int:
        """Calculate total actual output tokens (for pricing)."""
        return self.actual_output_tokens

    @property
    def actual_total(self) -> int:
        """Calculate total actual tokens (for pricing)."""
        return self.actual_total_input + self.actual_total_output

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
            # Message count tracking
            message_count=self.message_count + other.message_count,
            # Actual token fields
            actual_input_tokens=self.actual_input_tokens + other.actual_input_tokens,
            actual_cache_creation_input_tokens=self.actual_cache_creation_input_tokens
            + other.actual_cache_creation_input_tokens,
            actual_cache_read_input_tokens=self.actual_cache_read_input_tokens + other.actual_cache_read_input_tokens,
            actual_output_tokens=self.actual_output_tokens + other.actual_output_tokens,
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
    # Message count tracking
    message_count: int = 0  # Total number of messages in this block
    model_message_counts: dict[str, int] = field(default_factory=dict[str, int])  # Per-model message counts
    # Actual token fields (for accurate pricing calculations)
    actual_tokens: int = 0  # Total actual tokens for this block
    actual_model_tokens: dict[str, int] = field(default_factory=dict[str, int])  # Per-model actual tokens

    @property
    def is_active(self) -> bool:
        """Check if this block is currently active for billing purposes.

        A block is active if:
        1. It's not a gap block
        2. Time since last activity < 5 hours (session duration)
        3. Current time < block end time (start + 5 hours)
        """
        if self.is_gap:
            return False

        now = datetime.now(self.start_time.tzinfo)

        # Calculate block end time (start + 5 hours)
        block_end_time = self.start_time + timedelta(hours=5)

        # Check if current time is after block end time
        if now >= block_end_time:
            return False

        # Check time since last activity
        last_activity = self.actual_end_time or self.start_time
        time_since_activity = (now - last_activity).total_seconds()
        session_duration_seconds = 5 * 3600  # 5 hours in seconds

        return time_since_activity < session_duration_seconds

    @property
    def model_multiplier(self) -> float:
        """Get the model multiplier based on model name (fallback to hardcoded)."""
        return self.get_model_multiplier()

    def get_model_multiplier(self, model_multipliers: dict[str, float] | None = None) -> float:
        """Get the model multiplier based on model name and configuration.

        Args:
            model_multipliers: Dictionary of model multipliers from config

        Returns:
            Multiplier for the model
        """
        if model_multipliers is None:
            # Fallback to hardcoded values if no config provided
            if "opus" in self.model.lower():
                return 5.0
            # Sonnet and all other models default to 1.0
            return 1.0

        # Check for exact model name match first
        model_lower = self.model.lower()
        for model_key, multiplier in model_multipliers.items():
            if model_key.lower() in model_lower:
                return multiplier

        # Use default multiplier if no match found
        return model_multipliers.get("default", 1.0)

    @property
    def adjusted_tokens(self) -> int:
        """Get adjusted token count from per-model totals (display tokens)."""
        if self.model_tokens:
            return sum(self.model_tokens.values())
        else:
            # Fallback to old method for backward compatibility
            return self.token_usage.adjusted_total(self.model_multiplier)

    @property
    def actual_tokens_total(self) -> int:
        """Get actual token count from per-model totals (for pricing)."""
        if self.actual_model_tokens:
            return sum(self.actual_model_tokens.values())
        else:
            # Fallback to token_usage actual tokens if available
            if self.token_usage.actual_total > 0:
                return self.token_usage.actual_total
            else:
                # Last resort: use display tokens divided by multiplier
                multiplier = self.model_multiplier
                return int(self.token_usage.total / multiplier) if multiplier > 0 else self.token_usage.total

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

    def get_unified_block_messages(self, unified_start: datetime | None) -> int:
        """Get project messages for the unified block time window."""
        if unified_start is None:
            total_messages = 0
            for session in self.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        total_messages += block.message_count
            return total_messages

        total_messages = 0
        for session in self.sessions.values():
            for block in session.blocks:
                if block.is_active and self._block_overlaps_unified_window(block, unified_start):
                    total_messages += block.message_count
        return total_messages

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
    message_limit: int | None = None
    block_start_override: datetime | None = None
    unified_blocks: list[UnifiedBlock] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all projects."""
        return sum(project.total_tokens for project in self.projects.values())

    @property
    def active_tokens(self) -> int:
        """Calculate tokens in active blocks only."""
        return sum(project.active_tokens for project in self.projects.values())

    @property
    def total_messages(self) -> int:
        """Calculate total messages across all projects."""
        total = 0
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    total += block.message_count
        return total

    @property
    def active_messages(self) -> int:
        """Calculate messages in active blocks only."""
        total = 0
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        total += block.message_count
        return total

    @property
    def active_projects(self) -> list[Project]:
        """Get projects with active sessions."""
        return [project for project in self.projects.values() if project.active_sessions]

    @property
    def unified_block_projects(self) -> list[Project]:
        """Get projects with activity in the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if not current_block:
            return []

        # Return projects that have data in the current unified block
        active_projects = []
        for project_name in current_block.projects:
            if project_name in self.projects:
                active_projects.append(self.projects[project_name])
        return active_projects

    def get_unified_block_project_data(self, project_name: str) -> dict[str, Any]:
        """Get project data from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if not current_block or project_name not in current_block.projects:
            return {
                "tokens": 0,
                "messages": 0,
                "models": set(),
                "tools": set(),
                "tool_calls": 0,
                "cost": 0.0,
            }

        # Calculate project-specific data from unified block entries
        project_tokens = 0
        project_messages = 0
        project_models = set()
        project_tools = set()
        project_tool_calls = 0

        for entry in current_block.entries:
            if entry.project_name == project_name:
                project_tokens += entry.token_usage.total
                project_messages += 1
                project_models.add(entry.model)
                project_tools.update(entry.tools_used)
                project_tool_calls += entry.tool_use_count
                # Note: entry.cost_usd is always 0, so we store entries for async cost calculation
                # Cost calculation will be done separately by the display layer

        return {
            "tokens": project_tokens,
            "messages": project_messages,
            "models": project_models,
            "tools": project_tools,
            "tool_calls": project_tool_calls,
            "cost": 0.0,  # Cost calculation moved to async display layer
        }

    async def get_unified_block_project_cost(self, project_name: str) -> float:
        """Get project cost from the current unified block (async calculation)."""
        from .pricing import calculate_token_cost
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if not current_block or project_name not in current_block.projects:
            return 0.0

        project_cost = 0.0
        for entry in current_block.entries:
            if entry.project_name == project_name:
                usage = entry.token_usage
                try:
                    cost = await calculate_token_cost(
                        entry.full_model_name,
                        usage.actual_input_tokens,
                        usage.actual_output_tokens,
                        usage.actual_cache_creation_input_tokens,
                        usage.actual_cache_read_input_tokens,
                    )
                    project_cost += cost.total_cost
                except Exception:
                    # If cost calculation fails, skip this entry
                    continue

        return project_cost

    @property
    def active_session_count(self) -> int:
        """Get total count of active sessions."""
        return sum(len(project.active_sessions) for project in self.projects.values())

    @property
    def unified_block_session_count(self) -> int:
        """Get count of sessions in the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return len(current_block.sessions)
        return 0

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

    def messages_by_model(self) -> dict[str, int]:
        """Get message usage grouped by model from all active blocks."""
        model_messages: dict[str, int] = {}

        for project in self.projects.values():
            for session in project.sessions.values():
                # Sum messages from all active blocks
                for block in session.blocks:
                    if block.is_active:
                        if block.model_message_counts:
                            # Use per-model message tracking if available
                            for model, messages in block.model_message_counts.items():
                                if model not in model_messages:
                                    model_messages[model] = 0
                                model_messages[model] += messages
                        else:
                            # Fallback to block message count
                            model = block.model
                            if model not in model_messages:
                                model_messages[model] = 0
                            model_messages[model] += block.message_count

        return model_messages

    def unified_block_tokens(self) -> int:
        """Get tokens from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.total_tokens
        return 0

    def unified_block_tokens_by_model(self) -> dict[str, int]:
        """Get token usage by model from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.model_tokens.copy()
        return {}

    def unified_block_messages(self) -> int:
        """Get messages from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.messages_processed
        return 0

    def unified_block_messages_by_model(self) -> dict[str, int]:
        """Get message usage by model from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.model_message_counts.copy()
        return {}

    def unified_block_tool_usage(self) -> dict[str, int]:
        """Get tool usage counts from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.tool_call_counts.copy()
        return {}

    def unified_block_total_tool_calls(self) -> int:
        """Get total tool calls from the current unified block."""
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if current_block:
            return current_block.total_tool_calls
        return 0

    async def get_unified_block_cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model from the current unified block."""
        from .pricing import calculate_token_cost
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if not current_block:
            return {}

        # Calculate costs for each model in the unified block
        model_costs: dict[str, float] = {}
        for full_model in current_block.full_model_names:
            model_costs[full_model] = 0.0

            # Sum up costs from all entries with this model
            for entry in current_block.entries:
                if entry.full_model_name == full_model:
                    usage = entry.token_usage
                    cost = await calculate_token_cost(
                        full_model,
                        usage.actual_input_tokens,
                        usage.actual_output_tokens,
                        usage.actual_cache_creation_input_tokens,
                        usage.actual_cache_read_input_tokens,
                    )
                    model_costs[full_model] += cost.total_cost

        return model_costs

    async def get_unified_block_total_cost(self) -> float:
        """Get total cost from the current unified block."""
        from .pricing import calculate_token_cost
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        if not current_block:
            return 0.0

        total_cost = 0.0
        for entry in current_block.entries:
            usage = entry.token_usage
            try:
                cost = await calculate_token_cost(
                    entry.full_model_name,
                    usage.actual_input_tokens,
                    usage.actual_output_tokens,
                    usage.actual_cache_creation_input_tokens,
                    usage.actual_cache_read_input_tokens,
                )
                total_cost += cost.total_cost
            except Exception:
                # If cost calculation fails for any entry, skip it
                continue

        return total_cost

    async def get_total_cost_by_model(self, active_only: bool = True) -> dict[str, float]:
        """Get cost breakdown by model from blocks.

        Args:
            active_only: If True, only include active blocks. If False, include all blocks.
        """
        from .pricing import calculate_token_cost

        model_costs: dict[str, float] = {}
        for project in self.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if not active_only or block.is_active:
                        # Calculate cost for each full model name in the block
                        for full_model in block.full_model_names:
                            if full_model not in model_costs:
                                model_costs[full_model] = 0.0

                            # Calculate cost based on actual token usage (for accurate pricing)
                            usage = block.token_usage
                            cost = await calculate_token_cost(
                                full_model,
                                usage.actual_input_tokens,
                                usage.actual_output_tokens,
                                usage.actual_cache_creation_input_tokens,
                                usage.actual_cache_read_input_tokens,
                            )
                            model_costs[full_model] += cost.total_cost

        return model_costs

    async def get_total_cost(self, active_only: bool = True) -> float:
        """Get total cost from blocks.

        Args:
            active_only: If True, only include active blocks. If False, include all blocks.
        """
        model_costs = await self.get_total_cost_by_model(active_only=active_only)
        return sum(model_costs.values())

    def add_project(self, project: Project) -> None:
        """Add a project to the snapshot."""
        self.projects[project.name] = project

    @property
    def unified_block_start_time(self) -> datetime | None:
        """Get the unified billing block start time.

        Returns the start time of the currently active unified block,
        or returns the override if provided.

        Returns:
            Unified block start time or None if no active blocks
        """
        # Use override if provided
        if self.block_start_override:
            return self.block_start_override

        # Get the current active unified block
        from .token_calculator import get_current_unified_block

        current_block = get_current_unified_block(self.unified_blocks)
        return current_block.start_time if current_block else None

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
class UnifiedEntry:
    """Entry data for unified block calculation across all projects/sessions."""

    timestamp: datetime
    project_name: str
    session_id: str
    model: str
    full_model_name: str
    token_usage: TokenUsage
    tools_used: list[str] = field(default_factory=list[str])
    tool_use_count: int = 0
    cost_usd: float = 0.0
    version: str | None = None


@dataclass
class UnifiedBlock:
    """Represents a unified billing block across all projects and sessions."""

    id: str  # ISO string of block start time
    start_time: datetime
    end_time: datetime  # start_time + 5 hours
    actual_end_time: datetime | None = None  # Last activity in block
    entries: list[UnifiedEntry] = field(default_factory=list[UnifiedEntry])

    # Aggregated data
    total_tokens: int = 0
    actual_tokens: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    messages_processed: int = 0
    cost_usd: float = 0.0

    # Model tracking
    models_used: set[str] = field(default_factory=set[str])
    full_model_names: set[str] = field(default_factory=set[str])
    model_tokens: dict[str, int] = field(default_factory=dict[str, int])
    model_message_counts: dict[str, int] = field(default_factory=dict[str, int])

    # Tool tracking
    tools_used: set[str] = field(default_factory=set[str])
    tool_call_counts: dict[str, int] = field(default_factory=dict[str, int])
    total_tool_calls: int = 0

    # Project/session tracking
    projects: set[str] = field(default_factory=set[str])
    sessions: set[str] = field(default_factory=set[str])

    # Gap block flag
    is_gap: bool = False

    @property
    def is_active(self) -> bool:
        """Check if this block is currently active for billing purposes."""
        if self.is_gap:
            return False

        now = datetime.now(self.start_time.tzinfo)

        # Check if current time is after block end time
        if now >= self.end_time:
            return False

        # Check time since last activity
        last_activity = self.actual_end_time or self.start_time
        time_since_activity = (now - last_activity).total_seconds()
        session_duration_seconds = 5 * 3600  # 5 hours in seconds

        return time_since_activity < session_duration_seconds

    def add_entry(self, entry: UnifiedEntry) -> None:
        """Add an entry to this block and update aggregated data."""
        self.entries.append(entry)

        # Update timestamps
        if self.actual_end_time is None or entry.timestamp > self.actual_end_time:
            self.actual_end_time = entry.timestamp

        # Update tokens
        usage = entry.token_usage
        self.token_usage.input_tokens += usage.input_tokens
        self.token_usage.output_tokens += usage.output_tokens
        self.token_usage.cache_creation_input_tokens += usage.cache_creation_input_tokens
        self.token_usage.cache_read_input_tokens += usage.cache_read_input_tokens
        self.token_usage.actual_input_tokens += usage.actual_input_tokens
        self.token_usage.actual_output_tokens += usage.actual_output_tokens
        self.token_usage.actual_cache_creation_input_tokens += usage.actual_cache_creation_input_tokens
        self.token_usage.actual_cache_read_input_tokens += usage.actual_cache_read_input_tokens

        self.total_tokens = self.token_usage.total
        self.actual_tokens = self.token_usage.actual_total

        # Update messages
        self.messages_processed += 1

        # Update cost
        self.cost_usd += entry.cost_usd

        # Update model tracking
        self.models_used.add(entry.model)
        self.full_model_names.add(entry.full_model_name)

        if entry.model not in self.model_tokens:
            self.model_tokens[entry.model] = 0
        self.model_tokens[entry.model] += usage.total

        if entry.model not in self.model_message_counts:
            self.model_message_counts[entry.model] = 0
        self.model_message_counts[entry.model] += 1

        # Update tool tracking
        self.tools_used.update(entry.tools_used)
        self.total_tool_calls += entry.tool_use_count

        for tool in entry.tools_used:
            if tool not in self.tool_call_counts:
                self.tool_call_counts[tool] = 0
            self.tool_call_counts[tool] += 1

        # Update project/session tracking
        self.projects.add(entry.project_name)
        self.sessions.add(entry.session_id)

    async def get_total_cost(self) -> float:
        """Calculate total cost for this unified block from its entries."""
        from .pricing import calculate_token_cost

        total_cost = 0.0
        for entry in self.entries:
            usage = entry.token_usage
            try:
                cost = await calculate_token_cost(
                    entry.full_model_name,
                    usage.actual_input_tokens,
                    usage.actual_output_tokens,
                    usage.actual_cache_creation_input_tokens,
                    usage.actual_cache_read_input_tokens,
                )
                total_cost += cost.total_cost
            except Exception:
                # If cost calculation fails for any entry, skip it
                continue

        return total_cost


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


@dataclass
class TimeBucketSummary:
    """Summary statistics for a specific time bucket."""

    period_name: str  # e.g., "2025-01", "2025-W04", "2025-01-29", "All Time"
    start_date: datetime
    end_date: datetime

    # Token statistics
    total_tokens: int = 0
    average_tokens: float = 0.0
    p90_tokens: int = 0

    # Message statistics
    total_messages: int = 0
    average_messages: float = 0.0
    p90_messages: int = 0

    # Cost statistics
    total_cost: float = 0.0
    average_cost: float = 0.0
    p90_cost: float = 0.0

    # Activity statistics
    active_projects: int = 0
    active_sessions: int = 0
    unified_blocks_count: int = 0

    # Model breakdown
    tokens_by_model: dict[str, int] = field(default_factory=dict[str, int])
    messages_by_model: dict[str, int] = field(default_factory=dict[str, int])
    cost_by_model: dict[str, float] = field(default_factory=dict[str, float])

    # Tool usage
    tool_usage: dict[str, int] = field(default_factory=dict[str, int])
    total_tool_calls: int = 0


@dataclass
class UsageSummaryData:
    """Overall usage summary containing all time buckets and aggregate statistics."""

    time_bucket_type: str  # "daily", "weekly", "monthly", "all"
    buckets: list[TimeBucketSummary] = field(default_factory=list[TimeBucketSummary])

    # Overall statistics (across all buckets)
    overall_total_tokens: int = 0
    overall_total_messages: int = 0
    overall_total_cost: float = 0.0
    overall_average_tokens: float = 0.0
    overall_average_messages: float = 0.0
    overall_average_cost: float = 0.0
    overall_p90_tokens: int = 0
    overall_p90_messages: int = 0
    overall_p90_cost: float = 0.0

    # Time span
    earliest_date: datetime | None = None
    latest_date: datetime | None = None
    total_time_span_days: int = 0

    # Activity overview
    unique_projects: set[str] = field(default_factory=set[str])
    unique_sessions: set[str] = field(default_factory=set[str])
    unique_models: set[str] = field(default_factory=set[str])
    unique_tools: set[str] = field(default_factory=set[str])

    def add_bucket(self, bucket: TimeBucketSummary) -> None:
        """Add a time bucket to the summary."""
        self.buckets.append(bucket)

        # Update overall statistics
        self.overall_total_tokens += bucket.total_tokens
        self.overall_total_messages += bucket.total_messages
        self.overall_total_cost += bucket.total_cost

        # Update time span
        if self.earliest_date is None or bucket.start_date < self.earliest_date:
            self.earliest_date = bucket.start_date
        if self.latest_date is None or bucket.end_date > self.latest_date:
            self.latest_date = bucket.end_date

        # Update unique sets from bucket data
        for model in bucket.tokens_by_model.keys():
            self.unique_models.add(model)
        for tool in bucket.tool_usage.keys():
            self.unique_tools.add(tool)

    def calculate_overall_averages(self) -> None:
        """Calculate overall averages across all buckets."""
        if not self.buckets:
            return

        active_bucket_count = len([b for b in self.buckets if b.total_tokens > 0])

        if active_bucket_count > 0:
            self.overall_average_tokens = self.overall_total_tokens / active_bucket_count
            self.overall_average_messages = self.overall_total_messages / active_bucket_count
            self.overall_average_cost = self.overall_total_cost / active_bucket_count

        # Calculate time span
        if self.earliest_date and self.latest_date:
            self.total_time_span_days = (self.latest_date - self.earliest_date).days + 1

    def calculate_overall_p90(self) -> None:
        """Calculate overall P90 values across all buckets."""
        if not self.buckets:
            return

        import statistics

        # Get non-zero values for P90 calculation
        token_values = [b.total_tokens for b in self.buckets if b.total_tokens > 0]
        message_values = [b.total_messages for b in self.buckets if b.total_messages > 0]
        cost_values = [b.total_cost for b in self.buckets if b.total_cost > 0]

        if token_values:
            if len(token_values) == 1:
                self.overall_p90_tokens = token_values[0]
            else:
                self.overall_p90_tokens = int(statistics.quantiles(token_values, n=10)[8])

        if message_values:
            if len(message_values) == 1:
                self.overall_p90_messages = message_values[0]
            else:
                self.overall_p90_messages = int(statistics.quantiles(message_values, n=10)[8])

        if cost_values:
            if len(cost_values) == 1:
                self.overall_p90_cost = cost_values[0]
            else:
                self.overall_p90_cost = statistics.quantiles(cost_values, n=10)[8]
