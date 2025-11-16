"""
Common cache utilities and protocols.

This module provides shared functionality for cache backend implementations,
including abstract protocols, serialization helpers, and management utilities.

Components:
    - BaseCache: Protocol defining the standard cache backend interface
    - CacheUtils: Static utility methods for cache key normalization and sizing
    - SerializationHelper: JSON-based serialization with optional compression
    - TTLManager: Time-to-live expiration management utilities
    - SizeLimitManager: Cache size tracking and limit enforcement

All cache backends should implement the BaseCache protocol to ensure
consistency across different storage mechanisms (memory, Redis, disk, etc.).
"""

from __future__ import annotations

import json
import logging
import sys
import zlib
from typing import Protocol, runtime_checkable

from .transcription_cache import CacheEntry

logger = logging.getLogger(__name__)


@runtime_checkable
class BaseCache(Protocol):
    """Protocol defining the standard cache backend interface.

    This protocol establishes a contract that all cache backends must follow,
    enabling polymorphic usage and contract-based testing. Implementations
    should handle serialization, TTL expiration, and size management internally.

    Note:
        Implementations should be thread-safe if used in concurrent contexts.
        All methods should handle errors gracefully and return appropriate
        success/failure indicators rather than raising exceptions.
    """

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry by key.

        Args:
            key: Cache key to retrieve

        Returns:
            CacheEntry if found and not expired, None otherwise.
            Returns None for missing keys, expired entries, or deserialization errors.
        """
        ...

    def put(self, key: str, entry: CacheEntry) -> bool:
        """Store a cache entry.

        Args:
            key: Cache key for storage
            entry: CacheEntry object to store

        Returns:
            True if stored successfully, False on failure.
            May return False due to serialization errors, size limits,
            or backend storage issues.
        """
        ...

    def delete(self, key: str) -> bool:
        """Remove an entry from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if the entry existed and was deleted, False if key not found.
        """
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists and has not expired, False otherwise.
        """
        ...

    def clear(self) -> int:
        """Remove all entries from the cache.

        Returns:
            The number of entries that were cleared.
        """
        ...

    def size(self) -> int:
        """Get the current cache size.

        Returns:
            Total size of all cached entries in bytes, excluding overhead.
        """
        ...

    def keys(self) -> set[str]:
        """Retrieve all valid cache keys.

        Returns:
            Set containing all non-expired cache keys currently stored.
            May be empty if cache is empty or all entries have expired.
        """
        ...


class CacheUtils:
    """Static utility methods for common cache operations.

    Provides helper functions for key normalization, size calculation,
    and entry validation. All methods are stateless and thread-safe.
    """

    @staticmethod
    def normalize_key(key: str) -> str:
        """Normalize a cache key for consistent storage and retrieval.

        Performs case-insensitive normalization by stripping whitespace
        and converting to lowercase. This ensures that keys like "MyKey",
        "mykey", and " MyKey " all map to the same cache entry.

        Args:
            key: Raw cache key string

        Returns:
            Normalized lowercase key with whitespace removed.

        Note:
            For very long keys (>200 chars), consider using a hash-based
            approach to limit key length in storage backends.
        """
        # Simple normalization - could be extended with SHA256 hashing for very long keys
        return key.strip().lower()

    @staticmethod
    def calculate_size(value: object) -> int:
        """Calculate the approximate size of a value in bytes.

        Provides size estimates for different value types to assist with
        cache size management and eviction policies.

        Args:
            value: The value to measure (str, bytes, or any object)

        Returns:
            Estimated size in bytes. For bytes/bytearray returns exact length,
            for strings returns UTF-8 encoded size, for other objects returns
            sys.getsizeof() estimate (includes object overhead).

        Note:
            For complex objects, sys.getsizeof() only measures shallow size
            and may not include referenced objects. Consider deep size
            calculation for nested structures if accuracy is critical.
        """
        if isinstance(value, (bytes, bytearray)):
            return len(value)
        elif isinstance(value, str):
            return len(value.encode("utf-8"))

        # For complex objects, use sys.getsizeof as approximate estimate
        return sys.getsizeof(value)

    @staticmethod
    def is_expired(entry: CacheEntry) -> bool:
        """Check if a cache entry has expired based on its TTL.

        Delegates to the entry's built-in expiration check method,
        which compares the current time against the creation time plus TTL.

        Args:
            entry: CacheEntry instance to validate

        Returns:
            True if the entry has expired, False if still valid or no TTL set.
        """
        return entry.is_expired()


class SerializationHelper:
    """JSON-based serialization utilities with optional zlib compression.

    Provides safe serialization and deserialization methods for cache entries
    and arbitrary values. Handles edge cases gracefully and supports optional
    compression for larger payloads.

    All methods use UTF-8 encoding and JSON format for cross-platform compatibility.
    Compression uses zlib level 6 (balanced speed/size ratio).
    """

    @staticmethod
    def serialize_entry(entry: CacheEntry, use_compression: bool = False) -> bytes:
        """Serialize a CacheEntry to bytes for storage.

        Converts the entry to a dictionary representation, then encodes as
        JSON bytes. Optionally compresses the result using zlib.

        Args:
            entry: CacheEntry instance to serialize
            use_compression: If True, compress data with zlib level 6

        Returns:
            UTF-8 encoded JSON bytes, optionally compressed.

        Raises:
            ValueError: If entry cannot be serialized (e.g., non-JSON-safe values)
                or if compression fails.
        """
        try:
            # Convert entry to dict
            entry_dict = entry.to_dict()

            # Convert to JSON bytes
            json_bytes = json.dumps(entry_dict, ensure_ascii=False).encode("utf-8")

            if use_compression:
                # Compress with zlib
                json_bytes = zlib.compress(json_bytes, level=6)

            return json_bytes

        except (TypeError, ValueError, zlib.error) as e:
            raise ValueError(f"Failed to serialize cache entry: {e}") from e

    @staticmethod
    def deserialize_entry(data: bytes, is_compressed: bool = False) -> CacheEntry | None:
        """Deserialize bytes back into a CacheEntry instance.

        Reverses the serialization process: decompresses if needed, decodes
        UTF-8 JSON, and reconstructs the CacheEntry from the dictionary.

        Args:
            data: Serialized byte data
            is_compressed: If True, decompress data before deserializing

        Returns:
            Reconstructed CacheEntry instance, or None if deserialization fails.
            Returns None for corrupted data, invalid JSON, missing fields, or
            decompression errors. Errors are logged for debugging.

        Note:
            This method never raises exceptions - errors are logged and None
            is returned to allow graceful degradation in cache operations.
        """
        try:
            # Decompress if needed
            if is_compressed:
                data = zlib.decompress(data)

            # Parse JSON
            entry_dict = json.loads(data.decode("utf-8"))

            # Reconstruct entry
            return CacheEntry.from_dict(entry_dict)

        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, zlib.error, ValueError) as e:
            logger.error(f"Failed to deserialize cache entry: {e}")
            return None

    @staticmethod
    def serialize_value(value: object, use_compression: bool = False) -> bytes:
        """Serialize an arbitrary value to bytes with type preservation.

        Handles multiple value types intelligently:
        - Objects with to_dict() method: calls method and stores type info
        - JSON-serializable values: stores directly with type info
        - Non-serializable objects: converts to string representation

        Args:
            value: Any Python value to serialize
            use_compression: If True, compress the JSON bytes with zlib

        Returns:
            UTF-8 encoded JSON bytes containing type metadata and value data.

        Raises:
            ValueError: If serialization completely fails (rare - falls back to str()).

        Note:
            Type information is preserved in the serialized format to enable
            proper reconstruction during deserialization.
        """
        try:
            # Handle different value types
            if hasattr(value, "to_dict") and callable(value.to_dict):
                # Object with to_dict method
                value_dict = {"type": type(value).__name__, "data": value.to_dict()}
            else:
                # Try direct JSON serialization
                try:
                    json.dumps(value)  # Test serializable
                    value_dict = {"type": type(value).__name__, "data": value}
                except (TypeError, ValueError):
                    # Fallback to string representation
                    value_dict = {"type": "str", "data": str(value)}

            json_bytes = json.dumps(value_dict).encode("utf-8")

            if use_compression:
                json_bytes = zlib.compress(json_bytes, level=6)

            return json_bytes

        except Exception as e:
            raise ValueError(f"Failed to serialize value: {e}") from e

    @staticmethod
    def deserialize_value(data: bytes, is_compressed: bool = False) -> object | None:
        """Deserialize bytes back into the original value type.

        Attempts to reconstruct the original value using stored type metadata.
        Supports automatic reconstruction of known types (e.g., TranscriptionResult).

        Args:
            data: Serialized byte data
            is_compressed: If True, decompress before deserializing

        Returns:
            Reconstructed value in its original type, or None on failure.
            For TranscriptionResult objects, attempts class reconstruction.
            For unknown types, returns raw dictionary data.

        Note:
            Errors are logged but not raised. Returns None for corrupted data,
            invalid JSON, or decompression failures to enable graceful handling.
        """
        try:
            if is_compressed:
                data = zlib.decompress(data)

            value_dict = json.loads(data.decode("utf-8"))
            value_type = value_dict.get("type", "dict")
            value_data = value_dict.get("data")

            # Reconstruct based on type
            if value_type == "TranscriptionResult" and isinstance(value_data, dict):
                try:
                    from ..models.transcription import TranscriptionResult

                    return TranscriptionResult.from_dict(value_data)
                except ImportError:
                    # If model not available, return raw dict
                    return value_data
            elif value_type == "str":
                return str(value_data)
            else:
                # Return as object (dict, list, etc.)
                if isinstance(value_data, (dict, list, str, int, float, bool, type(None))):
                    return value_data
                else:
                    # Log warning for unexpected types instead of silent None
                    logger.warning(
                        f"Cannot deserialize non-primitive type {type(value_data).__name__}: "
                        f"expected dict, list, str, int, float, bool, or None. "
                        f"Cached data may be corrupted or from incompatible version."
                    )
                    return None

        except zlib.error as e:
            logger.warning(f"Failed to decompress cached data: {e}. Cache entry may be corrupted.")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse cached JSON data: {e}. Cache entry may be corrupted.")
            return None
        except Exception as e:
            logger.warning(
                f"Failed to deserialize cached value: {e}. Returning None for graceful degradation."
            )
            return None


class TTLManager:
    """Utilities for managing Time-To-Live (TTL) based cache expiration.

    Provides methods to check expiration status and calculate remaining lifetime
    for cache entries with TTL values. All time comparisons use Unix timestamps.
    """

    @staticmethod
    def is_expired(entry: CacheEntry, current_time: float | None = None) -> bool:
        """Determine if a cache entry has exceeded its TTL.

        Compares the entry's age (time since creation) against its TTL value.
        Entries without a TTL (None) never expire.

        Args:
            entry: CacheEntry instance to validate
            current_time: Optional Unix timestamp for "now". If None, uses time.time().
                Useful for testing or batch expiration checks with a fixed reference time.

        Returns:
            True if the entry has expired (age > TTL), False otherwise.
            Always returns False for entries with ttl=None (infinite lifetime).
        """
        if entry.ttl is None:
            return False

        import time

        now = current_time or time.time()
        created_timestamp = entry.created_at.timestamp()

        return (now - created_timestamp) > entry.ttl

    @staticmethod
    def time_until_expiry(entry: CacheEntry) -> float | None:
        """Calculate remaining lifetime for a cache entry.

        Computes how many seconds remain until the entry expires based on
        its creation time and TTL value.

        Args:
            entry: CacheEntry instance to analyze

        Returns:
            Remaining seconds until expiration (>= 0.0), or None if no TTL set.
            Returns 0.0 for already-expired entries (never negative).
            Returns None for entries with ttl=None (infinite lifetime).

        Example:
            >>> entry = CacheEntry(data="test", ttl=60)  # 60 second TTL
            >>> # After 45 seconds...
            >>> TTLManager.time_until_expiry(entry)
            15.0
        """
        if entry.ttl is None:
            return None

        import time

        now = time.time()
        created_timestamp = entry.created_at.timestamp()
        elapsed = now - created_timestamp

        return max(0, entry.ttl - elapsed)


class SizeLimitManager:
    """Stateful manager for tracking and enforcing cache size limits.

    Maintains a running total of cache size and provides methods to check
    capacity constraints before adding entries. Useful for implementing
    size-based eviction policies (e.g., LRU with max size).

    Attributes:
        max_size_bytes: Maximum allowed cache size in bytes (read-only)
        current_size: Current total size of cached entries in bytes
        available_space: Remaining capacity in bytes
        utilization_percent: Current usage as percentage (0-100)
    """

    def __init__(self, max_size_bytes: int) -> None:
        """Initialize a new size limit manager.

        Args:
            max_size_bytes: Maximum cache size in bytes (must be positive)
        """
        self.max_size_bytes = max_size_bytes
        self._current_size = 0

    def can_fit(self, entry_size: int) -> bool:
        """Check if an entry size is within absolute size limits.

        Validates that the entry itself doesn't exceed max_size_bytes,
        regardless of current cache usage.

        Args:
            entry_size: Size of the entry in bytes

        Returns:
            True if entry_size <= max_size_bytes, False otherwise.

        Note:
            This checks absolute size, not available space. Use would_exceed_limit()
            to check if adding the entry would overflow current usage.
        """
        return entry_size <= self.max_size_bytes

    def would_exceed_limit(self, entry_size: int) -> bool:
        """Check if adding an entry would overflow the size limit.

        Determines whether adding entry_size to the current cache would
        exceed max_size_bytes, indicating eviction is needed.

        Args:
            entry_size: Size of entry to potentially add (bytes)

        Returns:
            True if (current_size + entry_size) > max_size_bytes, False otherwise.
        """
        return (self._current_size + entry_size) > self.max_size_bytes

    def space_needed_for(self, entry_size: int) -> int:
        """Calculate how much space must be freed to fit an entry.

        Computes the number of bytes that need to be evicted from the cache
        before adding the new entry. Used for implementing eviction logic.

        Args:
            entry_size: Size of entry to add (bytes)

        Returns:
            Number of bytes to free (>= 0). Returns 0 if entry fits without eviction.

        Example:
            >>> manager = SizeLimitManager(max_size_bytes=1000)
            >>> manager.add_entry(800)  # Current size: 800
            >>> manager.space_needed_for(300)  # Would total 1100
            100  # Need to free 100 bytes
        """
        if not self.would_exceed_limit(entry_size):
            return 0

        return (self._current_size + entry_size) - self.max_size_bytes

    def add_entry(self, entry_size: int) -> None:
        """Increment the current size counter when adding an entry.

        Updates internal tracking when a new entry is stored. Should be called
        after successfully storing an entry in the cache backend.

        Args:
            entry_size: Size of the added entry in bytes

        Note:
            This method does not enforce limits - use can_fit() and
            would_exceed_limit() before adding entries.
        """
        self._current_size += entry_size

    def remove_entry(self, entry_size: int) -> None:
        """Decrement the current size counter when removing an entry.

        Updates internal tracking when an entry is deleted or evicted.
        Should be called after successfully removing an entry.

        Args:
            entry_size: Size of the removed entry in bytes

        Note:
            Ensures current_size never goes negative (floor of 0).
        """
        self._current_size = max(0, self._current_size - entry_size)

    def reset(self) -> None:
        """Reset the size counter to zero.

        Typically called when clearing the entire cache or during initialization.
        Does not modify max_size_bytes.
        """
        self._current_size = 0

    @property
    def current_size(self) -> int:
        """Current total size of all cached entries in bytes.

        Returns:
            Sum of all entry sizes tracked by add_entry() calls.
        """
        return self._current_size

    @property
    def available_space(self) -> int:
        """Remaining capacity before hitting the size limit.

        Returns:
            Number of bytes available (max_size_bytes - current_size).
            Always >= 0, even if current_size somehow exceeds limit.
        """
        return max(0, self.max_size_bytes - self._current_size)

    @property
    def utilization_percent(self) -> float:
        """Current cache utilization as a percentage.

        Returns:
            Percentage of max_size_bytes currently in use (0.0 - 100.0).
            Returns 0.0 if max_size_bytes is 0 to avoid division by zero.

        Example:
            >>> manager = SizeLimitManager(max_size_bytes=1000)
            >>> manager.add_entry(750)
            >>> manager.utilization_percent
            75.0
        """
        if self.max_size_bytes == 0:
            return 0.0
        return (self._current_size / self.max_size_bytes) * 100
