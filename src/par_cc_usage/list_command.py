"""List command implementation for par_cc_usage."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .enums import OutputFormat, SortBy, TimeFormat
from .models import Project, Session, TokenBlock, UsageSnapshot
from .token_calculator import format_token_count, get_model_display_name
from .utils import format_date_time_range


class ListDisplay:
    """Display component for list mode."""

    def __init__(self, console: Console | None = None, time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR) -> None:
        """Initialize list display.

        Args:
            console: Rich console instance
            time_format: Time format (12h or 24h)
        """
        self.console = console or Console()
        self.time_format = time_format

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

    def display_table(self, snapshot: UsageSnapshot, sort_by: SortBy = SortBy.TOKENS) -> None:
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
        table.add_column("Active", style="magenta", width=8, justify="center")

        # Get and sort blocks
        blocks = self.get_all_blocks(snapshot)
        blocks = self.sort_blocks(blocks, sort_by)

        # Add rows
        total_tokens = 0
        active_tokens = 0
        for project, session, block in blocks:
            is_active = block.is_active
            tokens = block.adjusted_tokens
            total_tokens += tokens
            if is_active:
                active_tokens += tokens

            table.add_row(
                project.name,
                session.session_id,
                block.all_models_display,
                format_date_time_range(block.start_time, block.end_time, self.time_format),
                str(block.messages_processed),
                format_token_count(tokens),
                "✓" if is_active else "",
                style="bright_white" if is_active else "dim",
            )

        # Add summary row
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            "",
            f"[bold]{format_token_count(total_tokens)}[/bold]",
            f"[bold]{format_token_count(active_tokens)}[/bold]",
            style="bright_yellow",
        )

        self.console.print(table)

    def export_json(self, snapshot: UsageSnapshot, output_file: Path, sort_by: SortBy = SortBy.TOKENS) -> None:
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
            data["blocks"].append(block_data)

        # Write to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.console.print(f"[green]Exported JSON to {output_file}[/green]")

    def export_csv(self, snapshot: UsageSnapshot, output_file: Path, sort_by: SortBy = SortBy.TOKENS) -> None:
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
            writer.writerow(
                [
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
                    "Is Active",
                ]
            )

            # Write data rows
            for project, session, block in blocks:
                writer.writerow(
                    [
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
                        block.is_active,
                    ]
                )

        self.console.print(f"[green]Exported CSV to {output_file}[/green]")


def display_usage_list(
    snapshot: UsageSnapshot,
    output_format: OutputFormat = OutputFormat.TABLE,
    sort_by: SortBy = SortBy.TOKENS,
    output_file: Path | None = None,
    console: Console | None = None,
    time_format: TimeFormat = TimeFormat.TWENTY_FOUR_HOUR,
) -> None:
    """Display usage data in list format.

    Args:
        snapshot: Usage snapshot
        output_format: Output format
        sort_by: Field to sort by
        output_file: Output file path (for JSON/CSV)
        console: Rich console instance
        time_format: Time format (12h or 24h)
    """
    display = ListDisplay(console, time_format)

    if output_format == OutputFormat.TABLE:
        display.display_table(snapshot, sort_by)
    elif output_format == OutputFormat.JSON:
        if output_file:
            display.export_json(snapshot, output_file, sort_by)
        else:
            # Print to console
            console = console or Console()
            blocks = display.get_all_blocks(snapshot)
            blocks = display.sort_blocks(blocks, sort_by)
            data: list[dict[str, Any]] = []
            for project, session, block in blocks:
                data.append(
                    {
                        "project": project.name,
                        "session": session.session_id,
                        "model": block.model,
                        "tokens": block.adjusted_tokens,
                        "active": block.is_active,
                    }
                )
            console.print_json(data=data)
    elif output_format == OutputFormat.CSV:
        if output_file:
            display.export_csv(snapshot, output_file, sort_by)
        else:
            console = console or Console()
            console.print("[red]CSV format requires --output option[/red]")
