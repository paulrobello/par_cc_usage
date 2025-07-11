"""Additional commands for par-cc-usage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .config import Config, load_config
from .json_analyzer import app as analyzer_app
from .main import app, scan_all_projects
from .models import Project, TokenBlock, UsageSnapshot
from .token_calculator import aggregate_usage

console = Console()


def register_commands() -> None:
    """Register additional commands to the main app."""
    # Add the analyzer command
    if analyzer_app.registered_commands and analyzer_app.registered_commands[0].callback:
        app.command(name="analyze")(analyzer_app.registered_commands[0].callback)

    # Add debug commands
    app.command(name="debug-blocks")(debug_blocks)
    app.command(name="debug-unified")(debug_unified_block)
    app.command(name="debug-activity")(debug_recent_activity)
    app.command(name="debug-session-table")(debug_session_table)


@app.command("debug-blocks")
def debug_blocks(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    show_inactive: Annotated[bool, typer.Option("--show-inactive", help="Show inactive blocks too")] = False,
) -> None:
    """Debug command to show detailed block information."""
    console.print("\n[bold cyan]Debug: Block Analysis[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    # Load configuration
    config = load_config(config_file)
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print("[red]No Claude directories found![/red]")
        return

    # Scan all projects
    console.print(f"[yellow]Scanning projects in {', '.join(str(p) for p in claude_paths)}...[/yellow]")
    projects = scan_all_projects(config, use_cache=False)

    if not projects:
        console.print("[yellow]No projects found[/yellow]")
        return

    # Show current time
    current_time = datetime.now(UTC)
    console.print(f"[bold]Current Time (UTC):[/bold] {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Create snapshot to use the unified block logic
    snapshot = aggregate_usage(projects, config.token_limit, config.timezone)

    console.print(f"[bold]Configured Timezone:[/bold] {config.timezone}")
    console.print(f"[bold]Snapshot Timestamp:[/bold] {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Show unified block info
    unified_start = snapshot.unified_block_start_time
    if unified_start:
        console.print(
            f"[bold green]Unified Block Start Time:[/bold green] {unified_start.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        console.print(f"[bold green]Active Tokens:[/bold green] {snapshot.active_tokens:,}")
    else:
        console.print("[yellow]No unified block start time (no active blocks)[/yellow]")

    console.print()

    # Create table for blocks
    table = Table(
        title="All Session Blocks (Active First)" if not show_inactive else "All Session Blocks",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("Project", style="cyan")
    table.add_column("Session ID", style="dim", max_width=20)
    table.add_column("Block Start", style="yellow")
    table.add_column("Block End", style="yellow")
    table.add_column("Last Activity", style="blue")
    table.add_column("Active", style="green")
    table.add_column("Tokens", style="white", justify="right")
    table.add_column("Model", style="magenta")

    # Collect all blocks
    all_blocks = []
    for project_name, project in projects.items():
        for session in project.sessions.values():
            for block in session.blocks:
                all_blocks.append((project_name, session.session_id, block))

    # Sort by active status first, then by start time
    all_blocks.sort(key=lambda x: (not x[2].is_active, x[2].start_time), reverse=False)

    # Add rows
    active_blocks_count = 0
    for project_name, session_id, block in all_blocks:
        if block.is_active:
            active_blocks_count += 1

        if not show_inactive and not block.is_active:
            continue

        # Format times
        block_start_str = block.start_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        block_end_str = block.end_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        last_activity_str = block.actual_end_time.strftime("%Y-%m-%d %H:%M:%S %Z") if block.actual_end_time else "None"

        # Status styling
        active_style = "bold green" if block.is_active else "dim"
        active_text = "YES" if block.is_active else "no"

        table.add_row(
            project_name,
            session_id[:8] + "...",
            block_start_str,
            block_end_str,
            last_activity_str,
            Text(active_text, style=active_style),
            f"{block.adjusted_tokens:,}",
            block.model,
        )

    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {active_blocks_count} active blocks out of {len(all_blocks)} total blocks")


def _print_active_block_info(project_name: str, session_id: str, block: TokenBlock) -> None:
    """Print information about an active block."""
    console.print("  • Active block found:")
    console.print(f"    - Project: {project_name}")
    console.print(f"    - Session: {session_id[:8]}...")
    console.print(f"    - Block start: {block.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print(f"    - Block end: {block.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print(
        f"    - Last activity: {block.actual_end_time.strftime('%Y-%m-%d %H:%M:%S %Z') if block.actual_end_time else 'None'}"
    )
    console.print(f"    - Tokens: {block.adjusted_tokens:,}")


def _print_strategy_explanation(strategy: str) -> None:
    """Print explanation for the smart unified block strategy."""
    console.print(f"\n  [dim]Strategy '{strategy}' explanation:[/dim]")
    console.print("    - Filters for blocks with recent activity (within 5 hours)")
    console.print("    - Among recent blocks, selects the one with most tokens (main work session)")
    console.print("    - Falls back to earliest active block if no recent activity")


def _validate_expected_time(
    actual_time: datetime,
    expected_hour: int | None,
    context: str,
) -> None:
    """Validate if actual time matches expected hour and print result.

    Args:
        actual_time: The actual datetime to validate
        expected_hour: Expected hour (0-23) or None to skip validation
        context: Description of what is being validated for error messages
    """
    if expected_hour is not None:
        if actual_time.hour == expected_hour and actual_time.minute == 0:
            # Show both 24h and 12h formats for clarity
            expected_display = datetime.now().replace(hour=expected_hour, minute=0).strftime("%I:%M %p")
            console.print(
                f"  [bold green]✓ {context} at {expected_hour:02d}:00 ({expected_display}) as expected[/bold green]"
            )
        else:
            expected_display = datetime.now().replace(hour=expected_hour, minute=0).strftime("%I:%M %p")
            console.print(
                f"  [bold red]✗ {context} does NOT start at {expected_hour:02d}:00 ({expected_display})![/bold red]"
            )
            console.print(
                f"  [bold red]  Expected: {expected_hour:02d}:00 ({expected_display}), Got: {actual_time.strftime('%H:%M')} ({actual_time.strftime('%I:%M %p')})[/bold red]"
            )
    else:
        console.print("  [dim]  No expected hour specified for validation[/dim]")


def _collect_active_blocks(projects: dict[str, Project]) -> list[tuple[str, str, TokenBlock]]:
    """Collect all active blocks from projects."""
    active_blocks = []
    for project_name, project in projects.items():
        for session in project.sessions.values():
            for block in session.blocks:
                if block.is_active:
                    active_blocks.append((project_name, session.session_id, block))
                    _print_active_block_info(project_name, session.session_id, block)
    return active_blocks


@app.command("debug-unified")
def debug_unified_block(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    expected_hour: Annotated[
        int | None, typer.Option("--expected-hour", "-e", help="Expected hour for validation (0-23, 24-hour format)")
    ] = None,
) -> None:
    """Debug command to trace unified block calculation step by step.

    Shows how the unified billing block start time is determined from active sessions.
    The unified block uses the most recently active session for timing.
    Optionally validates against expected hour (minute is always 0 for block starts).
    """
    console.print("\n[bold cyan]Debug: Unified Block Calculation[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    # Load configuration
    config = load_config(config_file)
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print("[red]No Claude directories found![/red]")
        return

    # Scan all projects
    console.print("[yellow]Scanning projects...[/yellow]")
    projects = scan_all_projects(config, use_cache=False)

    # Create snapshot
    snapshot = aggregate_usage(projects, config.token_limit, config.timezone)

    # Show step-by-step calculation
    console.print("[bold]Step 1: Current time configuration[/bold]")
    console.print(f"  • Configured timezone: {config.timezone}")
    console.print(f"  • Snapshot timestamp: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print("  • Unified block strategy: smart")

    console.print("\n[bold]Step 2: Find all active blocks[/bold]")
    active_blocks = _collect_active_blocks(projects)

    if not active_blocks:
        console.print("  [yellow]No active blocks found[/yellow]")
        return

    console.print("\n[bold]Step 3: Find earliest active block (for comparison)[/bold]")

    # Sort by start time to find earliest
    active_blocks.sort(key=lambda x: x[2].start_time)
    earliest_project, earliest_session, earliest_block = active_blocks[0]

    console.print("  • Earliest active block (old logic would use this):")
    console.print(f"    - Project: {earliest_project}")
    console.print(f"    - Session: {earliest_session[:8]}...")
    console.print(f"    - Start time: {earliest_block.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Convert to configured timezone for display
    import pytz

    configured_tz = pytz.timezone(config.timezone)
    earliest_local = earliest_block.start_time.astimezone(configured_tz)
    console.print(f"    - Start time (local): {earliest_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    console.print("\n[bold]Step 4: Unified block result[/bold]")
    unified_start = snapshot.unified_block_start_time
    if unified_start:
        unified_local = unified_start.astimezone(configured_tz)
        console.print(f"  • Unified block start (UTC): {unified_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        console.print(f"  • Unified block start (local): {unified_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        console.print(f"  • Total active tokens: {snapshot.active_tokens:,}")

        _print_strategy_explanation("smart")

        # Validate against expected time (if provided)
        _validate_expected_time(unified_local, expected_hour, "Unified block starts")
    else:
        console.print("  [red]No unified block start time calculated[/red]")
        if expected_hour is not None:
            console.print(
                f"  [bold red]✗ Expected block at {expected_hour:02d}:00 but no unified block found![/bold red]"
            )


@app.command("debug-activity")
def debug_recent_activity(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    hours: Annotated[int, typer.Option("--hours", "-h", help="Show activity within last N hours")] = 6,
    expected_hour: Annotated[
        int | None, typer.Option("--expected-hour", "-e", help="Expected hour for validation (0-23, 24-hour format)")
    ] = None,
) -> None:
    """Debug command to show recent activity and session timing.

    Analyzes recent session activity to understand unified block timing.
    Shows which session would be used for unified billing block calculation.
    Optionally validates against expected hour (minute is always 0 for block starts).
    """
    console.print("\n[bold cyan]Debug: Recent Activity Analysis[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    # Load configuration
    config = load_config(config_file)
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print("[red]No Claude directories found![/red]")
        return

    # Scan all projects
    console.print("[yellow]Scanning projects...[/yellow]")
    projects = scan_all_projects(config, use_cache=False)

    # Get current time and the cutoff time
    import pytz

    tz = pytz.timezone(config.timezone)
    current_time = datetime.now(tz)
    cutoff_time = current_time - timedelta(hours=hours)

    console.print(f"[bold]Current time ({config.timezone}):[/bold] {current_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    console.print(f"[bold]Showing activity since:[/bold] {cutoff_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")

    # Collect recent sessions and blocks
    recent_sessions = _collect_recent_sessions(projects, cutoff_time, tz)

    # Sort by last activity time (most recent first)
    recent_sessions.sort(key=lambda x: x[3], reverse=True)

    console.print(f"\n[bold]Recent Sessions (last {hours} hours):[/bold]")

    if not recent_sessions:
        console.print("  [yellow]No recent activity found[/yellow]")
        return

    # Create table
    table = _create_activity_table(hours)

    # Show the most recently active session first
    most_recent_active = None

    for project_name, session_id, block, last_activity_local, is_active in recent_sessions:
        if is_active and most_recent_active is None:
            most_recent_active = (project_name, session_id, block, last_activity_local)

        # Calculate time since last activity
        age = current_time - last_activity_local
        age_str = f"{int(age.total_seconds() // 3600)}h {int((age.total_seconds() % 3600) // 60)}m ago"

        # Format times in configured timezone
        block_start_str = block.start_time.astimezone(tz).strftime("%I:%M %p")
        last_activity_str = last_activity_local.strftime("%I:%M %p")

        # Status styling
        active_style = "bold green" if is_active else "dim"
        active_text = "YES" if is_active else "no"

        table.add_row(
            project_name,
            session_id[:8] + "...",
            block_start_str,
            last_activity_str,
            Text(active_text, style=active_style),
            f"{block.adjusted_tokens:,}",
            age_str,
        )

    console.print(table)

    # Analysis
    snapshot = aggregate_usage(projects, config.token_limit, config.timezone)
    _print_recent_activity_analysis(most_recent_active, snapshot, config, tz, expected_hour)


def _collect_recent_sessions(
    projects: dict[str, Project], cutoff_time: datetime, tz: Any
) -> list[tuple[str, str, TokenBlock, datetime, bool]]:
    """Collect sessions with activity after cutoff time."""
    recent_sessions = []
    for project_name, project in projects.items():
        for session in project.sessions.values():
            for block in session.blocks:
                last_activity = block.actual_end_time or block.start_time
                # Convert to configured timezone for comparison
                if last_activity.tzinfo != tz:
                    last_activity_local = last_activity.astimezone(tz)
                else:
                    last_activity_local = last_activity

                if last_activity_local >= cutoff_time:
                    recent_sessions.append(
                        (project_name, session.session_id, block, last_activity_local, block.is_active)
                    )
    return recent_sessions


def _create_activity_table(hours: int) -> Table:
    """Create table for displaying recent activity."""
    table = Table(
        title=f"Sessions Active in Last {hours} Hours",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Project", style="cyan")
    table.add_column("Session", style="dim", max_width=12)
    table.add_column("Block Start", style="yellow")
    table.add_column("Last Activity", style="blue")
    table.add_column("Active", style="green")
    table.add_column("Tokens", style="white", justify="right")
    table.add_column("Age", style="dim")
    return table


def _print_recent_activity_analysis(
    most_recent_active: tuple[str, str, TokenBlock, datetime] | None,
    snapshot: UsageSnapshot,
    config: Config,
    tz: Any,
    expected_hour: int | None = None,
) -> None:
    """Print analysis of recent activity."""
    console.print("\n[bold]Analysis:[/bold]")

    if most_recent_active:
        proj, sess_id, block, last_act = most_recent_active
        block_start_local = block.start_time.astimezone(tz)
        console.print("  • Most recently active session:")
        console.print(f"    - Project: {proj}")
        console.print(f"    - Session: {sess_id[:8]}...")
        console.print(f"    - Block started at: {block_start_local.strftime('%I:%M %p %Z')}")
        console.print(f"    - Last activity: {last_act.strftime('%I:%M %p %Z')}")

        # Validate against expected time (if provided)
        if expected_hour is not None:
            if block_start_local.hour == expected_hour and block_start_local.minute == 0:
                console.print(
                    f"  [bold green]✓ Most recent active session started at {expected_hour:02d}:00 as expected[/bold green]"
                )
            else:
                console.print(
                    f"  [bold yellow]⚠ Most recent active session did NOT start at {expected_hour:02d}:00[/bold yellow]"
                )
                console.print(f"    Expected: {expected_hour:02d}:00, Got: {block_start_local.strftime('%H:%M')}")

    # Show what the unified block logic would return
    unified_start = snapshot.unified_block_start_time
    if unified_start:
        unified_local = unified_start.astimezone(tz)
        console.print("\n  • Current unified block logic returns:")
        console.print(f"    - Start time: {unified_local.strftime('%I:%M %p %Z')}")

        # Validate against expected time (if provided)
        _validate_expected_time(unified_local, expected_hour, "Unified block starts")

    # Recommendations
    console.print("\n[bold]Potential Solutions:[/bold]")
    console.print("  1. Use most recently active session for unified block calculation")
    console.print("  2. Exclude sessions inactive for more than X hours from unified calculation")
    console.print("  3. Use a rolling window approach for unified block determination")


def _debug_block_overlap(block, unified_start, unified_end, now):
    """Check if block overlaps with unified block window."""
    last_activity = block.actual_end_time or block.start_time
    time_since_activity = (now - last_activity).total_seconds() / 3600

    console.print(f"      - is_gap: {block.is_gap}")
    console.print(f"      - last_activity: {last_activity}")
    console.print(f"      - time_since_activity: {time_since_activity:.2f}h")
    console.print(f"      - is_active: {block.is_active}")

    if not block.is_active:
        console.print("      [red]✗ Block is not active[/red]")
        return False, False

    # Check overlap with unified block
    block_end = block.actual_end_time or block.end_time
    overlap_check = block.start_time < unified_end and block_end > unified_start

    console.print(f"      - block_end: {block_end}")
    console.print(f"      - starts_before_unified_ends: {block.start_time < unified_end}")
    console.print(f"      - ends_after_unified_starts: {block_end > unified_start}")
    console.print(f"      - overlap_check: {overlap_check}")

    if overlap_check:
        console.print(f"      - tokens: {block.adjusted_tokens}")
        has_tokens = block.adjusted_tokens > 0
        if has_tokens:
            console.print("      [green]✓ Block would be included in session table[/green]")
        else:
            console.print("      [yellow]⚠ Block has 0 tokens[/yellow]")
        return True, has_tokens
    else:
        console.print("      [red]✗ Block does not overlap with unified window[/red]")
        return False, False


def _analyze_blocks(snapshot, unified_start, unified_end, now):
    """Analyze all blocks and return summary statistics."""
    total_sessions = 0
    total_blocks = 0
    active_blocks = 0
    blocks_with_overlap = 0
    blocks_passing_filter = 0

    for project_name, project in snapshot.projects.items():
        console.print(f"\n[cyan]Project: {project_name}[/cyan]")

        for session_id, session in project.sessions.items():
            total_sessions += 1
            console.print(f"  [yellow]Session: {session_id}[/yellow]")

            for block in session.blocks:
                total_blocks += 1
                console.print(f"    [white]Block: {block.start_time} to {block.end_time}[/white]")

                if block.is_active:
                    active_blocks += 1

                has_overlap, has_tokens = _debug_block_overlap(block, unified_start, unified_end, now)
                if has_overlap:
                    blocks_with_overlap += 1
                    if has_tokens:
                        blocks_passing_filter += 1

    return total_sessions, total_blocks, active_blocks, blocks_with_overlap, blocks_passing_filter


def _print_summary(total_sessions, total_blocks, active_blocks, blocks_with_overlap, blocks_passing_filter):
    """Print summary of block analysis."""
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total sessions: {total_sessions}")
    console.print(f"  Total blocks: {total_blocks}")
    console.print(f"  Active blocks: {active_blocks}")
    console.print(f"  Blocks with overlap: {blocks_with_overlap}")
    console.print(f"  Blocks passing filter: {blocks_passing_filter}")

    if blocks_passing_filter == 0:
        console.print("\n[red]No blocks are passing the filter - this explains why the session table is empty![/red]")
        if active_blocks == 0:
            console.print("  [red]Issue: No blocks are active[/red]")
        elif blocks_with_overlap == 0:
            console.print("  [red]Issue: No active blocks overlap with unified block window[/red]")
        else:
            console.print("  [red]Issue: Active blocks with overlap have 0 tokens[/red]")
    else:
        console.print(f"\n[green]Found {blocks_passing_filter} blocks that should appear in session table[/green]")


@app.command("debug-session-table")
def debug_session_table(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
) -> None:
    """Debug command to analyze why the session table might be empty."""
    console.print("\n[bold cyan]Debug: Session Table Analysis[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    # Load configuration
    config = load_config(config_file)
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print("[red]No Claude directories found![/red]")
        return

    # Get usage data
    try:
        projects = scan_all_projects(config)
        snapshot = aggregate_usage(projects, config.token_limit, config.timezone)
    except Exception as e:
        console.print(f"[red]Error scanning projects: {e}[/red]")
        return

    console.print(f"[bold]Found {len(snapshot.projects)} projects[/bold]")

    # Debug unified block logic
    unified_start = snapshot.unified_block_start_time
    console.print(f"[bold]Unified block start time: {unified_start}[/bold]")

    if not unified_start:
        console.print("[red]No unified block start time found![/red]")
        return

    unified_end = unified_start + timedelta(hours=5)
    console.print(f"[bold]Unified block end time: {unified_end}[/bold]")

    from datetime import datetime

    now = datetime.now(unified_start.tzinfo)
    console.print(f"[bold]Current time: {now}[/bold]")

    stats = _analyze_blocks(snapshot, unified_start, unified_end, now)
    _print_summary(*stats)
