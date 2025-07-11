"""Token block calculations for par_cc_usage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytz

from .json_models import TokenUsageData, ValidationResult
from .models import DeduplicationState, Project, Session, TokenBlock, TokenUsage, UsageSnapshot


def _get_model_multiplier(model: str) -> float:
    """Get the model multiplier based on model name."""
    if "opus" in model.lower():
        return 5.0
    return 1.0


def _populate_model_tokens(block: TokenBlock, model: str, token_usage: TokenUsage) -> None:
    """Populate the model_tokens dictionary with adjusted tokens."""
    normalized_model = normalize_model_name(model)
    multiplier = _get_model_multiplier(normalized_model)
    adjusted_tokens = int(token_usage.total * multiplier)

    if normalized_model not in block.model_tokens:
        block.model_tokens[normalized_model] = 0
    block.model_tokens[normalized_model] += adjusted_tokens


def _update_block_tool_usage(block: TokenBlock, token_usage: TokenUsage) -> None:
    """Update block tool usage with data from token usage."""
    # Count tool occurrences from the token usage
    from collections import Counter

    tool_counts = Counter(token_usage.tools_used)

    # Add tools to the set of tools used in this block and update counts
    for tool, count in tool_counts.items():
        block.tools_used.add(tool)
        # Update per-tool call counts
        if tool not in block.tool_call_counts:
            block.tool_call_counts[tool] = 0
        block.tool_call_counts[tool] += count

    # Add to total tool calls count
    block.total_tool_calls += token_usage.tool_use_count


def _update_block_interruption_tracking(block: TokenBlock, token_usage: TokenUsage) -> None:
    """Update block interruption tracking with data from token usage."""
    if token_usage.was_interrupted:
        # Increment total interruptions
        block.total_interruptions += 1

        # Track per-model interruptions
        normalized_model = normalize_model_name(token_usage.model or "unknown")
        if normalized_model not in block.interruptions_by_model:
            block.interruptions_by_model[normalized_model] = 0
        block.interruptions_by_model[normalized_model] += 1


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime with multiple parsing strategies.

    Args:
        timestamp_str: Timestamp string in various formats

    Returns:
        Parsed datetime with timezone

    Raises:
        ValueError: If timestamp cannot be parsed
    """
    if not timestamp_str:
        raise ValueError("Empty timestamp string")

    # Try different parsing strategies
    try:
        # Strategy 1: ISO format with 'Z' (UTC)
        if timestamp_str.endswith("Z"):
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Strategy 2: ISO format with timezone
        elif "+" in timestamp_str or timestamp_str.count("-") > 2:
            return datetime.fromisoformat(timestamp_str)

        # Strategy 3: Unix timestamp
        elif timestamp_str.isdigit() or (timestamp_str.startswith("-") and timestamp_str[1:].isdigit()):
            return datetime.fromtimestamp(int(timestamp_str), tz=UTC)

        # Strategy 4: ISO format without timezone (assume UTC)
        else:
            dt = datetime.fromisoformat(timestamp_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt

    except Exception as e:
        raise ValueError(f"Unable to parse timestamp: {timestamp_str}") from e


def calculate_block_start(timestamp: datetime) -> datetime:
    """Calculate the start time of the 5-hour block for a given timestamp.

    Uses simple UTC hour flooring approach.

    Args:
        timestamp: Timestamp to calculate block for

    Returns:
        Start time of the block (floored to the hour in UTC)
    """
    # Convert to UTC if needed
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    elif timestamp.tzinfo != UTC:
        timestamp = timestamp.astimezone(UTC)

    # Floor to the nearest hour
    return timestamp.replace(minute=0, second=0, microsecond=0)


def calculate_block_end(block_start: datetime) -> datetime:
    """Calculate the end time of a block.

    Args:
        block_start: Start time of the block

    Returns:
        End time of the block (5 hours later)
    """
    return block_start + timedelta(hours=5)


def is_block_active(block_start: datetime, current_time: datetime | None = None) -> bool:
    """Check if a block is currently active.

    Args:
        block_start: Start time of the block
        current_time: Current time to check against (default: now)

    Returns:
        True if the block is active
    """
    if current_time is None:
        current_time = datetime.now(block_start.tzinfo)

    block_end = calculate_block_end(block_start)
    return block_start <= current_time < block_end


def create_gap_block(
    last_activity_time: datetime,
    next_activity_time: datetime,
    session_id: str,
    project_name: str,
    session_duration_hours: int = 5,
) -> TokenBlock | None:
    """Create a gap block between two activity periods.

    Args:
        last_activity_time: Time of last activity
        next_activity_time: Time of next activity
        session_id: Session ID
        project_name: Project name
        session_duration_hours: Session duration in hours

    Returns:
        Gap block or None if gap is too small
    """
    gap_duration = (next_activity_time - last_activity_time).total_seconds()

    # Only create gap blocks for significant gaps
    if gap_duration > session_duration_hours * 3600:
        return TokenBlock(
            start_time=last_activity_time,
            end_time=next_activity_time,
            session_id=session_id,
            project_name=project_name,
            model="gap",
            token_usage=TokenUsage(),
            messages_processed=0,
            is_gap=True,
            block_id=f"gap-{last_activity_time.isoformat()}",
        )

    return None


def extract_tool_usage(message_data: dict[str, Any]) -> tuple[list[str], int]:
    """Extract tool usage information from message data.

    Args:
        message_data: Message data from JSONL

    Returns:
        Tuple of (tools_used, tool_use_count)
    """
    tools_used = []
    tool_use_count = 0

    # Get content array from message
    content = message_data.get("content", [])

    # Validate content is a list before processing
    if not content or not hasattr(content, "__iter__"):
        return tools_used, tool_use_count

    try:
        # Look for tool_use content blocks
        for content_block in content:
            # Ensure content_block has required structure
            if hasattr(content_block, "get") and content_block.get("type") == "tool_use" and content_block.get("name"):
                tool_name = content_block.get("name")
                tools_used.append(tool_name)
                tool_use_count += 1
    except (TypeError, AttributeError):
        # Return empty results if content structure is invalid
        pass

    return tools_used, tool_use_count


def extract_token_usage(data: dict[str, Any], message_data: dict[str, Any]) -> TokenUsage | None:
    """Extract token usage from a message data dictionary.

    Args:
        data: Top-level data from JSONL line
        message_data: Message data from JSONL

    Returns:
        TokenUsage instance or None if no usage data
    """
    usage_data = message_data.get("usage")
    if not usage_data:
        return None

    # Extract token counts with double-default protection pattern
    # This handles both missing keys and null values robustly
    input_tokens = usage_data.get("input_tokens", 0) or 0
    cache_creation_input_tokens = usage_data.get("cache_creation_input_tokens", 0) or 0
    cache_read_input_tokens = usage_data.get("cache_read_input_tokens", 0) or 0
    output_tokens = usage_data.get("output_tokens", 0) or 0

    # Extract other fields with appropriate defaults
    service_tier = usage_data.get("service_tier", "standard") or "standard"
    version = data.get("version") or None
    message_id = message_data.get("id") or None
    request_id = data.get("requestId") or None
    cost_usd = data.get("costUSD") or None
    is_api_error = data.get("isApiErrorMessage", False) or False
    model = normalize_model_name(message_data.get("model", "unknown"))

    # Extract tool usage information
    tools_used, tool_use_count = extract_tool_usage(message_data)

    # Extract interruption information
    was_interrupted = message_data.get("wasInterrupted", False) or False

    return TokenUsage(
        input_tokens=input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        output_tokens=output_tokens,
        service_tier=service_tier,
        version=version,
        message_id=message_id,
        request_id=request_id,
        cost_usd=cost_usd,
        is_api_error=is_api_error,
        timestamp=parse_timestamp(data["timestamp"]) if data.get("timestamp") else None,
        model=model,
        tools_used=tools_used,
        tool_use_count=tool_use_count,
        was_interrupted=was_interrupted,
    )


def _validate_and_parse_timestamp(data: dict[str, Any]) -> datetime | None:
    """Validate and parse timestamp from JSONL data.

    Args:
        data: Parsed JSON data from line

    Returns:
        Parsed timestamp or None if invalid
    """
    timestamp_str = data.get("timestamp")
    if not timestamp_str:
        return None

    try:
        return parse_timestamp(timestamp_str)
    except (ValueError, TypeError):
        return None


def _get_or_create_session(
    project_path: str, session_id: str, projects: dict[str, Project], timestamp: datetime
) -> Session:
    """Get or create session in project.

    Args:
        project_path: Path of the project
        session_id: Session ID
        projects: Dictionary of projects to update
        timestamp: Timestamp for session start tracking

    Returns:
        Session object
    """
    # Get or create project
    if project_path not in projects:
        projects[project_path] = Project(name=project_path)
    project = projects[project_path]

    # Get or create session
    if session_id not in project.sessions:
        project.sessions[session_id] = Session(
            session_id=session_id,
            project_name=project_path,
            model="unknown",
            project_path=project_path,
        )
    session = project.sessions[session_id]

    # Track session start time (first message of any type)
    if session.session_start is None:
        session.session_start = timestamp

    return session


def _process_token_usage(
    data: dict[str, Any], message: dict[str, Any], dedup_state: DeduplicationState | None
) -> TokenUsage | None:
    """Process and validate token usage data.

    Args:
        data: Parsed JSON data from line
        message: Message data
        dedup_state: Deduplication state (optional)

    Returns:
        TokenUsage or None if invalid
    """
    try:
        token_usage = extract_token_usage(data, message)
        if not token_usage or token_usage.total == 0:
            return None

        # Check for duplicates
        if dedup_state and token_usage.get_unique_hash():
            if dedup_state.is_duplicate(token_usage.get_unique_hash()):
                return None

        return token_usage
    except (KeyError, ValueError, TypeError):
        return None


def _update_existing_block(
    block: TokenBlock, token_usage: TokenUsage, model: str, original_model: str, timestamp: datetime
) -> bool:
    """Update existing block with new token usage.

    Args:
        block: Existing block to update
        token_usage: New token usage data
        model: Model name (normalized)
        original_model: Original full model name
        timestamp: Current timestamp

    Returns:
        True if update succeeded
    """
    try:
        block.token_usage = block.token_usage + token_usage
        block.messages_processed += 1
        block.model = model
        block.models_used.add(model)
        block.full_model_names.add(original_model)
        block.actual_end_time = timestamp
        block.cost_usd += token_usage.cost_usd or 0.0
        if token_usage.version and token_usage.version not in block.versions:
            block.versions.append(token_usage.version)

        # Update per-model tokens with multipliers
        _populate_model_tokens(block, model, token_usage)

        # Update tool usage
        _update_block_tool_usage(block, token_usage)

        # Update interruption tracking
        _update_block_interruption_tracking(block, token_usage)

        return True
    except Exception:
        return False


def _should_create_new_block(session: Session, timestamp: datetime, session_duration_hours: int = 5) -> bool:
    """Determine if a new block should be created.

    Args:
        session: Session to check
        timestamp: Current timestamp
        session_duration_hours: Session duration in hours

    Returns:
        True if a new block should be created
    """
    if not session.blocks:
        return True

    latest_block = session.latest_block
    if latest_block is None:
        return True

    # Check if time since block start > 5 hours
    time_since_start = (timestamp - latest_block.start_time).total_seconds()
    if time_since_start > session_duration_hours * 3600:
        return True

    # Check if time since last activity > 5 hours
    last_activity = latest_block.actual_end_time or latest_block.start_time
    time_since_activity = (timestamp - last_activity).total_seconds()
    if time_since_activity > session_duration_hours * 3600:
        return True

    return False


def _create_new_token_block(
    session: Session,
    timestamp: datetime,
    session_id: str,
    project_path: str,
    model: str,
    original_model: str,
    token_usage: TokenUsage,
) -> None:
    """Create a new token block and add it to the session."""
    # Create gap block if needed
    if session.latest_block and session.latest_block.actual_end_time:
        gap_block = create_gap_block(session.latest_block.actual_end_time, timestamp, session_id, project_path)
        if gap_block:
            session.add_block(gap_block)

    # Create new block
    block_start = calculate_block_start(timestamp)
    block_end = calculate_block_end(block_start)

    block = TokenBlock(
        start_time=block_start,
        end_time=block_end,
        session_id=session_id,
        project_name=project_path,
        model=model,
        token_usage=token_usage,
        messages_processed=1,
        models_used={model},
        full_model_names={original_model},
        actual_end_time=timestamp,
        block_id=block_start.isoformat(),
        cost_usd=token_usage.cost_usd or 0.0,
        versions=[token_usage.version] if token_usage.version else [],
    )

    # Populate per-model tokens with multipliers
    _populate_model_tokens(block, model, token_usage)

    # Initialize tool usage
    _update_block_tool_usage(block, token_usage)

    # Initialize interruption tracking
    _update_block_interruption_tracking(block, token_usage)

    session.add_block(block)


def _validate_jsonl_data(data: dict[str, Any]) -> ValidationResult:
    """Validate JSONL data using Pydantic models.

    Args:
        data: Raw JSON data from JSONL line

    Returns:
        ValidationResult with parsed data or errors
    """
    try:
        validated_data = TokenUsageData.model_validate(data)
        return ValidationResult.success(validated_data)
    except Exception as e:
        return ValidationResult.failure([str(e)])


def _process_message_data(
    data: dict[str, Any], dedup_state: DeduplicationState | None = None
) -> tuple[str, str, TokenUsage] | None:
    """Process message data and return normalized model, original model, and token usage."""
    # Validate using Pydantic models
    validation_result = _validate_jsonl_data(data)
    if not validation_result.is_valid or validation_result.data is None:
        return None

    validated_data = validation_result.data

    # Check if message data exists
    if validated_data.message is None:
        return None

    message_data = validated_data.message

    # Skip synthetic messages
    model = message_data.model or "unknown"
    normalized_model = normalize_model_name(model)
    if normalized_model == "synthetic":
        return None

    # Convert to legacy dict format for existing processing
    legacy_data = {
        "timestamp": validated_data.timestamp,
        "requestId": validated_data.request_id,
        "version": validated_data.version,
        "costUSD": validated_data.cost_usd,
        "isApiErrorMessage": validated_data.is_api_error_message,
    }

    legacy_message = {
        "id": message_data.id,
        "model": message_data.model,
        "usage": message_data.usage.model_dump() if message_data.usage else None,
        "content": [content.model_dump() for content in message_data.content],
        "wasInterrupted": message_data.was_interrupted,
    }

    # Process token usage using existing logic
    token_usage = _process_token_usage(legacy_data, legacy_message, dedup_state)
    if token_usage is None:
        return None

    return normalized_model, model, token_usage


def _update_session_model(session: Session, model: str) -> None:
    """Update session model if different from current model.

    Args:
        session: Session to update
        model: New model name
    """
    if session.model != model:
        session.model = model


def _process_token_block(
    session: Session,
    timestamp: datetime,
    session_id: str,
    project_path: str,
    model: str,
    original_model: str,
    token_usage: TokenUsage,
) -> None:
    """Process token usage into appropriate block (new or existing).

    Args:
        session: Session to update
        timestamp: Message timestamp
        session_id: Session identifier
        project_path: Project path
        model: Model name (normalized)
        original_model: Original full model name
        token_usage: Token usage data
    """
    if _should_create_new_block(session, timestamp):
        _create_new_token_block(session, timestamp, session_id, project_path, model, original_model, token_usage)
    else:
        # Add to existing block
        block = session.latest_block
        if block:
            _update_existing_block(block, token_usage, model, original_model, timestamp)


def process_jsonl_line(
    data: dict[str, Any],
    project_path: str,
    session_id: str,
    projects: dict[str, Project],
    dedup_state: DeduplicationState | None = None,
    timezone_str: str = "America/Los_Angeles",
) -> None:
    """Process a single JSONL line and update projects data with robust error handling.

    Args:
        data: Parsed JSON data from line
        project_path: Path of the project (from directory structure)
        session_id: Session ID (from directory structure)
        projects: Dictionary of projects to update
        dedup_state: Deduplication state (optional)
        timezone_str: Timezone for display
    """
    try:
        # Validate and parse timestamp
        timestamp = _validate_and_parse_timestamp(data)
        if timestamp is None:
            return

        # Get or create session
        session = _get_or_create_session(project_path, session_id, projects, timestamp)

        # Process message data
        message_result = _process_message_data(data, dedup_state)
        if message_result is None:
            return

        model, original_model, token_usage = message_result

        # Update session model if different
        _update_session_model(session, model)

        # Process token usage into appropriate block
        _process_token_block(session, timestamp, session_id, project_path, model, original_model, token_usage)

    except Exception:
        # Skip any entries that fail processing completely
        return


def create_unified_blocks(projects: dict[str, Project]) -> datetime | None:
    """Create unified block start time using optimal block selection logic.

    This implementation finds the active block that contains the current time,
    or falls back to the earliest active block if none contain the current time.

    Args:
        projects: Dictionary of projects with per-session blocks

    Returns:
        The current billing block start time or None if no active blocks exist
    """
    # Collect all blocks across all projects/sessions
    all_blocks = []
    for project in projects.values():
        for session in project.sessions.values():
            for block in session.blocks:
                if not block.is_gap:  # Skip gap blocks
                    all_blocks.append(block)

    # Filter for active blocks
    active_blocks = [block for block in all_blocks if block.is_active]

    if not active_blocks:
        return None

    # Find blocks that contain the current time
    now = datetime.now(UTC)
    current_blocks = [block for block in active_blocks if block.start_time <= now < block.end_time]

    if not current_blocks:
        # Fallback to earliest active block
        active_blocks.sort(key=lambda block: block.start_time)
        return active_blocks[0].start_time

    # Among blocks that contain the current time, return the earliest start time
    # This ensures consistent billing block representation
    current_blocks.sort(key=lambda block: block.start_time)
    return current_blocks[0].start_time


def aggregate_usage(
    projects: dict[str, Project],
    token_limit: int | None = None,
    timezone_str: str = "America/Los_Angeles",
    block_start_override: datetime | None = None,
) -> UsageSnapshot:
    """Aggregate usage data into a snapshot.

    Args:
        projects: Dictionary of projects
        token_limit: Token limit for display
        timezone_str: Timezone for display

    Returns:
        Usage snapshot
    """
    tz = pytz.timezone(timezone_str)
    current_time = datetime.now(tz)

    # Create unified blocks first
    unified_start = create_unified_blocks(projects)

    snapshot = UsageSnapshot(
        timestamp=current_time,
        projects=projects,
        total_limit=token_limit,
        block_start_override=block_start_override or unified_start,
    )

    return snapshot


def get_model_display_name(model: str) -> str:
    """Get a display-friendly model name with robust fallback handling.

    Args:
        model: Model identifier

    Returns:
        Display name
    """
    # Handle empty, None, or special cases
    if not model or model == "unknown" or model == "gap":
        return "Unknown"

    # Shorten common model names with robust pattern matching
    model_lower = model.lower()
    if "opus" in model_lower:
        return "Opus"
    elif "sonnet" in model_lower:
        return "Sonnet"
    elif "haiku" in model_lower:
        return "Haiku"
    elif "claude" in model_lower:
        # Handle other Claude models
        return "Claude"
    elif "gpt" in model_lower:
        # Handle GPT models
        return "GPT"
    elif "llama" in model_lower:
        # Handle Llama models
        return "Llama"

    # For completely unknown models, return truncated version
    if len(model) > 20:
        return model[:17] + "..."

    return model


def normalize_model_name(model: str) -> str:
    """Normalize model name for consistent tracking.

    Args:
        model: Raw model identifier

    Returns:
        Normalized model name
    """
    # Handle empty or None values
    if not model:
        return "unknown"

    # Convert to lowercase for consistency
    model = model.lower().strip()

    # Handle special cases
    if model == "<synthetic>":
        return "synthetic"

    # Normalize common patterns
    if "opus" in model:
        return "opus"
    elif "sonnet" in model:
        return "sonnet"
    elif "haiku" in model:
        return "haiku"
    elif "claude" in model:
        return "claude"
    elif "gpt" in model:
        return "gpt"
    elif "llama" in model:
        return "llama"

    # Return as-is for unknown models
    return model


def detect_token_limit_from_data(projects: dict[str, Project]) -> int | None:
    """Detect token limit from usage data.

    Analyzes the token usage patterns to infer the likely token limit.
    Looks at the total active tokens across all projects to estimate the limit.

    Args:
        projects: Dictionary of projects

    Returns:
        Detected token limit or None
    """
    # Calculate total active tokens across all projects
    total_active_tokens = sum(project.active_tokens for project in projects.values())

    # If we found active usage, estimate the limit
    if total_active_tokens > 0:
        # Round up to nearest reasonable limit
        # Common limits: 500k, 1M, 5M, 10M, 50M, 100M
        if total_active_tokens <= 500_000:
            return 500_000
        elif total_active_tokens <= 1_000_000:
            return 1_000_000
        elif total_active_tokens <= 5_000_000:
            return 5_000_000
        elif total_active_tokens <= 10_000_000:
            return 10_000_000
        elif total_active_tokens <= 50_000_000:
            return 50_000_000
        elif total_active_tokens <= 100_000_000:
            return 100_000_000
        else:
            # Round up to nearest 10 million
            return ((total_active_tokens // 10_000_000) + 1) * 10_000_000

    # Default if no active blocks found
    return 500_000


def format_token_count(count: int) -> str:
    """Format token count for display.

    Args:
        count: Token count

    Returns:
        Formatted string
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    else:
        return str(count)
