"""Main entry point for par-cc-usage command."""

from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import typer
from rich.console import Console

from .config import (
    Config,
    get_default_token_limit,
    load_config,
    save_config,
    save_default_config,
    update_config_token_limit,
)
from .display import DisplayManager, create_error_display, create_info_display
from .enums import DisplayMode, OutputFormat, SortBy, ThemeType
from .file_monitor import FileMonitor, FileState, JSONLReader, parse_session_from_path
from .list_command import display_usage_list
from .models import DeduplicationState, Project, UsageSnapshot
from .notification_manager import NotificationManager
from .options import MonitorOptions, TestWebhookOptions
from .theme import apply_temporary_theme, get_color, get_theme_manager
from .token_calculator import aggregate_usage, detect_token_limit_from_data, process_jsonl_line
from .xdg_dirs import get_config_file_path

app = typer.Typer(
    name="par-cc-usage",
    help="Monitor and analyze Claude Code token usage",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

console = Console()
logger = logging.getLogger(__name__)


def process_file(
    file_path: Path,
    file_state: FileState,
    projects: dict[str, Project],
    config: Config,
    base_dir: Path,
    dedup_state: DeduplicationState | None = None,
) -> int:
    """Process a single JSONL file.

    Args:
        file_path: Path to JSONL file
        file_state: File state with last position
        projects: Dictionary of projects to update
        config: Configuration
        base_dir: Base directory for session parsing
        dedup_state: Deduplication state (optional)

    Returns:
        Number of messages processed
    """
    # Parse session ID and project path from file path
    session_id, project_path = parse_session_from_path(file_path, base_dir, config.display.project_name_prefixes)
    messages_processed = 0

    try:
        with JSONLReader(file_path) as reader:
            for data, position in reader.read_lines(from_position=file_state.last_position):
                process_jsonl_line(data, project_path, session_id, projects, dedup_state, config.timezone)
                messages_processed += 1
                file_state.last_position = position
    except Exception as e:
        console.print(f"[red]Error processing {file_path}: {e}[/red]")

    return messages_processed


def scan_all_projects(config: Config, use_cache: bool = True) -> dict[str, Project]:
    """Scan all projects and build usage data.

    Args:
        config: Configuration
        use_cache: Whether to use cached file positions (False for list command)

    Returns:
        Dictionary of projects
    """
    projects: dict[str, Project] = {}
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print("[yellow]No Claude directories found![/yellow]")
        return projects

    monitor = FileMonitor(claude_paths, config.cache_dir, config.disable_cache)
    dedup_state = DeduplicationState()

    # Process all files
    for file_path in monitor.scan_files():
        # Find which base directory this file belongs to
        base_dir = None
        for claude_path in claude_paths:
            try:
                file_path.relative_to(claude_path)
                base_dir = claude_path
                break
            except ValueError:
                continue

        if not base_dir:
            continue

        if file_path not in monitor.file_states:
            # New file, create state
            try:
                stat = file_path.stat()
                file_state = FileState(
                    path=file_path,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )
                monitor.file_states[file_path] = file_state
            except OSError:
                continue
        else:
            file_state = monitor.file_states[file_path]
            # For list command, always read from beginning
            if not use_cache:
                file_state.last_position = 0

        process_file(file_path, file_state, projects, config, base_dir, dedup_state)

    # Log deduplication stats if any duplicates found
    if dedup_state.duplicate_count > 0:
        console.print(
            f"[dim]Processed {dedup_state.total_messages} messages, "
            f"skipped {dedup_state.duplicate_count} duplicates[/dim]"
        )

    return projects


def _initialize_config(config_file: Path | None) -> tuple[Config, Path | None]:
    """Initialize configuration and show loading information."""
    console.print("\n[bold cyan]Starting PAR Claude Code Usage Monitor[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")

    # Show which config file is being used
    config_file_to_load = config_file if config_file else get_config_file_path()
    if config_file_to_load.exists():
        console.print(f"[yellow]Loading config from:[/yellow] {config_file_to_load.absolute()}")
    else:
        console.print(f"[yellow]Config file not found:[/yellow] {config_file_to_load.absolute()}")
        console.print("[yellow]Using default configuration values[/yellow]")

    # Load configuration
    config = load_config(config_file)
    actual_config_file = config_file_to_load if config_file_to_load.exists() else None

    return config, actual_config_file


def _print_config_info(config: Config, theme_override: ThemeType | None = None) -> None:
    """Print loaded configuration values and time information."""
    # Show loaded configuration values
    console.print("\n[bold green]Configuration Values:[/bold green]")
    console.print(f"  • Projects directory: {config.projects_dir}")
    console.print(f"  • Cache directory: {config.cache_dir}")
    console.print(f"  • Cache disabled: {config.disable_cache}")
    console.print(f"  • Timezone: [bold]{config.timezone}[/bold]")
    console.print(f"  • Polling interval: {config.polling_interval}s")
    console.print(f"  • Token limit: {config.token_limit:,}" if config.token_limit else "  • Token limit: Auto-detect")
    console.print(f"  • Update in place: {config.display.update_in_place}")
    console.print(f"  • Show progress bars: {config.display.show_progress_bars}")
    console.print(f"  • Show active sessions: {config.display.show_active_sessions}")
    console.print(f"  • Refresh interval: {config.display.refresh_interval}s")

    # Show theme - display override if present, otherwise config value
    if theme_override is not None:
        console.print(f"  • Theme: {theme_override.value} [dim](override)[/dim]")
    else:
        console.print(f"  • Theme: {config.display.theme.value}")

    # Show time information
    from datetime import datetime

    import pytz

    system_time = datetime.now()
    configured_tz = pytz.timezone(config.timezone)
    configured_time = datetime.now(configured_tz)
    console.print("\n[bold yellow]Time Information:[/bold yellow]")
    console.print(f"  • System time: {system_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    console.print(f"  • Configured timezone time: {configured_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")


def _apply_command_overrides(config: Config, options: MonitorOptions) -> None:
    """Apply command line option overrides to configuration.

    Args:
        config: Configuration to modify
        options: Monitor options with overrides
    """
    if options.interval != config.polling_interval:
        config.polling_interval = options.interval
        console.print(f"\n[yellow]Overriding polling interval from command line:[/yellow] {options.interval}s")
    if options.token_limit:
        config.token_limit = options.token_limit
        console.print(f"[yellow]Overriding token limit from command line:[/yellow] {options.token_limit:,}")
    if options.show_sessions:
        config.display.show_active_sessions = options.show_sessions
    if options.show_tools:
        config.display.show_tool_usage = options.show_tools
    if options.show_pricing:
        config.display.show_pricing = options.show_pricing
    if options.no_cache:
        config.disable_cache = options.no_cache
        console.print("[yellow]Disabling cache from command line[/yellow]")
    if options.display_mode:
        config.display.display_mode = options.display_mode
        console.print(f"[yellow]Overriding display mode from command line:[/yellow] {options.display_mode.value}")


def _check_token_limit_update(config: Config, actual_config_file: Path | None, current_usage: int) -> None:
    """Check if token limit needs update and update config if necessary."""
    if config.token_limit and current_usage > config.token_limit:
        # Update token limit to current usage
        old_limit = config.token_limit
        config.token_limit = current_usage

        # Save updated config if we have a config file
        if actual_config_file:
            update_config_token_limit(actual_config_file, current_usage)
            console.print(
                f"\n[bold yellow]Token limit exceeded![/bold yellow] "
                f"Updated from {old_limit:,} to {current_usage:,} tokens"
            )


def _initialize_monitor_components(
    config: Config,
) -> tuple[list[Path], FileMonitor, DeduplicationState, NotificationManager]:
    """Initialize monitoring components and validate Claude paths."""
    claude_paths = config.get_claude_paths()

    if not claude_paths:
        console.print(create_error_display("No Claude directories found!"))
        console.print(create_info_display("Make sure Claude Code is installed and has been used at least once."))
        console.print(
            create_info_display(
                f"Checked paths: {', '.join(str(p) for p in [Path.home() / '.config' / 'claude' / 'projects', Path.home() / '.claude' / 'projects'])}"
            )
        )
        sys.exit(1)

    # Show Claude directories being monitored
    console.print("[bold blue]Claude Directories:[/bold blue]")
    for path in claude_paths:
        console.print(f"  • {path}")
    console.print()

    monitor = FileMonitor(claude_paths, config.cache_dir, config.disable_cache)
    dedup_state = DeduplicationState()
    notification_manager = NotificationManager(config)

    return claude_paths, monitor, dedup_state, notification_manager


def _auto_detect_token_limit(config: Config, projects: dict[str, Project], actual_config_file: Path | None) -> None:
    """Auto-detect and set token limit if not configured."""
    if config.token_limit is None:
        detected_limit = detect_token_limit_from_data(projects)
        if detected_limit:
            config.token_limit = detected_limit
            console.print(f"[yellow]Auto-detected token limit: {config.token_limit:,}[/yellow]")

            # Update config file if it exists
            if actual_config_file:
                update_config_token_limit(actual_config_file, config.token_limit)
                console.print("[green]Updated config file with token limit[/green]")
        else:
            config.token_limit = get_default_token_limit()


def _parse_monitor_options(
    interval: int,
    token_limit: int | None,
    config_file: Path | None,
    show_sessions: bool,
    show_tools: bool,
    show_pricing: bool,
    no_cache: bool,
    block_start_override: int | None,
    snapshot: bool,
    compact: bool,
    config: Config,
) -> MonitorOptions:
    """Parse and create monitor options from command arguments.

    Args:
        interval: Polling interval
        token_limit: Token limit override
        config_file: Config file path
        show_sessions: Show sessions flag
        show_tools: Show tools flag
        show_pricing: Show pricing flag
        no_cache: No cache flag
        block_start_override: Block start override hour
        snapshot: Take single snapshot flag
        compact: Use compact display mode
        config: Configuration object

    Returns:
        MonitorOptions object with parsed block start time
    """
    block_start_override_utc = _parse_block_start_time(block_start_override, config)

    return MonitorOptions(
        interval=interval,
        token_limit=token_limit,
        config_file=config_file,
        show_sessions=show_sessions,
        show_tools=show_tools,
        show_pricing=show_pricing,
        no_cache=no_cache,
        block_start_override=block_start_override,
        block_start_override_utc=block_start_override_utc,
        snapshot=snapshot,
        display_mode=DisplayMode.COMPACT if compact else None,
    )


def _parse_block_start_time(block_start_override: int | None, config: Config) -> datetime | None:
    """Parse block start override hour and return UTC datetime.

    Args:
        block_start_override: Hour (0-23) in configured timezone
        config: Configuration for timezone

    Returns:
        UTC datetime or None if not provided
    """
    if block_start_override is None:
        return None

    try:
        hour = block_start_override
        # Create datetime for today in configured timezone with minute=0
        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz)
        override_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)

        # If the override time is in the future, use yesterday
        if override_time > now:
            override_time = override_time - timedelta(days=1)

        # Convert to UTC for internal use
        override_time_utc = override_time.astimezone(UTC)
        console.print(
            f"[yellow]Overriding unified block start time:[/yellow] "
            f"{override_time.strftime('%I:%M %p %Z')} ({override_time_utc.strftime('%H:%M UTC')})"
        )
        return override_time_utc
    except Exception as e:
        console.print(f"[red]Invalid block start hour '{block_start_override}'. Must be 0-23.[/red]")
        raise typer.Exit(1) from e


def _get_current_usage_snapshot(
    config: Config, block_start_override_utc: datetime | None = None
) -> UsageSnapshot | None:
    """Get current usage snapshot by processing all JSONL files.

    Args:
        config: Application configuration
        block_start_override_utc: Optional block start override in UTC

    Returns:
        Usage snapshot or None if no data
    """
    try:
        # Initialize components
        projects: dict[str, Project] = {}
        dedup_state = DeduplicationState()

        # Find all JSONL files
        projects_dir = Path(config.projects_dir).expanduser()
        jsonl_files = list(projects_dir.glob("*/*.jsonl"))
        logger.info(f"Found {len(jsonl_files)} JSONL files in {projects_dir}")

        # Process files to get current state
        for file_path in jsonl_files:
            try:
                # Parse session info
                session_id, project_name = parse_session_from_path(file_path, projects_dir)

                # Read file lines using JSONLReader
                with JSONLReader(file_path) as jsonl_reader:
                    lines = list(jsonl_reader.read_lines())

                # Process lines
                for line_data, _ in lines:
                    process_jsonl_line(
                        line_data,
                        project_name,
                        session_id,
                        projects,
                        dedup_state,
                        str(file_path),
                    )
            except Exception:
                # Skip files with errors
                continue

        # Log project data before creating snapshot
        logger.info(f"Creating snapshot with {len(projects)} projects")
        for proj_name, project in projects.items():
            logger.debug(f"Project {proj_name}: {len(project.sessions)} sessions")
            for sess_id, session in project.sessions.items():
                logger.debug(f"  Session {sess_id}: {len(session.blocks)} blocks, {session.total_tokens} total tokens")

        # Create snapshot
        return aggregate_usage(
            projects,
            config.token_limit,
            config.timezone,
            block_start_override_utc,
        )
    except Exception as e:
        logger.debug(f"Could not get usage snapshot: {e}")
        return None


def _process_modified_files(
    modified_files: list[tuple[Path, FileState]],
    claude_paths: list[Path],
    projects: dict[str, Project],
    config: Config,
    dedup_state: DeduplicationState,
) -> None:
    """Process all modified files."""
    for file_path, file_state in modified_files:
        # Find which base directory this file belongs to
        base_dir = None
        for claude_path in claude_paths:
            try:
                file_path.relative_to(claude_path)
                base_dir = claude_path
                break
            except ValueError:
                continue

        if base_dir:
            messages = process_file(file_path, file_state, projects, config, base_dir, dedup_state)
            if messages > 0:
                console.print(f"[dim]Processed {messages} messages from {file_path.name}[/dim]")


@app.command()
def monitor(
    interval: Annotated[int, typer.Option("--interval", "-i", help="File polling interval in seconds")] = 5,
    token_limit: Annotated[
        int | None, typer.Option("--token-limit", "-l", help="Token limit (auto-detect if not set)")
    ] = None,
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    show_sessions: Annotated[bool, typer.Option("--show-sessions", "-s", help="Show active sessions list")] = False,
    show_tools: Annotated[bool, typer.Option("--show-tools", help="Show tool usage information")] = False,
    show_pricing: Annotated[bool, typer.Option("--show-pricing", help="Show pricing information")] = False,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Disable file monitoring cache")] = False,
    block_start_override: Annotated[
        int | None,
        typer.Option(
            "--block-start",
            "-b",
            help="Override unified block start hour (0-23 in configured timezone)",
            min=0,
            max=23,
        ),
    ] = None,
    snapshot: Annotated[
        bool, typer.Option("--snapshot", help="Take a single snapshot and exit (for debugging)")
    ] = False,
    compact: Annotated[bool, typer.Option("--compact", help="Use compact display mode (minimal view)")] = False,
    theme: Annotated[ThemeType | None, typer.Option("--theme", help="Override theme for this session")] = None,
) -> None:
    """Monitor Claude Code token usage in real-time."""
    import asyncio

    # Run the async monitor function
    asyncio.run(
        _monitor_async(
            interval=interval,
            token_limit=token_limit,
            config_file=config_file,
            show_sessions=show_sessions,
            show_tools=show_tools,
            show_pricing=show_pricing,
            no_cache=no_cache,
            block_start_override=block_start_override,
            snapshot=snapshot,
            compact=compact,
            theme=theme,
        )
    )


async def _monitor_async(
    interval: int,
    token_limit: int | None,
    config_file: Path | None,
    show_sessions: bool,
    show_tools: bool,
    show_pricing: bool,
    no_cache: bool,
    block_start_override: int | None,
    snapshot: bool,
    compact: bool,
    theme: ThemeType | None,
) -> None:
    """Async implementation of monitor command."""
    # Initialize configuration
    config, actual_config_file = _initialize_config(config_file)

    # Apply temporary theme override if provided (before printing config)
    if theme is not None:
        apply_temporary_theme(theme)

    _print_config_info(config, theme)

    # Create themed console after theme is applied
    from .theme import create_themed_console

    themed_console = create_themed_console()

    # Parse monitor options
    options = _parse_monitor_options(
        interval,
        token_limit,
        config_file,
        show_sessions,
        show_tools,
        show_pricing,
        no_cache,
        block_start_override,
        snapshot,
        compact,
        config,
    )

    # Apply command line overrides
    _apply_command_overrides(config, options)

    console.print("[dim]" + "─" * 50 + "[/dim]\n")

    # Set up signal handler for graceful shutdown
    stop_monitoring = False

    def signal_handler(signum: int, frame: Any) -> None:
        nonlocal stop_monitoring
        stop_monitoring = True
        console.print("\n[yellow]Stopping monitor...[/yellow]")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize components
    claude_paths, monitor, dedup_state, notification_manager = _initialize_monitor_components(config)
    projects: dict[str, Project] = {}

    # Initial scan - don't use cache for first scan to ensure we see all data
    console.print(f"[cyan]Scanning projects in {', '.join(str(p) for p in claude_paths)}...[/cyan]")
    projects = scan_all_projects(config, use_cache=False)

    # Auto-detect token limit if needed
    _auto_detect_token_limit(config, projects, actual_config_file)

    # Handle snapshot mode
    if options.snapshot:
        # Single snapshot mode - get current data and display once
        console.print("[green]Taking debug snapshot...[/green]\n")

        # Create snapshot
        usage_snapshot = aggregate_usage(
            projects,
            config.token_limit,
            config.timezone,
            options.block_start_override_utc,
        )

        # Check if current usage exceeds configured limit
        current_usage = usage_snapshot.active_tokens
        _check_token_limit_update(config, actual_config_file, current_usage)

        # Update snapshot with potentially new limit
        usage_snapshot.total_limit = config.token_limit or 0

        # Display snapshot
        with DisplayManager(
            console=themed_console,
            refresh_interval=config.display.refresh_interval,
            update_in_place=False,  # Don't update in place for snapshot
            show_sessions=config.display.show_active_sessions,
            time_format=config.display.time_format,
            config=config,
        ) as display_manager:
            await display_manager.update(usage_snapshot)

        from .theme import get_color

        themed_console.print(f"\n[{get_color('success')}]Snapshot complete.[/{get_color('success')}]")
        return

    # Start display
    with DisplayManager(
        console=themed_console,
        refresh_interval=config.display.refresh_interval,
        update_in_place=config.display.update_in_place,
        show_sessions=config.display.show_active_sessions,
        time_format=config.display.time_format,
        config=config,
    ) as display_manager:
        from .theme import get_color

        themed_console.print(
            f"[{get_color('success')}]Monitoring token usage (refresh every {config.polling_interval}s)...[/{get_color('success')}]"
        )

        themed_console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Monitor loop
        while not stop_monitoring:
            try:
                # Check for modified files
                modified_files = monitor.get_modified_files()
                _process_modified_files(modified_files, claude_paths, projects, config, dedup_state)

                # Update file positions
                monitor.save_state()

                # Create and display snapshot
                usage_snapshot = aggregate_usage(
                    projects,
                    config.token_limit,
                    config.timezone,
                    options.block_start_override_utc,
                )

                # Check if current usage exceeds configured limit
                current_usage = usage_snapshot.active_tokens
                _check_token_limit_update(config, actual_config_file, current_usage)

                # Update snapshot with potentially new limit
                usage_snapshot.total_limit = config.token_limit or 0

                await display_manager.update(usage_snapshot)

                # Check for block completion notifications
                notification_manager.check_and_send_notifications(usage_snapshot)

                # Wait for next interval
                time.sleep(config.polling_interval)

            except Exception as e:
                themed_console.print(create_error_display(f"Monitor error: {e}"))
                time.sleep(config.polling_interval)

    # Clean up
    monitor.save_state()
    themed_console.print(f"\n[{get_color('success')}]Monitor stopped.[/{get_color('success')}]")


@app.command(name="list")
def list_usage(
    output_format: Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")] = OutputFormat.TABLE,
    sort_by: Annotated[SortBy, typer.Option("--sort-by", "-s", help="Sort results by field")] = SortBy.TOKENS,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    theme: Annotated[ThemeType | None, typer.Option("--theme", help="Override theme for this session")] = None,
) -> None:
    """List all token usage data."""
    # Load configuration (defaults to XDG config location)
    config_file_to_load = config_file if config_file else get_config_file_path()
    config = load_config(config_file)

    # Apply temporary theme override if provided
    if theme is not None:
        apply_temporary_theme(theme)

    # Create themed console after theme application
    from .theme import create_themed_console

    themed_console = create_themed_console()

    # Check if Claude directories exist
    claude_paths = config.get_claude_paths()
    if not claude_paths:
        themed_console.print(create_error_display("No Claude directories found!"))
        sys.exit(1)

    # Scan all projects
    if output_format == OutputFormat.TABLE:
        from .theme import get_color

        themed_console.print(
            f"[{get_color('info')}]Scanning projects in {', '.join(str(p) for p in claude_paths)}...[/{get_color('info')}]"
        )
    projects = scan_all_projects(config, use_cache=False)

    # Detect token limit if not set
    config_file_used = config_file_to_load
    if config.token_limit is None:
        detected_limit = detect_token_limit_from_data(projects)
        if detected_limit:
            config.token_limit = detected_limit
            if output_format == OutputFormat.TABLE:
                themed_console.print(
                    f"[{get_color('warning')}]Auto-detected token limit: {config.token_limit:,}[/{get_color('warning')}]"
                )

            # Update config file if it exists
            if config_file_used.exists():
                update_config_token_limit(config_file_used, config.token_limit)
                if output_format == OutputFormat.TABLE:
                    themed_console.print(
                        f"[{get_color('success')}]Updated config file with token limit[/{get_color('success')}]"
                    )
        else:
            config.token_limit = get_default_token_limit()

    # Create snapshot
    snapshot = aggregate_usage(projects, config.token_limit, config.timezone)

    # Display results
    display_usage_list(
        snapshot,
        output_format=output_format,
        sort_by=sort_by,
        output_file=output,
        console=themed_console,
        time_format=config.display.time_format,
    )


@app.command()
def init(
    config_file: Annotated[
        Path, typer.Option("--config", "-c", help="Configuration file path")
    ] = get_config_file_path(),
) -> None:
    """Initialize configuration file with defaults."""
    if config_file.exists():
        console.print(f"[yellow]Configuration file already exists: {config_file}[/yellow]")
        if not typer.confirm("Overwrite?"):
            return

    save_default_config(config_file)
    console.print(f"[green]Created default configuration at {config_file}[/green]")


@app.command("set-limit")
def set_limit(
    limit: Annotated[int, typer.Argument(help="Token limit to set")],
    config_file: Annotated[
        Path, typer.Option("--config", "-c", help="Configuration file path")
    ] = get_config_file_path(),
) -> None:
    """Set the token limit in the configuration."""
    if not config_file.exists():
        console.print(f"[red]Configuration file not found: {config_file}[/red]")
        console.print("[yellow]Run 'par-cc-usage init' to create a configuration file[/yellow]")
        sys.exit(1)

    # Load current config
    config = load_config(config_file)
    old_limit = config.token_limit

    # Update token limit
    config.token_limit = limit
    save_config(config, config_file)

    if old_limit:
        console.print(f"[green]Updated token limit from {old_limit:,} to {limit:,}[/green]")
    else:
        console.print(f"[green]Set token limit to {limit:,}[/green]")


@app.command("clear-cache")
def clear_cache(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
) -> None:
    """Clear the file monitoring cache."""
    # Load configuration to get cache directory
    config = load_config(config_file)
    cache_file = config.cache_dir / "file_states.json"

    if cache_file.exists():
        cache_file.unlink()
        console.print(f"[green]Cache cleared: {cache_file}[/green]")
    else:
        console.print(f"[yellow]Cache file not found: {cache_file}[/yellow]")


def main() -> None:
    """Main entry point."""
    # Register additional commands
    from .commands import register_commands

    register_commands()

    app()


if __name__ == "__main__":
    main()


@app.command()
def test_webhook(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    block_start_override: Annotated[
        int | None,
        typer.Option(
            "--block-start",
            "-b",
            help="Override unified block start hour (0-23 in configured timezone)",
            min=0,
            max=23,
        ),
    ] = None,
) -> None:
    """Test webhook notifications (Discord and/or Slack).

    If there's an active unified block, sends a real block notification.
    Otherwise sends a generic test message.

    Use --block-start to override the unified block start time for testing.
    """
    config_file_to_load = config_file if config_file else get_config_file_path()
    config = load_config(config_file_to_load)

    # Check if any webhook is configured
    notification_manager = NotificationManager(config)
    if not notification_manager.is_configured():
        console.print(create_error_display("No webhook URLs configured!"))
        console.print(
            create_info_display(
                "Set 'notifications.discord_webhook_url' or 'notifications.slack_webhook_url' in your config file"
            )
        )
        sys.exit(1)

    # Show which webhooks are configured
    webhook_types = []
    if config.notifications.discord_webhook_url:
        webhook_types.append("Discord")
    if config.notifications.slack_webhook_url:
        webhook_types.append("Slack")

    console.print(f"[cyan]Testing {', '.join(webhook_types)} webhook(s)...[/cyan]")

    # Parse webhook test options
    webhook_options = TestWebhookOptions(
        config_file=config_file,
        block_start_override=block_start_override,
        block_start_override_utc=_parse_block_start_time(block_start_override, config),
    )

    # Try to get current usage snapshot
    snapshot = _get_current_usage_snapshot(config, webhook_options.block_start_override_utc)

    if snapshot:
        console.print(
            f"[dim]Snapshot has {len(snapshot.projects)} projects, {snapshot.total_tokens} total tokens[/dim]"
        )
        if snapshot.unified_block_start_time:
            console.print("[cyan]Found active unified block - sending real notification...[/cyan]")
        else:
            console.print("[cyan]No active block found - sending test notification...[/cyan]")
    else:
        console.print("[yellow]No snapshot data available - sending test notification...[/yellow]")

    if notification_manager.test_webhook(snapshot):
        console.print("[green]✓ Webhook test successful![/green]")
        if snapshot and snapshot.unified_block_start_time:
            console.print("[green]Sent real block notification with current usage data[/green]")
    else:
        console.print(create_error_display("Webhook test failed!"))
        console.print(create_info_display("Check your webhook URLs and server settings"))
        sys.exit(1)


def _scan_projects_for_sessions(config) -> dict[str, Project]:
    """Scan all projects and return project dictionary."""
    projects: dict[str, Project] = {}
    dedup_state = DeduplicationState()

    claude_paths = config.get_claude_paths()
    if not claude_paths:
        return projects

    file_monitor = FileMonitor(
        projects_dirs=claude_paths,
        cache_dir=config.cache_dir,
        disable_cache=False,
    )

    for file_path in file_monitor.scan_files():
        with JSONLReader(file_path) as reader:
            for data, _position in reader.read_lines():
                session_id, project_path = parse_session_from_path(file_path, config.projects_dir)
                process_jsonl_line(data, project_path, session_id, projects, dedup_state, config.timezone)

    return projects


def _create_sessions_table(show_pricing: bool):
    """Create table for sessions listing."""
    from rich.table import Table

    table = Table(title="Sessions List", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Session ID", style="yellow")
    table.add_column("Model", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Tokens", style="blue", justify="right")
    table.add_column("Last Activity", style="dim")

    if show_pricing:
        table.add_column("Cost", style=get_color("cost"), justify="right")

    return table


def _session_matches_filters(project, session, project_filter: str | None, session_filter: str | None) -> bool:
    """Check if session matches the provided filters."""
    if project_filter and project_filter.lower() not in project.name.lower():
        return False
    if session_filter and session_filter.lower() not in session.session_id.lower():
        return False
    return True


async def _calculate_session_cost(session) -> float:
    """Calculate total cost for a session."""
    cost = 0.0
    try:
        for block in session.blocks:
            if block.is_active:
                for full_model in block.full_model_names:
                    from .pricing import calculate_token_cost

                    usage = block.token_usage
                    cost_result = await calculate_token_cost(
                        full_model,
                        usage.input_tokens,
                        usage.output_tokens,
                        usage.cache_creation_input_tokens,
                        usage.cache_read_input_tokens,
                    )
                    cost += cost_result.total_cost
    except Exception:
        cost = 0.0
    return cost


async def _collect_filtered_sessions(projects, project_filter, session_filter, show_inactive, show_pricing):
    """Collect sessions that match the filters."""
    all_sessions = []
    for project in projects.values():
        for session in project.sessions.values():
            if not _session_matches_filters(project, session, project_filter, session_filter):
                continue

            latest_block = session.latest_block
            if not latest_block:
                continue

            is_active = latest_block.is_active
            if not show_inactive and not is_active:
                continue

            cost = await _calculate_session_cost(session) if show_pricing else 0.0
            all_sessions.append((project, session, latest_block, is_active, cost))

    return all_sessions


def _populate_sessions_table(table, all_sessions, config, show_pricing):
    """Populate the sessions table with data."""
    from .token_calculator import format_token_count, get_model_display_name
    from .utils import format_datetime

    for project, session, block, is_active, cost in all_sessions:
        status = "🟢 Active" if is_active else "🔴 Inactive"
        last_activity = block.actual_end_time or block.start_time
        time_str = format_datetime(last_activity, config.display.time_format)

        row_data = [
            project.name,
            session.session_id[:12] + "...",
            get_model_display_name(block.model),
            status,
            format_token_count(session.total_tokens),
            time_str,
        ]

        if show_pricing:
            from .pricing import format_cost

            row_data.append(format_cost(cost) if cost > 0 else "-")

        table.add_row(*row_data)


@app.command("list-sessions")
def list_sessions(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    show_inactive: Annotated[bool, typer.Option("--show-inactive", help="Show inactive sessions")] = False,
    project_filter: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project name")] = None,
    session_filter: Annotated[str | None, typer.Option("--session", "-s", help="Filter by session ID")] = None,
    show_pricing: Annotated[bool, typer.Option("--show-pricing", help="Show pricing information")] = False,
    theme: Annotated[ThemeType | None, typer.Option("--theme", help="Override theme for this session")] = None,
) -> None:
    """List all sessions with their status and activity information."""
    import asyncio

    async def _list_sessions_async() -> None:
        config = load_config(config_file)

        # Apply temporary theme override if provided
        if theme is not None:
            apply_temporary_theme(theme)

        console.print(f"[dim]Scanning projects in {config.projects_dir}...[/]")

        projects = _scan_projects_for_sessions(config)
        table = _create_sessions_table(show_pricing)

        # Collect and filter sessions
        all_sessions = await _collect_filtered_sessions(
            projects, project_filter, session_filter, show_inactive, show_pricing
        )

        # Sort by last activity (newest first)
        all_sessions.sort(key=lambda x: x[2].actual_end_time or x[2].start_time, reverse=True)

        # Populate table
        _populate_sessions_table(table, all_sessions, config, show_pricing)

        if table.row_count == 0:
            console.print("[dim italic]No sessions found matching criteria[/]")
        else:
            console.print(table)
            console.print(f"\n[dim]Found {table.row_count} sessions[/]")

    asyncio.run(_list_sessions_async())


def _print_debug_header(config, snapshot):
    """Print debug header information."""
    console.print("[bold blue]Debug: Session Activity Analysis[/]")
    console.print("─" * 50)
    console.print(f"Current Time (UTC): {datetime.now(UTC)}")
    console.print(f"Configured Timezone: {config.timezone}")
    console.print(f"Snapshot Timestamp: {snapshot.timestamp}")
    console.print(f"Unified Block Start Time: {snapshot.unified_block_start_time}")

    unified_start = snapshot.unified_block_start_time
    if unified_start:
        unified_end = unified_start + timedelta(hours=5)
        console.print(f"Unified Block Window: {unified_start} to {unified_end}")
    else:
        console.print("No unified block start time")
    console.print()


def _create_debug_table():
    """Create table for debug analysis."""
    from rich.table import Table

    table = Table(title="Session Debug Analysis", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Session", style="yellow")
    table.add_column("Block Start", style="green")
    table.add_column("Block End", style="green")
    table.add_column("Last Activity", style="blue")
    table.add_column("Is Active", style="bold")
    table.add_column("In Unified Window", style="bold")
    table.add_column("Tokens", style="dim", justify="right")
    table.add_column("Reason", style="dim")
    return table


def _analyze_block_window(block, unified_start, unified_end):
    """Analyze if block is in unified window."""
    is_active = block.is_active
    in_unified_window = False
    reason = ""

    if not is_active:
        reason = "Block not active"
    elif unified_start is None:
        in_unified_window = True
        reason = "No unified block filter"
    else:
        # Check overlap logic
        block_end = block.actual_end_time or block.end_time
        if block.start_time < unified_end and block_end > unified_start:
            in_unified_window = True
            reason = "Overlaps unified window"
        else:
            reason = f"No overlap: block({block.start_time}-{block_end}) vs unified({unified_start}-{unified_end})"

    return is_active, in_unified_window, reason


def _print_debug_summary(projects, snapshot, unified_start):
    """Print debug summary information."""
    active_sessions = [s for p in projects.values() for s in p.active_sessions]
    console.print("\n[bold]Summary:[/]")
    console.print(f"Total projects: {len(projects)}")
    console.print(f"Total active sessions: {len(active_sessions)}")
    console.print(f"Active tokens: {snapshot.active_tokens:,}")

    if unified_start:
        unified_tokens = snapshot.unified_block_tokens()
        console.print(f"Unified block tokens: {unified_tokens:,}")


@app.command("debug-sessions")
def debug_sessions(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    project_filter: Annotated[str | None, typer.Option("--project", "-p", help="Filter by project name")] = None,
    session_filter: Annotated[str | None, typer.Option("--session", "-s", help="Filter by session ID")] = None,
) -> None:
    """Debug session activity and filtering logic."""
    config = load_config(config_file)
    console.print(f"Scanning projects in {config.projects_dir}...")

    projects = _scan_projects_for_sessions(config)
    snapshot = aggregate_usage(projects, config.token_limit, config.timezone)

    _print_debug_header(config, snapshot)
    table = _create_debug_table()

    unified_start = snapshot.unified_block_start_time
    unified_end = unified_start + timedelta(hours=5) if unified_start else None

    for project in projects.values():
        if project_filter and project_filter.lower() not in project.name.lower():
            continue

        for session in project.sessions.values():
            if session_filter and session_filter.lower() not in session.session_id.lower():
                continue

            for block in session.blocks:
                is_active, in_unified_window, reason = _analyze_block_window(block, unified_start, unified_end)

                status_active = "🟢 YES" if is_active else "🔴 NO"
                status_window = "🟢 YES" if in_unified_window else "🔴 NO"

                from .token_calculator import format_token_count
                from .utils import format_datetime

                table.add_row(
                    project.name[:20],
                    session.session_id[:12] + "...",
                    format_datetime(block.start_time, "24h"),
                    format_datetime(block.end_time, "24h"),
                    format_datetime(block.actual_end_time or block.start_time, "24h"),
                    status_active,
                    status_window,
                    format_token_count(block.adjusted_tokens),
                    reason[:30] + "..." if len(reason) > 30 else reason,
                )

    console.print(table)
    _print_debug_summary(projects, snapshot, unified_start)


def _get_session_models(session) -> set[str]:
    """Get all models used in a session."""
    session_models = set()
    for block in session.blocks:
        session_models.update(block.models_used)
    return session_models


def _get_latest_activity(session):
    """Get the latest activity time for a session."""
    latest_activity = None
    for block in session.blocks:
        activity_time = block.actual_end_time or block.start_time
        if latest_activity is None or activity_time > latest_activity:
            latest_activity = activity_time
    return latest_activity


def _session_passes_filters(session, project, filters, now):
    """Check if session passes all filters."""
    active_only, min_tokens, max_tokens, model_filter, since_hours = filters

    # Active filter
    if active_only and not any(block.is_active for block in session.blocks):
        return False

    # Token filters
    if min_tokens and session.total_tokens < min_tokens:
        return False
    if max_tokens and session.total_tokens > max_tokens:
        return False

    # Model filter
    if model_filter:
        session_models = _get_session_models(session)
        if not any(model_filter.lower() in model.lower() for model in session_models):
            return False

    # Time filter
    if since_hours:
        latest_activity = _get_latest_activity(session)
        if latest_activity:
            hours_ago = (now - latest_activity).total_seconds() / 3600
            if hours_ago > since_hours:
                return False

    return True


def _display_table_results(filtered_sessions, config, show_pricing):
    """Display results in table format."""
    from rich.table import Table

    from .token_calculator import format_token_count, get_model_display_name

    table = Table(title="Filtered Sessions", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Session ID", style="yellow")
    table.add_column("Model(s)", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Tokens", style="blue", justify="right")
    table.add_column("Latest Activity", style="dim")

    if show_pricing:
        table.add_column("Cost", style=get_color("cost"), justify="right")

    for project, session, cost in filtered_sessions:
        is_active = any(block.is_active for block in session.blocks)
        status = "🟢 Active" if is_active else "🔴 Inactive"

        session_models = _get_session_models(session)
        models_str = ", ".join(sorted(get_model_display_name(m) for m in session_models))

        latest_activity = _get_latest_activity(session)
        from .utils import format_datetime

        time_str = format_datetime(latest_activity, config.display.time_format) if latest_activity else "Unknown"

        row_data = [
            project.name,
            session.session_id[:12] + "...",
            models_str,
            status,
            format_token_count(session.total_tokens),
            time_str,
        ]

        if show_pricing:
            from .pricing import format_cost

            row_data.append(format_cost(cost) if cost > 0 else "-")

        table.add_row(*row_data)

    console.print(table)
    console.print(f"\n[dim]Found {len(filtered_sessions)} sessions matching criteria[/]")


def _display_json_results(filtered_sessions, show_pricing):
    """Display results in JSON format."""
    import json

    result = []
    for project, session, cost in filtered_sessions:
        session_data = {
            "project": project.name,
            "session_id": session.session_id,
            "model": session.model,
            "total_tokens": session.total_tokens,
            "is_active": any(block.is_active for block in session.blocks),
        }
        if show_pricing:
            session_data["cost"] = cost
        result.append(session_data)

    console.print(json.dumps(result, indent=2))


def _display_csv_results(filtered_sessions, show_pricing):
    """Display results in CSV format."""
    import csv
    import io

    output = io.StringIO()
    fieldnames = ["project", "session_id", "model", "total_tokens", "is_active"]
    if show_pricing:
        fieldnames.append("cost")

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for project, session, cost in filtered_sessions:
        row = {
            "project": project.name,
            "session_id": session.session_id,
            "model": session.model,
            "total_tokens": session.total_tokens,
            "is_active": any(block.is_active for block in session.blocks),
        }
        if show_pricing:
            row["cost"] = cost
        writer.writerow(row)

    console.print(output.getvalue())


@app.command("filter-sessions")
def filter_sessions(
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
    min_tokens: Annotated[int | None, typer.Option("--min-tokens", help="Minimum token count")] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens", help="Maximum token count")] = None,
    model_filter: Annotated[str | None, typer.Option("--model", "-m", help="Filter by model name")] = None,
    active_only: Annotated[bool, typer.Option("--active-only", help="Show only active sessions")] = True,
    since_hours: Annotated[
        int | None, typer.Option("--since-hours", help="Show sessions with activity in last N hours")
    ] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")] = OutputFormat.TABLE,
    show_pricing: Annotated[bool, typer.Option("--show-pricing", help="Show pricing information")] = False,
) -> None:
    """Filter and display sessions based on various criteria."""
    import asyncio

    async def _filter_sessions_async() -> None:
        config = load_config(config_file)
        projects = _scan_projects_for_sessions(config)

        # Filter sessions
        filtered_sessions = []
        now = datetime.now(UTC)
        filters = (active_only, min_tokens, max_tokens, model_filter, since_hours)

        for project in projects.values():
            for session in project.sessions.values():
                if not _session_passes_filters(session, project, filters, now):
                    continue

                cost = await _calculate_session_cost(session) if show_pricing else 0.0
                filtered_sessions.append((project, session, cost))

        # Sort by total tokens (descending)
        filtered_sessions.sort(key=lambda x: x[1].total_tokens, reverse=True)

        # Display results
        if output_format == OutputFormat.TABLE:
            _display_table_results(filtered_sessions, config, show_pricing)
        elif output_format == OutputFormat.JSON:
            _display_json_results(filtered_sessions, show_pricing)
        elif output_format == OutputFormat.CSV:
            _display_csv_results(filtered_sessions, show_pricing)

    asyncio.run(_filter_sessions_async())


@app.command("theme")
def theme_command(
    action: Annotated[str, typer.Argument(help="Action: list, set, or current")] = "list",
    theme_name: Annotated[str | None, typer.Argument(help="Theme name for 'set' action")] = None,
    config_file: Annotated[Path | None, typer.Option("--config", "-c", help="Configuration file path")] = None,
) -> None:
    """Manage display themes."""
    console = Console()
    theme_manager = get_theme_manager()

    if action == "list":
        themes = theme_manager.list_themes()
        console.print("Available themes:", style="bold")
        for theme_type, theme_def in themes.items():
            current_marker = "→ " if theme_type == theme_manager.get_current_theme_type() else "  "
            console.print(f"{current_marker}[bold]{theme_def.name}[/bold] ({theme_type.value})")
            console.print(f"    {theme_def.description}", style="dim")

    elif action == "current":
        current_theme = theme_manager.get_current_theme()
        console.print(
            f"Current theme: [bold]{current_theme.name}[/bold] ({theme_manager.get_current_theme_type().value})"
        )
        console.print(f"Description: {current_theme.description}")

    elif action == "set":
        if not theme_name:
            console.print("Error: Theme name required for 'set' action", style="red")
            raise typer.Exit(1)

        try:
            theme_type = ThemeType(theme_name)

            # Load config and update theme
            config = load_config(config_file)
            config.display.theme = theme_type

            # Determine config file path - use default if not specified
            if config_file is None:
                config_file = get_config_file_path()

            save_config(config, config_file)

            theme_def = theme_manager.get_theme(theme_type)
            console.print(f"Theme set to: [bold]{theme_def.name}[/bold]")
            console.print("The new theme will be applied when you next run the monitor.", style="dim")

        except ValueError as e:
            available_themes = [t.value for t in ThemeType]
            console.print(f"Error: Invalid theme '{theme_name}'", style="red")
            console.print(f"Available themes: {', '.join(available_themes)}")
            raise typer.Exit(1) from e

    else:
        console.print(f"Error: Unknown action '{action}'", style="red")
        console.print("Available actions: list, set, current")
        raise typer.Exit(1)
