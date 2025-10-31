"""Status line management for Claude Code integration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config
from .file_monitor import _strip_project_name_prefixes
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

    def _get_progress_color(self, percentage: int) -> tuple[str, str]:
        """Get ANSI color codes based on percentage.

        Args:
            percentage: The percentage value

        Returns:
            Tuple of (color_start, color_end) ANSI codes
        """
        if percentage < 50:
            color_start = "\033[92m"  # Bright Green
        elif percentage < 80:
            color_start = "\033[93m"  # Bright Yellow
        else:
            color_start = "\033[91m"  # Bright Red
        color_end = "\033[39m"  # Reset to default foreground color only
        return color_start, color_end

    def _create_progress_bar_with_percent(self, percentage: int, length: int) -> str:
        """Create a progress bar with percentage display in center.

        Args:
            percentage: The percentage value (0-100)
            length: Total length of the bar

        Returns:
            Progress bar string with centered percentage
        """
        percent_str = f"{percentage:>3}%"
        percent_len = len(percent_str)
        bar_length = length
        center_pos = (bar_length - percent_len) // 2

        filled_total = int(bar_length * percentage / 100)
        before_percent_len = center_pos
        after_percent_len = bar_length - center_pos - percent_len

        filled_before = min(filled_total, before_percent_len)
        filled_after = max(0, min(filled_total - filled_before, after_percent_len))
        empty_before = before_percent_len - filled_before
        empty_after = after_percent_len - filled_after

        before_part = "█" * filled_before + "░" * empty_before
        after_part = "█" * filled_after + "░" * empty_after

        if not self.config.statusline_progress_bar_colorize:
            return f"[{before_part}{percent_str}{after_part}]"

        # Apply coloring
        color_start, color_end = self._get_progress_color(percentage)

        if filled_before > 0 and filled_after > 0:
            bar_content = f"{color_start}{before_part}{color_end}{percent_str}{color_start}{after_part}{color_end}"
        elif filled_before > 0:
            bar_content = f"{color_start}{before_part}{color_end}{percent_str}{after_part}"
        elif filled_after > 0:
            bar_content = f"{before_part}{percent_str}{color_start}{after_part}{color_end}"
        else:
            bar_content = f"{before_part}{percent_str}{after_part}"

        return f"[{bar_content}]"

    def _create_simple_progress_bar(self, percentage: int, length: int) -> str:
        """Create a simple progress bar without percentage display.

        Args:
            percentage: The percentage value (0-100)
            length: Total length of the bar

        Returns:
            Simple progress bar string
        """
        filled = int(length * percentage / 100)
        empty = length - filled
        filled_chars = "█" * filled
        empty_chars = "░" * empty

        if not self.config.statusline_progress_bar_colorize:
            return f"[{filled_chars}{empty_chars}]"

        color_start, color_end = self._get_progress_color(percentage)
        bar_content = f"{color_start}{filled_chars}{color_end}{empty_chars}"
        return f"[{bar_content}]"

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
            if self.config.statusline_progress_bar_show_percent:
                length += 3

        if max_value <= 0:
            if self.config.statusline_progress_bar_style == "rich":
                return self._create_rich_progress_bar(0, 100, length)
            return "[" + "░" * length + "]"

        percentage = min(100, max(0, int(value * 100 / max_value)))

        if self.config.statusline_progress_bar_style == "rich":
            return self._create_rich_progress_bar(percentage, 100, length)

        if self.config.statusline_progress_bar_show_percent:
            return self._create_progress_bar_with_percent(percentage, length)

        return self._create_simple_progress_bar(percentage, length)

    def _create_rich_bar_with_percent(self, percentage: int, length: int) -> str:
        """Create a Rich-style progress bar with centered percentage.

        Args:
            percentage: The percentage value (0-100)
            length: Total length of the bar

        Returns:
            Rich-formatted progress bar with percentage
        """
        percent_str = f"{percentage:>3}%"
        percent_len = len(percent_str)
        bar_length = length
        center_pos = (bar_length - percent_len) // 2

        filled_total = int(bar_length * percentage / 100)
        before_percent_len = center_pos
        after_percent_len = bar_length - center_pos - percent_len

        filled_before = min(filled_total, before_percent_len)
        filled_after = max(0, min(filled_total - filled_before, after_percent_len))
        empty_before = before_percent_len - filled_before
        empty_after = after_percent_len - filled_after

        before_percent = "━" * filled_before + "╺" * empty_before
        after_percent = "━" * filled_after + "╺" * empty_after

        if not self.config.statusline_progress_bar_colorize:
            return f"[{before_percent}{percent_str}{after_percent}]"

        # Apply coloring
        color_start, color_end = self._get_progress_color(percentage)
        filled_left = "━" * filled_before
        empty_left = "╺" * empty_before
        filled_right = "━" * filled_after
        empty_right = "╺" * empty_after

        if filled_before > 0 and filled_after > 0:
            left_colored = f"{color_start}{filled_left}{color_end}"
            right_colored = f"{color_start}{filled_right}{color_end}"
            bar_content = f"{left_colored}{empty_left}{percent_str}{right_colored}{empty_right}"
        elif filled_before > 0:
            left_part = f"{color_start}{filled_left}{color_end}{empty_left}"
            bar_content = f"{left_part}{percent_str}{empty_right}"
        elif filled_after > 0:
            right_part = f"{color_start}{filled_right}{color_end}{empty_right}"
            bar_content = f"{empty_left}{percent_str}{right_part}"
        else:
            bar_content = f"{empty_left}{percent_str}{empty_right}"

        return f"[{bar_content}]"

    def _create_simple_rich_bar(self, percentage: int, length: int) -> str:
        """Create a simple Rich-style progress bar.

        Args:
            percentage: The percentage value (0-100)
            length: Total length of the bar

        Returns:
            Simple Rich-formatted progress bar
        """
        filled = int(length * percentage / 100)
        empty = length - filled
        filled_chars = "━" * filled
        empty_chars = "╺" * empty

        if not self.config.statusline_progress_bar_colorize:
            return f"[{filled_chars}{empty_chars}]"

        color_start, color_end = self._get_progress_color(percentage)
        bar_content = f"{color_start}{filled_chars}{color_end}{empty_chars}"
        return f"[{bar_content}]"

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
            return self._create_rich_bar_with_percent(percentage, length)

        return self._create_simple_rich_bar(percentage, length)

    def _find_session_file(self, session_id: str) -> Path | None:
        """Find the session JSONL file for the given session ID.

        Args:
            session_id: Session ID to find

        Returns:
            Path to session file or None if not found
        """
        from pathlib import Path

        claude_projects = Path.home() / ".claude" / "projects"

        # First, try to find the file by searching through project directories
        if claude_projects.exists():
            for project_dir in claude_projects.iterdir():
                if project_dir.is_dir():
                    potential_file = project_dir / f"{session_id}.jsonl"
                    if potential_file.exists():
                        return potential_file

        # Try the expected path based on current directory
        cwd = Path.cwd()
        project_name = cwd.name.replace("_", "-")
        parent_path = str(cwd.parent).replace(str(Path.home()), "").lstrip("/").replace("/", "-")

        if parent_path:
            project_dir = f"-{parent_path}-{project_name}"
        else:
            project_dir = f"-{project_name}"

        session_file = claude_projects / project_dir / f"{session_id}.jsonl"
        return session_file if session_file.exists() else None

    def _extract_tokens_from_file(self, session_file: Path) -> int:
        """Extract token count from session JSONL file.

        Args:
            session_file: Path to the session file

        Returns:
            Number of tokens used or 0 if extraction fails
        """
        import subprocess

        try:
            cmd = [
                "sh",
                "-c",
                f"tail -20 '{session_file}' | jq -r 'select(.message.usage) | .message.usage | ((.input_tokens // 0) + (.cache_read_input_tokens // 0))' 2>/dev/null | tail -1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)

            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

        return 0

    def _get_session_tokens(self, session_id: str | None = None) -> tuple[int, int, int]:
        """Get current session token usage from JSONL file.

        Args:
            session_id: Session ID to check tokens for

        Returns:
            Tuple of (tokens_used, max_tokens, tokens_remaining)
        """
        if not session_id:
            return 0, 0, 0

        session_file = self._find_session_file(session_id)
        if not session_file:
            return 0, 0, 0

        tokens_used = self._extract_tokens_from_file(session_file)
        if tokens_used == 0:
            return 0, 0, 0

        # Determine max context based on model (default to 200K)
        max_tokens = 200000
        tokens_remaining = max(0, max_tokens - tokens_used)

        return tokens_used, max_tokens, tokens_remaining

    def _find_git_root(self, project_path: Path | None = None) -> Path | None:
        """Find the git root directory.

        Args:
            project_path: Path to check for git status

        Returns:
            Path to git root or None if not found
        """
        from pathlib import Path

        if project_path is None:
            try:
                # Use current working directory instead of script location
                check_path = Path.cwd().resolve()

                while check_path != check_path.parent:
                    if (check_path / ".git").exists():
                        return check_path
                    check_path = check_path.parent
            except Exception:
                pass
            return None

        # When project_path is provided, also check parent directories
        try:
            check_path = project_path.resolve()
            while check_path != check_path.parent:
                if (check_path / ".git").exists():
                    return check_path
                check_path = check_path.parent
        except Exception:
            pass
        return None

    def _get_git_branch(self, check_path: Path) -> str:
        """Get the current git branch name.

        Args:
            check_path: Path to git repository

        Returns:
            Branch name or empty string on failure
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
                cwd=check_path,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return ""

    def _get_git_status(self, check_path: Path) -> str:
        """Get the git repository status indicator.

        Args:
            check_path: Path to git repository

        Returns:
            Status indicator (clean/dirty) or empty string
        """
        import subprocess

        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
                cwd=check_path,
            )

            if status_result.returncode != 0:
                return ""

            if status_result.stdout.strip():
                return str(getattr(self.config, "statusline_git_dirty_indicator", "*"))
            else:
                return str(getattr(self.config, "statusline_git_clean_indicator", "*"))
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return ""

    def _get_git_info(self, project_path: Path | None = None) -> tuple[str, str]:
        """Get current git branch and status.

        Args:
            project_path: Path to check for git status. If None, uses the directory
                         where this code is running (the par_cc_usage repo itself).

        Returns:
            Tuple of (branch_name, status_indicator)
            branch_name: Current branch name or empty string if not in a git repo
            status_indicator: Clean (*), dirty (*), or empty string
        """
        check_path = self._find_git_root(project_path)
        if not check_path:
            return "", ""

        branch = self._get_git_branch(check_path)
        if not branch:
            return "", ""

        status = self._get_git_status(check_path)
        return branch, status

    def _prepare_basic_components(
        self,
        tokens: int,
        messages: int,
        cost: float,
        token_limit: int | None,
        message_limit: int | None,
        cost_limit: float | None,
        time_remaining: str | None,
        project_name: str | None,
    ) -> dict[str, str]:
        """Prepare basic template components.

        Args:
            tokens: Token count
            messages: Message count
            cost: Total cost
            token_limit: Token limit
            message_limit: Message limit
            cost_limit: Cost limit
            time_remaining: Time remaining
            project_name: Project name

        Returns:
            Dictionary of basic components
        """
        components = {}

        components["project"] = f"[{project_name}]" if project_name else ""
        components["sep"] = str(getattr(self.config, "statusline_separator", " - "))

        # Tokens component
        if token_limit and token_limit > 0:
            percentage = min(100, (tokens / token_limit) * 100)
            components["tokens"] = (
                f"🪙 {format_token_count(tokens)}/{format_token_count(token_limit)} ({percentage:.0f}%)"
            )
        else:
            components["tokens"] = f"🪙 {format_token_count(tokens)}"

        # Messages component
        if message_limit and message_limit > 0:
            components["messages"] = f"💬 {messages:,}/{message_limit:,}"
        else:
            components["messages"] = f"💬 {messages:,}"

        # Cost component
        if cost > 0:
            if cost_limit and cost_limit > 0:
                components["cost"] = f"💰 {format_cost(cost)}/{format_cost(cost_limit)}"
            else:
                components["cost"] = f"💰 {format_cost(cost)}"
        else:
            components["cost"] = ""

        # Time component
        components["remaining_block_time"] = f"⏱️ {time_remaining}" if time_remaining else ""

        return components

    def _prepare_system_components(self, template: str) -> dict[str, str]:
        """Prepare system-related template components.

        Args:
            template: Template string to check what's needed

        Returns:
            Dictionary of system components
        """
        import os
        import socket

        components = {}

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

        return components

    def _prepare_datetime_components(self, template: str) -> dict[str, str]:
        """Prepare date and time template components.

        Args:
            template: Template string to check what's needed

        Returns:
            Dictionary of datetime components
        """
        components = {"date": "", "current_time": ""}

        if "{date}" not in template and "{current_time}" not in template:
            return components

        now = datetime.now()

        if "{date}" in template:
            date_format = str(getattr(self.config, "statusline_date_format", "%Y-%m-%d"))
            components["date"] = now.strftime(date_format)

        if "{current_time}" in template:
            time_format = str(getattr(self.config, "statusline_time_format", "%I:%M %p"))
            components["current_time"] = now.strftime(time_format)

        return components

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
        if template is None:
            template = self.config.statusline_template

        # Get basic components
        components = self._prepare_basic_components(
            tokens, messages, cost, token_limit, message_limit, cost_limit, time_remaining, project_name
        )

        # Add system components if needed
        components.update(self._prepare_system_components(template))

        # Add datetime components if needed
        components.update(self._prepare_datetime_components(template))

        # Add git info if needed
        if "{git_branch}" in template or "{git_status}" in template:
            branch, status = self._get_git_info()
            components["git_branch"] = branch
            components["git_status"] = status
        else:
            components["git_branch"] = ""
            components["git_status"] = ""

        return components

    def _collapse_separators(self, line: str, sep: str, sep_stripped: str) -> str:
        """Collapse multiple consecutive separators into single separator.

        Args:
            line: Line to clean
            sep: Full separator
            sep_stripped: Stripped separator

        Returns:
            Line with collapsed separators
        """
        # Handle exact duplicates
        double_sep = sep + sep
        while double_sep in line:
            line = line.replace(double_sep, sep)

        # Handle separator with stripped version in between
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

        return line

    def _trim_separators(self, line: str, sep: str, sep_stripped: str) -> str:
        """Remove leading and trailing separators from line.

        Args:
            line: Line to trim
            sep: Full separator
            sep_stripped: Stripped separator

        Returns:
            Line with separators trimmed
        """
        # Remove leading separators
        while line.startswith(sep):
            line = line[len(sep) :].strip()
        while line.startswith(sep_stripped):
            line = line[len(sep_stripped) :].strip()

        # Handle partial separators like "- " when separator is " - "
        if sep_stripped == "-" and line.startswith("- "):
            line = line[2:].strip()

        # Remove trailing separators
        while line.endswith(sep):
            line = line[: -len(sep)].strip()
        while line.endswith(sep_stripped):
            line = line[: -len(sep_stripped)].strip()

        # Handle partial separators at the end
        if sep_stripped == "-" and line.endswith(" -"):
            line = line[:-2].strip()

        return line

    def _clean_template_line(self, line: str) -> str:
        """Clean up a single line from template result.

        Args:
            line: Line to clean

        Returns:
            Cleaned line or empty string
        """
        line = line.strip()

        sep = str(getattr(self.config, "statusline_separator", " - "))
        sep_stripped = sep.strip()

        # Collapse multiple separators
        line = self._collapse_separators(line, sep, sep_stripped)

        # Trim separators from start and end
        line = self._trim_separators(line, sep, sep_stripped)

        # Clean up line that's only separators
        if line in (sep_stripped, sep, ""):
            return ""

        return line

    def _format_token_value(self, value: int) -> str:
        """Format a token value with appropriate units.

        Args:
            value: Token count to format

        Returns:
            Formatted token string
        """
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1000:
            return f"{value // 1000}K"
        else:
            return str(value)

    def _prepare_session_components(self, session_id: str, template: str) -> dict[str, str]:
        """Prepare session-specific template components.

        Args:
            session_id: Session ID for token tracking
            template: Template string to check what's needed

        Returns:
            Dictionary of session components
        """
        session_token_vars = {
            "session_tokens",
            "session_tokens_total",
            "session_tokens_remaining",
            "session_tokens_percent",
            "session_tokens_progress_bar",
        }

        has_session_vars = any(f"{{{var}}}" in template for var in session_token_vars)
        if not has_session_vars:
            return {}

        session_tokens_used, session_tokens_total, session_tokens_remaining = self._get_session_tokens(session_id)

        if session_tokens_total <= 0:
            return {}

        components = {}
        components["session_tokens"] = self._format_token_value(session_tokens_used)
        components["session_tokens_total"] = self._format_token_value(session_tokens_total)
        components["session_tokens_remaining"] = self._format_token_value(session_tokens_remaining)

        percent_used = int(session_tokens_used * 100 / session_tokens_total)
        components["session_tokens_percent"] = f"{percent_used}%"
        components["session_tokens_progress_bar"] = self._create_progress_bar(session_tokens_used, session_tokens_total)

        return components

    def _process_template_variables(self, template: str, components: dict[str, str], session_id: str | None) -> str:
        """Process and replace template variables.

        Args:
            template: Template string
            components: Dictionary of component values
            session_id: Session ID (optional)

        Returns:
            Processed template string
        """
        import re

        result = template.replace("\\n", "\n")

        session_token_vars = {
            "session_tokens",
            "session_tokens_total",
            "session_tokens_remaining",
            "session_tokens_percent",
            "session_tokens_progress_bar",
        }
        claude_provided_vars = {"model"}

        all_vars = re.findall(r"\{([^}]+)\}", result)
        for var in all_vars:
            if var not in components:
                if (var in session_token_vars and not session_id) or var in claude_provided_vars:
                    continue  # Keep placeholder as-is
                else:
                    result = result.replace(f"{{{var}}}", f"[unknown_var: {var}]")

        # Replace known components
        for key, value in components.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value) if value else "")

        return result

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
        if template is None:
            template = self.config.statusline_template

        if not template:
            template = "{project}{sep}{tokens}{sep}{messages}{sep}{cost}{sep}{remaining_block_time}"

        # Prepare basic components
        components = self._prepare_template_components(
            tokens, messages, cost, token_limit, message_limit, cost_limit, time_remaining, project_name, template
        )

        # Add session components if needed
        if session_id:
            session_components = self._prepare_session_components(session_id, template)
            components.update(session_components)

        # Process template and replace variables
        result = self._process_template_variables(template, components, session_id)

        # Clean up lines
        lines = result.split("\n")
        cleaned_lines = [self._clean_template_line(line) for line in lines]
        cleaned_lines = [line for line in cleaned_lines if line]  # Remove empty lines

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
                            raw_project_name = entry.project_name
                            # Strip configured prefixes for cleaner display
                            project_name = _strip_project_name_prefixes(
                                raw_project_name, self.config.display.project_name_prefixes
                            )

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
                        raw_project_name = entry.project_name
                        # Strip configured prefixes for cleaner display
                        project_name = _strip_project_name_prefixes(
                            raw_project_name, self.config.display.project_name_prefixes
                        )
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
                        raw_project_name = entry.project_name
                        # Strip configured prefixes for cleaner display
                        project_name = _strip_project_name_prefixes(
                            raw_project_name, self.config.display.project_name_prefixes
                        )
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
                            raw_project_name = entry.project_name
                            # Strip configured prefixes for cleaner display
                            project_name = _strip_project_name_prefixes(
                                raw_project_name, self.config.display.project_name_prefixes
                            )

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
            from .file_monitor import FileMonitor
            from .models import UsageSnapshot

            # Create a minimal snapshot by scanning current data
            projects = {}

            # Use file monitor to scan files efficiently
            file_monitor = FileMonitor(
                projects_dirs=self.config.get_claude_paths(),
                cache_dir=self.config.cache_dir,
                disable_cache=False,
            )

            # Get modified files and process them
            modified_files = file_monitor.get_modified_files()

            # Process each modified file to build projects
            for _file_path, _state in modified_files:
                # This would normally be handled by a processor
                # For now, just create an empty snapshot
                pass

            # Create snapshot with current timestamp
            snapshot = UsageSnapshot(
                timestamp=datetime.now(),
                projects=projects,
                total_limit=self.config.token_limit,
                message_limit=self.config.message_limit,
            )

            # Calculate unified blocks if there are projects
            if projects:
                # Note: Would need to extract entries from projects to create blocks
                # For now, just use empty list
                snapshot.unified_blocks = []

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

    def _load_cached_status_line(self, cache_key: str, session_id: str | None, model_display_name: str) -> str | None:
        """Try to load and enrich a cached status line.

        Args:
            cache_key: Cache key to load
            session_id: Session ID for enrichment
            model_display_name: Model display name for enrichment

        Returns:
            Enriched status line or None if not found
        """
        # Try current template version
        cached = self.load_status_line(cache_key)
        if cached:
            return self._enrich_with_model_and_session_tokens(cached, session_id, model_display_name)

        # Fall back to old template version
        cached_old = self.load_status_line(cache_key, ignore_template_change=True)
        if cached_old:
            return self._enrich_with_model_and_session_tokens(cached_old, session_id, model_display_name)

        return None

    def _get_grand_total_status_line(self, session_id: str | None, model_display_name: str) -> str:
        """Get the grand total status line.

        Args:
            session_id: Session ID for enrichment
            model_display_name: Model display name for enrichment

        Returns:
            Grand total status line or default
        """
        # Try session-specific grand total first
        if session_id:
            result = self._load_cached_status_line(f"grand_total_{session_id}", session_id, model_display_name)
            if result:
                return result

        # Fall back to regular grand total
        result = self._load_cached_status_line("grand_total", session_id, model_display_name)
        return result if result else "🪙 0 - 💬 0"

    def _get_session_status_line(self, session_id: str, model_display_name: str) -> str | None:
        """Get the session-specific status line.

        Args:
            session_id: Session ID
            model_display_name: Model display name for enrichment

        Returns:
            Session status line or None if not found
        """
        return self._load_cached_status_line(session_id, session_id, model_display_name)

    def get_status_line_for_request(self, session_json: dict[str, Any]) -> str:
        """Get the appropriate status line for a Claude Code request.

        Args:
            session_json: JSON data from Claude Code containing session info

        Returns:
            The appropriate status line string
        """
        if not self.config.statusline_enabled:
            return ""

        # Extract session and model info
        session_id = session_json.get("sessionId") or session_json.get("session_id")
        model_info = session_json.get("model", {})
        model_display_name = model_info.get("display_name", "")

        # Grand total mode
        if self.config.statusline_use_grand_total:
            return self._get_grand_total_status_line(session_id, model_display_name)

        # Session-specific mode
        if session_id:
            result = self._get_session_status_line(session_id, model_display_name)
            if result:
                return result

        # Fall back to grand total
        return self._get_grand_total_status_line(session_id, model_display_name)
