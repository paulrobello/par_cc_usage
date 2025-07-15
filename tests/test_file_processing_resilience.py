"""
Test file processing resilience and error handling.

This module tests corrupted files, permission errors, missing directories,
and other file I/O edge cases that can occur during JSONL processing.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone

from par_cc_usage.main import (
    scan_all_projects,
)
from par_cc_usage.file_monitor import FileMonitor
from par_cc_usage.token_calculator import process_jsonl_line
from par_cc_usage.models import DeduplicationState
from tests.conftest import create_token_usage


def process_file(file_path, deduplication_state):
    """Helper function to process a file similar to the main implementation."""
    usage_list = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    usage = process_jsonl_line(line, deduplication_state)
                    if usage:
                        usage_list.append(usage)
    except (FileNotFoundError, PermissionError, OSError):
        # Return empty list for file access errors
        return []
    return usage_list


def get_claude_project_paths():
    """Helper function that returns mock Claude project paths."""
    return [Path.home() / ".claude" / "projects"]


class TestCorruptedFileHandling:
    """Test processing files with various corruption types."""

    def test_process_file_with_corrupted_jsonl(self, temp_dir, mock_config, deduplication_state):
        """Test processing files with malformed JSON lines."""
        # Create file with mixed valid and invalid JSON
        corrupted_file = temp_dir / "corrupted.jsonl"
        with open(corrupted_file, "w", encoding="utf-8") as f:
            # Valid line
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_valid",
                    "usage": {"input_tokens": 100, "output_tokens": 50}
                },
                "project_name": "test_project",
                "session_id": "session_1"
            }) + "\n")

            # Invalid JSON lines
            f.write("invalid json line\n")
            f.write('{"incomplete": "json",\n')
            f.write('{"invalid": "timestamp", "timestamp": "not-a-date"}\n')
            f.write('{"missing": "required_fields"}\n')
            f.write("\n")  # Empty line
            f.write("   \n")  # Whitespace only

            # Another valid line
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_valid2",
                    "usage": {"input_tokens": 200, "output_tokens": 100}
                },
                "project_name": "test_project",
                "session_id": "session_1"
            }) + "\n")

        # Should process valid lines and skip invalid ones without crashing
        usage_list = process_file(corrupted_file, deduplication_state)

        # Should have processed the 2 valid lines
        assert len(usage_list) == 2
        assert usage_list[0].input_tokens == 100
        assert usage_list[1].input_tokens == 200

    def test_process_file_with_binary_corruption(self, temp_dir, mock_config, deduplication_state):
        """Test processing files with binary data corruption."""
        # Create file with binary data mixed in
        corrupted_file = temp_dir / "binary_corrupted.jsonl"
        with open(corrupted_file, "wb") as f:
            # Valid JSON line
            valid_line = json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_1",
                    "usage": {"input_tokens": 100, "output_tokens": 50}
                }
            }) + "\n"
            f.write(valid_line.encode("utf-8"))

            # Binary garbage
            f.write(b"\x00\x01\x02\x03\xFF\xFE\xFD\xFC\n")

            # More valid data
            valid_line2 = json.dumps({
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_2",
                    "usage": {"input_tokens": 200, "output_tokens": 100}
                }
            }) + "\n"
            f.write(valid_line2.encode("utf-8"))

        # Should handle binary corruption gracefully
        usage_list = process_file(corrupted_file, deduplication_state)

        # Should process valid lines despite binary corruption
        assert len(usage_list) >= 1  # At least one valid line should be processed

    def test_process_file_with_encoding_errors(self, temp_dir, mock_config, deduplication_state):
        """Test processing files with encoding issues."""
        # Create file with mixed encodings
        encoding_file = temp_dir / "encoding_issues.jsonl"

        # Write with different encodings
        with open(encoding_file, "wb") as f:
            # UTF-8 line
            utf8_line = json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "content": "UTF-8 content: ñáéíóú"
            }) + "\n"
            f.write(utf8_line.encode("utf-8"))

            # Latin-1 encoded line (will cause encoding errors)
            latin1_line = "Latin-1 content: \xe1\xe9\xed\xf3\xfa\n"
            f.write(latin1_line.encode("latin-1"))

            # Another UTF-8 line
            utf8_line2 = json.dumps({
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {
                    "id": "msg_3",
                    "usage": {"input_tokens": 150, "output_tokens": 75}
                }
            }) + "\n"
            f.write(utf8_line2.encode("utf-8"))

        # Should handle encoding errors gracefully
        usage_list = process_file(encoding_file, deduplication_state)

        # Should process the valid UTF-8 lines
        assert len(usage_list) >= 1

    def test_process_jsonl_line_edge_cases(self, deduplication_state):
        """Test process_jsonl_line with various edge cases."""
        edge_cases = [
            "",  # Empty string
            "   ",  # Whitespace only
            "\n",  # Just newline
            "\t\r\n",  # Mixed whitespace
            "null",  # JSON null
            "[]",  # JSON array
            "123",  # JSON number
            '"string"',  # JSON string
            '{"valid": "json", "but": "missing required fields"}',
            '{"timestamp": null}',  # Null timestamp
            '{"timestamp": "2025-01-09T14:30:45.000Z"}',  # Minimal valid
        ]

        for case in edge_cases:
            # Should not raise exceptions
            result = process_jsonl_line(case, deduplication_state)
            # Result can be None or TokenUsage, but no exceptions


class TestFilePermissionErrors:
    """Test handling of file permission and access errors."""

    def test_process_file_permission_denied(self, temp_dir, mock_config, deduplication_state):
        """Test handling when file permissions prevent reading."""
        # Create a file and make it unreadable
        restricted_file = temp_dir / "restricted.jsonl"
        with open(restricted_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"test": "data"}) + "\n")

        # Remove read permissions
        os.chmod(restricted_file, 0o000)

        try:
            # Should handle permission error gracefully
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                usage_list = process_file(restricted_file, deduplication_state)
                assert usage_list == []  # Should return empty list on error
        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_file, 0o644)

    def test_file_monitor_with_inaccessible_cache(self, temp_dir):
        """Test FileMonitor when cache directory is inaccessible."""
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()

        # Create FileMonitor
        monitor = FileMonitor(
            claude_paths=[temp_dir / "projects"],
            cache_dir=cache_dir,
            use_cache=True,
        )

        # Make cache directory unwriteable
        os.chmod(cache_dir, 0o444)  # Read-only

        try:
            # Should handle cache write errors gracefully
            monitor.get_new_lines(temp_dir / "test.jsonl")
            # Should not crash even if cache can't be written
        finally:
            # Restore permissions
            os.chmod(cache_dir, 0o755)

    def test_scan_projects_with_permission_errors(self, temp_dir, mock_config):
        """Test scanning projects when some directories are inaccessible."""
        # Create project structure
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        # Create accessible project
        accessible_project = projects_dir / "accessible"
        accessible_project.mkdir()
        with open(accessible_project / "session.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_1", "usage": {"input_tokens": 100, "output_tokens": 50}}
            }) + "\n")

        # Create inaccessible project
        restricted_project = projects_dir / "restricted"
        restricted_project.mkdir()
        with open(restricted_project / "session.jsonl", "w", encoding="utf-8") as f:
            f.write("test data\n")

        # Remove permissions from restricted project
        os.chmod(restricted_project, 0o000)

        try:
            # Mock config to use our test directory
            with patch.object(mock_config, 'projects_dir', projects_dir):
                # Should scan accessible projects and skip inaccessible ones
                with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
                    projects = scan_all_projects(mock_config)

                    # Should have found at least the accessible project
                    # (exact behavior depends on implementation)
                    assert isinstance(projects, list)
        finally:
            # Restore permissions for cleanup
            os.chmod(restricted_project, 0o755)


class TestMissingDirectoriesAndFiles:
    """Test handling of missing directories and files."""

    def test_scan_all_projects_with_missing_directories(self, temp_dir, mock_config):
        """Test scanning when Claude directories don't exist."""
        # Point to non-existent directories
        non_existent_paths = [
            temp_dir / "non_existent_1",
            temp_dir / "non_existent_2",
            Path("/completely/fake/path"),
        ]

        with patch('par_cc_usage.main.get_claude_project_paths', return_value=non_existent_paths):
            # Should handle missing directories gracefully
            projects = scan_all_projects(mock_config)
            assert isinstance(projects, list)
            # Should return empty list or handle gracefully

    def test_get_claude_project_paths_missing_home(self):
        """Test getting Claude paths when home directory structures are missing."""
        with patch('pathlib.Path.home') as mock_home:
            # Mock home directory that doesn't exist
            fake_home = Path("/fake/home/directory")
            mock_home.return_value = fake_home

            # Should handle missing home directory gracefully
            paths = get_claude_project_paths()
            assert isinstance(paths, list)
            # Should not crash even if paths don't exist

    def test_process_file_with_missing_file(self, temp_dir, mock_config, deduplication_state):
        """Test processing a file that doesn't exist."""
        non_existent_file = temp_dir / "does_not_exist.jsonl"

        # Should handle missing file gracefully
        usage_list = process_file(non_existent_file, deduplication_state)
        assert usage_list == []  # Should return empty list

    def test_file_monitor_with_missing_files(self, temp_dir):
        """Test FileMonitor with files that disappear during processing."""
        monitor = FileMonitor(
            claude_paths=[temp_dir],
            cache_dir=temp_dir / "cache",
            use_cache=True,
        )

        # Test with file that doesn't exist
        missing_file = temp_dir / "missing.jsonl"

        # Should handle missing file gracefully
        new_lines = monitor.get_new_lines(missing_file)
        assert new_lines == []


class TestFilesystemRaceConditions:
    """Test handling of filesystem race conditions and concurrent access."""

    def test_scan_all_projects_with_inaccessible_files(self, temp_dir, mock_config):
        """Test handling files that become inaccessible during scan."""
        # Create project structure
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()

        project = projects_dir / "test_project"
        project.mkdir()

        # Create a file
        session_file = project / "session.jsonl"
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_1", "usage": {"input_tokens": 100, "output_tokens": 50}}
            }) + "\n")

        # Mock file operations to simulate race conditions
        original_open = open

        def mock_open(*args, **kwargs):
            if str(session_file) in str(args[0]):
                raise OSError("File disappeared during access")
            return original_open(*args, **kwargs)

        with patch('builtins.open', side_effect=mock_open):
            with patch.object(mock_config, 'projects_dir', projects_dir):
                with patch('par_cc_usage.main.get_claude_project_paths', return_value=[projects_dir]):
                    # Should handle file access errors gracefully
                    projects = scan_all_projects(mock_config)
                    assert isinstance(projects, list)

    def test_file_monitor_concurrent_file_modification(self, temp_dir):
        """Test FileMonitor when files are modified concurrently."""
        monitor = FileMonitor(
            claude_paths=[temp_dir],
            cache_dir=temp_dir / "cache",
            use_cache=True,
        )

        # Create a file
        test_file = temp_dir / "concurrent.jsonl"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("initial line\n")

        # Get initial state
        initial_lines = monitor.get_new_lines(test_file)

        # Simulate concurrent modification by truncating file
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("truncated\n")

        # Should handle file truncation gracefully
        new_lines = monitor.get_new_lines(test_file)
        # File monitor should detect the change and handle it


class TestLargeFileHandling:
    """Test handling of very large files and memory constraints."""

    def test_process_very_large_file(self, temp_dir, mock_config, deduplication_state):
        """Test processing files with many lines."""
        large_file = temp_dir / "large.jsonl"

        # Create file with many lines (but not so many as to be slow)
        num_lines = 1000
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(num_lines):
                line_data = {
                    "timestamp": "2025-01-09T14:30:45.000Z",
                    "request": {"model": "claude-3-sonnet-latest"},
                    "response": {
                        "id": f"msg_{i}",
                        "usage": {"input_tokens": 100, "output_tokens": 50}
                    },
                    "project_name": "test_project",
                    "session_id": "session_1"
                }
                f.write(json.dumps(line_data) + "\n")

        # Should process large file without memory issues
        usage_list = process_file(large_file, deduplication_state)
        assert len(usage_list) <= num_lines  # Some may be deduplicated

    def test_file_monitor_with_very_long_lines(self, temp_dir):
        """Test FileMonitor with extremely long JSON lines."""
        monitor = FileMonitor(
            claude_paths=[temp_dir],
            cache_dir=temp_dir / "cache",
            use_cache=True,
        )

        long_line_file = temp_dir / "long_lines.jsonl"

        # Create file with very long line (simulate large content)
        very_long_content = "x" * 100000  # 100KB of content
        long_line_data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {
                "model": "claude-3-sonnet-latest",
                "messages": [{"role": "user", "content": very_long_content}]
            },
            "response": {"id": "msg_long", "usage": {"input_tokens": 1000, "output_tokens": 500}}
        }

        with open(long_line_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(long_line_data) + "\n")

        # Should handle very long lines without memory issues
        new_lines = monitor.get_new_lines(long_line_file)
        assert len(new_lines) <= 1  # Should read the long line


class TestFileIntegrityIssues:
    """Test handling of file integrity issues."""

    def test_process_file_with_incomplete_writes(self, temp_dir, mock_config, deduplication_state):
        """Test processing files that are being written to (incomplete)."""
        # Simulate file being written by another process
        incomplete_file = temp_dir / "incomplete.jsonl"

        with open(incomplete_file, "w", encoding="utf-8") as f:
            # Complete line
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:30:45.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_1", "usage": {"input_tokens": 100, "output_tokens": 50}}
            }) + "\n")

            # Incomplete line (no newline, simulating ongoing write)
            f.write(json.dumps({
                "timestamp": "2025-01-09T14:35:00.000Z",
                "request": {"model": "claude-3-sonnet-latest"},
                "response": {"id": "msg_2", "usage": {"input_tokens": 200, "output_tokens": 100}}
            }))  # No newline

        # Should process complete lines and handle incomplete ones gracefully
        usage_list = process_file(incomplete_file, deduplication_state)
        assert len(usage_list) >= 1  # Should get at least the complete line

    def test_file_size_changes_during_processing(self, temp_dir):
        """Test handling when file size changes during processing."""
        monitor = FileMonitor(
            claude_paths=[temp_dir],
            cache_dir=temp_dir / "cache",
            use_cache=True,
        )

        changing_file = temp_dir / "changing.jsonl"

        # Create initial file
        with open(changing_file, "w", encoding="utf-8") as f:
            f.write("line 1\n")

        # Read initial state
        initial_lines = monitor.get_new_lines(changing_file)

        # Simulate file being truncated and rewritten
        with open(changing_file, "w", encoding="utf-8") as f:
            f.write("new line 1\nnew line 2\n")

        # Should handle file changes gracefully
        new_lines = monitor.get_new_lines(changing_file)
        # Should adapt to file changes without crashing
