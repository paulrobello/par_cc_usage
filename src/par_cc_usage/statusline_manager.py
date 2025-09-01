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
    get_statusline_dir,
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
        project_name: str | None = None,
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
            project_name: Project name to display (optional)

        Returns:
            Formatted status line string
        """
        parts = []

        # Project name part (if provided) - in square brackets
        if project_name:
            parts.append(f"[{project_name}]")

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

    def _create_progress_bar(self, value: int, max_value: int, length: int | None = None) -> str:
        """Create a progress bar string.

        Args:
            value: Current value
            max_value: Maximum value
            length: Length of progress bar (defaults to config setting)

        Returns:
            Progress bar string, either basic Unicode or Rich-formatted
        """
        if length is None:
            length = self.config.statusline_progress_bar_length
            # Add 3 extra characters if showing percent (for "99%" or "100%")
            if self.config.statusline_progress_bar_show_percent:
                length += 3

        if max_value <= 0:
            if self.config.statusline_progress_bar_style == "rich":
                return self._create_rich_progress_bar(0, 100, length)
            return "[" + "░" * length + "]"

        percentage = min(100, max(0, int(value * 100 / max_value)))

        # Use Rich progress bar if configured
        if self.config.statusline_progress_bar_style == "rich":
            return self._create_rich_progress_bar(percentage, 100, length)

        # Basic style progress bar
        if self.config.statusline_progress_bar_show_percent:
            # Show percentage in center of bar
            percent_str = f"{percentage:>3}%"
            percent_len = len(percent_str)

            # Calculate total bar content length (excluding brackets)
            bar_length = length

            # Calculate the center position for the percentage text
            center_pos = (bar_length - percent_len) // 2

            # Calculate filled and empty portions
            filled_total = int(bar_length * percentage / 100)

            # Determine what goes before and after the percentage
            before_percent_len = center_pos
            after_percent_len = bar_length - center_pos - percent_len

            # Calculate how many filled chars go before and after the percentage
            filled_before = min(filled_total, before_percent_len)
            filled_after = max(0, min(filled_total - filled_before, after_percent_len))

            # Calculate empty chars
            empty_before = before_percent_len - filled_before
            empty_after = after_percent_len - filled_after

            # Create the bar parts
            before_percent = "█" * filled_before + "░" * empty_before
            after_percent = "█" * filled_after + "░" * empty_after

            # Construct bar with percent
            if self.config.statusline_progress_bar_colorize:
                # Determine color
                if percentage < 50:
                    color_start = "\033[92m"  # Bright Green
                elif percentage < 80:
                    color_start = "\033[93m"  # Bright Yellow
                else:
                    color_start = "\033[91m"  # Bright Red
                color_end = "\033[39m"  # Reset to default foreground color only

                # Build the bar parts
                before_part = "█" * filled_before + "░" * empty_before
                after_part = "█" * filled_after + "░" * empty_after

                # Apply color to the entire bar except the percentage text
                if filled_before > 0 and filled_after > 0:
                    # Color spans both sides
                    bar_content = (
                        f"{color_start}{before_part}{color_end}{percent_str}{color_start}{after_part}{color_end}"
                    )
                elif filled_before > 0:
                    # Color only on left side
                    bar_content = f"{color_start}{before_part}{color_end}{percent_str}{after_part}"
                elif filled_after > 0:
                    # Color only on right side
                    bar_content = f"{before_part}{percent_str}{color_start}{after_part}{color_end}"
                else:
                    # No filled portion
                    bar_content = f"{before_part}{percent_str}{after_part}"
                return f"[{bar_content}]"
            else:
                # No coloring
                bar_content = f"{before_percent}{percent_str}{after_percent}"
                return f"[{bar_content}]"
        else:
            # Original logic without percent display
            filled = int(length * percentage / 100)
            empty = length - filled

            # Create the base progress bar
            filled_chars = "█" * filled
            empty_chars = "░" * empty

        # Apply colors if enabled (for non-percent display)
        if not self.config.statusline_progress_bar_show_percent and self.config.statusline_progress_bar_colorize:
            # ANSI color codes for terminal output
            # Green: < 50%, Yellow: 50-79%, Red: >= 80%
            if percentage < 50:
                # Green
                color_start = "\033[92m"  # Bright Green color
            elif percentage < 80:
                # Yellow
                color_start = "\033[93m"  # Bright Yellow color
            else:
                # Red
                color_start = "\033[91m"  # Bright Red color

            color_end = "\033[39m"  # Reset to default foreground color only

            # Apply color to the bar content only, not the brackets
            bar_content = f"{color_start}{filled_chars}{color_end}{empty_chars}"
            return f"[{bar_content}]"
        else:
            # No coloring
            return "[" + filled_chars + empty_chars + "]"

    def _create_rich_progress_bar(self, value: int, max_value: int, length: int) -> str:
        """Create a Rich-style progress bar.

        Args:
            value: Current value (0-100 percentage)
            max_value: Maximum value (always 100 for percentage)
            length: Desired length of progress bar

        Returns:
            Rich-formatted progress bar string with ANSI codes
        """
        percentage = value  # value is already the percentage

        if self.config.statusline_progress_bar_show_percent:
            # Show percentage in center of bar
            percent_str = f"{percentage:>3}%"
            percent_len = len(percent_str)

            # Calculate total bar content length (excluding brackets)
            bar_length = length

            # Calculate the center position for the percentage text
            center_pos = (bar_length - percent_len) // 2

            # Calculate filled and empty portions
            filled_total = int(bar_length * percentage / 100)

            # Determine what goes before and after the percentage
            before_percent_len = center_pos
            after_percent_len = bar_length - center_pos - percent_len

            # Calculate how many filled chars go before and after the percentage
            filled_before = min(filled_total, before_percent_len)
            filled_after = max(0, min(filled_total - filled_before, after_percent_len))

            # Calculate empty chars
            empty_before = before_percent_len - filled_before
            empty_after = after_percent_len - filled_after

            # Create the bar parts
            before_percent = "━" * filled_before + "╺" * empty_before
            after_percent = "━" * filled_after + "╺" * empty_after

            # Construct bar with percent
            if self.config.statusline_progress_bar_colorize:
                # Determine color
                if percentage < 50:
                    color_start = "\033[92m"  # Bright Green
                elif percentage < 80:
                    color_start = "\033[93m"  # Bright Yellow
                else:
                    color_start = "\033[91m"  # Bright Red
                color_end = "\033[39m"  # Reset to default foreground color only

                # Build the bar parts
                filled_left = "━" * filled_before
                empty_left = "╺" * empty_before
                filled_right = "━" * filled_after
                empty_right = "╺" * empty_after

                # Apply color to filled sections only, with identical ANSI codes
                if filled_before > 0 and filled_after > 0:
                    # Both sides have fill - apply color identically
                    # Use explicit SGR reset and reapply to ensure consistency
                    left_colored = f"{color_start}{filled_left}{color_end}"
                    right_colored = f"{color_start}{filled_right}{color_end}"
                    bar_content = f"{left_colored}{empty_left}{percent_str}{right_colored}{empty_right}"
                elif filled_before > 0:
                    # Only left has fill
                    left_part = f"{color_start}{filled_left}{color_end}{empty_left}"
                    right_part = empty_right
                    bar_content = f"{left_part}{percent_str}{right_part}"
                elif filled_after > 0:
                    # Only right has fill
                    left_part = empty_left
                    right_part = f"{color_start}{filled_right}{color_end}{empty_right}"
                    bar_content = f"{left_part}{percent_str}{right_part}"
                else:
                    # No fill
                    bar_content = f"{empty_left}{percent_str}{empty_right}"
                return f"[{bar_content}]"
            else:
                # No coloring
                bar_content = f"{before_percent}{percent_str}{after_percent}"
                return f"[{bar_content}]"
        else:
            # Original logic without percent display
            filled = int(length * value / 100)
            empty = length - filled

            # Use Rich-style characters
            filled_chars = "━" * filled
            empty_chars = "╺" * empty

        if not self.config.statusline_progress_bar_show_percent and self.config.statusline_progress_bar_colorize:
            # Use ANSI color codes directly (same as basic style)
            if value < 50:
                color_start = "\033[92m"  # Bright Green
            elif value < 80:
                color_start = "\033[93m"  # Bright Yellow
            else:
                color_start = "\033[91m"  # Bright Red

            color_end = "\033[39m"  # Reset to default foreground color only

            # Apply color to the bar content only, not the brackets
            bar_content = f"{color_start}{filled_chars}{color_end}{empty_chars}"
            return f"[{bar_content}]"
        else:
            # No color, just use the Rich characters
            return f"[{filled_chars}{empty_chars}]"

    def _get_session_tokens(self, session_id: str | None = None) -> tuple[int, int, int]:
        """Get current session token usage from JSONL file.

        Args:
            session_id: Session ID to check tokens for

        Returns:
            Tuple of (tokens_used, max_tokens, tokens_remaining)
        """
        import subprocess
        from pathlib import Path

        if not session_id:
            return 0, 0, 0

        # Try to find the session file in Claude projects
        # Claude uses the format: -Users-username-path-to-project
        # We need to search for the actual session file since the exact path format can vary

        claude_projects = Path.home() / ".claude" / "projects"
        session_file = None

        # First, try to find the file by searching through project directories
        if claude_projects.exists():
            for project_dir in claude_projects.iterdir():
                if project_dir.is_dir():
                    potential_file = project_dir / f"{session_id}.jsonl"
                    if potential_file.exists():
                        session_file = potential_file
                        break

        # If we found a session file, extract tokens from it
        if not session_file or not session_file.exists():
            # Try the expected path based on current directory
            cwd = Path.cwd()
            # Convert underscores to hyphens and create the expected path
            project_name = cwd.name.replace("_", "-")
            parent_path = str(cwd.parent).replace(str(Path.home()), "").lstrip("/").replace("/", "-")
            if parent_path:
                project_dir = f"-{parent_path}-{project_name}"
            else:
                project_dir = f"-{project_name}"
            session_file = claude_projects / project_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            return 0, 0, 0

        try:
            # Use jq to extract token counts efficiently (similar to bash script)
            cmd = [
                "sh",
                "-c",
                f"tail -20 '{session_file}' | jq -r 'select(.message.usage) | .message.usage | ((.input_tokens // 0) + (.cache_read_input_tokens // 0))' 2>/dev/null | tail -1",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0 and result.stdout.strip():
                tokens_used = int(result.stdout.strip())

                # Determine max context based on model (default to 200K)
                # This could be enhanced by detecting the actual model from the JSONL
                max_tokens = 200000

                tokens_remaining = max(0, max_tokens - tokens_used)
                return tokens_used, max_tokens, tokens_remaining

        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

        return 0, 0, 0

    def _get_git_info(self, project_path: "pathlib.Path | None" = None) -> tuple[str, str]:
        """Get current git branch and status.

        Args:
            project_path: Path to check for git status. If None, uses the directory
                         where this code is running (the par_cc_usage repo itself).

        Returns:
            Tuple of (branch_name, status_indicator)
            branch_name: Current branch name or empty string if not in a git repo
            status_indicator: Clean (✓), dirty (*), or empty string
        """
        import subprocess
        from pathlib import Path

        # Determine which directory to check
        if project_path is None:
            # Default to the par_cc_usage repo directory
            # This is where the monitor is running from
            try:
                # Try to find the git root of the current script's location
                script_path = Path(__file__).resolve()
                # Go up to find .git directory
                check_path = script_path.parent
                found_git = False
                while check_path != check_path.parent:
                    if (check_path / ".git").exists():
                        found_git = True
                        break
                    check_path = check_path.parent

                if not found_git:
                    # Not in a git repo
                    return "", ""
            except Exception:
                return "", ""
        else:
            check_path = project_path
            # Verify it's a git repository
            if not (check_path / ".git").exists():
                return "", ""

        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
                cwd=check_path,
            )

            if result.returncode != 0:
                # Not in a git repository or git command failed
                return "", ""

            branch = result.stdout.strip()

            # Check if working directory is clean
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
                cwd=check_path,
            )

            if status_result.returncode == 0:
                # If output is empty, working directory is clean
                if status_result.stdout.strip():
                    # Dirty (has changes) - use configured indicator
                    status = str(getattr(self.config, "statusline_git_dirty_indicator", "*"))
                else:
                    # Clean - use configured indicator
                    status = str(getattr(self.config, "statusline_git_clean_indicator", "✓"))
            else:
                status = ""

            return branch, status

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # Git not available or command failed
            return "", ""

    def _prepare_template_components(
        self,
        tokens: int,
        messages: int,
        cost: float,
        token_limit: int | None,
        message_limit: int | None,
        cost_limit: float | None,
        time_remaining: str | None,
        project_name: str | None,
        template: str | None = None,
    ) -> dict[str, str]:
        """Prepare individual components for template formatting.

        Args:
            tokens: Token count
            messages: Message count
            cost: Total cost
            token_limit: Token limit
            message_limit: Message limit
            cost_limit: Cost limit
            time_remaining: Time remaining
            project_name: Project name
            template: Template string to check what components are needed

        Returns:
            Dictionary of template components
        """
        import os
        import socket

        components = {}

        # Use provided template or config template for checking what's needed
        if template is None:
            template = self.config.statusline_template

        # Always prepare basic components (cheap to compute)
        components["project"] = f"[{project_name}]" if project_name else ""
        components["sep"] = str(getattr(self.config, "statusline_separator", " - "))

        # Tokens component (always needed for basic status)
        if token_limit and token_limit > 0:
            percentage = min(100, (tokens / token_limit) * 100)
            components["tokens"] = (
                f"🪙 {format_token_count(tokens)}/{format_token_count(token_limit)} ({percentage:.0f}%)"
            )
        else:
            components["tokens"] = f"🪙 {format_token_count(tokens)}"

        # Messages component (always needed for basic status)
        if message_limit and message_limit > 0:
            components["messages"] = f"💬 {messages:,}/{message_limit:,}"
        else:
            components["messages"] = f"💬 {messages:,}"

        # Cost component - only included if cost > 0
        if cost > 0:
            if cost_limit and cost_limit > 0:
                components["cost"] = f"💰 {format_cost(cost)}/{format_cost(cost_limit)}"
            else:
                components["cost"] = f"💰 {format_cost(cost)}"
        else:
            components["cost"] = ""

        # Time component (remaining time in block)
        components["remaining_block_time"] = f"⏱️ {time_remaining}" if time_remaining else ""

        # Only fetch system info if needed in template
        if "{username}" in template:
            components["username"] = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
        else:
            components["username"] = ""

        if "{hostname}" in template:
            try:
                components["hostname"] = socket.gethostname()
            except Exception:
                components["hostname"] = "unknown"
        else:
            components["hostname"] = ""

        # Only fetch date/time if needed in template
        if "{date}" in template or "{current_time}" in template:
            now = datetime.now()
            if "{date}" in template:
                date_format = str(getattr(self.config, "statusline_date_format", "%Y-%m-%d"))
                components["date"] = now.strftime(date_format)
            else:
                components["date"] = ""

            if "{current_time}" in template:
                time_format = str(getattr(self.config, "statusline_time_format", "%I:%M %p"))
                components["current_time"] = now.strftime(time_format)
            else:
                components["current_time"] = ""
        else:
            components["date"] = ""
            components["current_time"] = ""

        # Only fetch git info if needed in template
        if "{git_branch}" in template or "{git_status}" in template:
            branch, status = self._get_git_info()
            components["git_branch"] = branch
            components["git_status"] = status
        else:
            components["git_branch"] = ""
            components["git_status"] = ""

        # Don't add session token components here - they should only be added
        # when session_id is available in format_status_line_from_template
        # This allows the placeholders to remain in the template for later enrichment

        return components

    def _clean_template_line(self, line: str) -> str:
        """Clean up a single line from template result.

        Args:
            line: Line to clean

        Returns:
            Cleaned line or empty string
        """
        # Remove leading/trailing whitespace
        line = line.strip()

        # Get the separator from config (with fallback for backward compatibility)
        sep = str(getattr(self.config, "statusline_separator", " - "))
        sep_stripped = sep.strip()

        # Replace multiple consecutive separators with single separator
        # First handle exact duplicates
        double_sep = sep + sep
        while double_sep in line:
            line = line.replace(double_sep, sep)
        # Then handle separator with stripped version in between
        multi_sep = sep + sep_stripped + sep
        while multi_sep in line:
            line = line.replace(multi_sep, sep)
        # Handle stripped followed by full
        partial_sep = sep_stripped + sep
        while partial_sep in line and partial_sep != sep:
            line = line.replace(partial_sep, sep)
        # Handle full followed by stripped
        partial_sep2 = sep + sep_stripped
        while partial_sep2 in line and partial_sep2 != sep:
            line = line.replace(partial_sep2, sep)

        # Keep removing leading/trailing separators until none remain
        while line.startswith(sep):
            line = line[len(sep) :].strip()
        while line.startswith(sep_stripped):
            line = line[len(sep_stripped) :].strip()
        # Also handle partial separators like "- " when separator is " - "
        if sep_stripped == "-" and line.startswith("- "):
            line = line[2:].strip()
        while line.endswith(sep):
            line = line[: -len(sep)].strip()
        while line.endswith(sep_stripped):
            line = line[: -len(sep_stripped)].strip()
        # Also handle partial separators at the end
        if sep_stripped == "-" and line.endswith(" -"):
            line = line[:-2].strip()

        # Clean up line that's only separators
        if line == sep_stripped or line == sep or line == "":
            line = ""

        return line

    def format_status_line_from_template(
        self,
        tokens: int,
        messages: int,
        cost: float = 0.0,
        token_limit: int | None = None,
        message_limit: int | None = None,
        cost_limit: float | None = None,
        time_remaining: str | None = None,
        project_name: str | None = None,
        template: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Format a status line string using a template.

        Args:
            tokens: Token count
            messages: Message count
            cost: Total cost in USD
            token_limit: Token limit (optional)
            message_limit: Message limit (optional)
            cost_limit: Cost limit in USD (optional)
            time_remaining: Time remaining in block (optional)
            project_name: Project name to display (optional)
            template: Template string to use (defaults to config template)
            session_id: Session ID for session token tracking (optional)

        Returns:
            Formatted status line string based on template
        """
        # Use provided template or fall back to config template
        if template is None:
            template = self.config.statusline_template

        # If template is empty or None, use default
        if not template:
            template = "{project}{sep}{tokens}{sep}{messages}{sep}{cost}{sep}{remaining_block_time}"

        # Prepare individual components
        components = self._prepare_template_components(
            tokens, messages, cost, token_limit, message_limit, cost_limit, time_remaining, project_name, template
        )

        # Check if any session token variables are in the template
        session_token_vars = {
            "session_tokens",
            "session_tokens_total",
            "session_tokens_remaining",
            "session_tokens_percent",
            "session_tokens_progress_bar",
        }

        # Variables that are provided by Claude Code and should be preserved
        claude_provided_vars = {"model"}

        has_session_vars = any(f"{{{var}}}" in template for var in session_token_vars)

        # Add session token components if session_id is provided AND they're needed in template
        if session_id and has_session_vars:
            session_tokens_used, session_tokens_total, session_tokens_remaining = self._get_session_tokens(session_id)

            if session_tokens_total > 0:
                # Format session token values
                if session_tokens_used >= 1_000_000:
                    components["session_tokens"] = f"{session_tokens_used / 1_000_000:.1f}M"
                elif session_tokens_used >= 1000:
                    components["session_tokens"] = f"{session_tokens_used // 1000}K"
                else:
                    components["session_tokens"] = str(session_tokens_used)

                if session_tokens_total >= 1_000_000:
                    components["session_tokens_total"] = f"{session_tokens_total / 1_000_000:.1f}M"
                elif session_tokens_total >= 1000:
                    components["session_tokens_total"] = f"{session_tokens_total // 1000}K"
                else:
                    components["session_tokens_total"] = str(session_tokens_total)

                if session_tokens_remaining >= 1_000_000:
                    components["session_tokens_remaining"] = f"{session_tokens_remaining / 1_000_000:.1f}M"
                elif session_tokens_remaining >= 1000:
                    components["session_tokens_remaining"] = f"{session_tokens_remaining // 1000}K"
                else:
                    components["session_tokens_remaining"] = str(session_tokens_remaining)

                # Calculate percentage used
                percent_used = int(session_tokens_used * 100 / session_tokens_total)
                components["session_tokens_percent"] = f"{percent_used}%"

                # Create progress bar
                components["session_tokens_progress_bar"] = self._create_progress_bar(
                    session_tokens_used, session_tokens_total
                )
        else:
            # No session_id provided or session vars not in template - preserve placeholders for later enrichment
            # Don't set these to empty strings, leave them as placeholders
            # This way the cached status line will still have {session_tokens} etc.
            # and can be enriched later when session_id is available
            pass

        # Process the template
        result = template

        # Replace newline escapes with actual newlines
        result = result.replace("\\n", "\n")

        # First, identify and handle unknown template variables
        import re

        all_vars = re.findall(r"\{([^}]+)\}", result)
        for var in all_vars:
            if var not in components:
                # If it's a session token variable and we don't have session_id,
                # preserve it as a placeholder for later enrichment
                if var in session_token_vars and not session_id:
                    # Keep the placeholder as-is
                    continue
                # If it's a Claude-provided variable, preserve it for later enrichment
                elif var in claude_provided_vars:
                    # Keep the placeholder as-is
                    continue
                else:
                    # Replace unknown variables with a placeholder
                    result = result.replace(f"{{{var}}}", f"[unknown_var: {var}]")

        # Then replace known components
        for key, value in components.items():
            placeholder = f"{{{key}}}"
            # Ensure value is a string (in case of Mock objects in tests)
            result = result.replace(placeholder, str(value) if value else "")

        # Clean up multiple separators and trailing/leading separators
        lines = result.split("\n")
        cleaned_lines = []

        for line in lines:
            cleaned_line = self._clean_template_line(line)
            # Only add non-empty lines
            if cleaned_line:
                cleaned_lines.append(cleaned_line)

        return "\n".join(cleaned_lines)

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

        # Save template and format settings hash for cache validation
        import hashlib

        config_str = f"{self.config.statusline_template}|{self.config.statusline_date_format}|{self.config.statusline_time_format}"
        template_hash = hashlib.md5(config_str.encode()).hexdigest()
        meta_path = file_path.with_suffix(".meta")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(template_hash)

    def load_status_line(self, session_id: str, ignore_template_change: bool = False) -> str | None:
        """Load a cached status line from disk.

        Args:
            session_id: Session ID or "grand_total" for the grand total
            ignore_template_change: If True, return cached line even if template changed

        Returns:
            The cached status line or None if not found/expired
        """
        if session_id == "grand_total":
            file_path = get_grand_total_statusline_path()
        else:
            file_path = get_statusline_file_path(session_id)

        if not file_path.exists():
            return None

        # If not ignoring template changes, check if template or format settings have changed
        if not ignore_template_change:
            import hashlib

            config_str = f"{self.config.statusline_template}|{self.config.statusline_date_format}|{self.config.statusline_time_format}"
            current_template_hash = hashlib.md5(config_str.encode()).hexdigest()
            meta_path = file_path.with_suffix(".meta")

            if meta_path.exists():
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        saved_hash = f.read().strip()
                    if saved_hash != current_template_hash:
                        # Template has changed, invalidate cache
                        return None
                except OSError:
                    # If we can't read meta file, invalidate cache to be safe
                    return None
            else:
                # No meta file means old cache format, invalidate
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
        project_name = None

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
                        # Get project name from the first matching entry
                        if project_name is None:
                            project_name = entry.project_name

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line_from_template(
            tokens=session_tokens,
            messages=session_messages,
            cost=session_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
            project_name=project_name,
            session_id=session_id,
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
        return self.format_status_line_from_template(
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

        return self.format_status_line_from_template(
            tokens=total_tokens,
            messages=total_messages,
            cost=total_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
        )

    def generate_grand_total_with_project_name(self, usage_snapshot: UsageSnapshot, session_id: str) -> str:
        """Generate a grand total status line with project name from session.

        Args:
            usage_snapshot: Current usage snapshot
            session_id: Session ID to extract project name from

        Returns:
            Formatted status line with grand total stats and project name
        """
        total_tokens = usage_snapshot.unified_block_tokens()
        total_messages = usage_snapshot.unified_block_messages()
        time_remaining = None
        project_name = None

        # Get time remaining from current block
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

            # Find project name for the session
            if session_id in current_block.sessions:
                for entry in current_block.entries:
                    if entry.session_id == session_id:
                        project_name = entry.project_name
                        break

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line_from_template(
            tokens=total_tokens,
            messages=total_messages,
            cost=0.0,  # Note: Cost calculation requires async
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
            project_name=project_name,
        )

    async def generate_grand_total_with_project_name_async(self, usage_snapshot: UsageSnapshot, session_id: str) -> str:
        """Generate a grand total status line with project name from session (async version with cost).

        Args:
            usage_snapshot: Current usage snapshot
            session_id: Session ID to extract project name from

        Returns:
            Formatted status line with grand total stats, cost, and project name
        """
        total_tokens = usage_snapshot.unified_block_tokens()
        total_messages = usage_snapshot.unified_block_messages()
        time_remaining = None
        project_name = None

        # Get time remaining from current block
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            if current_block.is_active:
                time_remaining = self._calculate_time_remaining(current_block.end_time)

            # Find project name for the session
            if session_id in current_block.sessions:
                for entry in current_block.entries:
                    if entry.session_id == session_id:
                        project_name = entry.project_name
                        break

        # Calculate cost asynchronously
        try:
            total_cost = await usage_snapshot.get_unified_block_total_cost()
        except Exception:
            total_cost = 0.0

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line_from_template(
            tokens=total_tokens,
            messages=total_messages,
            cost=total_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
            project_name=project_name,
        )

    def _clear_outdated_cache(self) -> None:
        """Clear cache files that have outdated templates."""
        import hashlib

        # Calculate current template hash
        config_str = f"{self.config.statusline_template}|{self.config.statusline_date_format}|{self.config.statusline_time_format}"
        current_hash = hashlib.md5(config_str.encode()).hexdigest()

        # Check all .meta files in statuslines directory
        statusline_dir = get_statusline_dir()
        if statusline_dir.exists():
            for meta_file in statusline_dir.glob("*.meta"):
                try:
                    with open(meta_file, encoding="utf-8") as f:
                        saved_hash = f.read().strip()
                    if saved_hash != current_hash:
                        # Template changed, remove both cache and meta files
                        cache_file = meta_file.with_suffix(".txt")
                        if cache_file.exists():
                            cache_file.unlink()
                        meta_file.unlink()
                except Exception:
                    # If we can't read or delete, skip this file
                    pass

    def update_status_lines(self, usage_snapshot: UsageSnapshot) -> None:
        """Update all status lines based on current usage snapshot.

        Args:
            usage_snapshot: Current usage snapshot
        """
        if not self.config.statusline_enabled:
            return

        # Clear any outdated cache files first
        self._clear_outdated_cache()

        # Always generate grand total (this will update with new template)
        grand_total_line = self.generate_grand_total_status_line(usage_snapshot)
        self.save_status_line("grand_total", grand_total_line)

        # Generate per-session status lines and grand total with project name for each session
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            for session_id in current_block.sessions:
                # Generate session-specific status line (this will update with new template)
                session_line = self.generate_session_status_line(usage_snapshot, session_id)
                self.save_status_line(session_id, session_line)

                # Generate grand total with project name for this session (this will update with new template)
                grand_total_with_project = self.generate_grand_total_with_project_name(usage_snapshot, session_id)
                self.save_status_line(f"grand_total_{session_id}", grand_total_with_project)

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
        project_name = None

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
                        # Get project name from the first matching entry
                        if project_name is None:
                            project_name = entry.project_name

                # Calculate cost separately to reduce complexity
                session_cost = await self._calculate_session_cost(current_block.entries, session_id)

        # Get limits from config
        token_limit, message_limit, cost_limit = self._get_config_limits()

        return self.format_status_line_from_template(
            tokens=session_tokens,
            messages=session_messages,
            cost=session_cost,
            token_limit=token_limit,
            message_limit=message_limit,
            cost_limit=cost_limit,
            time_remaining=time_remaining,
            project_name=project_name,
            session_id=session_id,
        )

    async def update_status_lines_async(self, usage_snapshot: UsageSnapshot) -> None:
        """Update all status lines asynchronously with cost calculations.

        Args:
            usage_snapshot: Current usage snapshot
        """
        if not self.config.statusline_enabled:
            return

        # Clear any outdated cache files first
        self._clear_outdated_cache()

        # Always generate grand total with cost
        grand_total_line = await self.generate_grand_total_status_line_async(usage_snapshot)
        self.save_status_line("grand_total", grand_total_line)

        # Generate per-session status lines with cost and grand total with project name
        if usage_snapshot.unified_blocks:
            current_block = usage_snapshot.unified_blocks[-1]
            for session_id in current_block.sessions:
                # Generate session-specific status line with cost
                session_line = await self.generate_session_status_line_async(usage_snapshot, session_id)
                self.save_status_line(session_id, session_line)

                # Generate grand total with project name and cost for this session
                grand_total_with_project = await self.generate_grand_total_with_project_name_async(
                    usage_snapshot, session_id
                )
                self.save_status_line(f"grand_total_{session_id}", grand_total_with_project)

    def _try_load_latest_snapshot(self) -> UsageSnapshot | None:
        """Try to load the latest usage snapshot from disk cache.

        Returns:
            UsageSnapshot if successful, None otherwise
        """
        try:
            from .file_monitor import FileMonitor, poll_files
            from .models import UsageSnapshot
            from .processors import DeduplicationState

            # Create a minimal snapshot by scanning current data
            projects = {}
            dedup_state = DeduplicationState()

            # Use file monitor to scan files efficiently
            file_monitor = FileMonitor(
                projects_dirs=self.config.get_claude_paths(),
                cache_dir=self.config.cache_dir,
                disable_cache=False,
            )

            # Quick scan with cached positions
            poll_files(
                file_monitor=file_monitor,
                projects=projects,
                dedup_state=dedup_state,
                config=self.config,
                save_state=False,  # Don't save state for read-only operation
            )

            # Create snapshot from projects
            if projects:
                snapshot = UsageSnapshot.from_projects(projects, self.config)
                return snapshot

        except Exception:
            # If we can't load data, return None
            pass

        return None

    def _enrich_with_session_tokens(self, status_line: str, session_id: str | None) -> str:
        """Enrich a status line with session token information.

        Args:
            status_line: The base status line to enrich
            session_id: Session ID for token extraction

        Returns:
            Status line with session token placeholders replaced
        """
        if not session_id or "{session_tokens" not in status_line:
            return status_line

        # Get session token data
        tokens_used, tokens_total, tokens_remaining = self._get_session_tokens(session_id)

        if tokens_total > 0:
            # Format session token values
            if tokens_used >= 1_000_000:
                session_tokens = f"{tokens_used / 1_000_000:.1f}M"
            elif tokens_used >= 1000:
                session_tokens = f"{tokens_used // 1000}K"
            else:
                session_tokens = str(tokens_used)

            if tokens_total >= 1_000_000:
                session_tokens_total = f"{tokens_total / 1_000_000:.1f}M"
            elif tokens_total >= 1000:
                session_tokens_total = f"{tokens_total // 1000}K"
            else:
                session_tokens_total = str(tokens_total)

            if tokens_remaining >= 1_000_000:
                session_tokens_remaining = f"{tokens_remaining / 1_000_000:.1f}M"
            elif tokens_remaining >= 1000:
                session_tokens_remaining = f"{tokens_remaining // 1000}K"
            else:
                session_tokens_remaining = str(tokens_remaining)

            # Calculate percentage used
            percent_used = int(tokens_used * 100 / tokens_total)
            session_tokens_percent = f"{percent_used}%"

            # Create progress bar
            session_tokens_progress_bar = self._create_progress_bar(tokens_used, tokens_total)

            # Replace placeholders
            status_line = status_line.replace("{session_tokens}", session_tokens)
            status_line = status_line.replace("{session_tokens_total}", session_tokens_total)
            status_line = status_line.replace("{session_tokens_remaining}", session_tokens_remaining)
            status_line = status_line.replace("{session_tokens_percent}", session_tokens_percent)
            status_line = status_line.replace("{session_tokens_progress_bar}", session_tokens_progress_bar)
        else:
            # No token data available, remove placeholders
            status_line = status_line.replace("{session_tokens}", "")
            status_line = status_line.replace("{session_tokens_total}", "")
            status_line = status_line.replace("{session_tokens_remaining}", "")
            status_line = status_line.replace("{session_tokens_percent}", "")
            status_line = status_line.replace("{session_tokens_progress_bar}", "")

        # Clean up any duplicate separators
        status_line = self._clean_template_line(status_line)

        return status_line

    def _enrich_with_model_and_session_tokens(self, status_line: str, session_id: str | None, model_name: str) -> str:
        """Enrich a status line with model information and session token information.

        Args:
            status_line: The base status line to enrich
            session_id: Session ID for token extraction
            model_name: Model display name from Claude Code

        Returns:
            Status line with model and session token placeholders replaced
        """
        # First add model information if needed
        if "{model}" in status_line and model_name:
            status_line = status_line.replace("{model}", model_name)
        elif "{model}" in status_line:
            status_line = status_line.replace("{model}", "")

        # Clean up each line after model replacement
        lines = status_line.split("\n")
        cleaned_lines = []
        for line in lines:
            cleaned_line = self._clean_template_line(line)
            if cleaned_line:  # Only add non-empty lines
                cleaned_lines.append(cleaned_line)
        status_line = "\n".join(cleaned_lines)

        # Then enrich with session tokens
        return self._enrich_with_session_tokens(status_line, session_id)

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

        # Try to extract session ID from the JSON
        session_id = session_json.get("sessionId") or session_json.get("session_id")

        # Extract model information
        model_info = session_json.get("model", {})
        model_display_name = model_info.get("display_name", "")

        # Check if we should use grand total
        if self.config.statusline_use_grand_total:
            # If we have a valid session ID, try to get grand total with project name
            if session_id:
                # Try to load cached grand total with project name
                cached = self.load_status_line(f"grand_total_{session_id}")
                if cached:
                    return self._enrich_with_model_and_session_tokens(cached, session_id, model_display_name)
                # If template changed, fall back to old cached version until monitor updates
                cached_old = self.load_status_line(f"grand_total_{session_id}", ignore_template_change=True)
                if cached_old:
                    return self._enrich_with_model_and_session_tokens(cached_old, session_id, model_display_name)
            # Fall back to regular grand total
            cached = self.load_status_line("grand_total")
            if cached:
                return self._enrich_with_model_and_session_tokens(cached, session_id, model_display_name)
            # If template changed, fall back to old cached version until monitor updates
            cached_old = self.load_status_line("grand_total", ignore_template_change=True)
            if cached_old:
                return self._enrich_with_model_and_session_tokens(cached_old, session_id, model_display_name)
            return "🪙 0 - 💬 0"

        # Session-specific mode
        if session_id:
            # Try to load cached session status line
            cached = self.load_status_line(session_id)
            if cached:
                return self._enrich_with_model_and_session_tokens(cached, session_id, model_display_name)
            # If template changed, fall back to old cached version until monitor updates
            cached_old = self.load_status_line(session_id, ignore_template_change=True)
            if cached_old:
                return self._enrich_with_model_and_session_tokens(cached_old, session_id, model_display_name)

        # Fall back to grand total
        cached = self.load_status_line("grand_total")
        if cached:
            return self._enrich_with_model_and_session_tokens(cached, session_id, model_display_name)
        # If template changed, fall back to old cached version until monitor updates
        cached_old = self.load_status_line("grand_total", ignore_template_change=True)
        if cached_old:
            return self._enrich_with_model_and_session_tokens(cached_old, session_id, model_display_name)
        return "🪙 0 - 💬 0"
