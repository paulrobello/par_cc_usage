"""Token block calculations for par_cc_usage."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytz

from .json_models import TokenUsageData, ValidationResult
from .models import (
    DeduplicationState,
    Project,
    Session,
    TokenBlock,
    TokenUsage,
    UnifiedBlock,
    UnifiedEntry,
    UsageSnapshot,
)

logger = logging.getLogger(__name__)


class UnifiedBlockCalculator:
    """Calculates unified blocks across all projects and sessions."""

    def __init__(self, session_duration_hours: int = 5):
        """Initialize the calculator.

        Args:
            session_duration_hours: Duration of each block in hours (default: 5)
        """
        self.session_duration_hours = session_duration_hours
        self.session_duration_ms = session_duration_hours * 60 * 60 * 1000

    def create_unified_blocks(self, entries: list[UnifiedEntry]) -> list[UnifiedBlock]:
        """Create unified blocks from entries.

        This implements standard identifySessionBlocks logic:
        1. Sort entries by timestamp
        2. Group into blocks based on time proximity
        3. Create gap blocks for significant gaps

        Args:
            entries: List of unified entries from all projects/sessions

        Returns:
            List of unified blocks
        """
        if not entries:
            return []

        # Sort entries by timestamp
        sorted_entries = sorted(entries, key=lambda e: e.timestamp)

        blocks: list[UnifiedBlock] = []
        current_block_start: datetime | None = None
        current_block: UnifiedBlock | None = None

        for entry in sorted_entries:
            if current_block_start is None:
                # First entry - start a new block
                current_block_start, current_block = self._start_new_block(entry)
            else:
                # Check if we need to start a new block
                if self._should_start_new_block(entry, current_block_start, current_block):
                    # Close current block and handle gap if needed
                    blocks = self._close_and_handle_gap(blocks, current_block, entry)
                    # Start new block
                    current_block_start, current_block = self._start_new_block(entry)
                else:
                    # Add to current block
                    if current_block:
                        current_block.add_entry(entry)

        # Close the last block
        if current_block:
            blocks.append(current_block)

        return blocks

    def _should_start_new_block(
        self, entry: UnifiedEntry, current_block_start: datetime, current_block: UnifiedBlock | None
    ) -> bool:
        """Check if we should start a new block for this entry."""
        entry_time = entry.timestamp
        time_since_block_start = (entry_time - current_block_start).total_seconds() * 1000

        if current_block and current_block.actual_end_time:
            time_since_last_entry = (entry_time - current_block.actual_end_time).total_seconds() * 1000
        else:
            time_since_last_entry = 0

        return time_since_block_start > self.session_duration_ms or time_since_last_entry > self.session_duration_ms

    def _start_new_block(self, entry: UnifiedEntry) -> tuple[datetime, UnifiedBlock]:
        """Start a new block for the given entry."""
        block_start = _floor_to_hour(entry.timestamp)
        block = self._create_block(block_start)
        block.add_entry(entry)
        return block_start, block

    def _close_and_handle_gap(
        self, blocks: list[UnifiedBlock], current_block: UnifiedBlock | None, next_entry: UnifiedEntry
    ) -> list[UnifiedBlock]:
        """Close current block and add gap block if needed."""
        if current_block:
            blocks.append(current_block)

            # Add gap block if there's a significant gap
            if current_block.actual_end_time:
                time_since_last = (next_entry.timestamp - current_block.actual_end_time).total_seconds() * 1000
                if time_since_last > self.session_duration_ms:
                    gap_block = self._create_gap_block(current_block.actual_end_time, next_entry.timestamp)
                    if gap_block:
                        blocks.append(gap_block)

        return blocks

    def _create_block(self, start_time: datetime) -> UnifiedBlock:
        """Create a new unified block.

        Args:
            start_time: Block start time (already floored to hour)

        Returns:
            New UnifiedBlock instance
        """
        end_time = start_time + timedelta(hours=self.session_duration_hours)

        return UnifiedBlock(
            id=start_time.isoformat(),
            start_time=start_time,
            end_time=end_time,
        )

    def _create_gap_block(self, last_activity_time: datetime, next_activity_time: datetime) -> UnifiedBlock | None:
        """Create a gap block representing periods with no activity.

        Args:
            last_activity_time: Time of last activity before gap
            next_activity_time: Time of next activity after gap

        Returns:
            Gap block or None if gap is too short
        """
        # Only create gap blocks for gaps longer than the session duration
        gap_duration = (next_activity_time - last_activity_time).total_seconds() * 1000
        if gap_duration <= self.session_duration_ms:
            return None

        gap_start = last_activity_time + timedelta(hours=self.session_duration_hours)
        gap_end = next_activity_time

        return UnifiedBlock(
            id=f"gap-{gap_start.isoformat()}",
            start_time=gap_start,
            end_time=gap_end,
            is_gap=True,
        )

    def find_current_unified_block(self, blocks: list[UnifiedBlock]) -> UnifiedBlock | None:
        """Find the currently active unified block.

        Args:
            blocks: List of unified blocks

        Returns:
            The currently active block or None
        """
        for block in blocks:
            if block.is_active:
                return block
        return None


def _get_model_multiplier(model: str) -> float:
    """Get the model multiplier based on model name."""
    if "opus" in model.lower():
        return 5.0
    return 1.0


def _populate_model_tokens(block: TokenBlock, model: str, token_usage: TokenUsage) -> None:
    """Populate the model_tokens dictionary with adjusted tokens."""
    normalized_model = normalize_model_name(model)

    # Use display tokens from token_usage (already multiplied)
    display_tokens = token_usage.total

    # Use actual tokens from token_usage (raw from JSONL)
    actual_tokens = token_usage.actual_total

    # Update display tokens (for UI)
    if normalized_model not in block.model_tokens:
        block.model_tokens[normalized_model] = 0
    block.model_tokens[normalized_model] += display_tokens

    # Update actual tokens (for pricing)
    if normalized_model not in block.actual_model_tokens:
        block.actual_model_tokens[normalized_model] = 0
    block.actual_model_tokens[normalized_model] += actual_tokens


def _populate_model_messages(block: TokenBlock, model: str, token_usage: TokenUsage) -> None:
    """Populate the model_message_counts dictionary with message counts."""
    normalized_model = normalize_model_name(model)

    if normalized_model not in block.model_message_counts:
        block.model_message_counts[normalized_model] = 0
    block.model_message_counts[normalized_model] += token_usage.message_count


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

    # Store actual tokens (raw from JSONL)
    actual_input_tokens = input_tokens
    actual_cache_creation_input_tokens = cache_creation_input_tokens
    actual_cache_read_input_tokens = cache_read_input_tokens
    actual_output_tokens = output_tokens

    # Calculate display tokens (actual x multiplier)
    multiplier = _get_model_multiplier(model)
    display_input_tokens = int(input_tokens * multiplier)
    display_cache_creation_input_tokens = int(cache_creation_input_tokens * multiplier)
    display_cache_read_input_tokens = int(cache_read_input_tokens * multiplier)
    display_output_tokens = int(output_tokens * multiplier)

    return TokenUsage(
        input_tokens=display_input_tokens,
        cache_creation_input_tokens=display_cache_creation_input_tokens,
        cache_read_input_tokens=display_cache_read_input_tokens,
        output_tokens=display_output_tokens,
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
        message_count=1,  # Each TokenUsage represents one message
        actual_input_tokens=actual_input_tokens,
        actual_cache_creation_input_tokens=actual_cache_creation_input_tokens,
        actual_cache_read_input_tokens=actual_cache_read_input_tokens,
        actual_output_tokens=actual_output_tokens,
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

        # Update max cost in config if needed
        _update_max_cost_if_needed(block.cost_usd)

        if token_usage.version and token_usage.version not in block.versions:
            block.versions.append(token_usage.version)

        # Update per-model tokens with multipliers
        _populate_model_tokens(block, model, token_usage)

        # Update total actual tokens for the block
        block.actual_tokens += token_usage.actual_total

        # Update per-model message counts
        _populate_model_messages(block, model, token_usage)

        # Update total message count
        block.message_count += token_usage.message_count

        # Update tool usage
        _update_block_tool_usage(block, token_usage)

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

    # Additional check: Create new block if message timestamp >= block end time
    # This matches standard logic: blocks become inactive when current time >= end time
    block_end_time = latest_block.start_time + timedelta(hours=session_duration_hours)
    if timestamp >= block_end_time:
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

    # Update max cost in config if needed
    _update_max_cost_if_needed(block.cost_usd)

    # Populate per-model tokens with multipliers
    _populate_model_tokens(block, model, token_usage)

    # Set total actual tokens for the block
    block.actual_tokens = token_usage.actual_total

    # Populate per-model message counts
    _populate_model_messages(block, model, token_usage)

    # Initialize total message count
    block.message_count = token_usage.message_count

    # Initialize tool usage
    _update_block_tool_usage(block, token_usage)

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
        logger.debug(f"Validation failed: {validation_result.errors}")
        return None

    validated_data = validation_result.data

    # Check if message data exists
    if validated_data.message is None:
        logger.debug("No message data found in validated data")
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


def create_unified_entry(
    data: dict[str, Any],
    project_path: str,
    session_id: str,
    dedup_state: DeduplicationState | None = None,
) -> UnifiedEntry | None:
    """Create a UnifiedEntry from JSONL data.

    Args:
        data: Parsed JSON data from line
        project_path: Path of the project
        session_id: Session ID
        dedup_state: Deduplication state (optional)

    Returns:
        UnifiedEntry or None if processing fails
    """
    try:
        # Validate and parse timestamp
        timestamp = _validate_and_parse_timestamp(data)
        if timestamp is None:
            return None

        # Process message data
        message_result = _process_message_data(data, dedup_state)
        if message_result is None:
            return None

        model, original_model, token_usage = message_result

        # Extract tool usage from message data
        message = data.get("message", {})
        tools_used, tool_use_count = extract_tool_usage(message)

        # Create unified entry
        return UnifiedEntry(
            timestamp=timestamp,
            project_name=project_path,
            session_id=session_id,
            model=model,
            full_model_name=original_model,
            token_usage=token_usage,
            tools_used=tools_used,
            tool_use_count=tool_use_count,
            cost_usd=token_usage.cost_usd or 0.0,
            version=token_usage.version,
        )

    except Exception:
        return None


def process_jsonl_line(
    data: dict[str, Any],
    project_path: str,
    session_id: str,
    projects: dict[str, Project],
    dedup_state: DeduplicationState | None = None,
    timezone_str: str = "America/Los_Angeles",
    unified_entries: list[UnifiedEntry] | None = None,
) -> None:
    """Process a single JSONL line and update projects data with robust error handling.

    Args:
        data: Parsed JSON data from line
        project_path: Path of the project (from directory structure)
        session_id: Session ID (from directory structure)
        projects: Dictionary of projects to update
        dedup_state: Deduplication state (optional)
        timezone_str: Timezone for display
        unified_entries: Optional list to collect unified entries for unified block calculation
    """
    # If unified_entries is provided, create and collect the entry
    if unified_entries is not None:
        entry = create_unified_entry(data, project_path, session_id, dedup_state)
        if entry is not None:
            unified_entries.append(entry)

    try:
        # Validate and parse timestamp
        timestamp = _validate_and_parse_timestamp(data)
        if timestamp is None:
            logger.debug(f"No timestamp found in data for session {session_id}")
            return

        # Get or create session
        session = _get_or_create_session(project_path, session_id, projects, timestamp)

        # Process message data
        message_result = _process_message_data(data, dedup_state)
        if message_result is None:
            logger.debug(f"No message data found for session {session_id}")
            return

        model, original_model, token_usage = message_result
        logger.debug(f"Processing message for session {session_id}: model={model}, tokens={token_usage.total}")

        # Update session model if different
        _update_session_model(session, model)

        # Process token usage into appropriate block
        _process_token_block(session, timestamp, session_id, project_path, model, original_model, token_usage)
        logger.debug(f"Session {session_id} now has {len(session.blocks)} blocks")

    except Exception:
        # Skip any entries that fail processing completely
        return


def _has_usage_data(projects: dict[str, Project]) -> bool:
    """Check if projects contain any usage data."""
    for project in projects.values():
        if project.sessions:
            return True
    return False


def _is_block_active(block: TokenBlock, now: datetime) -> bool:
    """Check if a block is currently active for billing purposes.

    A block is considered active if:
    1. It's not a gap block
    2. Current time is before block end time (start + 5 hours)
    3. Time since last activity is < 5 hours

    Args:
        block: TokenBlock to check
        now: Current time

    Returns:
        True if block is active
    """
    if block.is_gap:
        return False

    # Check if current time < block end time (start + 5 hours)
    block_end_time = block.start_time + timedelta(hours=5)
    if now >= block_end_time:
        return False

    # Check time since last activity < 5 hours
    last_activity = block.actual_end_time or block.start_time
    time_since_activity = (now - last_activity).total_seconds()
    return time_since_activity < (5 * 3600)  # 5 hours in seconds


def _is_block_active_style(block: TokenBlock, now: datetime) -> bool:
    """Check if a block is active using standard logic.

    Matches isActive logic:
    now.getTime() - actualEndTime.getTime() < sessionDurationMs && now < endTime

    Args:
        block: Token block to check
        now: Current datetime in UTC

    Returns:
        True if block is active according to standard criteria
    """
    session_duration_seconds = 5 * 3600  # 5 hours in seconds
    actual_end_time = block.actual_end_time or block.start_time
    end_time = block.start_time + timedelta(hours=5)

    time_since_activity = (now - actual_end_time).total_seconds()

    return time_since_activity < session_duration_seconds and now < end_time


def create_unified_blocks(unified_entries: list[UnifiedEntry]) -> list[UnifiedBlock]:
    """Create unified blocks from entries using standard approach.

    This function implements standard logic:
    1. Aggregates all entries across projects/sessions
    2. Creates blocks based on the unified timeline
    3. Returns blocks that represent actual billing periods

    Args:
        unified_entries: List of all entries from all projects/sessions

    Returns:
        List of unified blocks
    """
    calculator = UnifiedBlockCalculator()
    return calculator.create_unified_blocks(unified_entries)


def get_current_unified_block(unified_blocks: list[UnifiedBlock]) -> UnifiedBlock | None:
    """Get the currently active unified block.

    Args:
        unified_blocks: List of unified blocks

    Returns:
        The currently active block or None
    """
    calculator = UnifiedBlockCalculator()
    return calculator.find_current_unified_block(unified_blocks)


def _floor_to_hour(timestamp: datetime) -> datetime:
    """Floor a timestamp to the beginning of the hour in UTC.

    Args:
        timestamp: The timestamp to floor

    Returns:
        New datetime object floored to the UTC hour
    """
    # Convert to UTC if needed
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    elif timestamp.tzinfo != UTC:
        timestamp = timestamp.astimezone(UTC)

    # Floor to the nearest hour
    return timestamp.replace(minute=0, second=0, microsecond=0)


def aggregate_usage(
    projects: dict[str, Project],
    token_limit: int | None = None,
    message_limit: int | None = None,
    timezone_str: str = "America/Los_Angeles",
    block_start_override: datetime | None = None,
    unified_blocks: list[UnifiedBlock] | None = None,
) -> UsageSnapshot:
    """Aggregate usage data into a snapshot.

    Args:
        projects: Dictionary of projects
        token_limit: Token limit for display
        message_limit: Message limit for display
        timezone_str: Timezone for display
        block_start_override: Override for block start time
        unified_blocks: Optional list of unified blocks (new approach)

    Returns:
        Usage snapshot
    """
    tz = pytz.timezone(timezone_str)
    current_time = datetime.now(tz)

    # Determine unified block start time from unified blocks
    if unified_blocks:
        current_block = get_current_unified_block(unified_blocks)
        unified_start = current_block.start_time if current_block else None
    else:
        unified_start = None

    snapshot = UsageSnapshot(
        timestamp=current_time,
        projects=projects,
        total_limit=token_limit,
        message_limit=message_limit,
        block_start_override=block_start_override or unified_start,
        unified_blocks=unified_blocks or [],
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


def _update_max_cost_if_needed(block_cost: float, config_file_path: Path | None = None) -> None:
    """Update max cost in config if block cost exceeds current max.

    Args:
        block_cost: Cost of the current block
        config_file_path: Path to config file (optional, will auto-detect if None)
    """
    if block_cost <= 0:
        return

    # Import here to avoid circular imports
    from .config import load_config, save_config
    from .xdg_dirs import get_config_file_path

    try:
        # Load current config
        if config_file_path is None:
            config_file_path = get_config_file_path()

        config = load_config()

        # Check if block cost exceeds max
        if block_cost > config.max_cost_encountered:
            config.max_cost_encountered = block_cost
            save_config(config, config_file_path)

    except Exception as e:
        # Log error but don't fail processing
        logging.debug(f"Failed to update max cost in config: {e}")
