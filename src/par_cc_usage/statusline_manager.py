"""Status line management for Claude Code integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import Config
from .models import UsageSnapshot
from .pricing import format_cost
from .token_calculator import format_token_count
from .xdg_dirs import (
    ensure_xdg_directories,
    get_grand_total_statusline_path,
    get_statusline_file_path,
)


class StatusLineManager:
    """Manages status line generation and caching for Claude Code."""

    def __init__(self, config: Config):
        """Initialize the status line manager.

        Args:
            config: Application configuration
        """
        self.config = config
        ensure_xdg_directories()

    def _get_config_limits(self) -> tuple[int | None, int | None, float | None]:
        """Get token, message, and cost limits from config.

        Returns:
            Tuple of (token_limit, message_limit, cost_limit)
        """
        # Get limits from config (using P90 if enabled)
        if self.config.display.use_p90_limit:
            token_limit = self.config.p90_unified_block_tokens_encountered
            message_limit = self.config.p90_unified_block_messages_encountered
            cost_limit = self.config.p90_unified_block_cost_encountered
        else:
            token_limit = self.config.max_unified_block_tokens_encountered
            message_limit = self.config.max_unified_block_messages_encountered
            cost_limit = self.config.max_unified_block_cost_encountered

        # Fall back to configured limits if no historical data
        if not token_limit or token_limit == 0:
            token_limit = self.config.token_limit
        if not message_limit or message_limit == 0:
            message_limit = self.config.message_limit
        if not cost_limit or cost_limit == 0:
            cost_limit = self.config.cost_limit

        return token_limit, message_limit, cost_limit

    def _calculate_time_remaining(self, block_end_time: datetime) -> str | None:
        """Calculate time remaining in the block.

        Args:
            block_end_time: End time of the block

        Returns:
            Formatted time remaining string or None
        """
        now = datetime.now(block_end_time.tzinfo)
        remaining = block_end_time - now

        if remaining.total_seconds() <= 0:
            return None

        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def format_status_line(
        self,
        tokens: int,
        messages: int,
        cost: float = 0.0,
        token_limit: int | None = None,
        message_limit: int | None = None,
        cost_limit: float | None = None,
        time_remaining: str | None = None,
    ) -> str:
        """Format a status line string.

        Args:
            tokens: Token count
            messages: Message count
            cost: Total cost in USD
            token_limit: Token limit (optional)
            message_limit: Message limit (optional)
            cost_limit: Cost limit in USD (optional)
            time_remaining: Time remaining in block (optional)

        Returns:
            Formatted status line string
        """
        parts = []

        # Tokens part
        if token_limit and token_limit > 0:
            percentage = min(100, (tokens / token_limit) * 100)
            parts.append(f"🪙 {format_token_count(tokens)}/{format_token_count(token_limit)} ({percentage:.0f}%)")
        else:
            parts.append(f"🪙 {format_token_count(tokens)}")

        # Messages part
        if message_limit and message_limit > 0:
            parts.append(f"💬 {messages:,}/{message_limit:,}")
        else:
            parts.append(f"💬 {messages:,}")

        # Cost part (only if cost > 0)
        if cost > 0:
            if cost_limit and cost_limit > 0:
                parts.append(f"💰 {format_cost(cost)}/{format_cost(cost_limit)}")
            else:
                parts.append(f"💰 {format_cost(cost)}")

        # Time remaining part
        if time_remaining:
            parts.append(f"⏱️ {time_remaining}")

        return " - ".join(parts)

    def save_status_line(self, session_id: str, status_line: str) -> None:
        """Save a status line to disk.

        Args:
            session_id: Session ID or "grand_total" for the grand total
            status_line: The formatted status line to save
        """
        if session_id == "grand_total":
            file_path = get_grand_total_statusline_path()
        else:
            file_path = get_statusline_file_path(session_id)

        # Write status line as plain text on a single line
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(status_line)

    def load_status_line(self, session_id: str) -> str | None:
        """Load a cached status line from disk.

        Args:
            session_id: Session ID or "grand_total" for the grand total

        Returns:
            The cached status line or None if not found/expired
        """
        if session_id == "grand_total":
            file_path = get_grand_total_statusline_path()
        else:
            file_path = get_statusline_file_path(session_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                # Read the plain text status line
                return f.read().strip()
        except OSError:
            return None

    def generate_session_status_line(self, usage_snapshot: UsageSnapshot, session_id: str) -> str:
        """Generate a status line for a specific session.

        Args:
            usage_snapshot: Current usage snapshot
            session_id: Session ID to generate status for

        Returns:
            Formatted status line for the session
        """
        # Find the session in the unified blocks
        session_tokens = 0
        session_messages = 0
        session_cost = 0.0
        time_remaining = None

        # Get the current unified block (most recent one)
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]  # Most recent block

            # Calculate time remaining in block
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

            # Calculate session data from unified block entries
            if session_id in current_block.sessions:
                for entry in current_block.entries:
                    if entry.session_id == session_id:
                        session_tokens += entry.token_usage.total
                        session_messages += 1  # Each entry is a message
                        session_cost += entry.cost_usd  # Sum up costs from entries

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line(
            tokens=session_tokens,
            messages=session_messages,
            cost=session_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
        )

    def generate_grand_total_status_line(self, usage_snapshot: UsageSnapshot) -> str:
        """Generate a status line for the grand total.

        Args:
            usage_snapshot: Current usage snapshot

        Returns:
            Formatted status line for the grand total
        """
        total_tokens = usage_snapshot.unified_block_tokens()
        total_messages = usage_snapshot.unified_block_messages()
        time_remaining = None

        # Get time remaining from current block
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        # Note: Cost calculation requires async, so we'll use 0 for now
        # This can be improved later with async support
        return self.format_status_line(
            tokens=total_tokens,
            messages=total_messages,
            cost=0.0,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
        )

    async def generate_grand_total_status_line_async(self, usage_snapshot: UsageSnapshot) -> str:
        """Generate a status line for the grand total with cost calculation.

        Args:
            usage_snapshot: Current usage snapshot

        Returns:
            Formatted status line for the grand total including cost
        """
        total_tokens = usage_snapshot.unified_block_tokens()
        total_messages = usage_snapshot.unified_block_messages()
        time_remaining = None

        # Get time remaining from current block
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

        # Calculate cost asynchronously
        try:
            total_cost = await usage_snapshot.get_unified_block_total_cost()
        except Exception:
            total_cost = 0.0

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line(
            tokens=total_tokens,
            messages=total_messages,
            cost=total_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
        )

    def update_status_lines(self, usage_snapshot: UsageSnapshot) -> None:
        """Update all status line cache files.

        Args:
            usage_snapshot: Current usage snapshot
        """
        if not self.config.statusline_enabled:
            return

        # Update grand total
        grand_total_line = self.generate_grand_total_status_line(usage_snapshot)
        self.save_status_line("grand_total", grand_total_line)

        # Update per-session status lines if we have unified block data
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]  # Most recent block
            for session_id in current_block.sessions:
                session_line = self.generate_session_status_line(usage_snapshot, session_id)
                self.save_status_line(session_id, session_line)

    async def _calculate_session_cost(self, entries, session_id: str) -> float:
        """Calculate cost for session entries.

        Args:
            entries: List of unified entries
            session_id: Session ID to calculate cost for

        Returns:
            Total cost in USD
        """
        from .pricing import calculate_token_cost

        total_cost = 0.0
        for entry in entries:
            if entry.session_id != session_id:
                continue

            usage = entry.token_usage
            try:
                cost_result = await calculate_token_cost(
                    entry.full_model_name,
                    usage.actual_input_tokens,
                    usage.actual_output_tokens,
                    usage.actual_cache_creation_input_tokens,
                    usage.actual_cache_read_input_tokens,
                )
                total_cost += cost_result.total_cost
            except Exception:
                # Fall back to entry's cost_usd if calculation fails
                total_cost += entry.cost_usd

        return total_cost

    async def generate_session_status_line_async(self, usage_snapshot: UsageSnapshot, session_id: str) -> str:
        """Generate a status line for a specific session with cost data from unified block.

        Args:
            usage_snapshot: Current usage snapshot
            session_id: Session ID to generate status for

        Returns:
            Formatted status line for the session including cost
        """
        # Find the session in the unified blocks
        session_tokens = 0
        session_messages = 0
        session_cost = 0.0
        time_remaining = None

        # Get the current unified block (most recent one)
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]  # Most recent block

            # Calculate time remaining in block
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

            # Calculate session data from unified block entries
            if session_id in current_block.sessions:
                for entry in current_block.entries:
                    if entry.session_id == session_id:
                        session_tokens += entry.token_usage.total
                        session_messages += 1  # Each entry is a message

                # Calculate cost separately to reduce complexity
                session_cost = await self._calculate_session_cost(current_block.entries, session_id)

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line(
            tokens=session_tokens,
            messages=session_messages,
            cost=session_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
        )

    async def update_status_lines_async(self, usage_snapshot: UsageSnapshot) -> None:
        """Update all status line cache files with cost calculation.

        Args:
            usage_snapshot: Current usage snapshot
        """
        if not self.config.statusline_enabled:
            return

        # Update grand total with cost
        grand_total_line = await self.generate_grand_total_status_line_async(usage_snapshot)
        self.save_status_line("grand_total", grand_total_line)

        # Update per-session status lines with cost data from unified block
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]  # Most recent block
            for session_id in current_block.sessions:
                # Use async version to ensure we have the cost data
                session_line = await self.generate_session_status_line_async(usage_snapshot, session_id)
                self.save_status_line(session_id, session_line)

    def get_status_line_for_request(self, session_json: dict[str, Any]) -> str:
        """Get the appropriate status line for a Claude Code request.

        Args:
            session_json: JSON data from Claude Code containing session info

        Returns:
            The appropriate status line string
        """
        # Check if statusline is enabled
        if not self.config.statusline_enabled:
            return ""

        # Check if we should always use grand total
        if self.config.statusline_use_grand_total:
            cached = self.load_status_line("grand_total")
            return cached or "🪙 0 - 💬 0"

        # Try to extract session ID from the JSON
        session_id = session_json.get("sessionId") or session_json.get("session_id")

        if session_id:
            # Try to load cached session status line
            cached = self.load_status_line(session_id)
            if cached:
                return cached

        # Fall back to grand total
        cached = self.load_status_line("grand_total")
        return cached or "🪙 0 - 💬 0"
