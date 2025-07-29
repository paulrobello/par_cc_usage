"""Display utilities for usage summaries."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .enums import OutputFormat
from .models import TimeBucketSummary, UsageSummaryData
from .pricing import format_cost
from .theme import get_color
from .token_calculator import format_token_count


class SummaryDisplayManager:
    """Manage display of usage summaries in different formats."""

    def __init__(self, console: Console):
        """Initialize the display manager.

        Args:
            console: Rich console for output
        """
        self.console = console

    async def display_summary(
        self,
        summary: UsageSummaryData,
        output_format: OutputFormat,
        output_file: Path | None = None,
        show_pricing: bool = True,
        show_p90: bool = True,
        show_models: bool = False,
        show_tools: bool = False,
    ) -> None:
        """Display usage summary in the specified format.

        Args:
            summary: The usage summary data
            output_format: Format to display in
            output_file: Optional file to write output to
            show_pricing: Whether to show pricing information
            show_p90: Whether to show P90 statistics
            show_models: Whether to show model breakdown
            show_tools: Whether to show tool usage breakdown
        """
        if output_format == OutputFormat.TABLE:
            await self._display_table(summary, show_pricing, show_p90, show_models, show_tools)
        elif output_format == OutputFormat.JSON:
            content = self._generate_json(summary, show_pricing, show_p90, show_models, show_tools)
            if output_file:
                output_file.write_text(content, encoding="utf-8")
                self.console.print(f"[green]Summary exported to {output_file}[/green]")
            else:
                self.console.print(content)
        elif output_format == OutputFormat.CSV:
            content = self._generate_csv(summary, show_pricing, show_p90)
            if output_file:
                output_file.write_text(content, encoding="utf-8")
                self.console.print(f"[green]Summary exported to {output_file}[/green]")
            else:
                self.console.print(content)

    async def _display_table(
        self,
        summary: UsageSummaryData,
        show_pricing: bool,
        show_p90: bool,
        show_models: bool,
        show_tools: bool,
    ) -> None:
        """Display summary as a rich table."""
        if not summary.buckets:
            self.console.print("[yellow]No usage data found[/yellow]")
            return

        # Main summary table
        table = self._create_main_table(summary, show_pricing, show_p90)

        # Add data rows
        for bucket in summary.buckets:
            row = self._create_table_row(bucket, show_pricing, show_p90)
            table.add_row(*row)

        # Add overall statistics row
        if len(summary.buckets) > 1:
            overall_row = self._create_overall_row(summary, show_pricing, show_p90)
            table.add_section()
            table.add_row(*overall_row, style="bold")

        self.console.print(table)

        # Additional breakdowns if requested
        if show_models and summary.buckets:
            await self._display_model_breakdown(summary)

        if show_tools and summary.buckets:
            self._display_tool_breakdown(summary)

        # Overall statistics
        self._display_overall_stats(summary, show_pricing)

    def _create_main_table(self, summary: UsageSummaryData, show_pricing: bool, show_p90: bool) -> Table:
        """Create the main summary table."""
        bucket_type = summary.time_bucket_type.title()
        title = f"Usage Summary ({bucket_type})"

        table = Table(title=title, show_header=True, header_style="bold magenta")

        # Period column
        table.add_column("Period", style="cyan", min_width=12)

        # Token columns
        table.add_column("Total Tokens", style="blue", justify="right", min_width=12)
        table.add_column("Avg Tokens", style="blue", justify="right", min_width=10)
        if show_p90:
            table.add_column("P90 Tokens", style="blue", justify="right", min_width=10)

        # Message columns
        table.add_column("Messages", style="green", justify="right", min_width=8)
        table.add_column("Avg Msgs", style="green", justify="right", min_width=8)
        if show_p90:
            table.add_column("P90 Msgs", style="green", justify="right", min_width=8)

        # Pricing columns
        if show_pricing:
            table.add_column("Total Cost", style=get_color("cost"), justify="right", min_width=10)
            table.add_column("Avg Cost", style=get_color("cost"), justify="right", min_width=8)
            if show_p90:
                table.add_column("P90 Cost", style=get_color("cost"), justify="right", min_width=8)

        # Activity columns
        table.add_column("Projects", style="yellow", justify="right", min_width=8)
        table.add_column("Sessions", style="yellow", justify="right", min_width=8)

        return table

    def _create_table_row(self, bucket: TimeBucketSummary, show_pricing: bool, show_p90: bool) -> list[str]:
        """Create a table row for a time bucket."""
        row = [bucket.period_name]

        # Token columns
        row.extend(
            [
                format_token_count(bucket.total_tokens),
                format_token_count(int(bucket.average_tokens)),
            ]
        )
        if show_p90:
            row.append(format_token_count(bucket.p90_tokens))

        # Message columns
        row.extend(
            [
                f"{bucket.total_messages:,}",
                f"{bucket.average_messages:.1f}",
            ]
        )
        if show_p90:
            row.append(f"{bucket.p90_messages:,}")

        # Pricing columns
        if show_pricing:
            row.extend(
                [
                    format_cost(bucket.total_cost),
                    format_cost(bucket.average_cost),
                ]
            )
            if show_p90:
                row.append(format_cost(bucket.p90_cost))

        # Activity columns
        row.extend(
            [
                str(bucket.active_projects),
                str(bucket.active_sessions),
            ]
        )

        return row

    def _create_overall_row(self, summary: UsageSummaryData, show_pricing: bool, show_p90: bool) -> list[str]:
        """Create the overall statistics row."""
        row = ["OVERALL"]

        # Token columns
        row.extend(
            [
                format_token_count(summary.overall_total_tokens),
                format_token_count(int(summary.overall_average_tokens)),
            ]
        )
        if show_p90:
            row.append(format_token_count(summary.overall_p90_tokens))

        # Message columns
        row.extend(
            [
                f"{summary.overall_total_messages:,}",
                f"{summary.overall_average_messages:.1f}",
            ]
        )
        if show_p90:
            row.append(f"{summary.overall_p90_messages:,}")

        # Pricing columns
        if show_pricing:
            row.extend(
                [
                    format_cost(summary.overall_total_cost),
                    format_cost(summary.overall_average_cost),
                ]
            )
            if show_p90:
                row.append(format_cost(summary.overall_p90_cost))

        # Activity columns
        row.extend(
            [
                str(len(summary.unique_projects)),
                str(len(summary.unique_sessions)),
            ]
        )

        return row

    async def _display_model_breakdown(self, summary: UsageSummaryData) -> None:
        """Display model usage breakdown."""
        self.console.print("\n[bold]Model Breakdown:[/bold]")

        # Aggregate model data across all buckets
        model_tokens = {}
        model_messages = {}
        model_costs = {}

        for bucket in summary.buckets:
            for model, tokens in bucket.tokens_by_model.items():
                model_tokens[model] = model_tokens.get(model, 0) + tokens
                model_messages[model] = model_messages.get(model, 0) + bucket.messages_by_model.get(model, 0)
                model_costs[model] = model_costs.get(model, 0.0) + bucket.cost_by_model.get(model, 0.0)

        if not model_tokens:
            self.console.print("[dim]No model data available[/dim]")
            return

        model_table = Table(show_header=True, header_style="bold cyan")
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Tokens", style="blue", justify="right")
        model_table.add_column("Messages", style="green", justify="right")
        model_table.add_column("Cost", style=get_color("cost"), justify="right")
        model_table.add_column("% of Total", style="dim", justify="right")

        # Sort by tokens (descending)
        total_tokens = sum(model_tokens.values())
        sorted_models = sorted(model_tokens.items(), key=lambda x: x[1], reverse=True)

        for model, tokens in sorted_models:
            percentage = (tokens / total_tokens * 100) if total_tokens > 0 else 0
            model_table.add_row(
                model,
                format_token_count(tokens),
                f"{model_messages.get(model, 0):,}",
                format_cost(model_costs.get(model, 0.0)),
                f"{percentage:.1f}%",
            )

        self.console.print(model_table)

    def _display_tool_breakdown(self, summary: UsageSummaryData) -> None:
        """Display tool usage breakdown."""
        self.console.print("\n[bold]Tool Usage Breakdown:[/bold]")

        # Aggregate tool data across all buckets
        tool_usage = {}
        for bucket in summary.buckets:
            for tool, count in bucket.tool_usage.items():
                tool_usage[tool] = tool_usage.get(tool, 0) + count

        if not tool_usage:
            self.console.print("[dim]No tool usage data available[/dim]")
            return

        tool_table = Table(show_header=True, header_style="bold green")
        tool_table.add_column("Tool", style="green")
        tool_table.add_column("Usage Count", style="blue", justify="right")
        tool_table.add_column("% of Total", style="dim", justify="right")

        # Sort by usage count (descending)
        total_usage = sum(tool_usage.values())
        sorted_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)

        for tool, count in sorted_tools:
            percentage = (count / total_usage * 100) if total_usage > 0 else 0
            tool_table.add_row(tool, f"{count:,}", f"{percentage:.1f}%")

        self.console.print(tool_table)

    def _display_overall_stats(self, summary: UsageSummaryData, show_pricing: bool) -> None:
        """Display overall statistics."""
        self.console.print("\n[bold]Summary Statistics:[/bold]")

        stats = [
            f"Time Span: {summary.total_time_span_days} days",
            f"Unique Projects: {len(summary.unique_projects)}",
            f"Unique Sessions: {len(summary.unique_sessions)}",
            f"Unique Models: {len(summary.unique_models)}",
            f"Unique Tools: {len(summary.unique_tools)}",
        ]

        if show_pricing:
            stats.append(f"Total Cost: {format_cost(summary.overall_total_cost)}")

        for stat in stats:
            self.console.print(f"  • {stat}")

    def _generate_json(
        self,
        summary: UsageSummaryData,
        show_pricing: bool,
        show_p90: bool,
        show_models: bool,
        show_tools: bool,
    ) -> str:
        """Generate JSON representation of the summary."""
        data = {
            "time_bucket_type": summary.time_bucket_type,
            "generated_at": datetime.now().isoformat(),
            "overall_statistics": self._build_overall_statistics(summary, show_pricing, show_p90),
            "buckets": self._build_bucket_data(summary.buckets, show_pricing, show_p90, show_models, show_tools),
        }

        return json.dumps(data, indent=2, default=str)

    def _build_overall_statistics(self, summary: UsageSummaryData, show_pricing: bool, show_p90: bool) -> dict:
        """Build overall statistics dictionary for JSON output."""
        stats = {
            "total_tokens": summary.overall_total_tokens,
            "total_messages": summary.overall_total_messages,
            "average_tokens": summary.overall_average_tokens,
            "average_messages": summary.overall_average_messages,
            "unique_projects": len(summary.unique_projects),
            "unique_sessions": len(summary.unique_sessions),
            "unique_models": len(summary.unique_models),
            "unique_tools": len(summary.unique_tools),
            "time_span_days": summary.total_time_span_days,
        }

        if show_pricing:
            stats.update(
                {
                    "total_cost": summary.overall_total_cost,
                    "average_cost": summary.overall_average_cost,
                }
            )

        if show_p90:
            stats.update(
                {
                    "p90_tokens": summary.overall_p90_tokens,
                    "p90_messages": summary.overall_p90_messages,
                }
            )
            if show_pricing:
                stats["p90_cost"] = summary.overall_p90_cost

        return stats

    def _build_bucket_data(
        self, buckets: list[TimeBucketSummary], show_pricing: bool, show_p90: bool, show_models: bool, show_tools: bool
    ) -> list[dict]:
        """Build bucket data list for JSON output."""
        bucket_list = []
        for bucket in buckets:
            bucket_data = self._build_single_bucket_data(bucket, show_pricing, show_p90, show_models, show_tools)
            bucket_list.append(bucket_data)
        return bucket_list

    def _build_single_bucket_data(
        self, bucket: TimeBucketSummary, show_pricing: bool, show_p90: bool, show_models: bool, show_tools: bool
    ) -> dict:
        """Build data dictionary for a single bucket."""
        bucket_data = {
            "period_name": bucket.period_name,
            "start_date": bucket.start_date.isoformat(),
            "end_date": bucket.end_date.isoformat(),
            "total_tokens": bucket.total_tokens,
            "total_messages": bucket.total_messages,
            "average_tokens": bucket.average_tokens,
            "average_messages": bucket.average_messages,
            "active_projects": bucket.active_projects,
            "active_sessions": bucket.active_sessions,
            "unified_blocks_count": bucket.unified_blocks_count,
        }

        if show_pricing:
            self._add_pricing_data(bucket_data, bucket)

        if show_p90:
            self._add_p90_data(bucket_data, bucket, show_pricing)

        if show_models:
            self._add_model_data(bucket_data, bucket, show_pricing)

        if show_tools:
            self._add_tool_data(bucket_data, bucket)

        return bucket_data

    def _add_pricing_data(self, bucket_data: dict, bucket: TimeBucketSummary) -> None:
        """Add pricing data to bucket dictionary."""
        bucket_data.update(
            {
                "total_cost": bucket.total_cost,
                "average_cost": bucket.average_cost,
            }
        )

    def _add_p90_data(self, bucket_data: dict, bucket: TimeBucketSummary, show_pricing: bool) -> None:
        """Add P90 data to bucket dictionary."""
        bucket_data.update(
            {
                "p90_tokens": bucket.p90_tokens,
                "p90_messages": bucket.p90_messages,
            }
        )
        if show_pricing:
            bucket_data["p90_cost"] = bucket.p90_cost

    def _add_model_data(self, bucket_data: dict, bucket: TimeBucketSummary, show_pricing: bool) -> None:
        """Add model breakdown data to bucket dictionary."""
        bucket_data["tokens_by_model"] = bucket.tokens_by_model
        bucket_data["messages_by_model"] = bucket.messages_by_model
        if show_pricing:
            bucket_data["cost_by_model"] = bucket.cost_by_model

    def _add_tool_data(self, bucket_data: dict, bucket: TimeBucketSummary) -> None:
        """Add tool usage data to bucket dictionary."""
        bucket_data["tool_usage"] = bucket.tool_usage
        bucket_data["total_tool_calls"] = bucket.total_tool_calls

    def _generate_csv(self, summary: UsageSummaryData, show_pricing: bool, show_p90: bool) -> str:
        """Generate CSV representation of the summary."""
        output = StringIO()

        # Define CSV headers
        headers = [
            "period_name",
            "start_date",
            "end_date",
            "total_tokens",
            "average_tokens",
            "total_messages",
            "average_messages",
            "active_projects",
            "active_sessions",
            "unified_blocks_count",
        ]

        if show_p90:
            headers.extend(["p90_tokens", "p90_messages"])

        if show_pricing:
            headers.extend(["total_cost", "average_cost"])
            if show_p90:
                headers.append("p90_cost")

        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        # Write bucket data
        for bucket in summary.buckets:
            row = {
                "period_name": bucket.period_name,
                "start_date": bucket.start_date.isoformat(),
                "end_date": bucket.end_date.isoformat(),
                "total_tokens": bucket.total_tokens,
                "average_tokens": bucket.average_tokens,
                "total_messages": bucket.total_messages,
                "average_messages": bucket.average_messages,
                "active_projects": bucket.active_projects,
                "active_sessions": bucket.active_sessions,
                "unified_blocks_count": bucket.unified_blocks_count,
            }

            if show_p90:
                row.update(
                    {
                        "p90_tokens": bucket.p90_tokens,
                        "p90_messages": bucket.p90_messages,
                    }
                )

            if show_pricing:
                row.update(
                    {
                        "total_cost": bucket.total_cost,
                        "average_cost": bucket.average_cost,
                    }
                )
                if show_p90:
                    row["p90_cost"] = bucket.p90_cost

            writer.writerow(row)

        return output.getvalue()
