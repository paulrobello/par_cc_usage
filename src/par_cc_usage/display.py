"""Display components for par_cc_usage monitor mode."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from .enums import DisplayMode
from .models import Project, Session, UsageSnapshot
from .theme import get_color, get_progress_color, get_style, get_theme_manager
from .token_calculator import format_token_count, get_model_display_name
from .utils import format_datetime, format_time_range


class MonitorDisplay:
    """Display component for monitor mode."""

    def __init__(
        self, console: Console | None = None, show_sessions: bool = False, time_format: str = "24h", config: Any = None
    ) -> None:
        """Initialize display.

        Args:
            console: Rich console instance
            show_sessions: Whether to show the sessions panel
            time_format: Time format ('12h' or '24h')
            config: Configuration object
        """
        self.console = console or Console()
        self.layout = Layout()
        self.show_sessions = show_sessions
        self.time_format = time_format
        self.config = config
        self.show_tool_usage = config and config.display.show_tool_usage if config else True
        self.compact_mode = config and config.display.display_mode == DisplayMode.COMPACT if config else False

        # Set up theme if config is provided
        if config and hasattr(config, "display") and hasattr(config.display, "theme"):
            theme_manager = get_theme_manager()
            try:
                theme_manager.set_current_theme(config.display.theme)
            except ValueError:
                # If theme is invalid (e.g., mock object), use default theme
                from .enums import ThemeType

                theme_manager.set_current_theme(ThemeType.DEFAULT)

        self._setup_layout(show_sessions)

    def _strip_project_name(self, project_name: str) -> str:
        """Strip configured prefixes from project name."""
        if not self.config or not self.config.display.project_name_prefixes:
            return project_name

        for prefix in self.config.display.project_name_prefixes:
            if project_name.startswith(prefix):
                return project_name[len(prefix) :]
        return project_name

    def _setup_layout(self, show_sessions: bool = False) -> None:
        """Set up the display layout."""
        if self.compact_mode:
            # Compact mode: only show header and progress (no block progress, tool usage, or sessions)
            self.layout.split_column(
                Layout(name="header", size=3),
                Layout(name="progress", size=6),
            )
        elif show_sessions:
            if self.show_tool_usage:
                self.layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="block_progress", size=3),
                    Layout(name="progress", size=6),
                    Layout(name="tool_usage", size=7),
                    Layout(name="sessions"),
                )
            else:
                self.layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="block_progress", size=3),
                    Layout(name="progress", size=6),
                    Layout(name="sessions"),
                )
        else:
            if self.show_tool_usage:
                self.layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="block_progress", size=3),
                    Layout(name="progress", size=6),
                    Layout(name="tool_usage", size=7),
                )
            else:
                self.layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="block_progress", size=3),
                    Layout(name="progress", size=6),
                )

    def _create_header(self, snapshot: UsageSnapshot) -> Panel:
        """Create header panel.

        Args:
            snapshot: Usage snapshot

        Returns:
            Header panel
        """
        active_projects = len(snapshot.active_projects)
        active_sessions = snapshot.active_session_count
        # Use the configured timezone from snapshot
        current_time = format_datetime(snapshot.timestamp, self.time_format)

        header_text = Text()
        header_text.append(f"Active Projects: {active_projects}", style=get_style("success", bold=True))
        header_text.append("  │  ", style="dim")
        header_text.append(f"Active Sessions: {active_sessions}", style=get_style("secondary", bold=True))
        header_text.append("\n")
        header_text.append(f"Current Time: {current_time}", style="dim")

        return Panel(
            header_text,
            title="PAR Claude Code Usage Monitor",
            border_style=get_color("primary"),
        )

    def _create_block_progress(self, snapshot: UsageSnapshot) -> Panel:
        """Create progress bar for current 5-hour block.

        Args:
            snapshot: Usage snapshot

        Returns:
            Block progress panel
        """
        # Get current time in the snapshot's timezone
        current_time = snapshot.timestamp

        # Find the unified block start time to show progress for
        unified_block_start = snapshot.unified_block_start_time

        if unified_block_start:
            # Use the unified block start time (most recently active session)
            block_start = unified_block_start
            # Ensure it's in the same timezone as current_time for display
            if block_start.tzinfo != current_time.tzinfo:
                block_start = block_start.astimezone(current_time.tzinfo)
        else:
            # No active blocks, show current hour block
            block_start = current_time.replace(minute=0, second=0, microsecond=0)

        block_end = block_start + timedelta(hours=5)

        # Calculate progress through the block
        elapsed = (current_time - block_start).total_seconds()
        total = (block_end - block_start).total_seconds()
        progress_percent = (elapsed / total) * 100

        # Calculate time remaining
        remaining = block_end - current_time
        hours_left = int(remaining.total_seconds() // 3600)
        minutes_left = int((remaining.total_seconds() % 3600) // 60)

        # Create progress bar
        progress = Progress(
            TextColumn("Block Progress"),
            BarColumn(bar_width=25),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn(format_time_range(block_start, block_end, self.time_format)),
            TextColumn(f"({hours_left}h {minutes_left}m left)", style=get_style("warning", bold=True)),
            console=self.console,
            expand=False,
        )
        progress.add_task("Block", total=100, completed=int(progress_percent))

        block_info = progress

        return Panel(
            block_info,
            border_style=get_color("info"),
            height=3,
        )

    def _get_model_emoji(self, model: str) -> str:
        """Get emoji for model type.

        Args:
            model: Model name

        Returns:
            Emoji string
        """
        if "opus" in model.lower():
            return "🚀"
        elif "sonnet" in model.lower():
            return "⚡"
        elif "haiku" in model.lower():
            return "💨"
        elif "claude" in model.lower():
            return "🤖"
        elif "gpt" in model.lower():
            return "🧠"
        elif "llama" in model.lower():
            return "🦙"
        else:
            return "❓"

    def _create_model_displays(
        self, model_tokens: dict[str, int], model_interruptions: dict[str, int] | None = None
    ) -> list[Text]:
        """Create model token displays.

        Args:
            model_tokens: Token count by model
            model_interruptions: Interruption count by model (optional)

        Returns:
            List of formatted model displays
        """
        model_displays: list[Text] = []
        for model, tokens in sorted(model_tokens.items()):
            display_name = get_model_display_name(model)
            emoji = self._get_model_emoji(model)

            model_text = Text()
            model_text.append(f"{emoji} {display_name:8}", style="bold")
            model_text.append(f"{format_token_count(tokens):>12}", style=get_color("token_count"))

            # Add interruption count if interruption data exists and not in compact mode (always show, even if 0)
            if model_interruptions is not None and not self.compact_mode:
                interruption_count = model_interruptions.get(model, 0)
                # Green for 0 interruptions (good), red for actual interruptions (warning)
                color = get_color("interruption_none") if interruption_count == 0 else get_color("interruption_present")
                model_text.append(f"  ({interruption_count} Interrupted)", style=color)

            model_displays.append(model_text)
        return model_displays

    async def _create_model_displays_with_pricing(
        self,
        model_tokens: dict[str, int],
        model_interruptions: dict[str, int] | None = None,
        snapshot: UsageSnapshot | None = None,
    ) -> list[Text]:
        """Create model token displays with pricing information.

        Args:
            model_tokens: Token count by model
            model_interruptions: Interruption count by model (optional)
            snapshot: Usage snapshot for accurate cost calculation

        Returns:
            List of formatted model displays with pricing
        """
        from .pricing import format_cost

        # Get accurate model costs from the snapshot if available
        model_costs = {}
        if snapshot:
            try:
                full_model_costs = await snapshot.get_unified_block_cost_by_model()
                # Map full model names back to normalized names for display
                from .token_calculator import normalize_model_name

                for full_model, cost in full_model_costs.items():
                    normalized = normalize_model_name(full_model)
                    if normalized not in model_costs:
                        model_costs[normalized] = 0.0
                    model_costs[normalized] += cost
            except Exception:
                # If cost calculation fails, use empty dict
                model_costs = {}

        model_displays: list[Text] = []
        for model, tokens in sorted(model_tokens.items()):
            display_name = get_model_display_name(model)
            emoji = self._get_model_emoji(model)

            model_text = Text()
            model_text.append(f"{emoji} {display_name:8}", style="bold")
            model_text.append(f"{format_token_count(tokens):>12}", style=get_color("token_count"))

            # Add pricing if enabled
            if self.config and self.config.display.show_pricing:
                cost = model_costs.get(model, 0.0)
                if cost > 0:
                    model_text.append(f"  {format_cost(cost)}", style=get_color("cost"))

            # Add interruption count if interruption data exists and not in compact mode (always show, even if 0)
            if model_interruptions is not None and not self.compact_mode:
                interruption_count = model_interruptions.get(model, 0)
                # Green for 0 interruptions (good), red for actual interruptions (warning)
                color = get_color("interruption_none") if interruption_count == 0 else get_color("interruption_present")
                model_text.append(f"  ({interruption_count} Interrupted)", style=color)

            model_displays.append(model_text)
        return model_displays

    def _get_progress_colors(self, percentage: float, total_tokens: int, base_limit: int) -> tuple[str, str]:
        """Get progress bar colors based on percentage.

        Args:
            percentage: Usage percentage
            total_tokens: Current token count
            base_limit: Base token limit

        Returns:
            Tuple of (bar_color, text_style)
        """
        # Determine color based on percentage thresholds using theme
        bar_color = get_progress_color(percentage)
        text_style = get_style("progress_critical", bold=True) if percentage >= 90 else f"bold {bar_color}"

        # Add warning color if over original limit (overrides percentage colors)
        if total_tokens > base_limit:
            text_style = get_style("error", bold=True)

        return bar_color, text_style

    def _get_fallback_tool_data(self, snapshot: UsageSnapshot) -> tuple[dict[str, int], int]:
        """Get fallback tool data from all active blocks."""
        tool_counts = {}
        total_tool_calls = 0
        for project in snapshot.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active:
                        for tool, count in block.tool_call_counts.items():
                            tool_counts[tool] = tool_counts.get(tool, 0) + count
                        total_tool_calls += block.total_tool_calls
        return tool_counts, total_tool_calls

    async def _create_progress_bars(self, snapshot: UsageSnapshot) -> Panel:
        """Create progress bars for token usage.

        Args:
            snapshot: Usage snapshot

        Returns:
            Progress panel
        """
        # Get token usage by model for unified block only
        model_tokens = snapshot.unified_block_tokens_by_model()
        total_tokens = snapshot.unified_block_tokens()
        model_interruptions = snapshot.unified_block_interruptions_by_model()

        # If no unified block data, fall back to all active tokens and models
        if not model_tokens and total_tokens == 0:
            model_tokens = snapshot.tokens_by_model()
            total_tokens = snapshot.active_tokens
            model_interruptions = snapshot.interruptions_by_model()

        # Ensure limit is at least as high as current usage
        base_limit = snapshot.total_limit or 500_000
        total_limit = max(base_limit, total_tokens)

        # Create per-model token displays (no progress bars)
        from rich.console import Group
        from rich.progress import BarColumn, Progress, TextColumn

        # Use pricing display if enabled, otherwise use regular display
        if self.config and self.config.display.show_pricing:
            model_displays = await self._create_model_displays_with_pricing(model_tokens, model_interruptions, snapshot)
        else:
            model_displays = self._create_model_displays(model_tokens, model_interruptions)

        # Calculate burn rate and estimated total usage
        burn_rate_text = await self._calculate_burn_rate(snapshot, total_tokens, total_limit)

        # Get total cost if pricing is enabled
        total_cost = 0.0
        if self.config and self.config.display.show_pricing:
            try:
                total_cost = await snapshot.get_unified_block_total_cost()
            except Exception:
                # If cost calculation fails, continue without cost display
                total_cost = 0.0

        # Combine model displays and burn rate
        all_displays = []
        if model_displays:
            all_displays.extend(model_displays)
        all_displays.append(burn_rate_text)

        # Add total progress bar only if not in compact mode
        if not self.compact_mode:
            # Total progress bar with color based on percentage
            percentage = (total_tokens / total_limit) * 100
            bar_color, text_style = self._get_progress_colors(percentage, total_tokens, base_limit)

            # Create the tokens text with optional cost
            tokens_text = f"{format_token_count(total_tokens):>8} / {format_token_count(total_limit)}"
            if total_cost > 0:
                from .pricing import format_cost

                tokens_text += f" {format_cost(total_cost)}"

            total_progress = Progress(
                TextColumn("📊 Total   ", style=text_style),
                BarColumn(bar_width=25, complete_style=bar_color, finished_style=bar_color),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn(tokens_text, style=text_style),
                console=self.console,
                expand=False,
            )
            total_progress.add_task("Total", total=total_limit, completed=total_tokens)
            all_displays.append(total_progress)
        else:
            # In compact mode, show total as simple text
            percentage = (total_tokens / total_limit) * 100
            _, text_style = self._get_progress_colors(percentage, total_tokens, base_limit)

            total_text = Text()
            total_text.append("📊 Total   ", style=text_style)
            total_text.append(
                f"{format_token_count(total_tokens):>8} / {format_token_count(total_limit)} ", style=text_style
            )
            if total_cost > 0:
                from .pricing import format_cost

                total_text.append(f"{format_cost(total_cost)} ", style=text_style)
            total_text.append(f"({percentage:>3.0f}%)", style=text_style)
            all_displays.append(total_text)

        all_progress = Group(*all_displays)

        return Panel(
            all_progress,
            title="Token Usage by Model",
            border_style=get_color("border"),
        )

    def _create_tool_usage_table(self, snapshot: UsageSnapshot) -> Table:
        """Create tool usage table with dynamic sizing and column distribution.

        Args:
            snapshot: Usage snapshot

        Returns:
            Tool usage table with optimized layout
        """
        from rich.table import Table

        # Create table for tool usage
        table = Table(
            show_header=False,
            show_lines=False,
            expand=True,
            title="Tool Use",
            border_style=get_color("tool_usage"),
        )

        # Only show tool usage if enabled
        if not (self.config and self.config.display.show_tool_usage):
            table.add_column("Status", style="dim italic")
            table.add_row("Tool usage display disabled")
            return table

        # Get tool usage data
        tool_counts = snapshot.unified_block_tool_usage()
        total_tool_calls = snapshot.unified_block_total_tool_calls()

        if not tool_counts:
            # Show empty table when no tools are used
            table.add_column("Status", style="dim italic")
            table.add_row("No tool usage in current block")
            return table

        # Sort tools by usage count (highest first), then by name (case-insensitive)
        sorted_tools = sorted(tool_counts.items(), key=lambda x: (-x[1], x[0].lower()))

        # Use fixed 3-column layout
        num_tools = len(sorted_tools)
        max_rows = 8  # Maximum table height (excluding total row)
        num_cols = 3  # Always use 3 columns

        # Limit tools to fit in 3-column layout with max_rows
        max_tools = max_rows * num_cols
        if num_tools > max_tools:
            sorted_tools = sorted_tools[:max_tools]

        # Add columns based on calculated layout
        for _col in range(num_cols):
            table.add_column("Tool", style=get_color("tool_usage"), no_wrap=False)
            table.add_column("Count", justify="right", style=get_color("token_count"), width=6)

        # Calculate tools per column for even distribution
        tools_per_col = (len(sorted_tools) + num_cols - 1) // num_cols  # Ceiling division

        # Distribute tools into columns
        tool_columns = []
        for col in range(num_cols):
            start_idx = col * tools_per_col
            end_idx = min(start_idx + tools_per_col, len(sorted_tools))
            tool_columns.append(sorted_tools[start_idx:end_idx])

        # Calculate actual number of rows needed
        actual_rows = max(len(col) for col in tool_columns) if tool_columns else 0

        # Arrange tools in rows
        for row in range(actual_rows):
            row_data = []
            for col in range(num_cols):
                if row < len(tool_columns[col]):
                    tool_name, tool_count = tool_columns[col][row]
                    row_data.extend([f"🔧 {tool_name}", f"{tool_count:,}"])
                else:
                    row_data.extend(["", ""])  # Empty cells

            table.add_row(*row_data)

        # Add total row if there are tool calls
        if total_tool_calls > 0:
            total_row = ["📊 Total", f"{total_tool_calls:,}"]
            # Fill remaining columns with empty strings
            total_row.extend([""] * ((num_cols - 1) * 2))
            table.add_row(*total_row, style="bold")

        return table

    def _calculate_tool_usage_height(self, snapshot: UsageSnapshot) -> int:
        """Calculate the optimal height for the tool usage section.

        Args:
            snapshot: Usage snapshot

        Returns:
            Height for tool usage layout (minimum 3, maximum 10)
        """
        if not (self.config and self.config.display.show_tool_usage):
            return 3  # Minimum height for disabled message

        tool_counts = snapshot.unified_block_tool_usage()

        if not tool_counts:
            return 3  # Minimum height for empty message

        num_tools = len(tool_counts)
        max_table_rows = 8  # Maximum data rows
        num_cols = 3  # Fixed 3-column layout

        # Calculate actual rows needed for 3-column layout
        tools_per_col = (num_tools + num_cols - 1) // num_cols
        actual_rows = min(tools_per_col, max_table_rows)

        # Add space for table borders and total row
        # Top border: 1, Data rows: actual_rows, Total row: 1, Bottom border: 1
        return min(actual_rows + 4, 10)  # Cap at 10 total height (8 data rows + 2 overhead)

    def _calculate_burn_rate_color(self, estimated_total: float, total_limit: int) -> str:
        """Determine color based on percentage of limit."""
        percentage = (estimated_total / total_limit) * 100
        if percentage >= 100:
            return get_style("error", bold=True)
        elif percentage >= 95:
            return get_style("warning", bold=True)
        else:
            return get_style("success", bold=True)

    async def _calculate_estimated_cost(self, snapshot: UsageSnapshot, elapsed_minutes: float) -> str:
        """Calculate estimated cost for the full 5-hour block."""
        if not (self.config and self.config.display.show_pricing):
            return ""

        try:
            current_cost = await snapshot.get_unified_block_total_cost()
            if elapsed_minutes > 0 and current_cost > 0:
                cost_per_minute = current_cost / elapsed_minutes
                estimated_total_cost = cost_per_minute * 60 * 5.0  # 5 hours
                from .pricing import format_cost

                return f"  Est: {format_cost(estimated_total_cost)}"
        except Exception:
            pass
        return ""

    def _format_burn_rate_text(
        self,
        burn_rate_per_minute: float,
        estimated_total: float,
        total_limit: int,
        estimated_cost_text: str,
        eta_display: str,
        eta_before_block_end: bool,
        remaining_tokens: int,
    ) -> Text:
        """Format the burn rate display text."""
        percentage = (estimated_total / total_limit) * 100
        color = self._calculate_burn_rate_color(estimated_total, total_limit)

        burn_rate_text = Text()
        burn_rate_text.append("🔥 Burn    ", style="bold")
        burn_rate_text.append(f"{format_token_count(int(burn_rate_per_minute)):>8}/m", style=get_color("burn_rate"))
        burn_rate_text.append("  Est: ", style="dim")
        burn_rate_text.append(f"{format_token_count(int(estimated_total)):>8}", style=color)
        burn_rate_text.append(f" ({percentage:>3.0f}%)", style=color)

        if estimated_cost_text:
            burn_rate_text.append(estimated_cost_text, style=get_color("cost"))

        if remaining_tokens > 0:
            burn_rate_text.append("  ETA: ", style="dim")
            if burn_rate_per_minute > 0:
                eta_style = get_color("eta_urgent") if eta_before_block_end else get_color("eta_normal")
                burn_rate_text.append(eta_display, style=eta_style)
            else:
                burn_rate_text.append("∞", style=get_color("success"))

        return burn_rate_text

    async def _calculate_burn_rate(self, snapshot: UsageSnapshot, total_tokens: int, total_limit: int) -> Text:
        """Calculate burn rate and estimated total usage.

        Args:
            snapshot: Usage snapshot
            total_tokens: Current total token usage
            total_limit: Token limit

        Returns:
            Formatted text with burn rate and estimate
        """
        # Get unified block start time
        block_start = snapshot.unified_block_start_time
        if not block_start:
            return Text("No active block", style="dim")

        # Calculate elapsed time
        elapsed_seconds = (snapshot.timestamp - block_start).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        # Avoid division by zero
        if elapsed_minutes < 0.1:  # Less than 6 seconds
            return Text("Burn rate: calculating...", style="dim")

        # Calculate burn rate and estimates
        burn_rate_per_minute = total_tokens / elapsed_minutes
        burn_rate_per_hour = burn_rate_per_minute * 60
        estimated_total = burn_rate_per_hour * 5.0

        # Calculate ETA to token limit
        remaining_tokens = total_limit - total_tokens
        eta_display, eta_before_block_end = self._calculate_eta_display(
            snapshot, total_tokens, total_limit, burn_rate_per_minute
        )

        # Calculate estimated cost if pricing is enabled
        estimated_cost_text = await self._calculate_estimated_cost(snapshot, elapsed_minutes)

        # Format the display
        return self._format_burn_rate_text(
            burn_rate_per_minute,
            estimated_total,
            total_limit,
            estimated_cost_text,
            eta_display,
            eta_before_block_end,
            remaining_tokens,
        )

    def _calculate_burn_rate_sync(self, snapshot: UsageSnapshot, total_tokens: int, total_limit: int) -> Text:
        """Calculate burn rate and estimated total usage (sync version without cost).

        Args:
            snapshot: Usage snapshot
            total_tokens: Current total token usage
            total_limit: Token limit

        Returns:
            Formatted text with burn rate and estimate (no cost)
        """
        # Get unified block start time
        block_start = snapshot.unified_block_start_time
        if not block_start:
            return Text("No active block", style="dim")

        # Calculate elapsed time
        elapsed_seconds = (snapshot.timestamp - block_start).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        # Avoid division by zero
        if elapsed_minutes < 0.1:  # Less than 6 seconds
            return Text("Burn rate: calculating...", style="dim")

        # Calculate burn rate (tokens per minute)
        burn_rate_per_minute = total_tokens / elapsed_minutes

        # Calculate burn rate per hour for estimation
        burn_rate_per_hour = burn_rate_per_minute * 60

        # Calculate estimated total usage for the full 5-hour block
        estimated_total = burn_rate_per_hour * 5.0

        # Calculate ETA to token limit
        remaining_tokens = total_limit - total_tokens
        eta_display, eta_before_block_end = self._calculate_eta_display(
            snapshot, total_tokens, total_limit, burn_rate_per_minute
        )

        # Determine color based on percentage of limit
        percentage = (estimated_total / total_limit) * 100
        color = self._calculate_burn_rate_color(estimated_total, total_limit)

        # Format the display (without cost)
        burn_rate_text = Text()
        burn_rate_text.append("🔥 Burn    ", style="bold")
        burn_rate_text.append(f"{format_token_count(int(burn_rate_per_minute)):>8}/m", style=get_color("burn_rate"))
        burn_rate_text.append("  Est: ", style="dim")
        burn_rate_text.append(f"{format_token_count(int(estimated_total)):>8}", style=color)
        burn_rate_text.append(f" ({percentage:>3.0f}%)", style=color)

        # Add time until limit
        if remaining_tokens > 0:
            burn_rate_text.append("  ETA: ", style="dim")
            if burn_rate_per_minute > 0:
                # Color ETA red if it's before block end (urgent), otherwise cyan (less urgent)
                eta_style = get_color("eta_urgent") if eta_before_block_end else get_color("eta_normal")
                burn_rate_text.append(eta_display, style=eta_style)
            else:
                burn_rate_text.append("∞", style=get_color("success"))

        return burn_rate_text

    def _calculate_eta_display(
        self, snapshot: UsageSnapshot, total_tokens: int, total_limit: int, burn_rate_per_minute: float
    ) -> tuple[str, bool]:
        """Calculate ETA display string with block end time capping.

        Returns:
            Tuple of (display_string, eta_before_block_end)
        """
        remaining_tokens = total_limit - total_tokens
        if burn_rate_per_minute <= 0 or remaining_tokens <= 0:
            return "N/A", False

        minutes_until_limit = remaining_tokens / burn_rate_per_minute

        # Calculate actual time when limit will be reached
        eta_time = snapshot.timestamp + timedelta(minutes=minutes_until_limit)

        # Check if ETA is before block end time (for styling purposes)
        block_end_time = snapshot.unified_block_end_time
        eta_before_block_end = False

        if block_end_time:
            # ETA is before block end if it's less than the block end time
            eta_before_block_end = eta_time < block_end_time

        # Format time remaining and actual time
        total_minutes = int(minutes_until_limit)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0:
            time_remaining = f"{hours}h {minutes}m"
        else:
            time_remaining = f"{minutes}m"

        # Format ETA time based on display settings
        if self.time_format == "12h":
            eta_clock = eta_time.strftime("%I:%M %p")
        else:
            eta_clock = eta_time.strftime("%H:%M")

        # Combine duration and clock time
        return f"{time_remaining} ({eta_clock})", eta_before_block_end

    async def _create_sessions_table(self, snapshot: UsageSnapshot) -> Panel:
        """Create active sessions table.

        Args:
            snapshot: Usage snapshot

        Returns:
            Sessions panel
        """
        table = Table(
            title=None,
            show_header=True,
            header_style=get_style("accent", bold=True),
            show_lines=False,
            expand=False,
        )

        # Get unified block start time
        unified_start = snapshot.unified_block_start_time

        if self.config.display.aggregate_by_project:
            await self._populate_project_table(table, snapshot, unified_start)
        else:
            await self._populate_session_table(table, snapshot, unified_start)

        # Add empty row if no data
        self._add_empty_row_if_needed(table)

        # Set title based on aggregation mode
        title = self._get_table_title()

        return Panel(
            table,
            title=title,
            border_style=get_color("success"),
        )

    def _add_project_table_columns(self, table: Table, show_pricing: bool) -> None:
        """Add columns to project table."""
        table.add_column("Project", style=get_color("project_name"))
        table.add_column("Model", style=get_color("model_name"))
        table.add_column("Tokens", style=get_color("token_count"), justify="right")

        if show_pricing:
            table.add_column("Cost", style=get_color("cost"), justify="right")

        if self.config.display.show_tool_usage:
            table.add_column("Tools", style=get_color("tool_usage"), justify="center")

    async def _calculate_project_cost(self, project: Project, unified_start: datetime | None) -> float:
        """Calculate total cost for a project."""
        project_cost = 0.0
        try:
            for session in project.sessions.values():
                for block in session.blocks:
                    if block.is_active and (
                        unified_start is None or project._block_overlaps_unified_window(block, unified_start)
                    ):
                        for full_model in block.full_model_names:
                            from .pricing import calculate_token_cost

                            usage = block.token_usage
                            cost = await calculate_token_cost(
                                full_model,
                                usage.input_tokens,
                                usage.output_tokens,
                                usage.cache_creation_input_tokens,
                                usage.cache_read_input_tokens,
                            )
                            project_cost += cost.total_cost
        except Exception:
            project_cost = 0.0
        return project_cost

    async def _collect_project_data(self, snapshot: UsageSnapshot, unified_start: datetime | None, show_pricing: bool):
        """Collect and sort project data."""
        active_projects = []

        for project in snapshot.active_projects:
            project_tokens = project.get_unified_block_tokens(unified_start)
            if project_tokens <= 0:
                continue

            project_models = project.get_unified_block_models(unified_start)
            project_latest_activity = project.get_unified_block_latest_activity(unified_start)
            project_tools = (
                project.get_unified_block_tools(unified_start) if self.config.display.show_tool_usage else set()
            )
            project_tool_calls = (
                project.get_unified_block_tool_calls(unified_start) if self.config.display.show_tool_usage else 0
            )

            project_cost = await self._calculate_project_cost(project, unified_start) if show_pricing else 0.0

            active_projects.append(
                (
                    project,
                    project_tokens,
                    project_models,
                    project_latest_activity,
                    project_tools,
                    project_tool_calls,
                    project_cost,
                )
            )

        # Sort projects by latest activity time (newest first)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        utc = ZoneInfo("UTC")
        active_projects.sort(key=lambda x: x[3] if x[3] is not None else datetime.min.replace(tzinfo=utc), reverse=True)

        return active_projects

    def _add_project_table_row(
        self,
        table: Table,
        project,
        project_tokens: int,
        model_display: str,
        cost_display: str,
        tool_display: str,
        show_pricing: bool,
    ) -> None:
        """Add a single row to the project table."""
        row_data = [
            self._strip_project_name(project.name),
            model_display,
            format_token_count(project_tokens),
        ]

        if show_pricing:
            row_data.append(cost_display)

        if self.config.display.show_tool_usage:
            row_data.append(tool_display)

        table.add_row(*row_data)

    async def _populate_project_table(
        self, table: Table, snapshot: UsageSnapshot, unified_start: datetime | None
    ) -> None:
        """Populate table with project aggregated data."""
        show_pricing = self.config and self.config.display.show_pricing

        self._add_project_table_columns(table, show_pricing)
        active_projects = await self._collect_project_data(snapshot, unified_start, show_pricing)

        # Add rows for sorted projects
        for (
            project,
            project_tokens,
            project_models,
            _,
            project_tools,
            project_tool_calls,
            project_cost,
        ) in active_projects:
            # Display models used
            from .token_calculator import get_model_display_name

            model_display = ", ".join(sorted({get_model_display_name(m) for m in project_models}))

            # Prepare cost display if pricing is enabled
            cost_display = ""
            if show_pricing:
                from .pricing import format_cost

                cost_display = format_cost(project_cost) if project_cost > 0 else "-"

            # Prepare tool display
            tool_display = ""
            if self.config.display.show_tool_usage:
                if project_tools:
                    tool_display = f"{', '.join(sorted(project_tools, key=str.lower))} ({project_tool_calls})"
                else:
                    tool_display = "-"

            self._add_project_table_row(
                table, project, project_tokens, model_display, cost_display, tool_display, show_pricing
            )

    def _add_session_table_columns(self, table: Table, show_pricing: bool) -> None:
        """Add columns to session table."""
        table.add_column("Project", style=get_color("project_name"))
        table.add_column("Session ID", style="dim")
        table.add_column("Model", style=get_color("model_name"))
        table.add_column("Tokens", style=get_color("token_count"), justify="right")

        if show_pricing:
            table.add_column("Cost", style=get_color("cost"), justify="right")

        if self.config.display.show_tool_usage:
            table.add_column("Tools", style=get_color("tool_usage"), justify="center")

    async def _collect_session_data(self, snapshot: UsageSnapshot, unified_start: datetime | None, show_pricing: bool):
        """Collect and sort session data."""
        active_sessions = []

        for project in snapshot.active_projects:
            for session in project.active_sessions:
                session_data = await self._calculate_session_data_with_cost(session, unified_start, show_pricing)
                if session_data[0] > 0:  # session_tokens > 0
                    active_sessions.append((project, session, *session_data))

        # Sort sessions by latest activity time (newest first)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        utc = ZoneInfo("UTC")
        active_sessions.sort(key=lambda x: x[4] if x[4] is not None else datetime.min.replace(tzinfo=utc), reverse=True)

        return active_sessions

    def _add_session_table_row(
        self,
        table: Table,
        project,
        session,
        session_tokens: int,
        model_display: str,
        cost_display: str,
        tool_display: str,
        show_pricing: bool,
    ) -> None:
        """Add a single row to the session table."""
        row_data = [
            self._strip_project_name(project.name),
            session.session_id,
            model_display,
            format_token_count(session_tokens),
        ]

        if show_pricing:
            row_data.append(cost_display)

        if self.config.display.show_tool_usage:
            row_data.append(tool_display)

        table.add_row(*row_data)

    async def _populate_session_table(
        self, table: Table, snapshot: UsageSnapshot, unified_start: datetime | None
    ) -> None:
        """Populate table with session data."""
        show_pricing = self.config and self.config.display.show_pricing

        self._add_session_table_columns(table, show_pricing)
        active_sessions = await self._collect_session_data(snapshot, unified_start, show_pricing)

        # Add rows for sorted sessions
        for (
            project,
            session,
            session_tokens,
            session_models,
            _,
            session_tools,
            session_tool_calls,
            session_cost,
        ) in active_sessions:
            # Display models used
            from .token_calculator import get_model_display_name

            model_display = ", ".join(sorted({get_model_display_name(m) for m in session_models}))

            # Prepare cost display if pricing is enabled
            cost_display = ""
            if show_pricing:
                from .pricing import format_cost

                cost_display = format_cost(session_cost) if session_cost > 0 else "-"

            # Prepare tool display if needed
            tool_display = ""
            if self.config.display.show_tool_usage:
                if session_tools:
                    tool_display = f"{', '.join(sorted(session_tools, key=str.lower))} ({session_tool_calls})"
                else:
                    tool_display = "-"

            self._add_session_table_row(
                table, project, session, session_tokens, model_display, cost_display, tool_display, show_pricing
            )

    def _calculate_session_data(
        self, session: Session, unified_start: datetime | None
    ) -> tuple[int, set[str], datetime | None, set[str], int]:
        """Calculate session tokens, models, latest activity, tools, and tool calls."""
        session_tokens = 0
        session_models: set[str] = set()
        session_latest_activity = None
        session_tools: set[str] = set()
        session_tool_calls = 0

        for block in session.blocks:
            # Show any session with activity within the current unified block time window
            include_block = self._should_include_block(block, unified_start)

            if include_block:
                session_tokens += block.adjusted_tokens
                session_models.update(block.models_used)
                session_tools.update(block.tools_used)
                session_tool_calls += block.total_tool_calls
                # Track the latest activity time for this session (for sorting)
                latest_time = block.actual_end_time or block.start_time
                if session_latest_activity is None or latest_time > session_latest_activity:
                    session_latest_activity = latest_time

        return session_tokens, session_models, session_latest_activity, session_tools, session_tool_calls

    async def _calculate_session_data_with_cost(
        self, session: Session, unified_start: datetime | None, show_pricing: bool
    ) -> tuple[int, set[str], datetime | None, set[str], int, float]:
        """Calculate session tokens, models, latest activity, tools, tool calls, and cost."""
        session_tokens = 0
        session_models: set[str] = set()
        session_latest_activity = None
        session_tools: set[str] = set()
        session_tool_calls = 0
        session_cost = 0.0

        for block in session.blocks:
            # Show any session with activity within the current unified block time window
            include_block = self._should_include_block(block, unified_start)

            if include_block:
                session_tokens += block.adjusted_tokens
                session_models.update(block.models_used)
                session_tools.update(block.tools_used)
                session_tool_calls += block.total_tool_calls
                # Track the latest activity time for this session (for sorting)
                latest_time = block.actual_end_time or block.start_time
                if session_latest_activity is None or latest_time > session_latest_activity:
                    session_latest_activity = latest_time

                # Calculate cost if pricing is enabled
                if show_pricing:
                    try:
                        # Calculate cost for each full model name in the block
                        for full_model in block.full_model_names:
                            from .pricing import calculate_token_cost

                            usage = block.token_usage
                            cost = await calculate_token_cost(
                                full_model,
                                usage.input_tokens,
                                usage.output_tokens,
                                usage.cache_creation_input_tokens,
                                usage.cache_read_input_tokens,
                            )
                            session_cost += cost.total_cost
                    except Exception:
                        # If cost calculation fails, continue without adding to cost
                        pass

        return session_tokens, session_models, session_latest_activity, session_tools, session_tool_calls, session_cost

    def _create_sessions_table_sync(self, snapshot: UsageSnapshot) -> Panel:
        """Create active sessions table (sync version without pricing).

        Args:
            snapshot: Usage snapshot

        Returns:
            Sessions panel
        """
        table = Table(
            title=None,
            show_header=True,
            header_style=get_style("accent", bold=True),
            show_lines=False,
            expand=False,
        )

        # Get unified block start time
        unified_start = snapshot.unified_block_start_time

        if self.config.display.aggregate_by_project:
            self._populate_project_table_sync(table, snapshot, unified_start)
        else:
            self._populate_session_table_sync(table, snapshot, unified_start)

        # Add empty row if no data
        self._add_empty_row_if_needed(table)

        # Set title based on aggregation mode
        title = self._get_table_title()

        return Panel(
            table,
            title=title,
            border_style=get_color("success"),
        )

    def _populate_project_table_sync(
        self, table: Table, snapshot: UsageSnapshot, unified_start: datetime | None
    ) -> None:
        """Populate table with project aggregated data (sync version without pricing)."""
        table.add_column("Project", style=get_color("project_name"))
        table.add_column("Model", style=get_color("model_name"))
        table.add_column("Tokens", style=get_color("token_count"), justify="right")
        if self.config.display.show_tool_usage:
            table.add_column("Tools", style=get_color("tool_usage"), justify="center")

        # Collect project data (without cost)
        active_projects: list[tuple[Project, int, set[str], datetime | None, set[str], int]] = []
        for project in snapshot.active_projects:
            project_tokens = project.get_unified_block_tokens(unified_start)
            project_models = project.get_unified_block_models(unified_start)
            project_latest_activity = project.get_unified_block_latest_activity(unified_start)
            project_tools = (
                project.get_unified_block_tools(unified_start) if self.config.display.show_tool_usage else set()
            )
            project_tool_calls = (
                project.get_unified_block_tool_calls(unified_start) if self.config.display.show_tool_usage else 0
            )

            if project_tokens > 0:
                active_projects.append(
                    (
                        project,
                        project_tokens,
                        project_models,
                        project_latest_activity,
                        project_tools,
                        project_tool_calls,
                    )
                )

        # Sort projects by latest activity time (newest first)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        utc = ZoneInfo("UTC")
        active_projects.sort(key=lambda x: x[3] if x[3] is not None else datetime.min.replace(tzinfo=utc), reverse=True)

        # Add rows for sorted projects
        for project, project_tokens, project_models, _, project_tools, project_tool_calls in active_projects:
            # Display models used
            from .token_calculator import get_model_display_name

            model_display = ", ".join(sorted({get_model_display_name(m) for m in project_models}))

            # Prepare tool display
            if self.config.display.show_tool_usage:
                if project_tools:
                    # Show tools and call count
                    tool_display = f"{', '.join(sorted(project_tools, key=str.lower))} ({project_tool_calls})"
                else:
                    tool_display = "-"

                table.add_row(
                    self._strip_project_name(project.name),
                    model_display,
                    format_token_count(project_tokens),
                    tool_display,
                )
            else:
                table.add_row(
                    self._strip_project_name(project.name),
                    model_display,
                    format_token_count(project_tokens),
                )

    def _populate_session_table_sync(
        self, table: Table, snapshot: UsageSnapshot, unified_start: datetime | None
    ) -> None:
        """Populate table with session data (sync version without pricing)."""
        table.add_column("Project", style=get_color("project_name"))
        table.add_column("Session ID", style="dim")
        table.add_column("Model", style=get_color("model_name"))
        table.add_column("Tokens", style=get_color("token_count"), justify="right")
        if self.config.display.show_tool_usage:
            table.add_column("Tools", style=get_color("tool_usage"), justify="center")

        # Collect all active sessions with their data (without cost)
        active_sessions: list[tuple[Project, Session, int, set[str], datetime | None, set[str], int]] = []
        for project in snapshot.active_projects:
            for session in project.active_sessions:
                session_data = self._calculate_session_data(session, unified_start)
                if session_data[0] > 0:  # session_tokens > 0
                    active_sessions.append((project, session, *session_data))

        # Sort sessions by latest activity time (newest first)
        from datetime import datetime
        from zoneinfo import ZoneInfo

        utc = ZoneInfo("UTC")
        active_sessions.sort(key=lambda x: x[4] if x[4] is not None else datetime.min.replace(tzinfo=utc), reverse=True)

        # Add rows for sorted sessions
        for project, session, session_tokens, session_models, _, session_tools, session_tool_calls in active_sessions:
            # Display models used
            from .token_calculator import get_model_display_name

            model_display = ", ".join(sorted({get_model_display_name(m) for m in session_models}))

            # Prepare tool display if needed
            if self.config.display.show_tool_usage:
                if session_tools:
                    # Show tools and call count
                    tool_display = f"{', '.join(sorted(session_tools, key=str.lower))} ({session_tool_calls})"
                else:
                    tool_display = "-"

                table.add_row(
                    self._strip_project_name(project.name),
                    session.session_id,
                    model_display,
                    format_token_count(session_tokens),
                    tool_display,
                )
            else:
                table.add_row(
                    self._strip_project_name(project.name),
                    session.session_id,
                    model_display,
                    format_token_count(session_tokens),
                )

    def _should_include_block(self, block: Any, unified_start: datetime | None) -> bool:
        """Determine if a block should be included based on unified block time window."""
        if not block.is_active:
            return False

        if unified_start is None:
            # No unified block, show all active blocks
            return True

        # Check if block has activity within the unified block time window
        from datetime import timedelta

        unified_end = unified_start + timedelta(hours=5)

        # Block is included if it overlaps with the unified block time window
        block_end = block.actual_end_time or block.end_time
        return (
            block.start_time < unified_end  # Block starts before unified block ends
            and block_end > unified_start  # Block ends after unified block starts
        )

    def _add_empty_row_if_needed(self, table: Table) -> None:
        """Add empty row if no data in table."""
        if table.row_count == 0:
            # Determine how many columns the table has
            column_count = len(table.columns)

            if self.config.display.aggregate_by_project:
                message = "[dim italic]No active projects[/]"
            else:
                message = "[dim italic]No active sessions[/]"

            # Create empty strings for all columns except the first one
            empty_cols = [""] * (column_count - 1)
            table.add_row(message, *empty_cols)

    def _get_table_title(self) -> str:
        """Get the appropriate table title based on aggregation mode."""
        if self.config.display.aggregate_by_project:
            return "Projects with Activity in Current Block"
        else:
            return "Sessions with Activity in Current Block"

    def update(self, snapshot: UsageSnapshot) -> None:
        """Update the display with new data (sync version for backwards compatibility).

        Args:
            snapshot: Usage snapshot
        """
        import asyncio

        # If we're in an async context, run the async version
        try:
            asyncio.get_running_loop()
            # We're in an async context, so we need to use the async version
            # For sync compatibility, we'll block until completion
            # This is not ideal but necessary for backwards compatibility
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.update_async(snapshot))
                try:
                    future.result(timeout=10)  # 10 second timeout
                except concurrent.futures.TimeoutError:
                    # If async fails, fall back to sync version without pricing
                    self._update_sync(snapshot)
        except RuntimeError:
            # No event loop running, we can run async directly
            asyncio.run(self.update_async(snapshot))

    async def update_async(self, snapshot: UsageSnapshot) -> None:
        """Update the display with new data (async version with pricing support).

        Args:
            snapshot: Usage snapshot
        """
        self.layout["header"].update(self._create_header(snapshot))
        self.layout["progress"].update(await self._create_progress_bars(snapshot))

        # Update non-compact mode elements only if not in compact mode
        if not self.compact_mode:
            try:
                self.layout["block_progress"].update(self._create_block_progress(snapshot))
            except KeyError:
                pass
            # Update tool usage with dynamic height only if tool usage is enabled
            if self.show_tool_usage:
                try:
                    tool_usage_height = self._calculate_tool_usage_height(snapshot)
                    self.layout["tool_usage"].size = tool_usage_height
                    self.layout["tool_usage"].update(self._create_tool_usage_table(snapshot))
                except KeyError:
                    pass
            if self.show_sessions:
                try:
                    self.layout["sessions"].update(await self._create_sessions_table(snapshot))
                except KeyError:
                    pass

    def _update_sync(self, snapshot: UsageSnapshot) -> None:
        """Update the display with new data (sync version without pricing).

        Args:
            snapshot: Usage snapshot
        """
        self.layout["header"].update(self._create_header(snapshot))
        # Use the sync version of progress bars (without pricing)
        self.layout["progress"].update(self._create_progress_bars_sync(snapshot))

        # Update non-compact mode elements only if not in compact mode
        if not self.compact_mode:
            try:
                self.layout["block_progress"].update(self._create_block_progress(snapshot))
            except KeyError:
                pass
            # Update tool usage with dynamic height only if tool usage is enabled
            if self.show_tool_usage:
                try:
                    tool_usage_height = self._calculate_tool_usage_height(snapshot)
                    self.layout["tool_usage"].size = tool_usage_height
                    self.layout["tool_usage"].update(self._create_tool_usage_table(snapshot))
                except KeyError:
                    pass
            if self.show_sessions:
                try:
                    self.layout["sessions"].update(self._create_sessions_table_sync(snapshot))
                except KeyError:
                    pass

    def _create_progress_bars_sync(self, snapshot: UsageSnapshot) -> Panel:
        """Create progress bars for token usage (sync version without pricing).

        Args:
            snapshot: Usage snapshot

        Returns:
            Progress panel
        """
        # Get token usage by model for unified block only
        model_tokens = snapshot.unified_block_tokens_by_model()
        total_tokens = snapshot.unified_block_tokens()
        model_interruptions = snapshot.unified_block_interruptions_by_model()

        # If no unified block data, fall back to all active tokens and models
        if not model_tokens and total_tokens == 0:
            model_tokens = snapshot.tokens_by_model()
            total_tokens = snapshot.active_tokens
            model_interruptions = snapshot.interruptions_by_model()

        # Ensure limit is at least as high as current usage
        base_limit = snapshot.total_limit or 500_000
        total_limit = max(base_limit, total_tokens)

        # Create per-model token displays (no progress bars)
        from rich.console import Group
        from rich.progress import BarColumn, Progress, TextColumn

        # Use regular display (no pricing in sync version)
        model_displays = self._create_model_displays(model_tokens, model_interruptions)

        # Calculate burn rate and estimated total usage (sync version without cost)
        burn_rate_text = self._calculate_burn_rate_sync(snapshot, total_tokens, total_limit)

        # Combine model displays and burn rate (no pricing in sync version)
        all_displays = []
        if model_displays:
            all_displays.extend(model_displays)
        all_displays.append(burn_rate_text)

        # Add total progress bar only if not in compact mode
        if not self.compact_mode:
            # Total progress bar with color based on percentage
            percentage = (total_tokens / total_limit) * 100
            bar_color, text_style = self._get_progress_colors(percentage, total_tokens, base_limit)

            # Create the tokens text (no cost in sync version)
            tokens_text = f"{format_token_count(total_tokens):>8} / {format_token_count(total_limit)}"

            total_progress = Progress(
                TextColumn("📊 Total   ", style=text_style),
                BarColumn(bar_width=25, complete_style=bar_color, finished_style=bar_color),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn(tokens_text, style=text_style),
                console=self.console,
                expand=False,
            )
            total_progress.add_task("Total", total=total_limit, completed=total_tokens)
            all_displays.append(total_progress)
        else:
            # In compact mode, show total as simple text (no cost in sync version)
            percentage = (total_tokens / total_limit) * 100
            _, text_style = self._get_progress_colors(percentage, total_tokens, base_limit)

            total_text = Text()
            total_text.append("📊 Total   ", style=text_style)
            total_text.append(
                f"{format_token_count(total_tokens):>8} / {format_token_count(total_limit)} ", style=text_style
            )
            total_text.append(f"({percentage:>3.0f}%)", style=text_style)
            all_displays.append(total_text)

        all_progress = Group(*all_displays)

        return Panel(
            all_progress,
            title="Token Usage by Model",
            border_style=get_color("border"),
        )

    def render(self) -> Layout:
        """Get the renderable layout.

        Returns:
            Layout to render
        """
        return self.layout


class DisplayManager:
    """Manage the live display."""

    def __init__(
        self,
        console: Console | None = None,
        refresh_interval: float = 1.0,
        update_in_place: bool = True,
        show_sessions: bool = False,
        time_format: str = "24h",
        config: Any = None,
    ) -> None:
        """Initialize display manager.

        Args:
            console: Rich console instance
            refresh_interval: Refresh interval in seconds
            update_in_place: Whether to update in place
            show_sessions: Whether to show the sessions panel
            time_format: Time format ('12h' or '24h')
            config: Configuration object
        """
        self.console = console or Console()
        self.refresh_interval = refresh_interval
        self.update_in_place = update_in_place
        self.display = MonitorDisplay(self.console, show_sessions, time_format, config)
        self.config = config
        self.live: Live | None = None

    def start(self) -> None:
        """Start the live display."""
        if self.update_in_place:
            self.live = Live(
                self.display.render(),
                console=self.console,
                refresh_per_second=1 / self.refresh_interval,
                transient=False,
            )
            self.live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None

    async def update(self, snapshot: UsageSnapshot) -> None:
        """Update the display with new data.

        Args:
            snapshot: Usage snapshot
        """
        await self.display.update_async(snapshot)

        if self.update_in_place and self.live:
            self.live.update(self.display.render())
        else:
            self.console.clear()
            self.console.print(self.display.render())

    def __enter__(self) -> DisplayManager:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()


def create_error_display(error_message: str) -> Panel:
    """Create an error display panel.

    Args:
        error_message: Error message to display

    Returns:
        Error panel
    """
    return Panel(
        Text(error_message, style=get_style("error", bold=True)),
        title="Error",
        border_style=get_color("error"),
        expand=False,
    )


def create_info_display(info_message: str) -> Panel:
    """Create an info display panel.

    Args:
        info_message: Info message to display

    Returns:
        Info panel
    """
    return Panel(
        Text(info_message, style=get_style("info", bold=True)),
        title="Info",
        border_style=get_color("info"),
        expand=False,
    )
