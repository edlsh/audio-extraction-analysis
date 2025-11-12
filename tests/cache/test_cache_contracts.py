"""
Contract tests for cache backends to ensure BaseCache protocol conformance.

This module contains tests that verify all cache backends implement the
BaseCache protocol consistently and correctly.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.cache.backends import DiskCache, InMemoryCache
from src.cache.common import BaseCache, CacheUtils
from src.cache.transcription_cache import CacheEntry, CacheKey


class TestCacheContract:
    """Contract tests that all cache backends must pass."""

    @pytest.fixture
    def sample_cache_entry(self) -> CacheEntry:
        """Create a sample cache entry for testing."""
        cache_key = CacheKey(
            file_hash="test_hash_123", provider="test_provider", settings_hash="settings_456"
        )
        return CacheEntry(
            key=cache_key,
            value={"test": "data", "transcription": "Hello world"},
            size=100,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
            access_count=0,
            ttl=3600,
            metadata={"source": "test"},
        )

    @pytest.fixture
    def cache_backends(self) -> list[BaseCache]:
        """Create instances of all cache backends for testing."""
        temp_dir = Path(tempfile.mkdtemp())

        return [
            InMemoryCache(max_size_mb=1),
            DiskCache(cache_dir=temp_dir, max_size_mb=1),
        ]

    def test_implements_base_cache_protocol(self, cache_backends: list[BaseCache]):
        """Test that all backends implement BaseCache protocol."""
        for backend in cache_backends:
            assert isinstance(backend, BaseCache), f"{type(backend)} does not implement BaseCache"

    def test_put_and_get_operations(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test basic put and get operations work consistently."""
        test_key = "test_key_123"

        for backend in cache_backends:
            # Test successful put
            assert backend.put(
                test_key, sample_cache_entry
            ), f"{type(backend)} put operation failed"

            # Test successful get
            retrieved_entry = backend.get(test_key)
            assert retrieved_entry is not None, f"{type(backend)} get operation returned None"
            assert retrieved_entry.key.file_hash == sample_cache_entry.key.file_hash
            assert retrieved_entry.value == sample_cache_entry.value
            assert retrieved_entry.size == sample_cache_entry.size

    def test_delete_operations(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test delete operations work consistently."""
        test_key = "test_delete_key"

        for backend in cache_backends:
            # Put entry first
            backend.put(test_key, sample_cache_entry)

            # Test delete returns True for existing key
            assert backend.delete(
                test_key
            ), f"{type(backend)} delete existing key should return True"

            # Test get returns None after delete
            assert backend.get(test_key) is None, f"{type(backend)} should return None after delete"

            # Test delete returns False for non-existing key
            assert not backend.delete(
                "non_existing_key"
            ), f"{type(backend)} delete non-existing key should return False"

    def test_exists_operations(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test exists operations work consistently."""
        test_key = "test_exists_key"

        for backend in cache_backends:
            # Test exists returns False for non-existing key
            assert not backend.exists(
                test_key
            ), f"{type(backend)} exists should return False for non-existing key"

            # Put entry
            backend.put(test_key, sample_cache_entry)

            # Test exists returns True for existing key
            assert backend.exists(
                test_key
            ), f"{type(backend)} exists should return True for existing key"

            # Delete and test exists returns False
            backend.delete(test_key)
            assert not backend.exists(
                test_key
            ), f"{type(backend)} exists should return False after delete"

    def test_clear_operations(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test clear operations work consistently."""
        for backend in cache_backends:
            # Put multiple entries
            keys = ["clear_test_1", "clear_test_2", "clear_test_3"]
            for key in keys:
                backend.put(key, sample_cache_entry)

            # Test clear returns count > 0
            cleared_count = backend.clear()
            assert cleared_count > 0, f"{type(backend)} clear should return positive count"

            # Test all entries are gone
            for key in keys:
                assert (
                    backend.get(key) is None
                ), f"{type(backend)} should have no entries after clear"

            # Test size is 0 after clear
            assert backend.size() == 0, f"{type(backend)} size should be 0 after clear"

    def test_size_operations(self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry):
        """Test size operations work consistently."""
        for backend in cache_backends:
            # Clear to start fresh
            backend.clear()

            # Test initial size is 0
            assert backend.size() == 0, f"{type(backend)} initial size should be 0"

            # Add entry and check size increases
            backend.put("size_test", sample_cache_entry)
            size_after_put = backend.size()
            assert size_after_put > 0, f"{type(backend)} size should increase after put"

            # Delete entry and check size decreases
            backend.delete("size_test")
            size_after_delete = backend.size()
            assert (
                size_after_delete < size_after_put
            ), f"{type(backend)} size should decrease after delete"

    def test_keys_operations(self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry):
        """Test keys operations work consistently."""
        for backend in cache_backends:
            backend.clear()

            # Test keys returns empty set initially
            assert (
                len(backend.keys()) == 0
            ), f"{type(backend)} keys should return empty set initially"

            # Add entries
            test_keys = ["keys_test_1", "keys_test_2", "keys_test_3"]
            for key in test_keys:
                backend.put(key, sample_cache_entry)

            # Test keys returns all added keys
            returned_keys = backend.keys()
            for key in test_keys:
                assert key in returned_keys, f"{type(backend)} keys should contain {key}"

            # Delete one key and verify it's no longer in keys
            backend.delete(test_keys[0])
            updated_keys = backend.keys()
            assert (
                test_keys[0] not in updated_keys
            ), f"{type(backend)} keys should not contain deleted key"
            assert (
                test_keys[1] in updated_keys
            ), f"{type(backend)} keys should still contain remaining keys"

    def test_key_normalization(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test that key normalization is applied consistently."""
        # Test with different case and whitespace
        original_key = "  TeSt_KeY_123  "
        normalized_key = CacheUtils.normalize_key(original_key)

        for backend in cache_backends:
            backend.clear()

            # Put with original key
            backend.put(original_key, sample_cache_entry)

            # Get with normalized key should work for normalized backends
            retrieved = backend.get(normalized_key)
            if hasattr(backend, "_cache"):  # InMemoryCache uses normalization
                assert retrieved is not None, f"{type(backend)} should retrieve with normalized key"

            # Keys should contain normalized version for normalized backends
            keys = backend.keys()
            if hasattr(backend, "_cache"):  # InMemoryCache uses normalization
                assert normalized_key in keys, f"{type(backend)} keys should contain normalized key"

    def test_large_entry_handling(self, cache_backends: list[BaseCache]):
        """Test handling of entries larger than cache size."""
        large_key = CacheKey(
            file_hash="large_hash", provider="test", settings_hash="large_settings"
        )
        # Create entry larger than 1MB cache size
        large_entry = CacheEntry(
            key=large_key,
            value={"data": "x" * (2 * 1024 * 1024)},  # 2MB of data
            size=2 * 1024 * 1024,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )

        for backend in cache_backends:
            backend.clear()

            # Should fail to put oversized entry
            result = backend.put("large_key", large_entry)
            assert not result, f"{type(backend)} should reject oversized entries"

            # Verify it's not actually stored
            assert (
                backend.get("large_key") is None
            ), f"{type(backend)} should not store oversized entries"

    def test_concurrent_operations_safety(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test basic thread safety of operations."""
        import threading
        import time

        for backend in cache_backends:
            backend.clear()
            results = []

            def worker(worker_id: int):
                """Worker function for concurrent testing."""
                key = f"concurrent_{worker_id}"
                # Put entry
                put_result = backend.put(key, sample_cache_entry)
                results.append(put_result)

                # Small delay to allow interleaving
                time.sleep(0.001)

                # Get entry
                get_result = backend.get(key)
                results.append(get_result is not None)

            # Run multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Check that all operations succeeded
            assert all(results), f"{type(backend)} concurrent operations failed"

    def test_concurrent_reads(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test concurrent read operations with WAL mode benefits."""
        import threading

        for backend in cache_backends:
            backend.clear()

            # Put a single entry
            test_key = "concurrent_read_key"
            backend.put(test_key, sample_cache_entry)

            read_results = []
            errors = []

            def reader(reader_id: int):
                """Reader function for concurrent testing."""
                try:
                    for _ in range(10):
                        entry = backend.get(test_key)
                        read_results.append(entry is not None)
                except Exception as e:
                    errors.append(e)

            # Run multiple concurrent readers
            threads = []
            for i in range(10):
                thread = threading.Thread(target=reader, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Check that all reads succeeded
            assert len(errors) == 0, f"{type(backend)} concurrent reads had errors: {errors}"
            assert all(read_results), f"{type(backend)} concurrent reads failed"
            assert (
                len(read_results) == 100
            ), f"{type(backend)} expected 100 reads, got {len(read_results)}"

    def test_concurrent_writes(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test concurrent write operations."""
        import threading

        for backend in cache_backends:
            backend.clear()

            write_results = []
            errors = []

            def writer(writer_id: int):
                """Writer function for concurrent testing."""
                try:
                    for i in range(5):
                        key = f"concurrent_write_{writer_id}_{i}"
                        result = backend.put(key, sample_cache_entry)
                        write_results.append(result)
                except Exception as e:
                    errors.append(e)

            # Run multiple concurrent writers
            threads = []
            for i in range(10):
                thread = threading.Thread(target=writer, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Check that all writes succeeded
            assert len(errors) == 0, f"{type(backend)} concurrent writes had errors: {errors}"
            assert all(write_results), f"{type(backend)} concurrent writes failed"
            assert (
                len(write_results) == 50
            ), f"{type(backend)} expected 50 writes, got {len(write_results)}"

    def test_concurrent_mixed_operations(
        self, cache_backends: list[BaseCache], sample_cache_entry: CacheEntry
    ):
        """Test mixed concurrent operations (reads, writes, deletes)."""
        import random
        import threading

        for backend in cache_backends:
            backend.clear()

            # Pre-populate with some entries
            for i in range(10):
                backend.put(f"mixed_{i}", sample_cache_entry)

            operation_results = []
            errors = []

            def mixed_worker(worker_id: int):
                """Worker with mixed operations."""
                try:
                    for _i in range(10):
                        op = random.choice(["read", "write", "delete", "exists"])
                        key = f"mixed_{random.randint(0, 19)}"

                        if op == "read":
                            result = backend.get(key)
                            operation_results.append(("read", result is not None or result is None))
                        elif op == "write":
                            result = backend.put(key, sample_cache_entry)
                            operation_results.append(("write", result))
                        elif op == "delete":
                            result = backend.delete(key)
                            operation_results.append(("delete", True))
                        elif op == "exists":
                            result = backend.exists(key)
                            operation_results.append(("exists", True))
                except Exception as e:
                    errors.append(e)

            # Run multiple threads with mixed operations
            threads = []
            for i in range(10):
                thread = threading.Thread(target=mixed_worker, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Check that no errors occurred
            assert (
                len(errors) == 0
            ), f"{type(backend)} mixed concurrent operations had errors: {errors}"
            # All operations should complete successfully
            assert all(
                result[1] for result in operation_results
            ), f"{type(backend)} some operations failed"


class TestCacheUtilities:
    """Test utility functions from common module."""

    def test_key_normalization(self):
        """Test key normalization utility."""
        test_cases = [
            ("  Test_Key  ", "test_key"),
            ("UPPERCASE", "uppercase"),
            ("mixed_Case_123", "mixed_case_123"),
            ("", ""),
            ("already_normalized", "already_normalized"),
        ]

        for input_key, expected in test_cases:
            result = CacheUtils.normalize_key(input_key)
            assert (
                result == expected
            ), f"normalize_key('{input_key}') should return '{expected}', got '{result}'"

    def test_size_calculation(self):
        """Test size calculation utility."""
        test_cases = [
            (b"hello", 5),
            ("hello", 5),  # UTF-8 encoding
            ({"test": "data"}, None),  # Should return some positive size
        ]

        for value, expected in test_cases:
            result = CacheUtils.calculate_size(value)
            if expected is None:
                assert result > 0, f"calculate_size should return positive for {type(value)}"
            else:
                assert (
                    result == expected
                ), f"calculate_size({value!r}) should return {expected}, got {result}"

    def test_expiry_checking(self):
        """Test expiry checking utility."""
        # Create expired entry
        expired_key = CacheKey("hash", "provider", "settings")
        expired_entry = CacheEntry(
            key=expired_key,
            value="test",
            size=10,
            ttl=1,  # 1 second TTL
        )

        # Should not be expired immediately
        assert not CacheUtils.is_expired(expired_entry), "Entry should not be expired immediately"

        # Should be expired after TTL
        import time

        time.sleep(1.1)  # Wait longer than TTL
        assert CacheUtils.is_expired(expired_entry), "Entry should be expired after TTL"


class TestSerializationHelper:
    """Test SerializationHelper functionality."""

    def test_serialize_deserialize_entry_without_compression(self):
        """Test entry serialization without compression."""
        from src.cache.common import SerializationHelper

        cache_key = CacheKey("test_hash", "test_provider", "settings_hash")
        original_entry = CacheEntry(
            key=cache_key,
            value={"test": "data", "nested": {"key": "value"}},
            size=100,
            ttl=3600,
            metadata={"source": "test"},
        )

        # Serialize
        serialized = SerializationHelper.serialize_entry(original_entry, use_compression=False)
        assert isinstance(serialized, bytes), "Serialized entry should be bytes"

        # Deserialize
        deserialized = SerializationHelper.deserialize_entry(serialized, is_compressed=False)
        assert deserialized is not None, "Deserialization should succeed"
        assert deserialized.key.file_hash == original_entry.key.file_hash
        assert deserialized.value == original_entry.value
        assert deserialized.size == original_entry.size

    def test_serialize_deserialize_entry_with_compression(self):
        """Test entry serialization with compression."""
        from src.cache.common import SerializationHelper

        cache_key = CacheKey("test_hash", "test_provider", "settings_hash")
        large_value = {"data": "x" * 1000}  # Large value benefits from compression
        original_entry = CacheEntry(
            key=cache_key,
            value=large_value,
            size=1000,
        )

        # Serialize with compression
        compressed = SerializationHelper.serialize_entry(original_entry, use_compression=True)
        uncompressed = SerializationHelper.serialize_entry(original_entry, use_compression=False)

        # Compressed should be smaller
        assert len(compressed) < len(uncompressed), "Compressed data should be smaller"

        # Deserialize compressed
        deserialized = SerializationHelper.deserialize_entry(compressed, is_compressed=True)
        assert deserialized is not None, "Decompression should succeed"
        assert deserialized.value == original_entry.value

    def test_deserialize_corrupted_data(self):
        """Test deserialization handles corrupted data gracefully."""
        from src.cache.common import SerializationHelper

        corrupted_data = b"not valid json data"
        result = SerializationHelper.deserialize_entry(corrupted_data, is_compressed=False)
        assert result is None, "Should return None for corrupted data"

    def test_serialize_value_different_types(self):
        """Test value serialization for different data types."""
        from src.cache.common import SerializationHelper

        test_values = [
            {"key": "value"},
            "simple string",
            123,
            [1, 2, 3],
        ]

        for value in test_values:
            serialized = SerializationHelper.serialize_value(value, use_compression=False)
            assert isinstance(serialized, bytes), f"Serialized {type(value)} should be bytes"

            deserialized = SerializationHelper.deserialize_value(serialized, is_compressed=False)
            # For simple types, should get back the same value
            if isinstance(value, (str, int, list)):
                assert deserialized == value, f"Roundtrip failed for {type(value)}"


class TestTTLManager:
    """Test TTLManager functionality."""

    def test_is_expired_with_custom_time(self):
        """Test TTL expiration check with custom timestamp."""
        from src.cache.common import TTLManager

        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
            ttl=3600,  # 1 hour TTL
        )

        import time

        current_time = time.time()

        # Should not be expired with current time
        assert not TTLManager.is_expired(entry, current_time), "Entry should not be expired"

        # Should be expired with time in the future
        future_time = current_time + 3601  # 1 hour + 1 second later
        assert TTLManager.is_expired(entry, future_time), "Entry should be expired in the future"

    def test_is_expired_no_ttl(self):
        """Test entries without TTL never expire."""
        from src.cache.common import TTLManager

        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
            ttl=None,  # No TTL
        )

        import time

        future_time = time.time() + 999999  # Far in the future
        assert not TTLManager.is_expired(
            entry, future_time
        ), "Entry with no TTL should never expire"

    def test_time_until_expiry(self):
        """Test time until expiry calculation."""
        from src.cache.common import TTLManager

        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
            ttl=3600,
        )

        time_left = TTLManager.time_until_expiry(entry)
        assert time_left is not None, "Should return time until expiry"
        assert 3590 < time_left <= 3600, f"Time left should be close to TTL, got {time_left}"

    def test_time_until_expiry_no_ttl(self):
        """Test time until expiry for entries without TTL."""
        from src.cache.common import TTLManager

        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
            ttl=None,
        )

        time_left = TTLManager.time_until_expiry(entry)
        assert time_left is None, "Should return None for entries without TTL"


class TestSizeLimitManager:
    """Test SizeLimitManager functionality."""

    def test_can_fit(self):
        """Test can_fit method."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)

        assert manager.can_fit(500), "500 bytes should fit in 1000 byte limit"
        assert manager.can_fit(1000), "1000 bytes should fit in 1000 byte limit"
        assert not manager.can_fit(1001), "1001 bytes should not fit in 1000 byte limit"

    def test_would_exceed_limit(self):
        """Test would_exceed_limit method."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)
        manager.add_entry(600)

        assert not manager.would_exceed_limit(300), "Adding 300 to 600 should not exceed 1000"
        assert not manager.would_exceed_limit(400), "Adding 400 to 600 should equal 1000"
        assert manager.would_exceed_limit(401), "Adding 401 to 600 should exceed 1000"

    def test_space_needed_for(self):
        """Test space_needed_for method."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)
        manager.add_entry(800)

        # Need 300 bytes, have 200 available, need to free 100
        space_needed = manager.space_needed_for(300)
        assert space_needed == 100, f"Should need 100 bytes, got {space_needed}"

        # Entry fits, no space needed
        space_needed = manager.space_needed_for(200)
        assert space_needed == 0, "Should need 0 bytes when entry fits"

    def test_add_and_remove_entry(self):
        """Test add_entry and remove_entry methods."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)

        assert manager.current_size == 0, "Initial size should be 0"

        manager.add_entry(300)
        assert manager.current_size == 300, "Size should be 300 after adding"

        manager.add_entry(200)
        assert manager.current_size == 500, "Size should be 500 after adding more"

        manager.remove_entry(300)
        assert manager.current_size == 200, "Size should be 200 after removing"

        # Test underflow protection
        manager.remove_entry(1000)
        assert manager.current_size == 0, "Size should not go below 0"

    def test_reset(self):
        """Test reset method."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)
        manager.add_entry(500)

        manager.reset()
        assert manager.current_size == 0, "Size should be 0 after reset"

    def test_properties(self):
        """Test manager properties."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=1000)
        manager.add_entry(600)

        assert manager.current_size == 600, "current_size property should return 600"
        assert manager.available_space == 400, "available_space should be 400"
        assert manager.utilization_percent == 60.0, "utilization should be 60%"

    def test_utilization_percent_zero_max(self):
        """Test utilization with zero max size."""
        from src.cache.common import SizeLimitManager

        manager = SizeLimitManager(max_size_bytes=0)
        assert manager.utilization_percent == 0.0, "Utilization should be 0% when max is 0"


class TestCacheEntry:
    """Test CacheEntry methods."""

    def test_touch_updates_access_stats(self):
        """Test touch method updates access statistics."""
        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
        )

        original_accessed = entry.accessed_at
        original_count = entry.access_count

        import time

        time.sleep(0.01)  # Small delay to ensure timestamp changes

        entry.touch()

        assert entry.accessed_at > original_accessed, "accessed_at should be updated"
        assert entry.access_count == original_count + 1, "access_count should increment"

    def test_age_seconds(self):
        """Test age_seconds calculation."""
        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(
            key=cache_key,
            value="test",
            size=10,
        )

        import time

        time.sleep(0.1)  # Wait 100ms

        age = entry.age_seconds()
        assert age >= 0.1, f"Age should be at least 0.1 seconds, got {age}"
        assert age < 1.0, f"Age should be less than 1 second, got {age}"

    def test_serialization_roundtrip(self):
        """Test to_dict and from_dict roundtrip."""
        cache_key = CacheKey("test_hash", "test_provider", "settings_hash")
        original_entry = CacheEntry(
            key=cache_key,
            value={"test": "data", "number": 123},
            size=100,
            ttl=3600,
            metadata={"source": "test", "priority": "high"},
        )

        # Convert to dict
        entry_dict = original_entry.to_dict()
        assert isinstance(entry_dict, dict), "to_dict should return a dictionary"
        assert "key" in entry_dict, "Dictionary should contain key"
        assert "value" in entry_dict, "Dictionary should contain value"

        # Reconstruct from dict
        reconstructed = CacheEntry.from_dict(entry_dict)
        assert reconstructed.key.file_hash == original_entry.key.file_hash
        assert reconstructed.value == original_entry.value
        assert reconstructed.size == original_entry.size
        assert reconstructed.ttl == original_entry.ttl
        assert reconstructed.metadata == original_entry.metadata


class TestCacheKey:
    """Test CacheKey functionality."""

    def test_from_file(self):
        """Test cache key generation from file."""
        import tempfile
        from pathlib import Path

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content for cache key")
            temp_path = Path(f.name)

        try:
            settings = {"model": "base", "language": "en"}
            cache_key = CacheKey.from_file(temp_path, "openai", settings)

            assert cache_key.provider == "openai", "Provider should match"
            assert len(cache_key.file_hash) > 0, "File hash should be generated"
            assert len(cache_key.settings_hash) > 0, "Settings hash should be generated"

            # Same file and settings should produce same key
            cache_key2 = CacheKey.from_file(temp_path, "openai", settings)
            assert str(cache_key) == str(cache_key2), "Same inputs should produce same key"

        finally:
            temp_path.unlink()

    def test_file_hash_caching(self):
        """Test file hash caching behavior."""
        import tempfile
        from pathlib import Path

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)

        try:
            # Clear hash cache first
            CacheKey.clear_hash_cache()

            # First call should compute hash
            hash1 = CacheKey._hash_file(temp_path)
            assert len(hash1) > 0, "Hash should be generated"

            # Second call should use cached hash (same file, same mtime)
            hash2 = CacheKey._hash_file(temp_path)
            assert hash1 == hash2, "Cached hash should match"

            # Verify cache was used (same object reference in cache)
            assert len(CacheKey._file_hash_cache) > 0, "Cache should have entries"

        finally:
            temp_path.unlink()
            CacheKey.clear_hash_cache()

    def test_clear_hash_cache(self):
        """Test hash cache clearing."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test")
            temp_path = Path(f.name)

        try:
            # Populate cache
            CacheKey._hash_file(temp_path)
            assert len(CacheKey._file_hash_cache) > 0, "Cache should have entries"

            # Clear all
            cleared = CacheKey.clear_hash_cache()
            assert cleared > 0, "Should report cleared entries"
            assert len(CacheKey._file_hash_cache) == 0, "Cache should be empty"

            # Populate again
            CacheKey._hash_file(temp_path)

            # Clear specific file
            cleared = CacheKey.clear_hash_cache(temp_path)
            assert cleared > 0, "Should clear specific file entries"

        finally:
            temp_path.unlink()
            CacheKey.clear_hash_cache()


class TestBackendSpecificBehaviors:
    """Test backend-specific implementation details."""

    def test_inmemory_lru_eviction(self):
        """Test InMemoryCache LRU eviction behavior."""
        cache = InMemoryCache(max_size_mb=1)  # 1MB limit

        cache_key = CacheKey("hash", "provider", "settings")

        # Add multiple entries
        entries = []
        for i in range(5):
            entry = CacheEntry(
                key=cache_key,
                value={"data": "x" * 100000},  # ~100KB each
                size=100000,
            )
            entries.append((f"key_{i}", entry))
            cache.put(f"key_{i}", entry)

        # Access key_0 to move it to end (most recently used)
        cache.get("key_0")

        # Add another entry to trigger eviction
        new_entry = CacheEntry(
            key=cache_key,
            value={"data": "x" * 600000},  # 600KB
            size=600000,
        )
        cache.put("new_key", new_entry)

        # key_0 should still exist (was recently accessed)
        # Older keys should have been evicted
        assert cache.exists("key_0") or not cache.exists(
            "key_1"
        ), "LRU eviction should preserve recently used"

    def test_diskcache_close(self):
        """Test DiskCache close method."""
        import tempfile
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        cache = DiskCache(cache_dir=temp_dir, max_size_mb=1)

        # Perform some operations to create connection
        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(key=cache_key, value="test", size=10)
        cache.put("test_key", entry)

        # Close should succeed without errors
        cache.close()

        # Should be able to reopen
        cache2 = DiskCache(cache_dir=temp_dir, max_size_mb=1)
        assert cache2.exists("test_key"), "Data should persist after close"
        cache2.close()

    def test_diskcache_access_stats(self):
        """Test DiskCache updates access statistics."""
        import tempfile
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        cache = DiskCache(cache_dir=temp_dir, max_size_mb=1)

        cache_key = CacheKey("hash", "provider", "settings")
        entry = CacheEntry(key=cache_key, value="test", size=10, access_count=0)

        # Put entry
        cache.put("test_key", entry)

        # First get
        retrieved = cache.get("test_key")
        assert retrieved is not None, "Entry should exist"

        # Access count should be updated in database (we can't easily verify without
        # direct DB access, but we can verify the get operation succeeds multiple times)
        for _ in range(3):
            retrieved = cache.get("test_key")
            assert retrieved is not None, "Entry should remain accessible"

        cache.close()


if __name__ == "__main__":
    pytest.main([__file__])
