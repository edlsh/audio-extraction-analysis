"""Cache backend implementations for audio extraction.

This module provides two cache backend implementations:

- InMemoryCache: Fast, thread-safe in-memory cache with LRU eviction policy.
  Best for: Small to medium-sized caches, low latency requirements.

- DiskCache: Persistent SQLite-based cache with WAL mode for concurrent access.
  Best for: Large datasets, persistence across sessions, multi-process scenarios.

Both backends implement the CacheBackend interface and provide automatic size
management with configurable limits.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock, RLock, local

from .common import CacheUtils, SizeLimitManager
from .transcription_cache import CacheBackend, CacheEntry

logger = logging.getLogger(__name__)


class InMemoryCache(CacheBackend):
    """Thread-safe in-memory cache with LRU eviction policy.

    This cache implementation stores entries in memory using an OrderedDict,
    providing O(1) access and automatic Least Recently Used (LRU) eviction
    when size limits are reached.

    Thread Safety:
        All operations are protected by an RLock, making this cache safe for
        concurrent access from multiple threads within a single process.

    Eviction Policy:
        - Entries are evicted in LRU order when size limit is exceeded
        - Each get() operation updates the access order (moves to end)
        - Eviction is automatic and transparent during put() operations

    Performance:
        - O(1) get, put, delete operations
        - In-memory storage provides minimal latency
        - No persistence - data lost on process termination

    Attributes:
        max_size_bytes (int): Maximum total size in bytes across all entries
        _cache (OrderedDict): Internal storage with LRU ordering
        _lock (RLock): Reentrant lock for thread safety
        _size_manager (SizeLimitManager): Tracks current cache size
    """

    def __init__(self, max_size_mb: int = 100) -> None:
        """Initialize in-memory cache.

        Args:
            max_size_mb: Maximum cache size in MB
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._size_manager = SizeLimitManager(self.max_size_bytes)

        logger.info(f"Initialized InMemoryCache with max_size={max_size_mb}MB")

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry and update its LRU position.

        Thread-safe operation that retrieves an entry by key and moves it to
        the end of the access order (marking it as most recently used).

        Args:
            key: Cache key to retrieve

        Returns:
            CacheEntry if found, None if key doesn't exist

        Note:
            Side effect: Updates LRU order by moving accessed entry to end
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                # Move to end (LRU)
                self._cache.move_to_end(key)
            return entry

    def put(self, key: str, entry: CacheEntry) -> bool:
        """Store a cache entry with automatic eviction if needed.

        Thread-safe operation that stores an entry, automatically evicting older
        entries if necessary to stay within size limits. The key is normalized
        before storage for consistency.

        Args:
            key: Cache key (will be normalized internally)
            entry: Cache entry to store

        Returns:
            True if entry was stored successfully, False if:
            - Entry size exceeds total cache capacity
            - Unable to free enough space through eviction

        Note:
            Side effects:
            - Normalizes the key for consistent lookups
            - Removes and replaces existing entry if key already exists
            - May evict oldest entries to make space
            - Updates size tracking
        """
        # Normalize key for consistency (handles case, whitespace variations)
        normalized_key = CacheUtils.normalize_key(key)

        with self._lock:
            # Reject if entry is larger than total cache capacity
            if not self._size_manager.can_fit(entry.size):
                return False

            # If updating existing entry, first remove it from size tracking
            if normalized_key in self._cache:
                old_entry = self._cache[normalized_key]
                self._size_manager.remove_entry(old_entry.size)

            # Evict oldest entries until enough space available
            # Continues until entry can fit or cache is empty
            while self._size_manager.would_exceed_limit(entry.size):
                if not self._evict_oldest():
                    return False

            # Store entry and update size tracking
            self._cache[normalized_key] = entry
            self._size_manager.add_entry(entry.size)
            return True

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            return key in self._cache

    def delete(self, key: str) -> bool:
        """Delete entry from memory.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self._size_manager.remove_entry(entry.size)
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._size_manager.reset()
            return count

    def size(self) -> int:
        """Get cache size in bytes.

        Returns:
            Size in bytes
        """
        return self._size_manager.current_size

    def keys(self) -> set[str]:
        """Get all cache keys.

        Returns:
            Set of keys
        """
        with self._lock:
            return set(self._cache.keys())

    def _evict_oldest(self) -> bool:
        """Evict the least recently used (oldest) entry from cache.

        Internal method called during put() operations when space is needed.
        Removes the first entry from the OrderedDict (least recently accessed).

        Returns:
            True if an entry was evicted, False if cache was empty

        Note:
            Must be called within a lock context. Updates size tracking.
        """
        if not self._cache:
            return False

        # Get oldest (first) entry
        key, entry = next(iter(self._cache.items()))
        self._size_manager.remove_entry(entry.size)
        del self._cache[key]
        return True


class DiskCache(CacheBackend):
    """Persistent, thread-safe disk cache using SQLite with WAL mode.

    This cache implementation provides durable storage using SQLite database
    with Write-Ahead Logging (WAL) for improved concurrent access. Suitable
    for larger datasets and scenarios requiring persistence across sessions.

    Thread Safety:
        Uses thread-local storage for SQLite connections (one per thread) since
        SQLite connections are not thread-safe. All operations are additionally
        protected by a Lock for consistency.

    Persistence:
        Data is persisted to disk in SQLite database format. Survives process
        restarts and can be shared across process instances (with file locking).

    WAL Mode Benefits:
        - Concurrent reads without blocking
        - Better write performance
        - Crash resistance with automatic recovery
        - Configured with NORMAL synchronous mode for balanced safety/performance

    Eviction Policy:
        - Evicts least recently accessed entries when size limit is exceeded
        - Access time and count tracked automatically in database
        - Uses indexed queries for efficient eviction selection

    Performance Optimizations:
        - Thread-local connections reduce connection overhead
        - Indexed access_at and size columns for fast queries
        - PRAGMA optimizations (temp_store=MEMORY, synchronous=NORMAL)
        - Lazy connection creation per thread

    Attributes:
        cache_dir (Path): Directory containing cache database
        db_path (Path): Path to SQLite database file
        max_size_bytes (int): Maximum total cache size in bytes
        _lock (Lock): Global lock for consistency across threads
        _local (threading.local): Thread-local storage for connections
    """

    def __init__(self, cache_dir: str | Path | None = None, max_size_mb: int = 1000) -> None:
        """Initialize disk cache.

        Args:
            cache_dir: Cache directory (string or Path object)
            max_size_mb: Maximum cache size in MB
        """
        if cache_dir is None:
            self.cache_dir = Path.home() / ".audio_extraction" / "cache"
        else:
            self.cache_dir = Path(cache_dir) if isinstance(cache_dir, str) else cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "cache.db"
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = Lock()

        # Thread-local storage for connections (SQLite connections aren't thread-safe)
        self._local = local()

        self._init_database()
        logger.info(
            f"Initialized DiskCache at {self.cache_dir} with max_size={max_size_mb}MB (WAL mode)"
        )

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local database connection with optimizations.

        Each thread gets its own connection stored in thread-local storage.
        Connections are lazily created on first use per thread and configured
        with performance optimizations (WAL mode, NORMAL sync, memory temp store).

        Returns:
            Thread-local SQLite connection with optimizations applied

        Note:
            Connection is cached in thread-local storage and reused for all
            subsequent calls from the same thread. Not thread-safe to share
            connections across threads.
        """
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path))
            # Enable WAL (Write-Ahead Logging) mode for concurrent reads
            # WAL allows multiple readers while a writer is active
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            # Performance optimizations:
            # - NORMAL sync: balance between safety and speed (fsync at checkpoints)
            # - MEMORY temp store: use RAM for temporary tables/indexes
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA temp_store=MEMORY")
        return self._local.conn

    def _init_database(self) -> None:
        """Initialize SQLite database schema with tables and indexes.

        Creates the cache_entries table with columns for key, value, metadata,
        and access tracking. Sets up indexes on accessed_at and size columns
        for efficient eviction queries.

        Note:
            Uses IF NOT EXISTS so safe to call multiple times.
            WAL mode is enabled per-connection in _get_connection().
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                size INTEGER NOT NULL,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                ttl INTEGER,
                metadata TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_accessed
            ON cache_entries(accessed_at)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_size
            ON cache_entries(size)
        """
        )

        conn.commit()

    def get(self, key: str) -> CacheEntry | None:
        """Retrieve a cache entry from disk and update access statistics.

        Thread-safe operation that reads an entry from SQLite database,
        deserializes it, and updates its access timestamp and count.

        Args:
            key: Cache key to retrieve

        Returns:
            CacheEntry if found and successfully deserialized, None if:
            - Key doesn't exist in database
            - Entry is corrupted and cannot be deserialized
            - Database error occurs

        Note:
            Side effects:
            - Updates accessed_at timestamp to current time
            - Increments access_count by 1
            - Removes corrupted entries automatically
            - Logs errors on deserialization failures
        """
        with self._lock:
            try:
                row = self._query_entry(key)
                if row:
                    self._update_access_stats(key)
                    return self._deserialize_entry(row, key)
                return None

            except Exception as e:
                logger.error(f"Failed to get from disk cache: {e}")
                return None

    def _query_entry(self, key: str) -> tuple | None:
        """Query cache entry from database.

        Args:
            key: Cache key

        Returns:
            Database row or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT value, size, created_at, accessed_at,
                   access_count, ttl, metadata
            FROM cache_entries
            WHERE key = ?
        """,
            (key,),
        )

        return cursor.fetchone()

    def _update_access_stats(self, key: str) -> None:
        """Update access time and count for an entry.

        Args:
            key: Cache key
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cache_entries
            SET accessed_at = ?, access_count = access_count + 1
            WHERE key = ?
        """,
            (time.time(), key),
        )
        conn.commit()

    def _deserialize_entry(self, row: tuple, key: str) -> CacheEntry | None:
        """Deserialize cache entry from database row with error recovery.

        Attempts to decode and deserialize JSON-encoded cache entry from
        database BLOB. Handles circular import issues and automatically
        cleans up corrupted entries.

        Args:
            row: Database row tuple with BLOB value at index 0
            key: Cache key (used for cleanup if deserialization fails)

        Returns:
            Deserialized CacheEntry object, or None if:
            - JSON decoding fails (invalid JSON)
            - Unicode decoding fails (corrupted BLOB)
            - Required keys missing from dict
            - CacheEntry import fails

        Note:
            Side effect: Automatically deletes corrupted entries from database
            and logs the error for debugging.
        """
        try:
            entry_dict = json.loads(row[0].decode("utf-8"))
            # Handle potential circular import when importing CacheEntry
            # at runtime (already imported at module level, but using explicit
            # import here for clarity and to handle edge cases)
            try:
                from .transcription_cache import CacheEntry
            except ImportError:
                # Fallback: use the already imported class from module globals
                CacheEntry = globals().get("CacheEntry")
                if not CacheEntry:
                    raise ImportError("CacheEntry not available")
            entry_data = CacheEntry.from_dict(entry_dict)
            return entry_data
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, ImportError) as e:
            logger.error(f"Failed to deserialize cache entry: {e}")
            # Clean up corrupted entry
            self._delete_corrupted_entry(key)
            return None

    def _delete_corrupted_entry(self, key: str) -> None:
        """Delete corrupted cache entry.

        Args:
            key: Cache key
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        conn.commit()

    def put(self, key: str, entry: CacheEntry) -> bool:
        """Store a cache entry to disk with automatic eviction if needed.

        Thread-safe operation that serializes and stores an entry in SQLite
        database. Automatically evicts least recently accessed entries if
        necessary to stay within size limits.

        Args:
            key: Cache key for storage
            entry: CacheEntry object to store (will be JSON-serialized)

        Returns:
            True if entry was stored successfully, False if:
            - Entry size exceeds total cache capacity
            - Serialization fails
            - Database error occurs

        Note:
            Side effects:
            - Uses INSERT OR REPLACE (updates existing entry if key exists)
            - May evict multiple entries to make space
            - Serializes entry to JSON and stores as BLOB
            - Stores metadata separately for query efficiency
            - Logs errors on failure
        """
        with self._lock:
            try:
                # Reject if entry is larger than total cache capacity
                if entry.size > self.max_size_bytes:
                    return False

                # Free up space by evicting old entries if needed
                self._evict_if_needed(entry.size)

                conn = self._get_connection()
                cursor = conn.cursor()

                # Serialize entry to JSON and encode as UTF-8 bytes for BLOB storage
                # Metadata is stored separately in TEXT column for easier querying
                entry_dict = entry.to_dict()
                entry_data = json.dumps(entry_dict).encode("utf-8")

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (key, value, size, created_at, accessed_at,
                     access_count, ttl, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        entry_data,
                        entry.size,
                        entry.created_at.timestamp(),
                        entry.accessed_at.timestamp(),
                        entry.access_count,
                        entry.ttl,
                        json.dumps(entry.metadata),
                    ),
                )

                conn.commit()
                return True

            except Exception as e:
                logger.error(f"Failed to put in disk cache: {e}")
                return False

    def exists(self, key: str) -> bool:
        """Check if key exists in disk cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cache_entries WHERE key = ?", (key,))
                count = cursor.fetchone()[0]
                return count > 0
            except Exception as e:
                logger.error(f"Failed to check disk cache exists: {e}")
                return False

    def delete(self, key: str) -> bool:
        """Delete entry from disk.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return cursor.rowcount > 0

            except Exception as e:
                logger.error(f"Failed to remove entry from disk cache: {e}")
                return False

    def clear(self) -> int:
        """Clear all entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cache_entries")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM cache_entries")
                conn.commit()
                return count

            except Exception as e:
                logger.error(f"Failed to clear disk cache: {e}")
                return 0

    def size(self) -> int:
        """Get cache size in bytes.

        Returns:
            Size in bytes
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(size) FROM cache_entries")
            result = cursor.fetchone()[0]
            return result or 0

        except Exception as e:
            logger.error(f"Failed to get disk cache size: {e}")
            return 0

    def keys(self) -> set[str]:
        """Get all cache keys.

        Returns:
            Set of keys
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT key FROM cache_entries")
            return {row[0] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Failed to get disk cache keys: {e}")
            return set()

    def _evict_if_needed(self, required_size: int) -> None:
        """Evict least recently accessed entries to make space for new entry.

        Iteratively removes the oldest accessed entry until enough space is
        available for the required size. Uses indexed queries for efficient
        selection of eviction candidates.

        Args:
            required_size: Size needed in bytes for new entry

        Note:
            - Eviction continues until: current_size + required_size <= max_size
            - Uses accessed_at index for O(log n) eviction candidate selection
            - Stops early if no more entries available to evict
            - Must be called within a lock context
        """
        current_size = self.size()

        while current_size + required_size > self.max_size_bytes:
            # Find and evict the least recently accessed entry
            # Uses indexed query on accessed_at for efficient selection
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT key, size FROM cache_entries
                ORDER BY accessed_at ASC
                LIMIT 1
            """
            )

            row = cursor.fetchone()
            if row:
                # Delete the entry and subtract its size from running total
                cursor.execute("DELETE FROM cache_entries WHERE key = ?", (row[0],))
                conn.commit()
                current_size -= row[1]
            else:
                # No more entries to evict - cache is empty
                break

    def close(self) -> None:
        """Close thread-local database connection and clean up resources.

        Closes the SQLite connection for the current thread and removes it
        from thread-local storage. Should be called when cache is no longer
        needed to prevent resource leaks.

        Note:
            - Only closes connection for the calling thread
            - Other threads' connections remain active
            - Safe to call multiple times (no-op if already closed)
            - Errors during close are logged but not raised
            - Consider using context manager pattern if available

        Best Practice:
            Call this method in cleanup code, thread exit handlers, or
            application shutdown sequences to ensure proper resource disposal.
        """
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
                delattr(self._local, "conn")
            except Exception as e:
                logger.error(f"Failed to close database connection: {e}")
