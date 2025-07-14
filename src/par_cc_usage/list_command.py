"""List command implementation for par_cc_usage."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .enums import OutputFormat, SortBy, TimeFormat
from .models import Project, Session, TokenBlock, UsageSnapshot
from .pricing import calculate_token_cost
from .token_calculator import format_token_count, get_model_display_name
from .utils import format_date_time_range

logger = logging.getLogger(__name__)


class ListDisplay:
    """Display component for list mode."""

    def __init__(
        self,
        console: Console | None = None,
        time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR,
        show_pricing: bool = False,
    ) -> None:
        """Initialize list display.

        Args:
            console: Rich console instance
            time_format: Time format (12h or 24h)
            show_pricing: Whether to show pricing information
        """
        self.console = console or Console()
        self.time_format = time_format
        self.show_pricing = show_pricing

    def _validate_native_cost(self, cost_value: float | None) -> bool:
        """Validate that native cost data is reasonable.

        Args:
            cost_value: Cost value to validate

        Returns:
            True if cost is valid and should be used
        """
        if cost_value is None or cost_value <= 0:
            return False

        # Sanity check: cost shouldn't be impossibly high
        # (e.g., more than $1000 for a single block)
        if cost_value > 1000.0:
            logger.warning(f"Suspiciously high native cost detected: ${cost_value}")
            return False

        return True

    def _get_cost_source(self, block: TokenBlock) -> str:
        """Determine the source of cost data.

        Args:
            block: Token block to analyze

        Returns:
            String indicating cost calculation source
        """
        if hasattr(block, "cost_usd") and self._validate_native_cost(block.cost_usd):
            return "block_native"
        elif hasattr(block.token_usage, "cost_usd") and self._validate_native_cost(block.token_usage.cost_usd):
            return "usage_native"
        else:
            return "litellm_calculated"

    async def _calculate_block_cost(self, block: TokenBlock) -> float:
        """Calculate cost for a token block, preferring native cost data.

        Args:
            block: Token block to calculate cost for

        Returns:
            Cost in dollars
        """
        if not self.show_pricing:
            return 0.0

        # Priority 1: Use native cost data from TokenBlock if available and valid
        if hasattr(block, "cost_usd") and self._validate_native_cost(block.cost_usd):
            logger.debug(f"Using block native cost: ${block.cost_usd}")
            return block.cost_usd

        # Priority 2: Use aggregated TokenUsage cost if available and valid
        if hasattr(block.token_usage, "cost_usd") and self._validate_native_cost(block.token_usage.cost_usd):
            logger.debug(f"Using token usage native cost: ${block.token_usage.cost_usd}")
            return block.token_usage.cost_usd or 0.0

        # Priority 3: Fallback to cached LiteLLM calculation (current method)
        logger.debug(f"Using LiteLLM calculated cost for model: {block.model}")
        cost_result = await calculate_token_cost(
            block.model,
            block.token_usage.actual_input_tokens + block.token_usage.actual_cache_creation_input_tokens,
            block.token_usage.actual_output_tokens,
        )
        return cost_result.total_cost

    def get_all_blocks(self, snapshot: UsageSnapshot) -> list[tuple[Project, Session, TokenBlock]]:
        """Get all blocks from snapshot.

        Args:
            snapshot: Usage snapshot

        Returns:
            List of (project, session, block) tuples
        """
        blocks: list[tuple[Project, Session, TokenBlock]] = []
        for project in snapshot.projects.values():
            for session in project.sessions.values():
                for block in session.blocks:
                    blocks.append((project, session, block))
        return blocks

    def sort_blocks(
        self,
        blocks: list[tuple[Project, Session, TokenBlock]],
        sort_by: SortBy,
    ) -> list[tuple[Project, Session, TokenBlock]]:
        """Sort blocks by specified field.

        Args:
            blocks: List of block tuples
            sort_by: Field to sort by

        Returns:
            Sorted list of block tuples
        """
        if sort_by == SortBy.PROJECT:
            return sorted(blocks, key=lambda x: x[0].name)
        elif sort_by == SortBy.SESSION:
            return sorted(blocks, key=lambda x: x[1].session_id)
        elif sort_by == SortBy.TOKENS:
            return sorted(blocks, key=lambda x: x[2].adjusted_tokens, reverse=True)
        elif sort_by == SortBy.TIME:
            return sorted(blocks, key=lambda x: x[2].start_time, reverse=True)
        elif sort_by == SortBy.MODEL:
            return sorted(blocks, key=lambda x: x[2].model)
        else:
            return blocks

    async def display_table(self, snapshot: UsageSnapshot, sort_by: SortBy = SortBy.TOKENS) -> None:
        """Display usage data as a table.

        Args:
            snapshot: Usage snapshot
            sort_by: Field to sort by
        """
        # Create table
        table = Table(
            title="Claude Code Token Usage",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )

        table.add_column("Project", style="cyan", width=40)
        table.add_column("Session ID", style="dim", width=36)
        table.add_column("Model", style="green", width=15)
        table.add_column("Block Time", style="dim", width=25)
        table.add_column("Messages", style="blue", width=10, justify="right")
        table.add_column("Tokens", style="yellow", width=12, justify="right")
        if self.show_pricing:
            table.add_column("Cost", style="green", width=10, justify="right")
        table.add_column("Active", style="magenta", width=8, justify="center")

        # Get and sort blocks
        blocks = self.get_all_blocks(snapshot)
        blocks = self.sort_blocks(blocks, sort_by)

        # Add rows
        total_tokens = 0
        active_tokens = 0
        total_cost = 0.0
        active_cost = 0.0

        for project, session, block in blocks:
            is_active = block.is_active
            tokens = block.adjusted_tokens
            total_tokens += tokens
            if is_active:
                active_tokens += tokens

            # Calculate cost if pricing is enabled
            cost = 0.0
            if self.show_pricing:
                cost = await self._calculate_block_cost(block)
                total_cost += cost
                if is_active:
                    active_cost += cost

            # Build row data
            row_data = [
                project.name,
                session.session_id,
                block.all_models_display,
                format_date_time_range(block.start_time, block.end_time, self.time_format),
                str(block.messages_processed),
                format_token_count(tokens),
            ]

            if self.show_pricing:
                row_data.append(f"${cost:.4f}")

            row_data.append("✓" if is_active else "")

            table.add_row(
                *row_data,
                style="bright_white" if is_active else "dim",
            )

        # Add summary row
        summary_row = [
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            "",
            f"[bold]{format_token_count(total_tokens)}[/bold]",
        ]

        if self.show_pricing:
            summary_row.append(f"[bold]${total_cost:.4f}[/bold]")

        summary_row.append(f"[bold]{format_token_count(active_tokens)}[/bold]")

        table.add_row(
            *summary_row,
            style="bright_yellow",
        )

        self.console.print(table)

    async def export_json(self, snapshot: UsageSnapshot, output_file: Path, sort_by: SortBy = SortBy.TOKENS) -> None:
        """Export usage data as JSON.

        Args:
            snapshot: Usage snapshot
            output_file: Output file path
            sort_by: Field to sort by
        """
        # Get and sort blocks
        blocks = self.get_all_blocks(snapshot)
        blocks = self.sort_blocks(blocks, sort_by)

        # Build JSON data
        data: dict[str, Any] = {
            "timestamp": snapshot.timestamp.isoformat(),
            "total_limit": snapshot.total_limit,
            "total_tokens": snapshot.total_tokens,
            "active_tokens": snapshot.active_tokens,
            "blocks": [],
        }

        for project, session, block in blocks:
            block_data = {
                "project": project.name,
                "session_id": session.session_id,
                "model": block.model,
                "model_display": get_model_display_name(block.model),
                "block_start": block.start_time.isoformat(),
                "block_end": block.end_time.isoformat(),
                "messages_processed": block.messages_processed,
                "is_active": block.is_active,
                "tokens": {
                    "input": block.token_usage.input_tokens,
                    "cache_creation": block.token_usage.cache_creation_input_tokens,
                    "cache_read": block.token_usage.cache_read_input_tokens,
                    "output": block.token_usage.output_tokens,
                    "total": block.token_usage.total,
                    "adjusted": block.adjusted_tokens,
                    "multiplier": block.model_multiplier,
                },
            }

            # Add cost information if pricing is enabled
            if self.show_pricing:
                cost = await self._calculate_block_cost(block)
                cost_source = self._get_cost_source(block)
                block_data["cost"] = cost
                block_data["cost_source"] = cost_source

            data["blocks"].append(block_data)

        # Write to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.console.print(f"[green]Exported JSON to {output_file}[/green]")

    async def export_csv(self, snapshot: UsageSnapshot, output_file: Path, sort_by: SortBy = SortBy.TOKENS) -> None:
        """Export usage data as CSV.

        Args:
            snapshot: Usage snapshot
            output_file: Output file path
            sort_by: Field to sort by
        """
        # Get and sort blocks
        blocks = self.get_all_blocks(snapshot)
        blocks = self.sort_blocks(blocks, sort_by)

        # Write CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            header = [
                "Project",
                "Session ID",
                "Model",
                "Model Display",
                "Block Start",
                "Block End",
                "Messages",
                "Input Tokens",
                "Cache Creation Tokens",
                "Cache Read Tokens",
                "Output Tokens",
                "Total Tokens",
                "Multiplier",
                "Adjusted Tokens",
            ]

            if self.show_pricing:
                header.append("Cost")
                header.append("Cost Source")

            header.append("Is Active")
            writer.writerow(header)

            # Write data rows
            for project, session, block in blocks:
                row_data = [
                    project.name,
                    session.session_id,
                    block.model,
                    get_model_display_name(block.model),
                    block.start_time.isoformat(),
                    block.end_time.isoformat(),
                    block.messages_processed,
                    block.token_usage.input_tokens,
                    block.token_usage.cache_creation_input_tokens,
                    block.token_usage.cache_read_input_tokens,
                    block.token_usage.output_tokens,
                    block.token_usage.total,
                    block.model_multiplier,
                    block.adjusted_tokens,
                ]

                if self.show_pricing:
                    cost = await self._calculate_block_cost(block)
                    cost_source = self._get_cost_source(block)
                    row_data.append(cost)
                    row_data.append(cost_source)

                row_data.append(block.is_active)
                writer.writerow(row_data)

        self.console.print(f"[green]Exported CSV to {output_file}[/green]")


async def display_usage_list(
    snapshot: UsageSnapshot,
    output_format: OutputFormat = OutputFormat.TABLE,
    sort_by: SortBy = SortBy.TOKENS,
    output_file: Path | None = None,
    console: Console | None = None,
    time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR,
    show_pricing: bool = False,
) -> None:
    """Display usage data in list format.

    Args:
        snapshot: Usage snapshot
        output_format: Output format
        sort_by: Field to sort by
        output_file: Output file path (for JSON/CSV)
        console: Rich console instance
        time_format: Time format (12h or 24h)
        show_pricing: Whether to show pricing information
    """
    display = ListDisplay(console, time_format, show_pricing)

    if output_format == OutputFormat.TABLE:
        await display.display_table(snapshot, sort_by)
    elif output_format == OutputFormat.JSON:
        if output_file:
            await display.export_json(snapshot, output_file, sort_by)
        else:
            # Print to console
            console = console or Console()
            blocks = display.get_all_blocks(snapshot)
            blocks = display.sort_blocks(blocks, sort_by)
            data: list[dict[str, Any]] = []
            for project, session, block in blocks:
                block_data = {
                    "project": project.name,
                    "session": session.session_id,
                    "model": block.model,
                    "tokens": block.adjusted_tokens,
                    "active": block.is_active,
                }
                if show_pricing:
                    cost = await display._calculate_block_cost(block)
                    cost_source = display._get_cost_source(block)
                    block_data["cost"] = cost
                    block_data["cost_source"] = cost_source
                data.append(block_data)
            console.print_json(data=data)
    elif output_format == OutputFormat.CSV:
        if output_file:
            await display.export_csv(snapshot, output_file, sort_by)
        else:
            console = console or Console()
            console.print("[red]CSV format requires --output option[/red]")
