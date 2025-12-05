"""Transcription caching service for avoiding redundant API calls."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.transcription import TranscriptionResult

from ..config import Config
from ..exceptions import CacheCorruptionError, CacheReadError, CacheWriteError

logger = logging.getLogger(__name__)


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

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "file_path": str(self.file_path),
            "file_hash": self.file_hash,
            "provider": self.provider,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CacheEntry:
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            file_path=Path(data["file_path"]),
            file_hash=data["file_hash"],
            provider=data["provider"],
            language=data["language"],
        )


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
        self._config = config or Config()
        self._cache_dir = self._config.cache_dir
        self._data_dir = self._cache_dir / self.CACHE_DATA_DIR
        self._index_path = self._cache_dir / self.CACHE_INDEX_FILE
        self._ttl = self._config.cache_ttl
        self._max_size = self._config.cache_max_size

        # Ensure directories exist
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize index
        self._index: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # For LRU tracking
        self._load_index()

    def _load_index(self) -> None:
        """Load cache index from disk."""
        if not self._index_path.exists():
            self._index = {}
            self._access_order = []
            return

        try:
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)
                self._index = {
                    key: CacheEntry.from_dict(entry)
                    for key, entry in data.get("entries", {}).items()
                }
                self._access_order = data.get("access_order", list(self._index.keys()))
                logger.debug(f"Loaded cache index with {len(self._index)} entries")
        except json.JSONDecodeError as e:
            logger.warning(f"Cache index corrupted, reinitializing: {e}")
            self._index = {}
            self._access_order = []
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to load cache index: {e}")
            self._index = {}
            self._access_order = []

    def _save_index(self) -> None:
        """Persist cache index to disk."""
        try:
            data = {
                "entries": {key: entry.to_dict() for key, entry in self._index.items()},
                "access_order": self._access_order,
            }
            # Write atomically using temp file
            temp_path = self._index_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self._index_path)
        except (OSError, PermissionError) as e:
            raise CacheWriteError(
                f"Failed to save cache index: {e}",
                context={"index_path": str(self._index_path)},
            ) from e

    def _generate_file_hash(self, file_path: Path) -> str:
        """Generate SHA-256 hash of file content.

        Args:
            file_path: Path to the file to hash

        Returns:
            Hex digest of the file hash
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

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
        """Update LRU access order for a key."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache exceeds max size."""
        while len(self._index) >= self._max_size and self._access_order:
            lru_key = self._access_order.pop(0)
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

        Returns:
            Number of entries removed
        """
        expired_keys = [key for key, entry in self._index.items() if entry.is_expired()]
        for key in expired_keys:
            self._index.pop(key)
            if key in self._access_order:
                self._access_order.remove(key)
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
            if cache_key in self._access_order:
                self._access_order.remove(cache_key)
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

        # Evict if needed before adding
        self._evict_if_needed()

        # Write data file
        try:
            data = result.to_dict()
            temp_path = cache_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(cache_file)
        except (OSError, PermissionError) as e:
            raise CacheWriteError(
                f"Failed to write cache data: {e}",
                context={"cache_key": cache_key, "file": str(cache_file)},
            ) from e

        # Update index
        self._index[cache_key] = entry
        self._update_access_order(cache_key)
        self._save_index()

        logger.info(
            f"Cached transcription: {cache_key[:8]}... (provider={provider}, ttl={self._ttl}s)"
        )
        return cache_key

    def invalidate(self, audio_file: Path, provider: str, language: str = "en") -> bool:
        """Invalidate a specific cache entry.

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

        if cache_key not in self._index:
            return False

        self._index.pop(cache_key)
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)

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

        Returns:
            Number of entries cleared
        """
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

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        self._cleanup_expired()  # Clean first for accurate stats

        total_size = 0
        for cache_key in self._index:
            cache_file = self._get_cache_file_path(cache_key)
            try:
                if cache_file.exists():
                    total_size += cache_file.stat().st_size
            except OSError:
                pass

        return {
            "entries": len(self._index),
            "max_entries": self._max_size,
            "ttl_seconds": self._ttl,
            "total_size_bytes": total_size,
            "cache_dir": str(self._cache_dir),
        }

    def has(self, audio_file: Path, provider: str, language: str = "en") -> bool:
        """Check if a valid cache entry exists.

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

        if cache_key not in self._index:
            return False

        entry = self._index[cache_key]
        if entry.is_expired():
            return False

        if entry.file_hash != file_hash:
            return False

        cache_file = self._get_cache_file_path(cache_key)
        return cache_file.exists()
