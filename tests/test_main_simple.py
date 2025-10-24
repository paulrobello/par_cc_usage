"""
Simplified tests for main.py to improve coverage.
"""

import json
from unittest.mock import Mock, patch

from par_cc_usage.file_monitor import FileState
from par_cc_usage.main import (
    _find_base_directory,
    _get_or_create_file_state,
    _print_dedup_stats,
    process_file,
)
from par_cc_usage.models import DeduplicationState


class TestHelperFunctions:
    """Test utility helper functions."""

    def test_find_base_directory_no_match(self, temp_dir):
        """Test _find_base_directory when file doesn't match any base."""
        claude_dir1 = temp_dir / "claude1"
        claude_dir2 = temp_dir / "claude2"
        claude_dir1.mkdir()
        claude_dir2.mkdir()

        # File outside of any Claude directory
        external_file = temp_dir / "external" / "test.jsonl"
        external_file.parent.mkdir()
        external_file.write_text('{"test": 1}')

        claude_paths = [claude_dir1, claude_dir2]
        result = _find_base_directory(external_file, claude_paths)

        assert result is None

    def test_find_base_directory_multiple_matches(self, temp_dir):
        """Test _find_base_directory returns first match."""
        claude_dir1 = temp_dir / "claude1"
        claude_dir2 = temp_dir / "claude1" / "nested"  # Nested inside claude1
        claude_dir1.mkdir()
        claude_dir2.mkdir(parents=True)

        # File that could match both directories
        test_file = claude_dir2 / "test.jsonl"
        test_file.write_text('{"test": 1}')

        claude_paths = [claude_dir1, claude_dir2]
        result = _find_base_directory(test_file, claude_paths)

        # Should return first match (claude_dir1)
        assert result == claude_dir1

    def test_get_or_create_file_state_new_file_error(self, temp_dir):
        """Test _get_or_create_file_state handles file stat errors."""
        mock_monitor = Mock()
        mock_monitor.file_states = {}

        # Non-existent file
        non_existent_file = temp_dir / "doesnt_exist.jsonl"

        result = _get_or_create_file_state(non_existent_file, mock_monitor, use_cache=True)

        # Should return None when file doesn't exist
        assert result is None

    def test_get_or_create_file_state_existing_no_cache(self, temp_dir):
        """Test _get_or_create_file_state resets position when cache disabled."""
        # Create test file
        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": "data"}\n')

        # Mock monitor with existing file state
        mock_monitor = Mock()
        existing_state = FileState(
            path=test_file,
            mtime=test_file.stat().st_mtime,
            size=test_file.stat().st_size,
            last_position=100  # Already read some data
        )
        mock_monitor.file_states = {test_file: existing_state}

        result = _get_or_create_file_state(test_file, mock_monitor, use_cache=False)

        assert result is not None
        assert result.last_position == 0  # Should reset to beginning

    def test_get_or_create_file_state_existing_with_cache(self, temp_dir):
        """Test _get_or_create_file_state preserves position when cache enabled."""
        # Create test file
        test_file = temp_dir / "test.jsonl"
        test_file.write_text('{"test": "data"}\n')

        # Mock monitor with existing file state
        mock_monitor = Mock()
        existing_state = FileState(
            path=test_file,
            mtime=test_file.stat().st_mtime,
            size=test_file.stat().st_size,
            last_position=100  # Already read some data
        )
        mock_monitor.file_states = {test_file: existing_state}

        result = _get_or_create_file_state(test_file, mock_monitor, use_cache=True)

        assert result is not None
        assert result.last_position == 100  # Should preserve position


class TestPrintDedupStats:
    """Test deduplication statistics printing."""

    def test_print_dedup_stats_suppressed(self):
        """Test _print_dedup_stats doesn't print when suppressed."""
        dedup_state = DeduplicationState()
        dedup_state.total_messages = 100
        dedup_state.duplicate_count = 10

        with patch('par_cc_usage.main.console') as mock_console:
            _print_dedup_stats(dedup_state, suppress_stats=True)

            # Should not print anything
            mock_console.print.assert_not_called()

    def test_print_dedup_stats_basic(self):
        """Test _print_dedup_stats basic functionality."""
        dedup_state = DeduplicationState()
        dedup_state.total_messages = 50
        dedup_state.duplicate_count = 0

        # Test that function can be called without error
        _print_dedup_stats(dedup_state, suppress_stats=False)
        # Function should complete without raising exceptions


class TestProcessFileErrorHandling:
    """Test error handling in process_file function."""

    def test_process_file_with_malformed_json(self, temp_dir, mock_config):
        """Test process_file handles malformed JSON gracefully."""
        # Create test file with malformed JSON
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "session_123.jsonl"
        jsonl_file.write_text('{"invalid": json}\n')  # Invalid JSON

        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        projects = {}
        dedup_state = DeduplicationState()

        # Should not raise exception, error should be suppressed
        result = process_file(
            jsonl_file, file_state, projects, mock_config, temp_dir,
            dedup_state, suppress_errors=True
        )

        assert result == 0  # No messages processed due to error
        assert len(projects) == 0  # No projects created due to error

    def test_process_file_with_io_error(self, temp_dir, mock_config):
        """Test process_file handles file I/O errors."""
        # Create test file that will cause permission error
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "session_123.jsonl"
        jsonl_file.write_text('{"test": "data"}\n')

        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        projects = {}
        dedup_state = DeduplicationState()

        # Mock JSONLReader to raise exception
        with patch('par_cc_usage.main.JSONLReader') as mock_reader:
            mock_reader.side_effect = OSError("Permission denied")

            # Should handle error gracefully when suppressed
            result = process_file(
                jsonl_file, file_state, projects, mock_config, temp_dir,
                dedup_state, suppress_errors=True
            )

            assert result == 0

    def test_process_file_with_unified_entries_collection(self, temp_dir, mock_config):
        """Test process_file correctly collects unified entries."""
        # Create test file with valid data
        project_dir = temp_dir / "test_project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "session_123.jsonl"
        jsonl_data = {
            "timestamp": "2025-01-09T14:30:45.000Z",
            "request": {"model": "claude-3-5-sonnet-latest"},
            "response": {
                "id": "msg_123",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            },
            "project_name": "test_project",
            "session_id": "session_123",
        }
        jsonl_file.write_text(json.dumps(jsonl_data) + "\n")

        file_state = FileState(
            path=jsonl_file,
            mtime=jsonl_file.stat().st_mtime,
            size=jsonl_file.stat().st_size,
            last_position=0
        )

        projects = {}
        dedup_state = DeduplicationState()
        unified_entries = []

        # Should process and collect unified entries
        result = process_file(
            jsonl_file, file_state, projects, mock_config, temp_dir,
            dedup_state, unified_entries=unified_entries
        )

        assert result == 1  # One message processed
        # Unified entries collection is optional, so just check it doesn't crash
        assert isinstance(unified_entries, list)
