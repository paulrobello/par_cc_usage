"""Additional commands for par-cc-usage."""

from __future__ import annotations

import asyncio
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

    # Add configuration update command
    app.command(name="update-maximums")(update_maximums_sync)


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
    projects, unified_entries = scan_all_projects(config, use_cache=False)

    if not projects:
        console.print("[yellow]No projects found[/yellow]")
        return

    # Create unified blocks
    from par_cc_usage.token_calculator import create_unified_blocks

    unified_blocks = create_unified_blocks(unified_entries)

    # Show current time
    current_time = datetime.now(UTC)
    console.print(f"[bold]Current Time (UTC):[/bold] {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Create snapshot to use the unified block logic
    snapshot = aggregate_usage(
        projects,
        config.token_limit,
        config.message_limit,
        config.get_effective_timezone(),
        unified_blocks=unified_blocks,
    )

    console.print(f"[bold]Configured Timezone:[/bold] {config.timezone} -> {config.get_effective_timezone()}")
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


def _print_strategy_explanation() -> None:
    """Print explanation for the unified block strategy."""
    console.print("\n  [dim]Strategy explanation:[/dim]")
    console.print("    - Aggregates ALL entries from ALL projects/sessions into unified timeline")
    console.print("    - Creates blocks based on temporal proximity")
    console.print("    - Selects currently active block from unified timeline")
    console.print("    - Provides accurate billing block representation")


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

    # Scan projects and collect unified entries
    projects, unified_entries = scan_all_projects(config, use_cache=False)

    # Create unified blocks
    from par_cc_usage.token_calculator import create_unified_blocks

    unified_blocks = create_unified_blocks(unified_entries)
    console.print(f"[dim]Created {len(unified_blocks)} unified blocks from {len(unified_entries)} entries[/dim]")

    # Create snapshot
    snapshot = aggregate_usage(
        projects,
        config.token_limit,
        config.message_limit,
        config.get_effective_timezone(),
        unified_blocks=unified_blocks,
    )

    # Show step-by-step calculation
    console.print("[bold]Step 1: Current time configuration[/bold]")
    console.print(f"  • Configured timezone: {config.timezone} -> {config.get_effective_timezone()}")
    console.print(f"  • Snapshot timestamp: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print("  • Unified block strategy: unified timeline")

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

    configured_tz = pytz.timezone(config.get_effective_timezone())
    earliest_local = earliest_block.start_time.astimezone(configured_tz)
    console.print(f"    - Start time (local): {earliest_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Show unified blocks info
    if unified_blocks:
        console.print("\n[bold]Step 3.5: Unified blocks (new approach)[/bold]")
        active_unified_blocks = [b for b in unified_blocks if b.is_active]
        console.print(f"  • Total unified blocks: {len(unified_blocks)}")
        console.print(f"  • Active unified blocks: {len(active_unified_blocks)}")

        if active_unified_blocks:
            current_block = active_unified_blocks[0]
            console.print("  • Current unified block:")
            console.print(f"    - Start time: {current_block.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            console.print(f"    - End time: {current_block.end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            console.print(f"    - Projects: {len(current_block.projects)}")
            console.print(f"    - Sessions: {len(current_block.sessions)}")
            console.print(f"    - Total tokens: {current_block.total_tokens:,}")
            console.print(f"    - Messages: {current_block.messages_processed}")

    console.print("\n[bold]Step 4: Unified block result[/bold]")
    unified_start = snapshot.unified_block_start_time
    if unified_start:
        unified_local = unified_start.astimezone(configured_tz)
        console.print(f"  • Unified block start (UTC): {unified_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        console.print(f"  • Unified block start (local): {unified_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        console.print(f"  • Total active tokens: {snapshot.active_tokens:,}")

        _print_strategy_explanation()

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
    projects, unified_entries = scan_all_projects(config, use_cache=False)

    # Get current time and the cutoff time
    import pytz

    tz = pytz.timezone(config.get_effective_timezone())
    current_time = datetime.now(tz)
    cutoff_time = current_time - timedelta(hours=hours)

    console.print(
        f"[bold]Current time ({config.get_effective_timezone()}):[/bold] {current_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')}"
    )
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

    # Create unified blocks
    from par_cc_usage.token_calculator import create_unified_blocks

    unified_blocks = create_unified_blocks(unified_entries)

    # Analysis
    snapshot = aggregate_usage(
        projects,
        config.token_limit,
        config.message_limit,
        config.get_effective_timezone(),
        unified_blocks=unified_blocks,
    )
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
        projects, unified_entries = scan_all_projects(config)

        # Create unified blocks
        from par_cc_usage.token_calculator import create_unified_blocks

        unified_blocks = create_unified_blocks(unified_entries)

        snapshot = aggregate_usage(
            projects,
            config.token_limit,
            config.message_limit,
            config.get_effective_timezone(),
            unified_blocks=unified_blocks,
        )
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


async def update_maximums(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Force update even if config is read-only")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-d", help="Show what would be updated without making changes")
    ] = False,
    use_current_block: Annotated[
        bool,
        typer.Option(
            "--use-current-block", "-u", help="Use only current active block totals instead of historical maximums"
        ),
    ] = False,
) -> None:
    """Update config file maximum values with current usage and set read-only mode.

    This command:
    1. Gets the current usage snapshot from all projects
    2. Updates the config file maximum values with current usage
    3. Sets the config_ro parameter to true to prevent automatic updates

    This is useful to set your configuration baselines based on actual usage.
    """
    from .config import get_config_file_path, load_config, save_config
    from .main import _get_current_usage_snapshot, scan_all_projects
    from .token_calculator import create_unified_blocks

    # Load configuration
    config_file_to_use = config_file if config_file else get_config_file_path()
    config = load_config(config_file_to_use)

    # Check if config is read-only and force is not set
    if config.config_ro and not force:
        console.print("[red]Configuration is in read-only mode![/red]")
        console.print("[yellow]Use --force to override read-only mode[/yellow]")
        return

    # Get current usage snapshot
    console.print("[cyan]Scanning projects to get current usage...[/cyan]")
    snapshot = _get_current_usage_snapshot(config)

    if not snapshot:
        console.print("[yellow]No usage data found![/yellow]")
        return

    # Get current values from snapshot
    current_values = await _get_current_values(snapshot)

    if use_current_block:
        # Use only current block values
        console.print("[cyan]Using current active block totals for maximums...[/cyan]")
        max_values = current_values.copy()
        p90_values = current_values.copy()
        total_blocks = 1  # Current block only
    else:
        # Analyze historical data
        console.print("[cyan]Analyzing all historical data for maximums...[/cyan]")
        _projects, unified_entries = scan_all_projects(config, use_cache=False)
        unified_blocks = create_unified_blocks(unified_entries)

        # Calculate all values
        max_values = await _calculate_max_values(unified_blocks, current_values, config)
        p90_values = await _calculate_p90_values(unified_blocks)
        total_blocks = len(unified_blocks)

    # Display results
    _display_update_summary(config, current_values, max_values, p90_values, total_blocks)

    # Handle dry run
    if dry_run:
        console.print("\n[yellow]Dry run mode - no changes will be made[/yellow]")
        return

    # Get confirmation
    if not force:
        import typer

        if not typer.confirm("\nUpdate configuration with these values?"):
            console.print("[yellow]Update cancelled[/yellow]")
            return

    # Apply updates
    _apply_config_updates(config, max_values, p90_values)
    save_config(config, config_file_to_use)

    console.print("\n[green]✓ Configuration updated successfully![/green]")
    console.print("[green]✓ Read-only mode enabled[/green]")
    console.print(f"[dim]Configuration saved to: {config_file_to_use}[/dim]")


def update_maximums_sync(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Force update even if config is read-only")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-d", help="Show what would be updated without making changes")
    ] = False,
    use_current_block: Annotated[
        bool,
        typer.Option(
            "--use-current-block", "-u", help="Use only current active block totals instead of historical maximums"
        ),
    ] = False,
) -> None:
    """Update config file maximum values with current usage and set read-only mode.

    This command:
    1. Gets the current usage snapshot from all projects
    2. Updates the config file maximum values with current usage
    3. Sets the config_ro parameter to true to prevent automatic updates

    This is useful to set your configuration baselines based on actual usage.
    """
    asyncio.run(update_maximums(config_file, force, dry_run, use_current_block))


async def _get_current_values(snapshot: UsageSnapshot) -> dict[str, float]:
    """Get current values from snapshot."""
    return {
        "tokens": snapshot.unified_block_tokens(),
        "messages": snapshot.unified_block_messages(),
        "cost": await snapshot.get_unified_block_total_cost(),
    }


async def _calculate_block_cost(block) -> float:
    """Calculate total cost for a block asynchronously."""
    from .pricing import calculate_token_cost

    block_cost = 0.0
    for entry in block.entries:
        usage = entry.token_usage
        cost_result = await calculate_token_cost(
            entry.full_model_name,
            usage.actual_input_tokens,
            usage.actual_output_tokens,
            usage.actual_cache_creation_input_tokens,
            usage.actual_cache_read_input_tokens,
        )
        block_cost += cost_result.total_cost
    return block_cost


async def _calculate_max_values(
    unified_blocks: list, current_values: dict[str, float], config: Config
) -> dict[str, float]:
    """Calculate maximum values from historical data."""
    # Find historical maximums from all unified blocks
    max_tokens_found = max((block.total_tokens for block in unified_blocks), default=0)
    max_messages_found = max((block.messages_processed for block in unified_blocks), default=0)

    # Calculate max cost from all blocks
    max_cost = 0.0
    for block in unified_blocks:
        try:
            block_cost = await _calculate_block_cost(block)
            max_cost = max(max_cost, block_cost)
        except Exception:
            # Skip blocks where cost calculation fails
            continue

    # Determine new maximum values (use historical max or current, whichever is higher)
    return {
        "tokens": max(max_tokens_found, current_values["tokens"], config.max_unified_block_tokens_encountered),
        "messages": max(max_messages_found, current_values["messages"], config.max_unified_block_messages_encountered),
        "cost": max(max_cost, current_values["cost"], config.max_unified_block_cost_encountered),
    }


def _calculate_percentile(values: list[int], percentile: float) -> int:
    """Calculate percentile of a list of values without numpy dependency."""
    if not values:
        return 0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 0:
        return 0
    if n == 1:
        return sorted_values[0]

    # Calculate percentile index
    index = (percentile / 100.0) * (n - 1)

    # If index is whole number, return that element
    if index == int(index):
        return sorted_values[int(index)]

    # Otherwise, interpolate between the two nearest values
    lower_index = int(index)
    upper_index = min(lower_index + 1, n - 1)
    weight = index - lower_index

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]

    return int(lower_value + weight * (upper_value - lower_value))


async def _calculate_p90_values(unified_blocks: list) -> dict[str, float]:
    """Calculate P90 values from unified blocks."""
    if len(unified_blocks) == 0:
        return {"tokens": 0, "messages": 0, "cost": 0.0}

    token_values = [block.total_tokens for block in unified_blocks if block.total_tokens > 0]
    message_values = [block.messages_processed for block in unified_blocks if block.messages_processed > 0]

    new_p90_tokens = _calculate_percentile(token_values, 90)
    new_p90_messages = _calculate_percentile(message_values, 90)

    # Calculate P90 cost
    cost_values = []
    for block in unified_blocks:
        try:
            block_cost = await _calculate_block_cost(block)
            if block_cost > 0:
                cost_values.append(block_cost)
        except Exception:
            continue

    # Calculate P90 cost using percentile logic for floats
    if cost_values:
        sorted_costs = sorted(cost_values)
        n = len(sorted_costs)
        if n == 1:
            new_p90_cost = sorted_costs[0]
        else:
            # Calculate 90th percentile for floats
            index = 0.9 * (n - 1)
            if index == int(index):
                new_p90_cost = sorted_costs[int(index)]
            else:
                lower_index = int(index)
                upper_index = min(lower_index + 1, n - 1)
                weight = index - lower_index
                lower_value = sorted_costs[lower_index]
                upper_value = sorted_costs[upper_index]
                new_p90_cost = lower_value + weight * (upper_value - lower_value)
    else:
        new_p90_cost = 0.0

    return {"tokens": new_p90_tokens, "messages": new_p90_messages, "cost": new_p90_cost}


def _format_change(old_val: float, new_val: float) -> str:
    """Format numeric change display."""
    if new_val > old_val:
        return f"+{new_val - old_val:,}"
    elif new_val < old_val:
        return f"-{old_val - new_val:,}"
    else:
        return "No change"


def _format_cost_change(old_val: float, new_val: float) -> str:
    """Format cost change display."""
    if new_val > old_val:
        return f"+${new_val - old_val:.2f}"
    elif new_val < old_val:
        return f"-${old_val - new_val:.2f}"
    else:
        return "No change"


def _display_update_summary(
    config: Config,
    current_values: dict[str, float],
    max_values: dict[str, float],
    p90_values: dict[str, float],
    total_blocks: int,
) -> None:
    """Display the configuration update summary table."""
    from rich.table import Table

    table = Table(title="Configuration Update Summary", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Current Value", style="yellow", justify="right")
    table.add_column("New Value", style="green", justify="right")
    table.add_column("Change", style="blue")

    # Add rows to table
    table.add_row(
        "Max Tokens (Unified Block)",
        f"{config.max_unified_block_tokens_encountered:,}",
        f"{max_values['tokens']:,.0f}",
        _format_change(config.max_unified_block_tokens_encountered, max_values["tokens"]),
    )
    table.add_row(
        "Max Messages (Unified Block)",
        f"{config.max_unified_block_messages_encountered:,}",
        f"{max_values['messages']:,.0f}",
        _format_change(config.max_unified_block_messages_encountered, max_values["messages"]),
    )
    table.add_row(
        "Max Cost (Unified Block)",
        f"${config.max_unified_block_cost_encountered:.2f}",
        f"${max_values['cost']:.2f}",
        _format_cost_change(config.max_unified_block_cost_encountered, max_values["cost"]),
    )
    table.add_row(
        "P90 Tokens (Unified Block)",
        f"{config.p90_unified_block_tokens_encountered:,}",
        f"{p90_values['tokens']:,.0f}",
        _format_change(config.p90_unified_block_tokens_encountered, p90_values["tokens"]),
    )
    table.add_row(
        "P90 Messages (Unified Block)",
        f"{config.p90_unified_block_messages_encountered:,}",
        f"{p90_values['messages']:,.0f}",
        _format_change(config.p90_unified_block_messages_encountered, p90_values["messages"]),
    )
    table.add_row(
        "P90 Cost (Unified Block)",
        f"${config.p90_unified_block_cost_encountered:.2f}",
        f"${p90_values['cost']:.2f}",
        _format_cost_change(config.p90_unified_block_cost_encountered, p90_values["cost"]),
    )
    table.add_row(
        "Read-Only Mode",
        str(config.config_ro),
        "True",
        "Will be enabled" if not config.config_ro else "Already enabled",
    )

    console.print(table)

    # Additional current usage info
    console.print("\n[bold]Current Usage Snapshot:[/bold]")
    console.print(f"  Current Unified Block Tokens: {current_values['tokens']:,.0f}")
    console.print(f"  Current Unified Block Messages: {current_values['messages']:,.0f}")
    console.print(f"  Current Unified Block Cost: ${current_values['cost']:.2f}")
    console.print(f"  Total Historical Unified Blocks: {total_blocks:,}")


def _apply_config_updates(config: Config, max_values: dict[str, float], p90_values: dict[str, float]) -> None:
    """Apply the calculated values to configuration."""
    config.max_unified_block_tokens_encountered = int(max_values["tokens"])
    config.max_unified_block_messages_encountered = int(max_values["messages"])
    config.max_unified_block_cost_encountered = max_values["cost"]
    config.p90_unified_block_tokens_encountered = int(p90_values["tokens"])
    config.p90_unified_block_messages_encountered = int(p90_values["messages"])
    config.p90_unified_block_cost_encountered = p90_values["cost"]
    config.config_ro = True
