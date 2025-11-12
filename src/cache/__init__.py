"""Caching layer for transcription results.

This module provides a comprehensive caching system for transcription operations,
enabling efficient storage and retrieval of transcription results to avoid
redundant processing of the same audio files.

Components:
    Cache Backends:
        - DiskCache: Persistent file-based caching for long-term storage
        - InMemoryCache: Fast in-memory caching for temporary results

    Core Classes:
        - TranscriptionCache: Main cache interface for transcription operations
        - CacheBackend: Abstract base class for implementing cache backends
        - CachePolicy: Configuration for cache behavior (TTL, size limits, etc.)
        - CacheKey: Unique identifier for cached entries based on file hash
        - CacheEntry: Container for cached transcription data and metadata
        - CacheStats: Statistics and metrics for cache performance monitoring

Usage:
    Basic caching with disk backend::

        from cache import TranscriptionCache, DiskCache, CachePolicy

        cache = TranscriptionCache(
            backend=DiskCache(cache_dir="./cache"),
            policy=CachePolicy(ttl_seconds=3600)
        )

        # Check for cached result
        result = cache.get(cache_key)
        if result is None:
            # Process and cache new result
            result = process_audio(file_path)
            cache.set(cache_key, result)

The caching system supports automatic invalidation based on TTL, size limits,
and file modification detection to ensure cache consistency.
"""

# Cache backend implementations
from .backends import DiskCache, InMemoryCache

# Core cache components and interfaces
from .transcription_cache import (
    CacheBackend,
    CacheEntry,
    CacheKey,
    CachePolicy,
    CacheStats,
    TranscriptionCache,
)

# Public API exports - all classes and interfaces available to consumers
__all__ = [
    "CacheBackend",  # Abstract base class for cache implementations
    "CacheEntry",  # Data container for cached items
    "CacheKey",  # Unique identifier for cache entries
    "CachePolicy",  # Cache configuration and behavior settings
    "CacheStats",  # Cache performance metrics
    "DiskCache",  # Persistent file-based cache backend
    "InMemoryCache",  # Fast in-memory cache backend
    "TranscriptionCache",  # Main cache interface for transcriptions
]
