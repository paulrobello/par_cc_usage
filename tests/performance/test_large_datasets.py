"""
Performance tests for large datasets.

Tests system behavior with large amounts of data and memory constraints.
"""

import pytest
import json
import time
import gc
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from par_cc_usage.token_calculator import aggregate_usage, process_jsonl_line
from par_cc_usage.models import TokenUsage, DeduplicationState, UsageSnapshot
from par_cc_usage.display import MonitorDisplay
from par_cc_usage.config import Config


@pytest.mark.performance
class TestLargeDatasetPerformance:
    """Test performance with large datasets."""

    def test_large_jsonl_processing(self, temp_dir):
        """Test processing performance with large JSONL files."""
        # Create large JSONL file
        large_file = temp_dir / "large.jsonl"
        num_lines = 1000  # Moderate size for testing

        start_time = time.time()

        # Generate large file
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(num_lines):
                entry = {
                    "timestamp": f"2025-01-09T{14 + i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}.000Z",
                    "request": {"model": "claude-3-sonnet-latest"},
                    "response": {
                        "id": f"msg_{i}",
                        "usage": {
                            "input_tokens": 100 + (i % 1000),
                            "output_tokens": 50 + (i % 500)
                        }
                    },
                    "project_name": f"project_{i % 10}",
                    "session_id": f"session_{i % 50}"
                }
                f.write(json.dumps(entry) + "\n")

        creation_time = time.time() - start_time

        # Process the file
        dedup_state = DeduplicationState()
        usage_list = []

        processing_start = time.time()

        with open(large_file, "r", encoding="utf-8") as f:
            for line in f:
                usage = process_jsonl_line(line.strip(), dedup_state)
                if usage:
                    usage_list.append(usage)

        processing_time = time.time() - processing_start

        # Verify performance
        assert len(usage_list) == num_lines
        assert processing_time < 10.0  # Should process 1000 lines in under 10 seconds

        print(f"Created {num_lines} lines in {creation_time:.2f}s")
        print(f"Processed {num_lines} lines in {processing_time:.2f}s")
        print(f"Processing rate: {num_lines / processing_time:.1f} lines/second")

    def test_large_aggregation_performance(self, temp_dir):
        """Test aggregation performance with many usage entries."""
        # Create large number of usage entries
        num_entries = 5000
        usage_list = []
        base_time = datetime.now(timezone.utc)

        generation_start = time.time()

        for i in range(num_entries):
            usage = TokenUsage(
                input_tokens=100 + (i % 1000),
                output_tokens=50 + (i % 500),
                cache_creation_input_tokens=i % 100,
                cache_read_input_tokens=(i * 2) % 100,
                service_tier="standard",
                message_id=f"msg_{i}",
                request_id=f"req_{i}",
                timestamp=base_time + timedelta(seconds=i),
                model="claude-3-sonnet-latest",
                project_name=f"project_{i % 20}",  # 20 projects
                session_id=f"session_{i % 100}",  # 100 sessions
            )
            usage_list.append(usage)

        generation_time = time.time() - generation_start

        # Test aggregation performance
        config = Config()

        aggregation_start = time.time()
        snapshot = aggregate_usage(usage_list, config)
        aggregation_time = time.time() - aggregation_start

        # Verify results
        assert snapshot is not None
        assert len(snapshot.projects) <= 20

        # Check performance
        assert aggregation_time < 30.0  # Should aggregate 5000 entries in under 30 seconds

        print(f"Generated {num_entries} entries in {generation_time:.2f}s")
        print(f"Aggregated {num_entries} entries in {aggregation_time:.2f}s")
        print(f"Aggregation rate: {num_entries / aggregation_time:.1f} entries/second")

    def test_display_performance_with_large_data(self, temp_dir):
        """Test display performance with large datasets."""
        # Create large snapshot
        projects = {}
        base_time = datetime.now(timezone.utc)

        for proj_i in range(10):  # 10 projects
            sessions = {}
            for sess_i in range(20):  # 20 sessions per project
                from tests.conftest import create_block_with_tokens

                blocks = []
                for block_i in range(10):  # 10 blocks per session
                    block = create_block_with_tokens(
                        start_time=base_time + timedelta(hours=block_i),
                        session_id=f"session_{sess_i}",
                        project_name=f"project_{proj_i}",
                        token_count=1000 + block_i * 100,
                    )
                    blocks.append(block)

                from par_cc_usage.models import Session
                session = Session(
                    session_id=f"session_{sess_i}",
                    project_name=f"project_{proj_i}",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=base_time,
                    last_seen=base_time + timedelta(hours=10),
                    session_start=base_time,
                )
                sessions[f"session_{sess_i}"] = session

            from par_cc_usage.models import Project
            project = Project(name=f"project_{proj_i}", sessions=sessions)
            projects[f"project_{proj_i}"] = project

        snapshot = UsageSnapshot(
            timestamp=base_time,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        # Test display performance
        config = Config()
        display = MonitorDisplay(config.display, show_pricing=False)

        display_start = time.time()
        display.update(snapshot)
        display_time = time.time() - display_start

        # Should handle large display updates efficiently
        assert display_time < 5.0  # Should update display in under 5 seconds

        print(f"Display update with large data took {display_time:.2f}s")

    def test_memory_usage_with_large_datasets(self, temp_dir):
        """Test memory usage characteristics with large datasets."""
        # Get initial memory usage
        initial_memory = self._get_memory_usage()

        # Create large dataset
        num_entries = 2000
        usage_list = []
        base_time = datetime.now(timezone.utc)

        for i in range(num_entries):
            usage = TokenUsage(
                input_tokens=1000 + i,
                output_tokens=500 + i,
                model="claude-3-sonnet-latest",
                timestamp=base_time + timedelta(minutes=i),
                project_name=f"project_{i % 5}",
                session_id=f"session_{i % 25}",
            )
            usage_list.append(usage)

        after_creation_memory = self._get_memory_usage()

        # Aggregate data
        config = Config()
        snapshot = aggregate_usage(usage_list, config)

        after_aggregation_memory = self._get_memory_usage()

        # Clear references and force garbage collection
        del usage_list
        gc.collect()

        after_cleanup_memory = self._get_memory_usage()

        # Memory should be manageable
        creation_increase = after_creation_memory - initial_memory
        aggregation_increase = after_aggregation_memory - after_creation_memory
        cleanup_decrease = after_aggregation_memory - after_cleanup_memory

        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"After creation: {after_creation_memory:.1f} MB (+{creation_increase:.1f} MB)")
        print(f"After aggregation: {after_aggregation_memory:.1f} MB (+{aggregation_increase:.1f} MB)")
        print(f"After cleanup: {after_cleanup_memory:.1f} MB (-{cleanup_decrease:.1f} MB)")

        # Memory increases should be reasonable
        assert creation_increase < 100.0  # Less than 100MB for test data
        assert aggregation_increase < 50.0  # Aggregation shouldn't double memory
        assert cleanup_decrease > 0  # Should free some memory after cleanup

    def _get_memory_usage(self):
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            # Fallback to sys.getsizeof for rough estimation
            return sys.getsizeof({}) / 1024 / 1024


@pytest.mark.performance
class TestConcurrencyPerformance:
    """Test performance under concurrent access."""

    def test_concurrent_file_processing(self, temp_dir):
        """Test concurrent file processing performance."""
        import threading
        import queue

        # Create multiple files
        num_files = 5
        files = []

        for i in range(num_files):
            file_path = temp_dir / f"concurrent_{i}.jsonl"
            with open(file_path, "w", encoding="utf-8") as f:
                for j in range(200):  # 200 lines per file
                    entry = {
                        "timestamp": f"2025-01-09T14:{j // 60:02d}:{j % 60:02d}.000Z",
                        "request": {"model": "claude-3-sonnet-latest"},
                        "response": {
                            "id": f"msg_{i}_{j}",
                            "usage": {"input_tokens": 100 + j, "output_tokens": 50 + j}
                        },
                        "project_name": f"project_{i}",
                        "session_id": f"session_{i}"
                    }
                    f.write(json.dumps(entry) + "\n")
            files.append(file_path)

        # Process files concurrently
        results_queue = queue.Queue()

        def process_file(file_path):
            """Process a single file."""
            dedup_state = DeduplicationState()
            usage_list = []

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    usage = process_jsonl_line(line.strip(), dedup_state)
                    if usage:
                        usage_list.append(usage)

            results_queue.put((file_path.name, len(usage_list)))

        # Start concurrent processing
        threads = []
        start_time = time.time()

        for file_path in files:
            thread = threading.Thread(target=process_file, args=(file_path,))
            thread.start()
            threads.append(thread)

        # Wait for completion
        for thread in threads:
            thread.join()

        concurrent_time = time.time() - start_time

        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        # Verify results
        assert len(results) == num_files
        total_processed = sum(count for _, count in results)
        assert total_processed == num_files * 200

        print(f"Processed {num_files} files concurrently in {concurrent_time:.2f}s")
        print(f"Total entries processed: {total_processed}")

    def test_deduplication_performance(self, temp_dir):
        """Test deduplication performance with large datasets."""
        # Create data with duplicates
        num_entries = 3000
        num_unique = 1000  # 1/3 will be unique, rest duplicates

        usage_list = []
        base_time = datetime.now(timezone.utc)

        generation_start = time.time()

        for i in range(num_entries):
            unique_id = i % num_unique  # Creates duplicates
            usage = TokenUsage(
                input_tokens=100 + unique_id,
                output_tokens=50 + unique_id,
                message_id=f"msg_{unique_id}",  # Duplicate message IDs
                request_id=f"req_{unique_id}",  # Duplicate request IDs
                timestamp=base_time + timedelta(seconds=unique_id),
                model="claude-3-sonnet-latest",
                project_name="dedup_test",
                session_id="dedup_session",
            )
            usage_list.append(usage)

        generation_time = time.time() - generation_start

        # Test deduplication performance
        dedup_start = time.time()

        dedup_state = DeduplicationState()
        unique_usage = []

        for usage in usage_list:
            if dedup_state.add(usage.create_hash()):
                unique_usage.append(usage)

        dedup_time = time.time() - dedup_start

        # Verify deduplication worked
        assert len(unique_usage) == num_unique
        assert len(unique_usage) < len(usage_list)

        print(f"Generated {num_entries} entries in {generation_time:.2f}s")
        print(f"Deduplicated to {len(unique_usage)} unique entries in {dedup_time:.2f}s")
        print(f"Deduplication rate: {num_entries / dedup_time:.1f} entries/second")


@pytest.mark.performance
class TestMemoryStress:
    """Test system behavior under memory stress."""

    def test_memory_pressure_handling(self, temp_dir):
        """Test system behavior under memory pressure."""
        # Create progressively larger datasets
        sizes = [100, 500, 1000, 2000]

        for size in sizes:
            print(f"Testing with {size} entries...")

            # Create dataset
            usage_list = []
            base_time = datetime.now(timezone.utc)

            for i in range(size):
                usage = TokenUsage(
                    input_tokens=1000 + i,
                    output_tokens=500 + i,
                    model="claude-3-sonnet-latest",
                    timestamp=base_time + timedelta(minutes=i),
                    project_name=f"project_{i % 10}",
                    session_id=f"session_{i % 50}",
                )
                usage_list.append(usage)

            # Test aggregation under memory pressure
            config = Config()

            try:
                start_time = time.time()
                snapshot = aggregate_usage(usage_list, config)
                end_time = time.time()

                assert snapshot is not None
                print(f"  Aggregated {size} entries in {end_time - start_time:.2f}s")

            except MemoryError:
                print(f"  Memory error at {size} entries")
                break

            # Clean up
            del usage_list
            del snapshot
            gc.collect()

    def test_large_block_count_handling(self, temp_dir):
        """Test handling of sessions with many blocks."""
        from tests.conftest import create_block_with_tokens
        from par_cc_usage.models import Session, Project

        # Create session with many blocks
        num_blocks = 500
        base_time = datetime.now(timezone.utc)

        blocks = []
        for i in range(num_blocks):
            block = create_block_with_tokens(
                start_time=base_time + timedelta(hours=i),
                session_id="large_session",
                project_name="large_project",
                token_count=1000 + i,
            )
            blocks.append(block)

        # Create session and project
        session = Session(
            session_id="large_session",
            project_name="large_project",
            model="claude-3-sonnet-latest",
            blocks=blocks,
            first_seen=base_time,
            last_seen=base_time + timedelta(hours=num_blocks),
            session_start=base_time,
        )

        project = Project(
            name="large_project",
            sessions={"large_session": session},
        )

        # Test creation and access performance
        start_time = time.time()

        # Test various operations
        total_tokens = sum(block.token_usage.total_tokens for block in session.blocks)
        active_blocks = [block for block in session.blocks if not hasattr(block, 'is_active') or block.is_active]

        end_time = time.time()

        assert total_tokens > 0
        assert len(session.blocks) == num_blocks

        print(f"Handled {num_blocks} blocks in {end_time - start_time:.2f}s")
        print(f"Total tokens: {total_tokens}")

    def test_unified_block_calculation_performance(self, temp_dir):
        """Test unified block calculation performance with large datasets."""
        from par_cc_usage.models import Project, Session
        from tests.conftest import create_block_with_tokens

        # Create many projects with overlapping time ranges
        num_projects = 20
        num_sessions = 10
        num_blocks = 20

        projects = {}
        base_time = datetime.now(timezone.utc)

        creation_start = time.time()

        for proj_i in range(num_projects):
            sessions = {}

            for sess_i in range(num_sessions):
                blocks = []

                for block_i in range(num_blocks):
                    # Create overlapping blocks
                    block_start = base_time + timedelta(hours=block_i - 5)
                    block = create_block_with_tokens(
                        start_time=block_start,
                        session_id=f"session_{sess_i}",
                        project_name=f"project_{proj_i}",
                        token_count=1000 + block_i * 10,
                    )
                    blocks.append(block)

                session = Session(
                    session_id=f"session_{sess_i}",
                    project_name=f"project_{proj_i}",
                    model="claude-3-sonnet-latest",
                    blocks=blocks,
                    first_seen=base_time - timedelta(hours=5),
                    last_seen=base_time + timedelta(hours=15),
                    session_start=base_time - timedelta(hours=5),
                )
                sessions[f"session_{sess_i}"] = session

            project = Project(name=f"project_{proj_i}", sessions=sessions)
            projects[f"project_{proj_i}"] = project

        creation_time = time.time() - creation_start

        # Create snapshot and test unified block calculations
        snapshot = UsageSnapshot(
            timestamp=base_time,
            projects=projects,
            total_limit=1000000,
            block_start_override=None,
        )

        # Test unified block calculations
        calc_start = time.time()

        unified_tokens = snapshot.unified_block_tokens()
        unified_by_model = snapshot.unified_block_tokens_by_model()
        unified_start = snapshot.unified_block_start_time

        calc_time = time.time() - calc_start

        # Verify calculations completed
        assert unified_tokens >= 0
        assert isinstance(unified_by_model, dict)

        total_blocks = num_projects * num_sessions * num_blocks

        print(f"Created {total_blocks} blocks in {creation_time:.2f}s")
        print(f"Unified calculations completed in {calc_time:.2f}s")
        print(f"Unified tokens: {unified_tokens}")
        print(f"Unified models: {list(unified_by_model.keys())}")

        # Performance should be reasonable
        assert calc_time < 10.0  # Should complete calculations in under 10 seconds
