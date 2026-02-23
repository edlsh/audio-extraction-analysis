"""Transcription caching service for avoiding redundant API calls."""

from __future__ import annotations

import collections
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

from ..config import Config, get_config
from ..exceptions import CacheCorruptionError, CacheReadError, CacheWriteError

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Metadata for a cached transcription result."""

    key: str
    created_at: float
    expires_at: float
    file_path: Path
    file_hash: str
    provider: str
    language: str
    cache_file_size: int = 0  # Size of the cached JSON file in bytes

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, object]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "file_path": str(self.file_path),
            "file_hash": self.file_hash,
            "provider": self.provider,
            "language": self.language,
            "cache_file_size": self.cache_file_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> CacheEntry:
        """Deserialize from dictionary."""
        return cls(
            key=cast(str, data["key"]),
            created_at=cast(float, data["created_at"]),
            expires_at=cast(float, data["expires_at"]),
            file_path=Path(cast(str, data["file_path"])),
            file_hash=cast(str, data["file_hash"]),
            provider=cast(str, data["provider"]),
            language=cast(str, data["language"]),
            cache_file_size=cast(int, data.get("cache_file_size", 0)),
        )


# Module-level hash cache: maps (file_path, mtime, size) -> hash
# This avoids re-reading entire files when only checking if they changed
# Capped at 1000 entries to prevent unbounded memory growth in long-running processes
_FILE_HASH_CACHE_MAX_SIZE = 1000
_file_hash_cache: collections.OrderedDict[tuple[str, float, int], str] = collections.OrderedDict()
_file_hash_cache_lock = threading.Lock()


class TranscriptionCache:
    """File-based cache for transcription results.

    Uses content-addressable storage based on file hash, provider, and language.
    Implements TTL-based expiration and LRU eviction.
    """

    CACHE_INDEX_FILE = "cache_index.json"
    CACHE_DATA_DIR = "transcriptions"

    def __init__(self, config: Config | None = None) -> None:
        """Initialize the cache service.

        Args:
            config: Configuration object. If None, uses default Config().
        """
        self._config = config or get_config()
        self._cache_dir = self._config.cache_dir
        self._data_dir = self._cache_dir / self.CACHE_DATA_DIR
        self._index_path = self._cache_dir / self.CACHE_INDEX_FILE
        self._ttl = self._config.cache_ttl
        self._max_size = self._config.cache_max_size

        # Ensure directories exist with secure permissions
        from src.utils.secure_file import ensure_secure_directory

        ensure_secure_directory(self._cache_dir)
        ensure_secure_directory(self._data_dir)

        # Thread safety: RLock protects _index and _access_order from concurrent access.
        # RLock (reentrant) is used because some methods call other methods that also need the lock.
        self._state_lock = threading.RLock()

        # Load or initialize index
        self._index: dict[str, CacheEntry] = {}
        # OrderedDict provides O(1) LRU operations (move_to_end, popitem) vs O(n) list operations
        self._access_order: collections.OrderedDict[str, None] = collections.OrderedDict()
        self._load_index()

    def _load_index(self) -> None:
        """Load cache index from disk."""
        if not self._index_path.exists():
            self._index = {}
            self._access_order = collections.OrderedDict()
            return

        try:
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)
                self._index = {
                    key: CacheEntry.from_dict(entry)
                    for key, entry in data.get("entries", {}).items()
                }
                # Load access_order as OrderedDict for O(1) LRU operations
                access_list = data.get("access_order", list(self._index.keys()))
                self._access_order = collections.OrderedDict({key: None for key in access_list})
                logger.debug(f"Loaded cache index with {len(self._index)} entries")
        except json.JSONDecodeError as e:
            logger.warning(f"Cache index corrupted, reinitializing: {e}")
            self._index = {}
            self._access_order = collections.OrderedDict()
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to load cache index: {e}")
            self._index = {}
            self._access_order = collections.OrderedDict()

    def _save_index(self) -> None:
        """Persist cache index to disk with secure permissions.

        Thread-safe: acquires _state_lock to ensure consistent snapshot.
        """
        with self._state_lock:
            try:
                from src.utils.secure_file import secure_write_json

                data = {
                    "entries": {key: entry.to_dict() for key, entry in self._index.items()},
                    "access_order": list(self._access_order.keys()),
                }
                secure_write_json(self._index_path, data)
            except (OSError, PermissionError) as e:
                raise CacheWriteError(
                    f"Failed to save cache index: {e}",
                    context={"index_path": str(self._index_path)},
                ) from e

    def _generate_file_hash(self, file_path: Path) -> str:
        """Generate SHA-256 hash of file content with caching by (mtime, size).

        Uses a module-level cache keyed by (path, mtime, size) to avoid
        re-reading entire files when they haven't changed.

        Args:
            file_path: Path to the file to hash

        Returns:
            Hex digest of the file hash
        """
        from src.utils.constants import Limits

        stat = file_path.stat()
        cache_key = (str(file_path.resolve()), stat.st_mtime, stat.st_size)

        with _file_hash_cache_lock:
            if cache_key in _file_hash_cache:
                _file_hash_cache.move_to_end(cache_key)
                return _file_hash_cache[cache_key]

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(Limits.FILE_HASH_CHUNK_SIZE), b""):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()

        with _file_hash_cache_lock:
            _file_hash_cache[cache_key] = file_hash
            while len(_file_hash_cache) > _FILE_HASH_CACHE_MAX_SIZE:
                _file_hash_cache.popitem(last=False)

        return file_hash

    def _generate_cache_key(self, file_hash: str, provider: str, language: str) -> str:
        """Generate unique cache key from components.

        Args:
            file_hash: Hash of the audio file content
            provider: Transcription provider name
            language: Language code

        Returns:
            Cache key string
        """
        # Combine components and hash for consistent key length
        combined = f"{file_hash}:{provider}:{language}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for cached data.

        Args:
            cache_key: Cache key

        Returns:
            Path to the cache data file
        """
        return self._data_dir / f"{cache_key}.json"

    def _update_access_order(self, key: str) -> None:
        """Update LRU access order for a key.

        Thread-safe: acquires _state_lock. Uses RLock for reentrant calls.
        Uses OrderedDict.move_to_end() for O(1) operation vs O(n) list.remove()+append().
        """
        with self._state_lock:
            # move_to_end(key, last=True) moves key to the end (most recently used)
            # This is O(1) for OrderedDict vs O(n) for list.remove() + list.append()
            if key in self._access_order:
                self._access_order.move_to_end(key, last=True)
            else:
                self._access_order[key] = None

    def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache exceeds max size.

        Thread-safe: acquires _state_lock. File deletion occurs under lock
        for correctness (prevents race where entry is re-added during delete).
        Uses OrderedDict.popitem(last=False) for O(1) operation vs O(n) list.pop(0).
        """
        with self._state_lock:
            while len(self._index) >= self._max_size and self._access_order:
                # popitem(last=False) removes and returns the first (least recently used) item
                # This is O(1) for OrderedDict vs O(n) for list.pop(0)
                lru_key, _ = self._access_order.popitem(last=False)
                if lru_key in self._index:
                    self._index.pop(lru_key)
                    cache_file = self._get_cache_file_path(lru_key)
                    try:
                        if cache_file.exists():
                            cache_file.unlink()
                        logger.debug(f"Evicted cache entry: {lru_key}")
                    except OSError as e:
                        logger.warning(f"Failed to delete evicted cache file: {e}")

    def _cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Thread-safe: acquires _state_lock for the entire cleanup operation.

        Returns:
            Number of entries removed
        """
        with self._state_lock:
            expired_keys = [key for key, entry in self._index.items() if entry.is_expired()]
            for key in expired_keys:
                self._index.pop(key)
                # pop(key, None) is O(1) for OrderedDict vs O(n) for list.remove()
                self._access_order.pop(key, None)
                cache_file = self._get_cache_file_path(key)
                try:
                    if cache_file.exists():
                        cache_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete expired cache file: {e}")

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                self._save_index()

            return len(expired_keys)

    def get(
        self, audio_file: Path, provider: str, language: str = "en"
    ) -> TranscriptionResult | None:
        """Retrieve cached transcription result if available and valid.

        Thread-safe: acquires _state_lock for all state access.
        File hashing occurs outside the lock (read-only operation).

        Args:
            audio_file: Path to the audio file
            provider: Transcription provider name
            language: Language code (default: 'en')

        Returns:
            Cached TranscriptionResult or None if not found/expired

        Raises:
            CacheReadError: If cache file cannot be read
            CacheCorruptionError: If cached data is corrupted
        """
        from ..models.transcription import TranscriptionResult

        try:
            file_hash = self._generate_file_hash(audio_file)
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot hash file for cache lookup: {e}")
            return None

        cache_key = self._generate_cache_key(file_hash, provider, language)

        with self._state_lock:
            if cache_key not in self._index:
                logger.debug(f"Cache miss: {cache_key[:8]}...")
                return None

            entry = self._index[cache_key]

            # Check expiration
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {cache_key[:8]}...")
                self._cleanup_expired()
                return None

            # Verify file hash still matches (file hasn't changed)
            if entry.file_hash != file_hash:
                logger.debug(f"File hash mismatch, invalidating cache: {cache_key[:8]}...")
                self.invalidate(audio_file, provider, language)
                return None

            # Read cached data
            cache_file = self._get_cache_file_path(cache_key)
            if not cache_file.exists():
                logger.warning(f"Cache file missing: {cache_file}")
                self._index.pop(cache_key, None)
                # pop(key, None) is O(1) for OrderedDict vs O(n) for list.remove()
                self._access_order.pop(cache_key, None)
                self._save_index()
                return None

            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                result = TranscriptionResult.from_dict(data)
                self._update_access_order(cache_key)
                logger.info(f"Cache hit: {cache_key[:8]}... (provider={provider})")
                return result
            except json.JSONDecodeError as e:
                raise CacheCorruptionError(
                    f"Cached data is corrupted: {e}",
                    context={"cache_key": cache_key, "file": str(cache_file)},
                ) from e
            except (OSError, PermissionError) as e:
                raise CacheReadError(
                    f"Failed to read cache file: {e}",
                    context={"cache_key": cache_key, "file": str(cache_file)},
                ) from e
            except (KeyError, TypeError, ValueError) as e:
                raise CacheCorruptionError(
                    f"Cached data format invalid: {e}",
                    context={"cache_key": cache_key, "file": str(cache_file)},
                ) from e

    def put(
        self,
        audio_file: Path,
        provider: str,
        language: str,
        result: TranscriptionResult,
    ) -> str:
        """Store transcription result in cache.

        Thread-safe: acquires _state_lock for eviction and index updates only.
        File I/O (hashing and writing) occurs outside the lock to avoid blocking.

        Args:
            audio_file: Path to the audio file
            provider: Transcription provider name
            language: Language code
            result: TranscriptionResult to cache

        Returns:
            Cache key for the stored entry

        Raises:
            CacheWriteError: If cache cannot be written
        """
        try:
            file_hash = self._generate_file_hash(audio_file)
        except (OSError, PermissionError) as e:
            raise CacheWriteError(
                f"Cannot hash file for caching: {e}",
                context={"file": str(audio_file)},
            ) from e

        cache_key = self._generate_cache_key(file_hash, provider, language)
        cache_file = self._get_cache_file_path(cache_key)
        now = time.time()

        # Create cache entry
        entry = CacheEntry(
            key=cache_key,
            created_at=now,
            expires_at=now + self._ttl,
            file_path=audio_file,
            file_hash=file_hash,
            provider=provider,
            language=language,
        )

        # Serialize data outside the lock (I/O operation)
        from src.utils.secure_file import secure_write_json

        data = result.to_dict()

        # Write data file (I/O) without holding lock - allows concurrent cache access
        try:
            secure_write_json(cache_file, data)
            entry.cache_file_size = cache_file.stat().st_size
        except (OSError, PermissionError) as e:
            raise CacheWriteError(
                f"Failed to write cache data: {e}",
                context={"cache_key": cache_key, "file": str(cache_file)},
            ) from e

        # Atomic eviction + insert under single lock to prevent race condition
        with self._state_lock:
            self._evict_if_needed()
            self._index[cache_key] = entry
            self._update_access_order(cache_key)
            self._save_index()

        logger.info(
            f"Cached transcription: {cache_key[:8]}... (provider={provider}, ttl={self._ttl}s)"
        )
        return cache_key

    def invalidate(self, audio_file: Path, provider: str, language: str = "en") -> bool:
        """Invalidate a specific cache entry.

        Thread-safe: acquires _state_lock for state modifications.

        Args:
            audio_file: Path to the audio file
            provider: Transcription provider name
            language: Language code (default: 'en')

        Returns:
            True if entry was found and removed, False otherwise
        """
        try:
            file_hash = self._generate_file_hash(audio_file)
        except (OSError, PermissionError):
            return False

        cache_key = self._generate_cache_key(file_hash, provider, language)

        with self._state_lock:
            if cache_key not in self._index:
                return False

            self._index.pop(cache_key)
            # pop(key, None) is O(1) for OrderedDict vs O(n) for list.remove()
            self._access_order.pop(cache_key, None)

            cache_file = self._get_cache_file_path(cache_key)
            try:
                if cache_file.exists():
                    cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete cache file: {e}")

            self._save_index()
            logger.debug(f"Invalidated cache entry: {cache_key[:8]}...")
            return True

    def clear(self) -> int:
        """Clear all cached entries.

        Thread-safe: acquires _state_lock for the entire operation.

        Returns:
            Number of entries cleared
        """
        with self._state_lock:
            count = len(self._index)

            # Delete all cache files
            for cache_key in list(self._index.keys()):
                cache_file = self._get_cache_file_path(cache_key)
                try:
                    if cache_file.exists():
                        cache_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to delete cache file: {e}")

            self._index.clear()
            self._access_order.clear()
            self._save_index()

            logger.info(f"Cleared {count} cache entries")
            return count

    def stats(self) -> dict[str, object]:
        """Get cache statistics.

        Thread-safe: acquires _state_lock to ensure consistent snapshot.
        Uses stored cache_file_size from CacheEntry to avoid per-entry stat() calls.

        Returns:
            Dictionary with cache statistics
        """
        with self._state_lock:
            self._cleanup_expired()

            total_size = sum(entry.cache_file_size for entry in self._index.values())

            return {
                "entries": len(self._index),
                "max_entries": self._max_size,
                "ttl_seconds": self._ttl,
                "total_size_bytes": total_size,
                "cache_dir": str(self._cache_dir),
            }

    def has(self, audio_file: Path, provider: str, language: str = "en") -> bool:
        """Check if a valid cache entry exists.

        Thread-safe: acquires _state_lock for state access.

        Args:
            audio_file: Path to the audio file
            provider: Transcription provider name
            language: Language code (default: 'en')

        Returns:
            True if valid cache entry exists
        """
        try:
            file_hash = self._generate_file_hash(audio_file)
        except (OSError, PermissionError):
            return False

        cache_key = self._generate_cache_key(file_hash, provider, language)

        with self._state_lock:
            if cache_key not in self._index:
                return False

            entry = self._index[cache_key]
            if entry.is_expired():
                return False

            if entry.file_hash != file_hash:
                return False

            cache_file = self._get_cache_file_path(cache_key)
            return cache_file.exists()
