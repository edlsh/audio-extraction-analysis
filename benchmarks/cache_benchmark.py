#!/usr/bin/env python3
"""
Benchmark script to compare DiskCache performance before and after connection pooling.

This script measures the throughput improvement from using persistent connections
with WAL mode instead of creating new connections for each operation.
"""

import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cache.backends import DiskCache
from src.cache.transcription_cache import CacheEntry, CacheKey


def create_sample_entry(index: int) -> CacheEntry:
    """Create a sample cache entry for benchmarking."""
    cache_key = CacheKey(
        file_hash=f"test_hash_{index}",
        provider="benchmark_provider",
        settings_hash=f"settings_{index}",
    )
    return CacheEntry(
        key=cache_key,
        value={"benchmark": "data", "index": index, "transcription": f"Sample text {index}"},
        size=500,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
        access_count=0,
        ttl=3600,
        metadata={"source": "benchmark"},
    )


def benchmark_operation(name: str, operation: Callable, iterations: int) -> float:
    """Benchmark an operation and return operations per second."""
    start_time = time.perf_counter()
    for _ in range(iterations):
        operation()
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    ops_per_sec = iterations / elapsed if elapsed > 0 else 0

    print(f"{name:30s}: {iterations:6d} ops in {elapsed:7.3f}s = {ops_per_sec:10.2f} ops/sec")
    return ops_per_sec


def run_benchmarks():
    """Run comprehensive cache benchmarks."""
    print("=" * 80)
    print("DiskCache Performance Benchmark")
    print("=" * 80)
    print()

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=100)

    # Prepare test data
    print("Preparing test data...")
    entries = [create_sample_entry(i) for i in range(1000)]
    keys = [f"benchmark_key_{i}" for i in range(1000)]
    print(f"Created {len(entries)} test entries")
    print()

    # Benchmark: Sequential Writes
    print("Benchmark: Sequential Writes")
    print("-" * 80)
    write_counter = [0]

    def write_op():
        idx = write_counter[0] % len(entries)
        cache.put(keys[idx], entries[idx])
        write_counter[0] += 1

    write_ops = benchmark_operation("Sequential writes", write_op, 1000)
    print()

    # Benchmark: Sequential Reads
    print("Benchmark: Sequential Reads")
    print("-" * 80)
    read_counter = [0]

    def read_op():
        idx = read_counter[0] % len(keys)
        cache.get(keys[idx])
        read_counter[0] += 1

    read_ops = benchmark_operation("Sequential reads", read_op, 1000)
    print()

    # Benchmark: Mixed Operations (70% reads, 30% writes)
    print("Benchmark: Mixed Operations (70% reads, 30% writes)")
    print("-" * 80)
    mixed_counter = [0]

    def mixed_op():
        idx = mixed_counter[0] % len(keys)
        if mixed_counter[0] % 10 < 7:
            cache.get(keys[idx])
        else:
            cache.put(keys[idx], entries[idx])
        mixed_counter[0] += 1

    mixed_ops = benchmark_operation("Mixed operations", mixed_op, 1000)
    print()

    # Benchmark: Concurrent Reads
    print("Benchmark: Concurrent Reads")
    print("-" * 80)
    import threading

    def concurrent_reader(thread_id: int, iterations: int):
        for i in range(iterations):
            idx = (thread_id * iterations + i) % len(keys)
            cache.get(keys[idx])

    num_threads = 10
    iterations_per_thread = 100

    start_time = time.perf_counter()
    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=concurrent_reader, args=(i, iterations_per_thread))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    end_time = time.perf_counter()
    total_ops = num_threads * iterations_per_thread
    elapsed = end_time - start_time
    concurrent_read_ops = total_ops / elapsed if elapsed > 0 else 0

    print(
        f"{'Concurrent reads (10 threads)':30s}: {total_ops:6d} ops in {elapsed:7.3f}s = {concurrent_read_ops:10.2f} ops/sec"
    )
    print()

    # Benchmark: exists() operation
    print("Benchmark: exists() operation")
    print("-" * 80)
    exists_counter = [0]

    def exists_op():
        idx = exists_counter[0] % len(keys)
        cache.exists(keys[idx])
        exists_counter[0] += 1

    exists_ops = benchmark_operation("Exists checks", exists_op, 1000)
    print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Sequential writes:      {write_ops:10.2f} ops/sec")
    print(f"Sequential reads:       {read_ops:10.2f} ops/sec")
    print(f"Mixed operations:       {mixed_ops:10.2f} ops/sec")
    print(f"Concurrent reads:       {concurrent_read_ops:10.2f} ops/sec")
    print(f"Exists checks:          {exists_ops:10.2f} ops/sec")
    print()

    # Calculate improvement estimate
    print("Expected improvement with connection pooling + WAL:")
    print("  - Previous: ~200-500 ops/sec (1-5ms connection overhead per op)")
    print("  - Current:  5-10x improvement expected")
    print(f"  - Actual:   {read_ops:.2f} ops/sec for sequential reads")
    print()

    # Verify WAL mode is enabled
    conn = cache._get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    print(f"SQLite journal mode: {journal_mode}")
    print(f"WAL mode enabled: {journal_mode.upper() == 'WAL'}")
    print()

    # Cleanup
    cache.close()
    print(f"Benchmark complete. Temporary directory: {temp_dir}")


if __name__ == "__main__":
    run_benchmarks()
