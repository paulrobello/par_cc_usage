"""
Tests for the file_monitor module.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from par_cc_usage.file_monitor import FileMonitor, FileState


class TestFileMonitor:
    """Test the FileMonitor class."""

    def test_initialization(self, temp_dir):
        """Test FileMonitor initialization."""
        projects_dirs = [temp_dir / "claude1", temp_dir / "claude2"]
        cache_dir = temp_dir / "cache"

        monitor = FileMonitor(projects_dirs, cache_dir, disable_cache=False)

        assert monitor.projects_dirs == projects_dirs
        assert monitor.cache_dir == cache_dir
        assert monitor.disable_cache is False
        assert monitor.file_states == {}

    def test_load_cache_file_exists(self, temp_dir):
        """Test loading existing cache file."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "file_states.json"

        # Create a real file first
        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Create cache with test data for the real file
        cache_data = {
            "_metadata": {
                "cache_version": "1.0",
                "tool_usage_enabled": True,
                "created_at": "2025-01-09T12:00:00",
                "last_updated": "2025-01-09T12:00:00"
            },
            str(test_file): {
                "mtime": test_file.stat().st_mtime,
                "size": test_file.stat().st_size,
                "last_position": 500,
                "last_processed": "2025-01-09T12:00:00"
            }
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=False)
        # _load_cache is called in __init__ if disable_cache is False

        assert len(monitor.file_states) == 1
        assert test_file in monitor.file_states

    def test_load_cache_file_not_exists(self, temp_dir):
        """Test loading cache when file doesn't exist."""
        cache_dir = temp_dir / "cache"

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=False)

        assert monitor.file_states == {}

    def test_load_cache_disabled(self, temp_dir):
        """Test that cache is not loaded when disabled."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "file_states.json"

        # Create cache file
        cache_data = {
            "/test/file.jsonl": {
                "path": "/test/file.jsonl",
                "mtime": 1234567890.0,
                "size": 1000,
                "last_position": 500,
                "last_processed": "2025-01-09T12:00:00"
            }
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=True)

        # Should not load cache when disabled
        assert monitor.file_states == {}

    def test_save_cache(self, temp_dir):
        """Test saving cache to file."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=False)

        # Add a file state
        test_path = Path("/path/to/file1.jsonl")
        monitor.file_states[test_path] = FileState(
            path=test_path,
            mtime=1234567890.0,
            size=1000,
            last_position=500,
            last_processed=datetime.now()
        )

        monitor._save_cache()

        # Verify cache file was created
        cache_file = cache_dir / "file_states.json"
        assert cache_file.exists()

    def test_save_cache_disabled(self, temp_dir):
        """Test that cache is not saved when disabled."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=True)

        # Add a file state
        test_path = Path("/path/to/file1.jsonl")
        monitor.file_states[test_path] = FileState(
            path=test_path,
            mtime=1234567890.0,
            size=1000,
            last_position=500,
            last_processed=datetime.now()
        )

        monitor._save_cache()

        # Cache file should not be created
        cache_file = cache_dir / "file_states.json"
        assert not cache_file.exists()

    def test_scan_files(self, temp_dir):
        """Test scanning for JSONL files in directories."""
        # Create test directory structure
        project1 = temp_dir / "claude1" / "project1"
        project1.mkdir(parents=True)
        project2 = temp_dir / "claude2" / "project2"
        project2.mkdir(parents=True)

        # Create JSONL files
        jsonl1 = project1 / "test1.jsonl"
        jsonl1.write_text('{"test": 1}\n')

        jsonl2 = project2 / "test2.jsonl"
        jsonl2.write_text('{"test": 2}\n')

        # Create non-JSONL file (should be ignored)
        other_file = project1 / "test.txt"
        other_file.write_text("not jsonl")

        monitor = FileMonitor(
            [temp_dir / "claude1", temp_dir / "claude2"],
            temp_dir / "cache",
        )

        files = monitor.scan_files()

        # Should find both JSONL files
        assert len(files) == 2
        file_paths = [str(f) for f in files]
        assert str(jsonl1) in file_paths
        assert str(jsonl2) in file_paths
        assert str(other_file) not in file_paths

    def test_get_modified_files(self, temp_dir):
        """Test getting modified files."""
        project_dir = temp_dir / "claude" / "project"
        project_dir.mkdir(parents=True)

        jsonl_file = project_dir / "test.jsonl"
        jsonl_file.write_text('{"test": 1}\n')

        monitor = FileMonitor([temp_dir / "claude"], temp_dir / "cache")

        # First scan should find the file as modified
        modified = monitor.get_modified_files()

        assert len(modified) == 1
        assert modified[0][0] == jsonl_file
        assert isinstance(modified[0][1], FileState)

    def test_update_position(self, temp_dir):
        """Test updating file position."""
        jsonl_file = temp_dir / "test.jsonl"
        jsonl_file.write_text('{"test": 1}\n')

        monitor = FileMonitor([temp_dir], temp_dir / "cache")

        # Add file state
        monitor.file_states[jsonl_file] = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        # Update position
        monitor.update_position(jsonl_file, 100)

        assert monitor.file_states[jsonl_file].last_position == 100

    def test_save_state(self, temp_dir):
        """Test save_state method."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=False)

        # Add a file state
        test_path = Path("/path/to/file.jsonl")
        monitor.file_states[test_path] = FileState(
            path=test_path,
            mtime=1234567890.0,
            size=1000,
            last_position=500
        )

        # save_state should call _save_cache
        monitor.save_state()

        # Verify cache file was created
        cache_file = cache_dir / "file_states.json"
        assert cache_file.exists()


class TestJSONLReader:
    """Test the JSONLReader class."""

    def test_jsonl_reader_init(self, temp_dir):
        """Test JSONLReader initialization."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        reader = JSONLReader(test_file)

        assert reader.file_path == test_file
        assert reader._position == 0

    def test_jsonl_reader_without_file_handle(self, temp_dir):
        """Test JSONLReader methods without file handle."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        reader = JSONLReader(test_file)

        # Try to seek without file handle
        reader.seek(10)  # Should do nothing
        assert reader._position == 0

        # Try to read without file handle
        lines = list(reader.read_lines())
        assert len(lines) == 0

    def test_jsonl_reader_context_manager(self, temp_dir):
        """Test JSONLReader as context manager."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        with JSONLReader(test_file) as reader:
            assert reader._file_handle is not None

        # File should be closed after exiting context
        assert reader._file_handle is None

    def test_jsonl_reader_read_lines(self, temp_dir):
        """Test reading lines from JSONL file."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_data = [
            {"id": 1, "value": "first"},
            {"id": 2, "value": "second"},
            {"id": 3, "value": "third"}
        ]

        with open(test_file, "w", encoding="utf-8") as f:
            for data in test_data:
                f.write(json.dumps(data) + "\n")

        with JSONLReader(test_file) as reader:
            lines = list(reader.read_lines())

        assert len(lines) == 3
        for i, (data, pos) in enumerate(lines):
            assert data["id"] == i + 1
            assert pos > 0

    def test_jsonl_reader_seek(self, temp_dir):
        """Test seeking to position in file."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        line1 = json.dumps({"line": 1})
        line2 = json.dumps({"line": 2})
        test_file.write_text(f"{line1}\n{line2}\n")

        with JSONLReader(test_file) as reader:
            # Read first line
            lines = list(reader.read_lines())
            assert len(lines) == 2

            # Seek back to start of second line
            reader.seek(len(line1) + 1)

            # Read from second line
            lines = list(reader.read_lines())
            assert len(lines) == 1
            assert lines[0][0]["line"] == 2

    def test_jsonl_reader_error_handling(self, temp_dir):
        """Test JSONLReader error handling."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        # Mix valid and invalid JSON
        test_file.write_text('{"valid": 1}\ninvalid json\n{"valid": 2}\n')

        with JSONLReader(test_file) as reader:
            lines = list(reader.read_lines())

        # Should skip the invalid line
        assert len(lines) == 2
        assert lines[0][0]["valid"] == 1
        assert lines[1][0]["valid"] == 2

    def test_jsonl_reader_non_dict_data(self, temp_dir):
        """Test JSONLReader with non-dict JSON data."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        # Mix dict and non-dict JSON
        test_file.write_text('{"valid": 1}\n["array", "data"]\n123\n{"valid": 2}\n')

        with JSONLReader(test_file) as reader:
            lines = list(reader.read_lines())

        # Should only return dict objects
        assert len(lines) == 2
        assert lines[0][0]["valid"] == 1
        assert lines[1][0]["valid"] == 2

    def test_jsonl_reader_empty_lines(self, temp_dir):
        """Test JSONLReader with empty lines."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"line": 1}\n\n\n{"line": 2}\n\n')

        with JSONLReader(test_file) as reader:
            lines = list(reader.read_lines())

        # Should skip empty lines
        assert len(lines) == 2
        assert lines[0][0]["line"] == 1
        assert lines[1][0]["line"] == 2

    def test_jsonl_reader_file_read_exception(self, temp_dir):
        """Test JSONLReader with file read exceptions."""
        from par_cc_usage.file_monitor import JSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"valid": 1}\n{"valid": 2}\n')

        with JSONLReader(test_file) as reader:
            # Mock the file handle to raise an exception
            original_readline = reader._file_handle.readline
            call_count = 0

            def mock_readline():
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise IOError("Simulated read error")
                return original_readline()

            reader._file_handle.readline = mock_readline

            lines = list(reader.read_lines())

        # Should handle read error and return first line only
        assert len(lines) == 1
        assert lines[0][0]["valid"] == 1


class TestAsyncJSONLReader:
    """Test the AsyncJSONLReader class."""

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_init(self, temp_dir):
        """Test AsyncJSONLReader initialization."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        reader = AsyncJSONLReader(test_file)

        assert reader.file_path == test_file
        assert reader._position == 0

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_context_manager(self, temp_dir):
        """Test AsyncJSONLReader as async context manager."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        async with AsyncJSONLReader(test_file) as reader:
            assert reader._file_handle is not None

        # File should be closed after exiting context
        assert reader._file_handle is None

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_read_lines(self, temp_dir):
        """Test reading lines from JSONL file asynchronously."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        test_data = [
            {"id": 1, "value": "first"},
            {"id": 2, "value": "second"},
            {"id": 3, "value": "third"}
        ]

        with open(test_file, "w", encoding="utf-8") as f:
            for data in test_data:
                f.write(json.dumps(data) + "\n")

        async with AsyncJSONLReader(test_file) as reader:
            lines = []
            async for line_data, pos in reader.read_lines():
                lines.append((line_data, pos))

        assert len(lines) == 3
        for i, (data, pos) in enumerate(lines):
            assert data["id"] == i + 1
            assert pos > 0

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_seek(self, temp_dir):
        """Test seeking to position in file asynchronously."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        line1 = json.dumps({"line": 1})
        line2 = json.dumps({"line": 2})
        test_file.write_text(f"{line1}\n{line2}\n")

        async with AsyncJSONLReader(test_file) as reader:
            # Read all lines first
            all_lines = []
            async for line_data, pos in reader.read_lines():
                all_lines.append((line_data, pos))
            assert len(all_lines) == 2

            # Seek back to start of second line
            await reader.seek(len(line1) + 1)

            # Read from second line
            second_lines = []
            async for line_data, pos in reader.read_lines():
                second_lines.append((line_data, pos))
            assert len(second_lines) == 1
            assert second_lines[0][0]["line"] == 2

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_error_handling(self, temp_dir):
        """Test AsyncJSONLReader error handling."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        # Mix valid and invalid JSON
        test_file.write_text('{"valid": 1}\ninvalid json\n{"valid": 2}\n')

        async with AsyncJSONLReader(test_file) as reader:
            lines = []
            async for line_data, pos in reader.read_lines():
                lines.append((line_data, pos))

        # Should skip the invalid line
        assert len(lines) == 2
        assert lines[0][0]["valid"] == 1
        assert lines[1][0]["valid"] == 2

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_without_file_handle(self, temp_dir):
        """Test AsyncJSONLReader methods without file handle."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        reader = AsyncJSONLReader(test_file)

        # Try to seek without file handle
        await reader.seek(10)  # Should do nothing
        assert reader._position == 0

        # Try to read without file handle
        lines = []
        async for line in reader.read_lines():
            lines.append(line)
        assert len(lines) == 0

    @pytest.mark.asyncio
    async def test_async_jsonl_reader_non_dict_data(self, temp_dir):
        """Test AsyncJSONLReader with non-dict JSON data."""
        from par_cc_usage.file_monitor import AsyncJSONLReader

        test_file = temp_dir / "test.jsonl"
        # Mix dict and non-dict JSON
        test_file.write_text('{"valid": 1}\n["array", "data"]\n123\n{"valid": 2}\n')

        async with AsyncJSONLReader(test_file) as reader:
            lines = []
            async for line_data, pos in reader.read_lines():
                lines.append((line_data, pos))

        # Should only return dict objects
        assert len(lines) == 2
        assert lines[0][0]["valid"] == 1
        assert lines[1][0]["valid"] == 2


class TestFileWatcher:
    """Test the FileWatcher class."""

    def test_file_watcher_init(self, temp_dir):
        """Test FileWatcher initialization."""
        from par_cc_usage.file_monitor import FileWatcher

        callback = Mock()
        watcher = FileWatcher([temp_dir], callback)

        assert watcher.projects_dirs == [temp_dir]
        assert watcher.callback == callback
        assert watcher.observer is not None

    @patch('par_cc_usage.file_monitor.Observer')
    def test_file_watcher_start_stop(self, mock_observer_class, temp_dir):
        """Test FileWatcher start and stop."""
        from par_cc_usage.file_monitor import FileWatcher

        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer

        callback = Mock()
        watcher = FileWatcher([temp_dir], callback)

        # Start watcher
        watcher.start()
        mock_observer.start.assert_called_once()

        # Stop watcher
        watcher.stop()
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    def test_file_watcher_context_manager(self, temp_dir):
        """Test FileWatcher as context manager."""
        from par_cc_usage.file_monitor import FileWatcher

        callback = Mock()

        with patch('par_cc_usage.file_monitor.Observer'):
            with FileWatcher([temp_dir], callback) as watcher:
                assert watcher is not None

    def test_file_watcher_nonexistent_dirs(self, temp_dir):
        """Test FileWatcher with non-existent directories."""
        from par_cc_usage.file_monitor import FileWatcher

        nonexistent_dir = temp_dir / "does_not_exist"
        callback = Mock()

        with patch('par_cc_usage.file_monitor.Observer') as mock_observer_class:
            mock_observer = Mock()
            mock_observer.emitters = []  # No directories being watched
            mock_observer_class.return_value = mock_observer

            watcher = FileWatcher([nonexistent_dir], callback)

            # Should create observer but not schedule any directories
            assert watcher.observer is not None

            # Start should not call observer.start() when no emitters
            watcher.start()
            mock_observer.start.assert_not_called()

            # Stop should still work
            watcher.stop()
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

    @patch('par_cc_usage.file_monitor.Observer')
    def test_file_watcher_mixed_dirs(self, mock_observer_class, temp_dir):
        """Test FileWatcher with mix of existing and non-existing directories."""
        from par_cc_usage.file_monitor import FileWatcher

        mock_observer = Mock()
        mock_observer.emitters = [Mock()]  # Simulate having at least one watched dir
        mock_observer_class.return_value = mock_observer

        existing_dir = temp_dir / "exists"
        existing_dir.mkdir()
        nonexistent_dir = temp_dir / "does_not_exist"

        callback = Mock()
        watcher = FileWatcher([existing_dir, nonexistent_dir], callback)

        watcher.start()

        # Should have scheduled only the existing directory
        assert mock_observer.schedule.call_count == 1
        mock_observer.schedule.assert_called_with(
            watcher.handler, str(existing_dir), recursive=True
        )

        watcher.stop()


class TestFileChangeHandler:
    """Test the FileChangeHandler class."""

    def test_file_change_handler_init(self):
        """Test FileChangeHandler initialization."""
        from par_cc_usage.file_monitor import FileChangeHandler

        callback = Mock()
        handler = FileChangeHandler(callback)

        assert handler.callback == callback

    def test_on_modified_jsonl_file(self):
        """Test handling modification of JSONL file."""
        from par_cc_usage.file_monitor import FileChangeHandler

        callback = Mock()
        handler = FileChangeHandler(callback)

        # Create mock event for JSONL file
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.jsonl"

        handler.on_modified(event)

        callback.assert_called_once_with(Path("/path/to/file.jsonl"))

    def test_on_modified_non_jsonl_file(self):
        """Test handling modification of non-JSONL file."""
        from par_cc_usage.file_monitor import FileChangeHandler

        callback = Mock()
        handler = FileChangeHandler(callback)

        # Create mock event for non-JSONL file
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.txt"

        handler.on_modified(event)

        # Should not call callback for non-JSONL files
        callback.assert_not_called()

    def test_on_modified_directory(self):
        """Test handling modification of directory."""
        from par_cc_usage.file_monitor import FileChangeHandler

        callback = Mock()
        handler = FileChangeHandler(callback)

        # Create mock event for directory
        event = Mock()
        event.is_directory = True
        event.src_path = "/path/to/dir"

        handler.on_modified(event)

        # Should not call callback for directories
        callback.assert_not_called()

    def test_on_created_jsonl_file(self):
        """Test handling creation of JSONL file."""
        from par_cc_usage.file_monitor import FileChangeHandler

        callback = Mock()
        handler = FileChangeHandler(callback)

        # Create mock event for new JSONL file
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/new.jsonl"

        handler.on_created(event)

        callback.assert_called_once_with(Path("/path/to/new.jsonl"))


class TestPollFiles:
    """Test the poll_files function."""

    @patch('par_cc_usage.file_monitor.time.sleep')
    def test_poll_files_basic(self, mock_sleep, temp_dir):
        """Test basic poll_files functionality."""
        from par_cc_usage.file_monitor import poll_files, FileMonitor, FileState

        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        # Create project directory structure
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir)
        callback = Mock()

        # Create a test file in project structure
        test_file = project_dir / "test.jsonl"
        test_file.write_text('{"test": 1}\n')

        # Set up mock to raise KeyboardInterrupt after first iteration
        mock_sleep.side_effect = KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            poll_files(monitor, callback, interval=1)

        # Should have called callback for the modified file
        assert callback.call_count == 1
        callback.assert_called_with(test_file, monitor.file_states[test_file])

    @patch('par_cc_usage.file_monitor.time.sleep')
    def test_poll_files_save_state(self, mock_sleep, temp_dir):
        """Test that poll_files saves state."""
        from par_cc_usage.file_monitor import poll_files, FileMonitor

        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir, disable_cache=False)
        callback = Mock()

        # Mock save_state to verify it's called
        monitor.save_state = Mock()

        # Set up mock to raise KeyboardInterrupt after first iteration
        mock_sleep.side_effect = KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            poll_files(monitor, callback, interval=1)

        # Should have saved state
        monitor.save_state.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions in file_monitor module."""

    def test_parse_session_from_path(self):
        """Test parsing session info from file path."""
        from par_cc_usage.file_monitor import parse_session_from_path

        # Test with prefixes
        path1 = Path("/home/user/.claude/projects/-Users-john-project/file.jsonl")
        session_id, project = parse_session_from_path(
            path1,
            Path("/home/user/.claude/projects"),
            project_name_prefixes=["-Users-john-"]
        )
        assert session_id == "file"
        assert project == "project"

        # Test without prefixes
        path2 = Path("/home/user/.claude/projects/my-project/session.jsonl")
        session_id, project = parse_session_from_path(
            path2,
            Path("/home/user/.claude/projects")
        )
        assert session_id == "session"
        assert project == "my-project"

        # Test with non-relative path (ValueError case)
        path3 = Path("/different/path/file.jsonl")
        session_id, project = parse_session_from_path(
            path3,
            Path("/home/user/.claude/projects")
        )
        assert session_id == "unknown"
        assert project == "Unknown Project"

        # Test with insufficient parts (single part)
        path4 = Path("/home/user/.claude/projects/file.jsonl")
        session_id, project = parse_session_from_path(
            path4,
            Path("/home/user/.claude/projects")
        )
        # When parts length is 1 (just "file.jsonl"), function returns fallback
        assert session_id == "unknown"
        assert project == "Unknown Project"

    def test_strip_project_name_prefixes(self):
        """Test stripping prefixes from project names."""
        from par_cc_usage.file_monitor import _strip_project_name_prefixes

        # Test basic prefix stripping
        result = _strip_project_name_prefixes(
            "-Users-john-my-project",
            ["-Users-john-"]
        )
        assert result == "my-project"

        # Test with multiple prefixes (longest first)
        result = _strip_project_name_prefixes(
            "-Users-john-doe-project",
            ["-Users-", "-Users-john-", "-Users-john-doe-"]
        )
        assert result == "project"

        # Test when stripping would remove everything
        result = _strip_project_name_prefixes(
            "-Users-john-",
            ["-Users-john-"]
        )
        assert result == "-Users-john-"

        # Test with no matching prefix
        result = _strip_project_name_prefixes(
            "my-project",
            ["-Users-", "-Home-"]
        )
        assert result == "my-project"


class TestFileStateHandling:
    """Test FileState handling and edge cases."""

    def test_file_state_comparison(self):
        """Test FileState comparison and updates."""
        from par_cc_usage.file_monitor import FileState

        state1 = FileState(
            path=Path("/test/file.jsonl"),
            mtime=1000.0,
            size=1000,
            last_position=500
        )

        state2 = FileState(
            path=Path("/test/file.jsonl"),
            mtime=2000.0,
            size=1500,
            last_position=500
        )

        # Different mtime means file was modified
        assert state2.mtime > state1.mtime
        assert state2.size > state1.size

    def test_get_modified_files_new_file(self, temp_dir):
        """Test detecting new files as modified."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        monitor = FileMonitor([temp_dir], cache_dir)

        # Create project directory structure
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        # Create a new file in proper structure
        new_file = project_dir / "new.jsonl"
        new_file.write_text('{"new": true}\n')

        modified = monitor.get_modified_files()

        # New file should be detected as modified
        assert len(modified) > 0
        assert any(f[0] == new_file for f in modified)

    def test_cache_corruption_handling(self, temp_dir):
        """Test handling corrupted cache file."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "file_states.json"

        # Write corrupted JSON
        cache_file.write_text("corrupted json data")

        # Should not crash when loading corrupted cache
        monitor = FileMonitor([temp_dir], cache_dir)

        # Should have empty file states due to corrupted cache
        assert monitor.file_states == {}

    def test_file_modified_detection(self, temp_dir):
        """Test detecting file modifications by size change."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        # Create project directory structure
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        jsonl_file = project_dir / "test.jsonl"
        jsonl_file.write_text('{"initial": true}\n')

        monitor = FileMonitor([temp_dir], cache_dir)

        # First check - new file
        modified = monitor.get_modified_files()
        assert len(modified) == 1
        assert modified[0][0] == jsonl_file

        # Append to file (size change)
        with open(jsonl_file, "a", encoding="utf-8") as f:
            f.write('{"appended": true}\n')

        # Should detect modification
        modified = monitor.get_modified_files()
        assert len(modified) == 1
        assert modified[0][0] == jsonl_file

    def test_file_inaccessible_handling(self, temp_dir):
        """Test handling inaccessible files."""
        monitor = FileMonitor([temp_dir], temp_dir / "cache")

        # Add a fake file state for a non-existent file
        fake_path = temp_dir / "nonexistent.jsonl"
        monitor.file_states[fake_path] = FileState(
            path=fake_path,
            mtime=1234567890.0,
            size=1000,
            last_position=0
        )

        # scan_files won't find it, but get_modified_files should handle gracefully
        modified = monitor.get_modified_files()

        # Should return empty list (file doesn't exist)
        assert len(modified) == 0
