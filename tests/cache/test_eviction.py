"""Unit tests for cache eviction strategies.

This module tests all eviction strategies to ensure they correctly identify
victims for eviction according to their respective algorithms.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.cache.backends import InMemoryCache
from src.cache.eviction import (
    select_fifo_victim,
    select_lfu_victim,
    select_lru_victim,
    select_size_victim,
    select_ttl_victim,
)
from src.cache.transcription_cache import CacheEntry, CacheKey

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
]


class TestLRUEviction:
    """Tests for Least Recently Used (LRU) eviction strategy."""

    def test_lru_selects_least_recently_accessed(self):
        """LRU should select the entry with the oldest accessed_at time."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries with different access times
        for i in range(5):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time + timedelta(seconds=i),  # key_0 is oldest
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_0 as it has the oldest accessed_at
        victim = select_lru_victim(cache, keys)
        assert victim == "key_0"

    def test_lru_with_ordered_dict_backend(self):
        """LRU should use O(1) optimization for OrderedDict backends."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        # InMemoryCache uses OrderedDict internally
        base_time = datetime.now()

        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time + timedelta(seconds=i),
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # First key in OrderedDict should be selected
        victim = select_lru_victim(cache, keys)
        assert victim in keys  # Should return a valid key

    def test_lru_empty_cache_fallback(self):
        """LRU should handle empty cache gracefully."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"dummy_key"}

        # Should return the only key available
        victim = select_lru_victim(cache, keys)
        assert victim == "dummy_key"

    def test_lru_with_identical_access_times(self):
        """LRU should handle tie-breaking when multiple entries have same accessed_at."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # All entries have the same accessed_at time
        for i in range(5):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,  # All same time
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should return a valid key (deterministic based on min() behavior)
        victim = select_lru_victim(cache, keys)
        assert victim in keys


class TestLFUEviction:
    """Tests for Least Frequently Used (LFU) eviction strategy."""

    def test_lfu_selects_least_frequently_accessed(self):
        """LFU should select the entry with the lowest access count."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries with different access counts
        access_counts = [10, 5, 20, 2, 15]  # key_3 has count 2 (lowest)
        for i, count in enumerate(access_counts):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=count,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_3 with access_count=2
        victim = select_lfu_victim(cache, keys)
        assert victim == "key_3"

    def test_lfu_with_zero_access_count(self):
        """LFU should handle entries with zero access count."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries with varying counts including zero
        access_counts = [5, 0, 10, 3]  # key_1 has count 0
        for i, count in enumerate(access_counts):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=count,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        victim = select_lfu_victim(cache, keys)
        assert victim == "key_1"

    def test_lfu_empty_cache_fallback(self):
        """LFU should handle empty cache gracefully."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"dummy_key"}

        victim = select_lfu_victim(cache, keys)
        assert victim == "dummy_key"

    def test_lfu_with_identical_access_counts(self):
        """LFU should handle tie-breaking when multiple entries have same access_count."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # All entries have the same access count
        for i in range(5):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=10,  # All same count
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should return a valid key (first one encountered with min count)
        victim = select_lfu_victim(cache, keys)
        assert victim in keys

    def test_lfu_multiple_entries_with_same_minimum(self):
        """LFU should handle multiple entries sharing the minimum access count."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Multiple entries with minimum count (5), others higher
        access_counts = [10, 5, 20, 5, 15, 5]  # key_1, key_3, key_5 all have count 5

        for i, count in enumerate(access_counts):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=count,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should return one of the keys with count=5
        victim = select_lfu_victim(cache, keys)
        assert victim in {"key_1", "key_3", "key_5"}


class TestTTLEviction:
    """Tests for TTL (Time To Live) eviction strategy."""

    def test_ttl_selects_soonest_to_expire(self):
        """TTL should select the entry closest to expiration."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now() - timedelta(seconds=100)

        # Create entries with different TTLs
        # Entry with smallest (TTL - age) should be selected
        ttls = [300, 150, 500, 120, 400]  # key_3 with TTL=120 expires soonest
        for i, ttl in enumerate(ttls):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=ttl,
                metadata={},
            )
            cache.put(key, entry)

        victim = select_ttl_victim(cache, keys)
        assert victim == "key_3"

    def test_ttl_with_no_ttl_entries(self):
        """TTL should fallback when no entries have TTL set."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries without TTL (ttl=None)
        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=None,  # No TTL
                metadata={},
            )
            cache.put(key, entry)

        # Should return a valid key (fallback behavior)
        victim = select_ttl_victim(cache, keys)
        assert victim in keys

    def test_ttl_empty_cache_fallback(self):
        """TTL should handle empty cache gracefully."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"dummy_key"}

        victim = select_ttl_victim(cache, keys)
        assert victim == "dummy_key"

    def test_ttl_with_expired_entries(self):
        """TTL should handle entries with negative remaining TTL (expired)."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        # Create entries that expired in the past (created long ago with short TTL)
        base_time = datetime.now() - timedelta(seconds=1000)

        # All entries are expired, but key_0 has least remaining (most negative)
        ttls_and_ages = [
            (100, 1000),  # key_0: TTL=100, age=1000, remaining=-900 (most expired)
            (200, 1000),  # key_1: TTL=200, age=1000, remaining=-800
            (500, 1000),  # key_2: TTL=500, age=1000, remaining=-500
        ]

        for i, (ttl, age_offset) in enumerate(ttls_and_ages):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time - timedelta(seconds=age_offset - 1000),
                accessed_at=base_time,
                access_count=1,
                ttl=ttl,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_0 with most negative remaining TTL
        victim = select_ttl_victim(cache, keys)
        assert victim == "key_0"

    def test_ttl_with_mixed_ttl_and_none(self):
        """TTL should handle mix of entries with TTL and without TTL (None)."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now() - timedelta(seconds=50)

        # Mix of TTL and None entries
        ttl_values = [None, 200, None, 100, None]  # key_3 has TTL=100, expires soonest

        for i, ttl in enumerate(ttl_values):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=ttl,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_3 (TTL=100) ignoring None entries
        victim = select_ttl_victim(cache, keys)
        assert victim == "key_3"


class TestSizeEviction:
    """Tests for SIZE eviction strategy (largest entry)."""

    def test_size_selects_largest_entry(self):
        """SIZE should select the entry with the largest size."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries with different sizes
        sizes = [100, 500, 200, 1000, 300]  # key_3 with size=1000 is largest
        for i, size in enumerate(sizes):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=size,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        victim = select_size_victim(cache, keys)
        assert victim == "key_3"

    def test_size_with_equal_sizes(self):
        """SIZE should handle entries with equal sizes."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # All entries have the same size
        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,  # All same size
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        victim = select_size_victim(cache, keys)
        assert victim in keys  # Should return any valid key

    def test_size_empty_cache_fallback(self):
        """SIZE should handle empty cache gracefully."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"dummy_key"}

        victim = select_size_victim(cache, keys)
        assert victim == "dummy_key"

    def test_size_with_zero_sizes(self):
        """SIZE should handle entries with zero size."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Mix of zero and positive sizes
        sizes = [0, 100, 0, 500, 0]  # key_3 with size=500 is largest

        for i, size in enumerate(sizes):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=size,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_3 with largest size (500)
        victim = select_size_victim(cache, keys)
        assert victim == "key_3"

    def test_size_all_zero_sizes(self):
        """SIZE should handle all entries having zero size."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # All entries have zero size
        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=0,
                created_at=base_time,
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should return a valid key (arbitrary choice when all are zero)
        victim = select_size_victim(cache, keys)
        assert victim in keys


class TestFIFOEviction:
    """Tests for FIFO (First In First Out) eviction strategy."""

    def test_fifo_selects_oldest_entry(self):
        """FIFO should select the entry with the oldest created_at time."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # Create entries with different creation times
        for i in range(5):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time + timedelta(seconds=i),  # Sequential creation
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should select key_0 as it was created first
        victim = select_fifo_victim(cache, keys)
        assert victim == "key_0"

    def test_fifo_with_ordered_dict_backend(self):
        """FIFO should use O(1) optimization for OrderedDict backends."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time + timedelta(seconds=i),
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # First key in OrderedDict should be selected
        victim = select_fifo_victim(cache, keys)
        assert victim in keys

    def test_fifo_empty_cache_fallback(self):
        """FIFO should handle empty cache gracefully."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"dummy_key"}

        victim = select_fifo_victim(cache, keys)
        assert victim == "dummy_key"

    def test_fifo_with_identical_creation_times(self):
        """FIFO should handle tie-breaking when multiple entries have same created_at."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        # All entries have the same creation time
        for i in range(5):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,  # All same time
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            cache.put(key, entry)

        # Should return a valid key (deterministic based on min() behavior)
        victim = select_fifo_victim(cache, keys)
        assert victim in keys


class TestEvictionFallbackPaths:
    """Tests for fallback code paths when OrderedDict optimization unavailable."""

    class MockBackendWithoutOrderedDict:
        """Mock backend that doesn't use OrderedDict for fallback path testing."""

        def __init__(self):
            self._data = {}

        def get(self, key: str):
            return self._data.get(key)

        def put(self, key: str, entry: CacheEntry):
            self._data[key] = entry

    def test_lru_fallback_without_ordered_dict(self):
        """LRU should use fallback path for non-OrderedDict backends."""
        backend = self.MockBackendWithoutOrderedDict()
        keys = set()

        base_time = datetime.now()

        # Create entries with different access times
        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time,
                accessed_at=base_time + timedelta(seconds=i),
                access_count=1,
                ttl=3600,
                metadata={},
            )
            backend.put(key, entry)

        # Should select key_0 (oldest accessed_at) via fallback path
        victim = select_lru_victim(backend, keys)
        assert victim == "key_0"

    def test_fifo_fallback_without_ordered_dict(self):
        """FIFO should use fallback path for non-OrderedDict backends."""
        backend = self.MockBackendWithoutOrderedDict()
        keys = set()

        base_time = datetime.now()

        # Create entries with different creation times
        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100,
                created_at=base_time + timedelta(seconds=i),
                accessed_at=base_time,
                access_count=1,
                ttl=3600,
                metadata={},
            )
            backend.put(key, entry)

        # Should select key_0 (oldest created_at) via fallback path
        victim = select_fifo_victim(backend, keys)
        assert victim == "key_0"


class TestEvictionEdgeCases:
    """Tests for edge cases and error handling in eviction strategies."""

    def test_all_strategies_with_single_key(self):
        """All strategies should handle single-key scenarios."""
        cache = InMemoryCache(max_size_mb=10)
        keys = {"only_key"}

        base_time = datetime.now()
        cache_key = CacheKey(
            file_hash="hash",
            provider="test",
            settings_hash="settings",
        )
        entry = CacheEntry(
            key=cache_key,
            value={"data": "value"},
            size=100,
            created_at=base_time,
            accessed_at=base_time,
            access_count=1,
            ttl=3600,
            metadata={},
        )
        cache.put("only_key", entry)

        # All strategies should return the only key
        assert select_lru_victim(cache, keys) == "only_key"
        assert select_lfu_victim(cache, keys) == "only_key"
        assert select_ttl_victim(cache, keys) == "only_key"
        assert select_size_victim(cache, keys) == "only_key"
        assert select_fifo_victim(cache, keys) == "only_key"

    def test_strategies_with_missing_entries(self):
        """Strategies should handle keys that don't exist in backend."""
        cache = InMemoryCache(max_size_mb=10)
        # Keys set has entries not in cache
        keys = {"missing_key_1", "missing_key_2"}

        # Should fallback to first key in set
        victim_lru = select_lru_victim(cache, keys)
        victim_lfu = select_lfu_victim(cache, keys)
        victim_ttl = select_ttl_victim(cache, keys)
        victim_size = select_size_victim(cache, keys)
        victim_fifo = select_fifo_victim(cache, keys)

        # All should return a valid key from the set
        assert victim_lru in keys
        assert victim_lfu in keys
        assert victim_ttl in keys
        assert victim_size in keys
        assert victim_fifo in keys

    def test_strategies_return_consistent_types(self):
        """All strategies should return string keys."""
        cache = InMemoryCache(max_size_mb=10)
        keys = set()

        base_time = datetime.now()

        for i in range(3):
            key = f"key_{i}"
            keys.add(key)
            cache_key = CacheKey(
                file_hash=f"hash_{i}",
                provider="test",
                settings_hash=f"settings_{i}",
            )
            entry = CacheEntry(
                key=cache_key,
                value={"data": f"value_{i}"},
                size=100 * (i + 1),
                created_at=base_time + timedelta(seconds=i),
                accessed_at=base_time + timedelta(seconds=i * 2),
                access_count=i + 1,
                ttl=3600 - (i * 100),
                metadata={},
            )
            cache.put(key, entry)

        # All strategies should return string type
        assert isinstance(select_lru_victim(cache, keys), str)
        assert isinstance(select_lfu_victim(cache, keys), str)
        assert isinstance(select_ttl_victim(cache, keys), str)
        assert isinstance(select_size_victim(cache, keys), str)
        assert isinstance(select_fifo_victim(cache, keys), str)
