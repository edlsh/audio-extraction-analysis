"""Cache eviction helpers for LRU and TTL policies.

Provides simple victim selection for cache eviction:
- LRU: Evict least recently used (O(1) for OrderedDict backends)
- TTL: Evict entries closest to expiration
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


def select_lru_victim(backend: Any, keys: set[str]) -> str:
    """Select least recently used cache entry for eviction.

    O(1) for OrderedDict backends, O(n) fallback.
    """
    # Fast path for OrderedDict backends
    if hasattr(backend, "_cache") and isinstance(backend._cache, OrderedDict):
        if len(backend._cache) > 0:
            return next(iter(backend._cache.keys()))

    # Fallback: find entry with oldest access time
    entries_with_time = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_time.append((entry.accessed_at, key))

    if not entries_with_time:
        return next(iter(keys))

    return min(entries_with_time)[1]


def select_ttl_victim(backend: Any, keys: set[str]) -> str:
    """Select entry closest to TTL expiration for eviction."""
    min_key = None
    min_remaining = float("inf")

    for key in keys:
        entry = backend.get(key)
        if entry and entry.ttl:
            remaining = entry.ttl - entry.age_seconds()
            if remaining < min_remaining:
                min_remaining = remaining
                min_key = key

    return min_key if min_key is not None else next(iter(keys))


def select_lfu_victim(backend: Any, keys: set[str]) -> str:
    """Select least frequently used cache entry for eviction."""
    entries_with_count = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_count.append((entry.access_count, key))

    if not entries_with_count:
        return next(iter(keys))

    return min(entries_with_count)[1]


def select_size_victim(backend: Any, keys: set[str]) -> str:
    """Select largest cache entry for eviction."""
    entries_with_size = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_size.append((entry.size, key))

    if not entries_with_size:
        return next(iter(keys))

    return max(entries_with_size)[1]


def select_fifo_victim(backend: Any, keys: set[str]) -> str:
    """Select first in (oldest created) cache entry for eviction."""
    entries_with_time = []
    for key in keys:
        entry = backend.get(key)
        if entry:
            entries_with_time.append((entry.created_at, key))

    if not entries_with_time:
        return next(iter(keys))

    return min(entries_with_time)[1]
