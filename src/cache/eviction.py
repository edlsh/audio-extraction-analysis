"""Cache eviction strategy helpers for selecting victims during cache cleanup.

This module provides pure helper functions for implementing various cache eviction
policies (LRU, LFU, TTL, Size-based, FIFO). These functions are designed to be
reusable across different cache backend implementations and are optimized for
performance using heap-based and OrderedDict operations.

Each function selects a victim key from a set of candidates based on a specific
eviction strategy. The victim is the cache entry that should be removed to make
space for new entries.

Performance characteristics:
- LRU/FIFO: O(1) for OrderedDict backends, O(n) fallback
- LFU/TTL/Size: O(n) optimized with single-pass algorithms
- All functions avoid intermediate list construction for memory efficiency

Backend Requirements:
The backend parameter must implement a get(key) method that returns cache entries
with the following attributes (depending on the eviction strategy):
- accessed_at: datetime (for LRU)
- access_count: int (for LFU)
- ttl: Optional[float], age_seconds(): float (for TTL)
- size: int (for Size-based)
- created_at: datetime (for FIFO)
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


def select_lru_victim(backend: Any, keys: set[str]) -> str:
    """Select the least recently used (LRU) cache entry as eviction victim.

    Chooses the cache entry with the oldest accessed_at timestamp. For
    OrderedDict-based backends that maintain LRU order via move_to_end(),
    this is O(1) as the first key is always the LRU entry. Otherwise falls
    back to O(n) scan of all entries.

    Args:
        backend: Cache backend with get(key) method returning entries with
            accessed_at attribute. For O(1) performance, backend should have
            an OrderedDict _cache attribute maintained in LRU order.
        keys: Set of candidate cache keys to consider for eviction. Must not
            be empty.

    Returns:
        The key of the least recently used entry. If no valid entries are found,
        returns an arbitrary key from the input set.

    Complexity:
        O(1) for OrderedDict backends, O(n) for generic backends.
    """
    # O(1) optimization for OrderedDict-based backends
    if hasattr(backend, "_cache") and isinstance(backend._cache, OrderedDict):
        if len(backend._cache) > 0:
            return next(iter(backend._cache.keys()))

    # Fallback: O(n) single-pass with min() built-in (faster than manual loop)
    entries_with_time = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_time.append((entry.accessed_at, key))

    # If no valid entries found (all None from backend.get), return arbitrary key
    if not entries_with_time:
        return next(iter(keys))

    # min() on tuple compares by first element (accessed_at), return key at [1]
    return min(entries_with_time)[1]


def select_lfu_victim(backend: Any, keys: set[str]) -> str:
    """Select the least frequently used (LFU) cache entry as eviction victim.

    Chooses the cache entry with the lowest access_count. Uses a single-pass
    algorithm with in-place comparison to minimize memory allocation and avoid
    redundant backend.get() calls.

    Args:
        backend: Cache backend with get(key) method returning entries with
            access_count attribute (integer representing usage frequency).
        keys: Set of candidate cache keys to consider for eviction. Must not
            be empty.

    Returns:
        The key of the least frequently used entry. If no valid entries are found,
        returns an arbitrary key from the input set.

    Complexity:
        O(n) where n is the number of keys, optimized with single-pass algorithm.
    """
    min_key = None
    min_count = float("inf")

    # Single pass: track minimum access count and corresponding key
    for key in keys:
        entry = backend.get(key)
        if entry:
            if entry.access_count < min_count:
                min_count = entry.access_count
                min_key = key

    # If no valid entries found, return arbitrary key; otherwise return min_key
    return min_key if min_key is not None else next(iter(keys))


def select_ttl_victim(backend: Any, keys: set[str]) -> str:
    """Select the cache entry closest to expiration (TTL) as eviction victim.

    Chooses the cache entry with the least remaining time-to-live (TTL). This
    strategy prioritizes evicting entries that will expire soon anyway, making
    space while minimizing the loss of potentially useful cached data. Uses a
    single-pass algorithm with in-place comparison for efficiency.

    Args:
        backend: Cache backend with get(key) method returning entries with
            ttl attribute (Optional[float], seconds until expiry) and
            age_seconds() method (returns elapsed time since creation).
        keys: Set of candidate cache keys to consider for eviction. Must not
            be empty.

    Returns:
        The key of the entry with the least remaining TTL. Only considers entries
        that have a TTL set. If no entries have TTL configured, returns an
        arbitrary key from the input set.

    Complexity:
        O(n) where n is the number of keys, optimized with single-pass algorithm.
    """
    min_key = None
    min_remaining = float("inf")

    # Single pass: find entry with least remaining TTL (only considers entries with TTL set)
    for key in keys:
        entry = backend.get(key)
        if entry and entry.ttl:
            remaining = entry.ttl - entry.age_seconds()
            if remaining < min_remaining:
                min_remaining = remaining
                min_key = key

    # If no TTL entries found, return arbitrary key; otherwise return min_key
    return min_key if min_key is not None else next(iter(keys))


def select_size_victim(backend: Any, keys: set[str]) -> str:
    """Select the largest cache entry (by size) as eviction victim.

    Chooses the cache entry with the largest size attribute. This strategy is
    useful for freeing maximum space quickly, as removing one large entry may
    provide enough room for multiple smaller entries. Uses a single-pass
    algorithm with in-place comparison for efficiency.

    Args:
        backend: Cache backend with get(key) method returning entries with
            size attribute (integer representing memory/storage size in bytes).
        keys: Set of candidate cache keys to consider for eviction. Must not
            be empty.

    Returns:
        The key of the largest entry. If no valid entries are found, returns
        an arbitrary key from the input set.

    Complexity:
        O(n) where n is the number of keys, optimized with single-pass algorithm.
    """
    max_key = None
    max_size = 0

    # Single pass: track maximum size and corresponding key
    for key in keys:
        entry = backend.get(key)
        if entry:
            if entry.size > max_size:
                max_size = entry.size
                max_key = key

    # If no valid entries found, return arbitrary key; otherwise return max_key
    return max_key if max_key is not None else next(iter(keys))


def select_fifo_victim(backend: Any, keys: set[str]) -> str:
    """Select the oldest cache entry (FIFO) as eviction victim.

    Chooses the cache entry with the oldest created_at timestamp. This implements
    a First-In-First-Out (FIFO) queue eviction policy, where the oldest entry is
    always evicted first. For OrderedDict-based backends that maintain insertion
    order, this is O(1) as the first key is always the oldest. Otherwise falls
    back to O(n) scan of all entries.

    Args:
        backend: Cache backend with get(key) method returning entries with
            created_at attribute (datetime). For O(1) performance, backend should
            have an OrderedDict _cache attribute that preserves insertion order.
        keys: Set of candidate cache keys to consider for eviction. Must not
            be empty.

    Returns:
        The key of the oldest entry (earliest created_at). If no valid entries
        are found, returns an arbitrary key from the input set.

    Complexity:
        O(1) for OrderedDict backends, O(n) for generic backends.
    """
    # O(1) optimization for OrderedDict-based backends
    if hasattr(backend, "_cache") and isinstance(backend._cache, OrderedDict):
        if len(backend._cache) > 0:
            return next(iter(backend._cache.keys()))

    # Fallback: O(n) single-pass with min() built-in
    entries_with_time = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_time.append((entry.created_at, key))

    # If no valid entries found (all None from backend.get), return arbitrary key
    if not entries_with_time:
        return next(iter(keys))

    # min() on tuple compares by first element (created_at), return key at [1]
    return min(entries_with_time)[1]
