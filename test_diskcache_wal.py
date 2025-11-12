#!/usr/bin/env python3
"""
Simple test to verify DiskCache works correctly with WAL mode.
"""

import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from src.cache.backends import DiskCache
from src.cache.transcription_cache import CacheEntry, CacheKey


def test_basic_operations():
    """Test basic DiskCache operations."""
    print("Testing basic operations...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Create test entry
    key = CacheKey(file_hash="test_hash", provider="test_provider", settings_hash="test_settings")
    entry = CacheEntry(
        key=key,
        value={"test": "data"},
        size=100,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )

    # Test put
    assert cache.put("test_key", entry), "Put failed"
    print("  ✓ Put operation successful")

    # Test get
    retrieved = cache.get("test_key")
    assert retrieved is not None, "Get failed"
    assert retrieved.key.file_hash == "test_hash", "Retrieved wrong data"
    print("  ✓ Get operation successful")

    # Test exists
    assert cache.exists("test_key"), "Exists failed"
    print("  ✓ Exists operation successful")

    # Test delete
    assert cache.delete("test_key"), "Delete failed"
    assert not cache.exists("test_key"), "Key still exists after delete"
    print("  ✓ Delete operation successful")

    # Verify WAL mode
    conn = cache._get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    assert journal_mode.upper() == "WAL", f"WAL mode not enabled: {journal_mode}"
    print(f"  ✓ WAL mode enabled: {journal_mode}")

    cache.close()
    print("Basic operations test: PASSED\n")


def _create_cache_test_entries(cache: DiskCache, count: int = 10) -> None:
    """Create test cache entries for concurrent testing."""
    for i in range(count):
        key = CacheKey(file_hash=f"hash_{i}", provider="test", settings_hash=f"settings_{i}")
        entry = CacheEntry(
            key=key,
            value={"index": i},
            size=100,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        cache.put(f"key_{i}", entry)


def _concurrent_worker(
    cache: DiskCache, worker_id: int, results: list, errors: list, operations: int = 50
) -> None:
    """Worker thread for concurrent cache testing."""
    try:
        for i in range(operations):
            key = f"key_{i % 10}"
            # Read operation
            entry = cache.get(key)
            results.append(entry is not None)
            # Check exists operation
            exists = cache.exists(key)
            results.append(exists)
    except Exception as e:
        errors.append(e)


def _run_concurrent_threads(
    cache: DiskCache, results: list, errors: list, num_threads: int = 5
) -> list:
    """Run concurrent worker threads and return the thread list."""
    threads = []
    for i in range(num_threads):
        thread = threading.Thread(target=_concurrent_worker, args=(cache, i, results, errors))
        threads.append(thread)
        thread.start()
    return threads


def test_concurrent_access():
    """Test concurrent access with multiple threads."""
    print("Testing concurrent access...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Create test entries
    _create_cache_test_entries(cache, count=10)

    # Run concurrent workers
    results = []
    errors = []
    threads = _run_concurrent_threads(cache, results, errors, num_threads=5)

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify results
    assert len(errors) == 0, f"Concurrent access had errors: {errors}"
    assert all(results), "Some concurrent operations failed"
    print(f"  ✓ {len(threads)} threads completed {len(results)} operations successfully")

    cache.close()
    print("Concurrent access test: PASSED\n")


def test_persistent_connection():
    """Test that connections are reused across operations."""
    print("Testing persistent connection...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Get connection multiple times in same thread
    conn1 = cache._get_connection()
    conn2 = cache._get_connection()

    # Should be the same connection object
    assert conn1 is conn2, "Connection not reused in same thread"
    print("  ✓ Connection reused within same thread")

    # Test that different threads get different connections
    other_thread_conn = [None]

    def get_connection_in_thread():
        other_thread_conn[0] = cache._get_connection()

    thread = threading.Thread(target=get_connection_in_thread)
    thread.start()
    thread.join()

    assert other_thread_conn[0] is not None, "Failed to get connection in thread"
    assert other_thread_conn[0] is not conn1, "Connections shared across threads (unsafe!)"
    print("  ✓ Different threads get separate connections")

    cache.close()
    print("Persistent connection test: PASSED\n")


def test_cache_size_and_keys():
    """Test size() and keys() operations."""
    print("Testing cache size and keys operations...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Initially empty
    assert cache.size() == 0, "Cache should be empty initially"
    assert len(cache.keys()) == 0, "Cache should have no keys initially"
    print("  ✓ Empty cache state verified")

    # Add entries
    total_size = 0
    for i in range(5):
        key = CacheKey(file_hash=f"hash_{i}", provider="test", settings_hash=f"settings_{i}")
        entry = CacheEntry(
            key=key,
            value={"index": i},
            size=100,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        cache.put(f"key_{i}", entry)
        total_size += 100

    # Verify size tracking
    assert cache.size() == total_size, f"Expected size {total_size}, got {cache.size()}"
    print(f"  ✓ Size tracking correct: {total_size} bytes")

    # Verify keys
    keys = cache.keys()
    assert len(keys) == 5, f"Expected 5 keys, got {len(keys)}"
    for i in range(5):
        assert f"key_{i}" in keys, f"key_{i} not found in cache keys"
    print("  ✓ Keys retrieval correct")

    cache.close()
    print("Cache size and keys test: PASSED\n")


def test_cache_clear():
    """Test clear() operation."""
    print("Testing cache clear operation...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Add entries
    for i in range(5):
        key = CacheKey(file_hash=f"hash_{i}", provider="test", settings_hash=f"settings_{i}")
        entry = CacheEntry(
            key=key,
            value={"index": i},
            size=100,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        cache.put(f"key_{i}", entry)

    # Verify entries exist
    assert cache.size() > 0, "Cache should not be empty"
    assert len(cache.keys()) == 5, "Should have 5 entries"
    print("  ✓ Cache populated with 5 entries")

    # Clear cache
    count = cache.clear()
    assert count == 5, f"Expected to clear 5 entries, got {count}"
    print(f"  ✓ Cleared {count} entries")

    # Verify empty
    assert cache.size() == 0, "Cache size should be 0 after clear"
    assert len(cache.keys()) == 0, "Cache should have no keys after clear"
    print("  ✓ Cache empty after clear")

    cache.close()
    print("Cache clear test: PASSED\n")


def test_cache_eviction():
    """Test automatic eviction when cache is full."""
    print("Testing cache eviction...")

    temp_dir = Path(tempfile.mkdtemp())
    # Small cache: 500 bytes max
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=500 / 1024 / 1024)  # 500 bytes

    # Add entries that will fill and overflow the cache
    # Each entry is 200 bytes
    for i in range(6):
        key = CacheKey(file_hash=f"hash_{i}", provider="test", settings_hash=f"settings_{i}")
        entry = CacheEntry(
            key=key,
            value={"index": i, "data": "x" * 50},
            size=200,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        cache.put(f"key_{i}", entry)
        time.sleep(0.01)  # Small delay to ensure different access times

    # Should have evicted oldest entries
    # Cache can hold max 2 entries (400 bytes), or 3 entries with eviction
    size = cache.size()
    assert size <= 500, f"Cache size {size} exceeds limit 500"
    print(f"  ✓ Cache size within limit: {size} bytes")

    # First entries should be evicted (LRU)
    assert not cache.exists("key_0"), "Oldest entry should be evicted"
    assert not cache.exists("key_1"), "Second oldest should be evicted"
    assert not cache.exists("key_2"), "Third oldest should be evicted"
    print("  ✓ Oldest entries evicted (LRU policy)")

    # Recent entries should still exist
    assert cache.exists("key_5"), "Most recent entry should exist"
    assert cache.exists("key_4"), "Second most recent should exist"
    print("  ✓ Recent entries preserved")

    cache.close()
    print("Cache eviction test: PASSED\n")


def test_entry_too_large():
    """Test handling of entries too large for cache."""
    print("Testing entry too large...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=500 / 1024 / 1024)  # 500 bytes max

    # Try to add entry larger than max size
    key = CacheKey(file_hash="huge_hash", provider="test", settings_hash="huge_settings")
    entry = CacheEntry(
        key=key,
        value={"data": "x" * 200},
        size=600,  # 600 bytes - larger than 500 bytes max
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )

    result = cache.put("huge_key", entry)
    assert not result, "Should reject entry too large for cache"
    print("  ✓ Rejected entry larger than max cache size")

    # Verify entry not in cache
    assert not cache.exists("huge_key"), "Entry should not exist in cache"
    assert cache.size() == 0, "Cache should be empty"
    print("  ✓ Entry not added to cache")

    cache.close()
    print("Entry too large test: PASSED\n")


def test_entry_replacement():
    """Test replacing existing entries."""
    print("Testing entry replacement...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Add initial entry
    key = CacheKey(file_hash="test_hash", provider="test", settings_hash="test_settings")
    entry1 = CacheEntry(
        key=key,
        value={"version": 1},
        size=100,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )
    cache.put("test_key", entry1)
    print("  ✓ Added initial entry")

    # Verify initial size
    initial_size = cache.size()
    assert initial_size == 100, f"Expected size 100, got {initial_size}"

    # Replace with different entry
    entry2 = CacheEntry(
        key=key,
        value={"version": 2},
        size=150,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )
    cache.put("test_key", entry2)
    print("  ✓ Replaced entry with new version")

    # Verify size updated correctly
    new_size = cache.size()
    assert new_size == 150, f"Expected size 150 after replacement, got {new_size}"
    print("  ✓ Size updated correctly after replacement")

    # Verify only one entry exists
    assert len(cache.keys()) == 1, "Should have exactly one entry"

    # Verify new value
    retrieved = cache.get("test_key")
    assert retrieved.value["version"] == 2, "Should have new value"
    print("  ✓ Retrieved updated value")

    cache.close()
    print("Entry replacement test: PASSED\n")


def test_access_tracking():
    """Test access count and time tracking in database."""
    print("Testing access tracking...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Add entry
    key = CacheKey(file_hash="test_hash", provider="test", settings_hash="test_settings")
    entry = CacheEntry(
        key=key,
        value={"test": "data"},
        size=100,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )
    cache.put("test_key", entry)

    # Get initial access count from database
    conn = cache._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT access_count FROM cache_entries WHERE key = ?", ("test_key",))
    initial_count = cursor.fetchone()[0]
    print(f"  ✓ Initial access count: {initial_count}")

    time.sleep(0.1)  # Small delay

    # Access multiple times
    for _ in range(3):
        cache.get("test_key")
        time.sleep(0.05)

    # Check access count increased in database
    cursor.execute("SELECT access_count FROM cache_entries WHERE key = ?", ("test_key",))
    final_count = cursor.fetchone()[0]
    assert (
        final_count > initial_count
    ), f"Access count should increase: {initial_count} -> {final_count}"
    print(f"  ✓ Access count increased: {initial_count} -> {final_count}")

    # Check accessed_at was updated
    cursor.execute("SELECT accessed_at FROM cache_entries WHERE key = ?", ("test_key",))
    accessed_at = cursor.fetchone()[0]
    assert accessed_at is not None, "accessed_at should be set"
    print("  ✓ accessed_at timestamp updated")

    cache.close()
    print("Access tracking test: PASSED\n")


def test_concurrent_writes():
    """Test concurrent write operations."""
    print("Testing concurrent writes...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    errors = []
    results = []

    def writer_thread(thread_id: int, num_writes: int = 20):
        """Write entries concurrently."""
        try:
            for i in range(num_writes):
                key = CacheKey(
                    file_hash=f"hash_{thread_id}_{i}",
                    provider="test",
                    settings_hash=f"settings_{thread_id}_{i}",
                )
                entry = CacheEntry(
                    key=key,
                    value={"thread": thread_id, "index": i},
                    size=100,
                    created_at=datetime.now(),
                    accessed_at=datetime.now(),
                )
                result = cache.put(f"key_{thread_id}_{i}", entry)
                results.append(result)
        except Exception as e:
            errors.append(e)

    # Run concurrent writers
    threads = []
    num_threads = 5
    for i in range(num_threads):
        thread = threading.Thread(target=writer_thread, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrent writes had errors: {errors}"
    print(f"  ✓ {num_threads} threads completed writes without errors")

    # Verify all writes succeeded
    assert all(results), "Some writes failed"
    print(f"  ✓ All {len(results)} write operations successful")

    # Verify entries exist
    keys = cache.keys()
    assert len(keys) > 0, "Cache should have entries"
    print(f"  ✓ Cache contains {len(keys)} entries")

    cache.close()
    print("Concurrent writes test: PASSED\n")


def test_close_and_cleanup():
    """Test close() and cleanup operations."""
    print("Testing close and cleanup...")

    temp_dir = Path(tempfile.mkdtemp())
    cache = DiskCache(cache_dir=temp_dir, max_size_mb=10)

    # Add some data
    key = CacheKey(file_hash="test_hash", provider="test", settings_hash="test_settings")
    entry = CacheEntry(
        key=key,
        value={"test": "data"},
        size=100,
        created_at=datetime.now(),
        accessed_at=datetime.now(),
    )
    cache.put("test_key", entry)
    print("  ✓ Added test data")

    # Close cache
    cache.close()
    print("  ✓ Cache closed")

    # Verify connection cleanup
    assert not hasattr(cache._local, "conn"), "Connection should be cleaned up"
    print("  ✓ Connection cleaned up")

    # Can reopen by getting connection
    new_conn = cache._get_connection()
    assert new_conn is not None, "Should be able to get new connection"
    print("  ✓ Can get new connection after close")

    # Data should persist
    assert cache.exists("test_key"), "Data should persist after close/reopen"
    print("  ✓ Data persisted across close/reopen")

    cache.close()
    print("Close and cleanup test: PASSED\n")


if __name__ == "__main__":
    print("=" * 60)
    print("DiskCache WAL Mode Tests")
    print("=" * 60)
    print()

    # Basic functionality tests
    test_basic_operations()
    test_cache_size_and_keys()
    test_cache_clear()

    # Edge cases and error handling
    test_cache_eviction()
    test_entry_too_large()
    test_entry_replacement()
    test_access_tracking()

    # Concurrency tests
    test_concurrent_access()
    test_concurrent_writes()
    test_persistent_connection()

    # Cleanup tests
    test_close_and_cleanup()

    print("=" * 60)
    print("All tests PASSED! ✓")
    print("=" * 60)
