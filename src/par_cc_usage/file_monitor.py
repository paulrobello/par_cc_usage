"""File monitoring and JSONL streaming for par_cc_usage."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


@dataclass
class FileState:
    """State of a monitored file."""

    path: Path
    mtime: float
    size: int
    last_position: int = 0
    last_processed: datetime = field(default_factory=datetime.now)


class JSONLReader:
    """Streaming reader for JSONL files."""

    def __init__(self, file_path: Path) -> None:
        """Initialize JSONL reader.

        Args:
            file_path: Path to JSONL file
        """
        self.file_path = file_path
        self._file_handle: Any = None
        self._position = 0

    def __enter__(self) -> JSONLReader:
        """Enter context manager."""
        self._file_handle = open(self.file_path, encoding="utf-8")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def seek(self, position: int) -> None:
        """Seek to position in file.

        Args:
            position: Byte position to seek to
        """
        if self._file_handle:
            self._file_handle.seek(position)
            self._position = position

    def read_lines(self, from_position: int | None = None) -> Iterator[tuple[dict[str, Any], int]]:
        """Read lines from file starting at position with robust error handling.

        Args:
            from_position: Starting byte position (default: current position)

        Yields:
            Tuple of (parsed JSON data, end position of line)
        """
        if from_position is not None:
            self.seek(from_position)

        if not self._file_handle:
            return

        line_count = 0
        error_count = 0

        while True:
            try:
                line = self._file_handle.readline()
                if not line:
                    break

                line_count += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    # Basic validation - ensure it's a dict
                    if not isinstance(data, dict):
                        error_count += 1
                        continue

                    self._position = self._file_handle.tell()
                    yield data, self._position

                except json.JSONDecodeError:
                    error_count += 1
                    # Log error details if needed for debugging
                    continue
                except (UnicodeDecodeError, ValueError):
                    error_count += 1
                    # Handle encoding issues or other parsing errors
                    continue

            except Exception:
                # Handle any other file reading errors
                error_count += 1
                break


class AsyncJSONLReader:
    """Async streaming reader for JSONL files."""

    def __init__(self, file_path: Path) -> None:
        """Initialize async JSONL reader.

        Args:
            file_path: Path to JSONL file
        """
        self.file_path = file_path
        self._file_handle: Any = None
        self._position = 0

    async def __aenter__(self) -> AsyncJSONLReader:
        """Enter async context manager."""
        self._file_handle = await aiofiles.open(self.file_path, encoding="utf-8")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._file_handle:
            await self._file_handle.close()
            self._file_handle = None

    async def seek(self, position: int) -> None:
        """Seek to position in file.

        Args:
            position: Byte position to seek to
        """
        if self._file_handle:
            await self._file_handle.seek(position)
            self._position = position

    async def read_lines(self, from_position: int | None = None) -> AsyncIterator[tuple[dict[str, Any], int]]:
        """Read lines from file starting at position with robust error handling.

        Args:
            from_position: Starting byte position (default: current position)

        Yields:
            Tuple of (parsed JSON data, end position of line)
        """
        if from_position is not None:
            await self.seek(from_position)

        if not self._file_handle:
            return

        line_count = 0
        error_count = 0

        try:
            async for line in self._file_handle:
                line_count += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    # Basic validation - ensure it's a dict
                    if not isinstance(data, dict):
                        error_count += 1
                        continue

                    self._position = await self._file_handle.tell()
                    yield data, self._position

                except json.JSONDecodeError:
                    error_count += 1
                    # Log error details if needed for debugging
                    continue
                except (UnicodeDecodeError, ValueError):
                    error_count += 1
                    # Handle encoding issues or other parsing errors
                    continue

        except Exception:
            # Handle any other file reading errors
            error_count += 1
            return


class FileMonitor:
    """Monitor JSONL files for changes."""

    def __init__(self, projects_dirs: list[Path], cache_dir: Path, disable_cache: bool = False) -> None:
        """Initialize file monitor.

        Args:
            projects_dirs: List of directories containing project JSONL files
            cache_dir: Directory for caching file states
            disable_cache: If True, disable cache loading and saving
        """
        self.projects_dirs = projects_dirs
        self.cache_dir = cache_dir
        self.disable_cache = disable_cache
        self.file_states: dict[Path, FileState] = {}
        if not self.disable_cache:
            self._load_cache()

    def _load_cache(self) -> None:
        """Load cached file states."""
        cache_file = self.cache_dir / "file_states.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for path_str, state_data in data.items():
                        path = Path(path_str)
                        if path.exists():
                            self.file_states[path] = FileState(
                                path=path,
                                mtime=state_data["mtime"],
                                size=state_data["size"],
                                last_position=state_data["last_position"],
                                last_processed=datetime.fromisoformat(state_data["last_processed"]),
                            )
            except (json.JSONDecodeError, KeyError):
                # Ignore corrupted cache
                pass

    def _save_cache(self) -> None:
        """Save file states to cache."""
        if self.disable_cache:
            return

        cache_file = self.cache_dir / "file_states.json"
        data = {}
        for path, state in self.file_states.items():
            data[str(path)] = {
                "mtime": state.mtime,
                "size": state.size,
                "last_position": state.last_position,
                "last_processed": state.last_processed.isoformat(),
            }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def scan_files(self) -> list[Path]:
        """Scan for JSONL files in projects directories.

        Returns:
            List of JSONL file paths
        """
        jsonl_files: list[Path] = []

        for projects_dir in self.projects_dirs:
            if not projects_dir.exists():
                continue

            # Use glob pattern to find JSONL files in Claude's directory structure
            # Pattern: projects/*/*.jsonl (project/file.jsonl)
            for jsonl_file in projects_dir.glob("*/*.jsonl"):
                jsonl_files.append(jsonl_file)

        return sorted(jsonl_files)

    def get_modified_files(self) -> list[tuple[Path, FileState]]:
        """Get files that have been modified since last check.

        Returns:
            List of (path, file_state) tuples for modified files
        """
        modified_files: list[tuple[Path, FileState]] = []
        for file_path in self.scan_files():
            try:
                stat = file_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                if file_path in self.file_states:
                    state = self.file_states[file_path]
                    if mtime > state.mtime or size != state.size:
                        # File has been modified
                        state.mtime = mtime
                        state.size = size
                        modified_files.append((file_path, state))
                else:
                    # New file
                    state = FileState(path=file_path, mtime=mtime, size=size)
                    self.file_states[file_path] = state
                    modified_files.append((file_path, state))
            except OSError:
                # File might have been deleted or is inaccessible
                continue

        return modified_files

    def update_position(self, file_path: Path, position: int) -> None:
        """Update the last processed position for a file.

        Args:
            file_path: Path to file
            position: Last processed byte position
        """
        if file_path in self.file_states:
            self.file_states[file_path].last_position = position
            self.file_states[file_path].last_processed = datetime.now()

    def save_state(self) -> None:
        """Save current file states to cache."""
        self._save_cache()


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events for JSONL files."""

    def __init__(self, callback: Any) -> None:
        """Initialize handler.

        Args:
            callback: Callback function to call on file changes
        """
        self.callback = callback

    def on_modified(self, event: Any) -> None:
        """Handle file modification event."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self.callback(Path(event.src_path))

    def on_created(self, event: Any) -> None:
        """Handle file creation event."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            self.callback(Path(event.src_path))


class FileWatcher:
    """Watch for file changes using watchdog."""

    def __init__(self, projects_dirs: list[Path], callback: Any) -> None:
        """Initialize file watcher.

        Args:
            projects_dirs: List of directories to watch
            callback: Callback function for file changes
        """
        self.projects_dirs = projects_dirs
        self.callback = callback
        self.observer = Observer()
        self.handler = FileChangeHandler(callback)

    def start(self) -> None:
        """Start watching for file changes."""
        for projects_dir in self.projects_dirs:
            if projects_dir.exists():
                self.observer.schedule(self.handler, str(projects_dir), recursive=True)
        if self.observer.emitters:  # Only start if at least one directory is being watched
            self.observer.start()

    def stop(self) -> None:
        """Stop watching for file changes."""
        self.observer.stop()
        self.observer.join()

    def __enter__(self) -> FileWatcher:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()


def poll_files(monitor: FileMonitor, callback: Any, interval: int = 5) -> None:
    """Poll files for changes at regular intervals.

    Args:
        monitor: File monitor instance
        callback: Callback function for modified files
        interval: Polling interval in seconds
    """
    while True:
        modified_files = monitor.get_modified_files()
        for file_path, state in modified_files:
            callback(file_path, state)

        monitor.save_state()
        time.sleep(interval)


def parse_session_from_path(
    file_path: Path, base_dir: Path, project_name_prefixes: list[str] | None = None
) -> tuple[str, str]:
    """Parse session ID and project path from file path.

    Args:
        file_path: Path to JSONL file
        base_dir: Base Claude directory
        project_name_prefixes: List of prefixes to strip from project names

    Returns:
        Tuple of (session_id, project_path)
    """
    try:
        relative_path = file_path.relative_to(base_dir)
        parts = relative_path.parts

        # Expected structure: project/file.jsonl
        if len(parts) >= 2:
            # Session ID is the filename without extension
            session_id = file_path.stem
            # Project directory name (e.g., "-Users-probello-Repos-par-cc-usage")
            claude_dir_name = parts[0] if len(parts) > 1 else "Unknown Project"

            # Strip configured prefixes from project name
            if project_name_prefixes:
                project_path = _strip_project_name_prefixes(claude_dir_name, project_name_prefixes)
            else:
                project_path = claude_dir_name
            return session_id, project_path
    except ValueError:
        pass

    # Fallback
    return "unknown", "Unknown Project"


def _strip_project_name_prefixes(project_name: str, prefixes: list[str]) -> str:
    """Strip configured prefixes from project names for cleaner display.

    Args:
        project_name: Raw project name from Claude directory
        prefixes: List of prefixes to strip from the name

    Returns:
        Project name with prefixes stripped
    """
    result = project_name

    # Try to strip each prefix (longest first to handle overlapping prefixes)
    for prefix in sorted(prefixes, key=len, reverse=True):
        if result.startswith(prefix):
            result = result[len(prefix) :]
            break  # Only strip one prefix to avoid over-stripping

    # If we stripped everything, return the original name
    if not result:
        return project_name

    return result
