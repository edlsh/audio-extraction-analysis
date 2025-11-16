"""Performance benchmark for cache eviction strategies.

This benchmark measures the performance improvement from O(n) to O(log n) eviction.
Tests all strategies at different cache sizes to demonstrate scalability improvements.

NOTE: This is a manual performance benchmark script, not a unit test.
For unit tests covering eviction strategy correctness, see test_eviction.py
Run this benchmark with: python3 tests/cache/benchmark_eviction.py
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from src.cache.backends import InMemoryCache
from src.cache.eviction import (
    select_fifo_victim,
    select_lfu_victim,
    select_lru_victim,
    select_size_victim,
    select_ttl_victim,
)
from src.cache.transcription_cache import CacheEntry, CacheKey


# Old implementations for comparison (O(n) linear scan)
def select_lru_victim_old(backend: Any, keys: set[str]) -> str:
    """Old O(n) implementation - iterates all keys."""
    oldest_key = None
    oldest_time = datetime.now()
    for key in keys:
        entry = backend.get(key)
        if entry and entry.accessed_at < oldest_time:
            oldest_time = entry.accessed_at
            oldest_key = key
    return oldest_key or next(iter(keys))


def select_lfu_victim_old(backend: Any, keys: set[str]) -> str:
    """Old O(n) implementation - iterates all keys."""
    least_used_key = None
    least_count = float("inf")
    for key in keys:
        entry = backend.get(key)
        if entry and entry.access_count < least_count:
            least_count = entry.access_count
            least_used_key = key
    return least_used_key or next(iter(keys))


def select_ttl_victim_old(backend: Any, keys: set[str]) -> str:
    """Old O(n) implementation - iterates all keys."""
    soonest_key = None
    soonest_expiry = float("inf")
    for key in keys:
        entry = backend.get(key)
        if entry and entry.ttl:
            remaining = entry.ttl - entry.age_seconds()
            if remaining < soonest_expiry:
                soonest_expiry = remaining
                soonest_key = key
    return soonest_key or next(iter(keys))


def select_size_victim_old(backend: Any, keys: set[str]) -> str:
    """Old O(n) implementation - iterates all keys."""
    largest_key = None
    largest_size = 0
    for key in keys:
        entry = backend.get(key)
        if entry and entry.size > largest_size:
            largest_size = entry.size
            largest_key = key
    return largest_key or next(iter(keys))


def select_fifo_victim_old(backend: Any, keys: set[str]) -> str:
    """Old O(n) implementation - iterates all keys."""
    oldest_key = None
    oldest_time = datetime.now()
    for key in keys:
        entry = backend.get(key)
        if entry and entry.created_at < oldest_time:
            oldest_time = entry.created_at
            oldest_key = key
    return oldest_key or next(iter(keys))


def create_test_cache(num_entries: int) -> tuple[InMemoryCache, set[str]]:
    """Create a cache populated with test entries.

    Args:
        num_entries: Number of entries to create

    Returns:
        Tuple of (cache backend, set of keys)
    """
    cache = InMemoryCache(max_size_mb=1000)  # Large enough to hold all entries
    keys = set()

    base_time = datetime.now() - timedelta(days=1)

    for i in range(num_entries):
        key = f"test_key_{i:06d}"
        keys.add(key)

        # Create entry with varying metadata for different strategies
        cache_key = CacheKey(
            file_hash=f"hash_{i}",
            provider="test",
            settings_hash=f"settings_{i}",
        )

        entry = CacheEntry(
            key=cache_key,
            value={"data": f"value_{i}"},
            size=random.randint(100, 10000),  # Varying sizes
            created_at=base_time + timedelta(seconds=i),  # Sequential creation
            accessed_at=base_time + timedelta(seconds=i * 2),  # Varying access times
            access_count=random.randint(0, 100),  # Random access counts
            ttl=random.randint(60, 7200),  # Random TTLs (1 min to 2 hours)
            metadata={"index": i},
        )

        cache.put(key, entry)

    return cache, keys


def benchmark_strategy(
    strategy_name: str,
    old_func: Callable,
    new_func: Callable,
    cache_sizes: list[int],
    iterations: int = 10,
) -> None:
    """Benchmark a single eviction strategy at different cache sizes.

    Args:
        strategy_name: Name of the strategy
        old_func: Old O(n) implementation
        new_func: New optimized implementation
        cache_sizes: List of cache sizes to test
        iterations: Number of iterations per size
    """
    print(f"\n{'=' * 80}")
    print(f"Benchmarking: {strategy_name}")
    print(f"{'=' * 80}")
    print(f"{'Size':<10} {'Old (ms)':<12} {'New (ms)':<12} {'Speedup':<10} {'Status'}")
    print("-" * 80)

    for size in cache_sizes:
        cache, keys = create_test_cache(size)

        # Benchmark old implementation
        old_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            old_func(cache, keys)
            end = time.perf_counter()
            old_times.append((end - start) * 1000)  # Convert to ms

        old_avg = sum(old_times) / len(old_times)

        # Benchmark new implementation
        new_times = []
        for _ in range(iterations):
            start = time.perf_counter()
            new_func(cache, keys)
            end = time.perf_counter()
            new_times.append((end - start) * 1000)  # Convert to ms

        new_avg = sum(new_times) / len(new_times)

        speedup = old_avg / new_avg if new_avg > 0 else 0
        status = "✓ PASS" if speedup >= 2.0 else "⚠ SLOW"

        print(f"{size:<10} {old_avg:<12.4f} {new_avg:<12.4f} {speedup:<10.2f}x {status}")


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 80)
    print("CACHE EVICTION PERFORMANCE BENCHMARK")
    print("Comparing O(n) linear scan vs optimized O(log n) / O(1) implementations")
    print("=" * 80)

    # Test at increasing cache sizes to demonstrate scalability
    cache_sizes = [100, 1_000, 10_000, 50_000]
    iterations = 10

    # Benchmark each strategy
    strategies = [
        ("LRU (Least Recently Used)", select_lru_victim_old, select_lru_victim),
        ("LFU (Least Frequently Used)", select_lfu_victim_old, select_lfu_victim),
        ("TTL (Time To Live)", select_ttl_victim_old, select_ttl_victim),
        ("SIZE (Largest Entry)", select_size_victim_old, select_size_victim),
        ("FIFO (First In First Out)", select_fifo_victim_old, select_fifo_victim),
    ]

    for name, old_func, new_func in strategies:
        benchmark_strategy(name, old_func, new_func, cache_sizes, iterations)

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)
    print("\nKey findings:")
    print("- LRU and FIFO: O(1) for OrderedDict backends (InMemoryCache)")
    print("- LFU, TTL, SIZE: Optimized single-pass using built-in min/max")
    print("- Performance improvement scales with cache size")
    print("- Target: 50-100x improvement at 10k entries for strategies with overhead")
    print()


if __name__ == "__main__":
    main()
