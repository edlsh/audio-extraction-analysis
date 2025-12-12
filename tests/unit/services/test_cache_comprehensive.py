"""Comprehensive tests for cache eviction, TTL, and key generation.

This module covers:
- Cache hit/miss scenarios
- TTL expiration with mocked time
- LRU eviction when max_size reached
- Cache key includes provider/language (no collisions)
- Atomic write behavior
- Cleanup of expired entries
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import CacheCorruptionError, CacheWriteError
from src.models.transcription import TranscriptionResult
from src.services.cache import CacheEntry, TranscriptionCache


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def mock_config(temp_cache_dir: Path) -> MagicMock:
    """Create a mock config with test settings."""
    config = MagicMock()
    config.cache_dir = temp_cache_dir
    config.cache_ttl = 3600  # 1 hour
    config.cache_max_size = 10
    return config


@pytest.fixture
def cache(mock_config: MagicMock) -> TranscriptionCache:
    """Create a cache instance with test config."""
    return TranscriptionCache(config=mock_config)


@pytest.fixture
def sample_audio_file(tmp_path: Path) -> Path:
    """Create a sample audio file for testing."""
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"fake audio content for testing" * 100)
    return audio_file


@pytest.fixture
def sample_result() -> TranscriptionResult:
    """Create a sample transcription result."""
    return TranscriptionResult(
        transcript="Hello, this is a test transcription.",
        duration=10.5,
        generated_at=datetime.now(),
        audio_file="test_audio.wav",
        provider_name="test_provider",
        provider_features=["transcription"],
    )


@pytest.fixture
def multiple_audio_files(tmp_path: Path) -> list[Path]:
    """Create multiple audio files with distinct content."""
    files = []
    for i in range(10):
        f = tmp_path / f"audio_{i}.wav"
        # Each file has unique content for distinct hash
        f.write_bytes(f"unique content for file {i}".encode() * 100)
        files.append(f)
    return files


class TestCacheHitMissScenarios:
    """Test cache hit and miss scenarios."""

    def test_cache_hit_returns_cached_result(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that cache hit returns the cached transcription."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Should hit
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is not None
        assert result.transcript == sample_result.transcript

    def test_cache_miss_for_nonexistent_entry(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that cache miss returns None."""
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_cache_miss_for_different_provider(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that different provider causes miss."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Different provider should miss
        result = cache.get(sample_audio_file, "elevenlabs", "en")
        assert result is None

    def test_cache_miss_for_different_language(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that different language causes miss."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Different language should miss
        result = cache.get(sample_audio_file, "deepgram", "es")
        assert result is None

    def test_cache_miss_for_modified_file(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that modified audio file causes cache miss."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Modify the file content
        sample_audio_file.write_bytes(b"completely different content" * 100)

        # Should miss due to hash mismatch
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_has_method_accuracy(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that has() accurately reflects cache state."""
        # Initially missing
        assert not cache.has(sample_audio_file, "deepgram", "en")

        # After put
        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        assert cache.has(sample_audio_file, "deepgram", "en")

        # Different provider still missing
        assert not cache.has(sample_audio_file, "elevenlabs", "en")


class TestTTLExpiration:
    """Test TTL (Time-To-Live) expiration logic."""

    def test_entry_expires_after_ttl(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that cache entry expires after TTL."""
        mock_config.cache_ttl = 1  # 1 second TTL
        cache = TranscriptionCache(config=mock_config)

        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        assert cache.has(sample_audio_file, "deepgram", "en")

        # Wait for expiration
        time.sleep(1.5)

        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_entry_valid_before_ttl(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that cache entry is valid before TTL expires."""
        mock_config.cache_ttl = 10  # 10 second TTL
        cache = TranscriptionCache(config=mock_config)

        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Should still be valid
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is not None

    @patch("time.time")
    def test_ttl_with_mocked_time(
        self,
        mock_time: MagicMock,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test TTL expiration with mocked time."""
        mock_config.cache_ttl = 3600  # 1 hour
        cache = TranscriptionCache(config=mock_config)

        # Set initial time
        current_time = 1000000.0
        mock_time.return_value = current_time

        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Advance time by 30 minutes (within TTL)
        mock_time.return_value = current_time + 1800
        assert cache.has(sample_audio_file, "deepgram", "en")

        # Advance time past TTL (2 hours later)
        mock_time.return_value = current_time + 7200
        assert not cache.has(sample_audio_file, "deepgram", "en")

    def test_cleanup_expired_removes_old_entries(
        self,
        mock_config: MagicMock,
        tmp_path: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that cleanup_expired removes old entries."""
        mock_config.cache_ttl = 1  # 1 second TTL
        cache = TranscriptionCache(config=mock_config)

        # Create and cache multiple files
        files = []
        for i in range(3):
            f = tmp_path / f"audio_{i}.wav"
            f.write_bytes(f"content {i}".encode() * 100)
            files.append(f)
            cache.put(f, "deepgram", "en", sample_result)

        # Wait for expiration
        time.sleep(1.5)

        # Trigger cleanup
        removed = cache._cleanup_expired()
        assert removed == 3

        # All entries should be gone
        for f in files:
            assert not cache.has(f, "deepgram", "en")


class TestLRUEviction:
    """Test LRU (Least Recently Used) eviction logic."""

    def test_lru_eviction_when_max_size_reached(
        self,
        mock_config: MagicMock,
        multiple_audio_files: list[Path],
        sample_result: TranscriptionResult,
    ) -> None:
        """Test LRU eviction when cache exceeds max size."""
        mock_config.cache_max_size = 5
        cache = TranscriptionCache(config=mock_config)

        # Add 7 files (exceeds max_size of 5)
        for f in multiple_audio_files[:7]:
            cache.put(f, "deepgram", "en", sample_result)

        # First two files should be evicted (LRU)
        assert not cache.has(multiple_audio_files[0], "deepgram", "en")
        assert not cache.has(multiple_audio_files[1], "deepgram", "en")

        # Later files should still exist
        assert cache.has(multiple_audio_files[6], "deepgram", "en")
        assert cache.has(multiple_audio_files[5], "deepgram", "en")

    def test_access_updates_lru_order(
        self,
        mock_config: MagicMock,
        tmp_path: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that accessing an entry moves it to most recently used."""
        mock_config.cache_max_size = 3
        cache = TranscriptionCache(config=mock_config)

        # Create 3 files
        files = []
        for i in range(3):
            f = tmp_path / f"audio_{i}.wav"
            f.write_bytes(f"content {i}".encode() * 100)
            files.append(f)
            cache.put(f, "deepgram", "en", sample_result)

        # Access file 0 to move it to most recently used
        cache.get(files[0], "deepgram", "en")

        # Add a new file to trigger eviction
        new_file = tmp_path / "audio_new.wav"
        new_file.write_bytes(b"new content" * 100)
        cache.put(new_file, "deepgram", "en", sample_result)

        # File 1 should be evicted (was LRU), file 0 should still exist
        assert not cache.has(files[1], "deepgram", "en")
        assert cache.has(files[0], "deepgram", "en")
        assert cache.has(new_file, "deepgram", "en")

    def test_eviction_deletes_cache_files(
        self,
        mock_config: MagicMock,
        tmp_path: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that eviction actually deletes the cache data files."""
        mock_config.cache_max_size = 2
        cache = TranscriptionCache(config=mock_config)

        # Create files
        files = []
        cache_keys = []
        for i in range(3):
            f = tmp_path / f"audio_{i}.wav"
            f.write_bytes(f"content {i}".encode() * 100)
            files.append(f)
            key = cache.put(f, "deepgram", "en", sample_result)
            cache_keys.append(key)

        # First file's cache should be deleted
        evicted_cache_file = cache._get_cache_file_path(cache_keys[0])
        assert not evicted_cache_file.exists()

        # Third file's cache should exist
        latest_cache_file = cache._get_cache_file_path(cache_keys[2])
        assert latest_cache_file.exists()


class TestCacheKeyGeneration:
    """Test cache key generation and collision prevention."""

    def test_same_file_different_providers_different_keys(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that same file with different providers creates different keys."""
        file_hash = cache._generate_file_hash(sample_audio_file)

        key1 = cache._generate_cache_key(file_hash, "deepgram", "en")
        key2 = cache._generate_cache_key(file_hash, "elevenlabs", "en")
        key3 = cache._generate_cache_key(file_hash, "whisper", "en")

        # All keys should be different
        assert key1 != key2
        assert key2 != key3
        assert key1 != key3

    def test_same_file_different_languages_different_keys(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that same file with different languages creates different keys."""
        file_hash = cache._generate_file_hash(sample_audio_file)

        key_en = cache._generate_cache_key(file_hash, "deepgram", "en")
        key_es = cache._generate_cache_key(file_hash, "deepgram", "es")
        key_de = cache._generate_cache_key(file_hash, "deepgram", "de")

        # All keys should be different
        assert key_en != key_es
        assert key_es != key_de
        assert key_en != key_de

    def test_different_files_same_provider_different_keys(
        self, cache: TranscriptionCache, multiple_audio_files: list[Path]
    ) -> None:
        """Test that different files create different keys."""
        keys = []
        for f in multiple_audio_files[:5]:
            file_hash = cache._generate_file_hash(f)
            key = cache._generate_cache_key(file_hash, "deepgram", "en")
            keys.append(key)

        # All keys should be unique
        assert len(keys) == len(set(keys))

    def test_key_is_consistent_for_same_inputs(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that the same inputs always produce the same key."""
        file_hash = cache._generate_file_hash(sample_audio_file)

        key1 = cache._generate_cache_key(file_hash, "deepgram", "en")
        key2 = cache._generate_cache_key(file_hash, "deepgram", "en")

        assert key1 == key2

    def test_cache_key_length_is_bounded(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that cache keys have bounded length."""
        file_hash = cache._generate_file_hash(sample_audio_file)
        key = cache._generate_cache_key(file_hash, "deepgram", "en")

        # Key should be 32 chars (truncated SHA-256 hex)
        assert len(key) == 32

    @pytest.mark.parametrize(
        "provider,language",
        [
            ("deepgram", "en"),
            ("elevenlabs", "es"),
            ("whisper", "de"),
            ("parakeet", "ja"),
            ("azure-speech", "zh-CN"),
            ("google-speech", "pt-BR"),
        ],
    )
    def test_various_provider_language_combinations(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        provider: str,
        language: str,
    ) -> None:
        """Test key generation for various provider/language combinations."""
        file_hash = cache._generate_file_hash(sample_audio_file)
        key = cache._generate_cache_key(file_hash, provider, language)

        # Key should be valid hex string
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


class TestAtomicWriteBehavior:
    """Test atomic write behavior for cache files."""

    def test_cache_write_is_atomic(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that cache writes are atomic (via temp file + rename)."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)
        cache_file = cache._get_cache_file_path(cache_key)

        # File should exist and be complete
        assert cache_file.exists()

        # File should contain valid JSON
        with open(cache_file) as f:
            data = json.load(f)
        assert "transcript" in data

    def test_no_partial_writes_on_interruption(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that partial writes don't corrupt the cache."""
        cache = TranscriptionCache(config=mock_config)

        # Simulate write failure during secure_write_json
        with patch(
            "src.utils.secure_file.secure_write_json",
            side_effect=OSError("Disk full"),
        ):
            with pytest.raises(CacheWriteError):
                cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Cache should not contain partial entry
        assert not cache.has(sample_audio_file, "deepgram", "en")

    def test_index_saved_after_operations(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that index is persisted after cache operations."""
        cache1 = TranscriptionCache(config=mock_config)
        cache1.put(sample_audio_file, "deepgram", "en", sample_result)

        # Create new instance to read persisted index
        cache2 = TranscriptionCache(config=mock_config)
        assert cache2.has(sample_audio_file, "deepgram", "en")


class TestExpiredEntryCleanup:
    """Test cleanup of expired cache entries."""

    def test_get_triggers_expired_cleanup(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that get() triggers cleanup of expired entries."""
        mock_config.cache_ttl = 1
        cache = TranscriptionCache(config=mock_config)

        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Wait for expiration
        time.sleep(1.5)

        # Get should return None and cleanup
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

        # Entry should be removed from index
        assert sample_audio_file.name not in str(cache._index)

    def test_stats_triggers_cleanup(
        self,
        mock_config: MagicMock,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that stats() triggers cleanup of expired entries."""
        mock_config.cache_ttl = 1
        cache = TranscriptionCache(config=mock_config)

        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        initial_stats = cache.stats()
        assert initial_stats["entries"] == 1

        # Wait for expiration
        time.sleep(1.5)

        # Stats should trigger cleanup
        stats = cache.stats()
        assert stats["entries"] == 0

    def test_cleanup_removes_orphaned_files(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test cleanup behavior when cache file exists but is expired."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)
        cache_file = cache._get_cache_file_path(cache_key)

        # Manually expire the entry
        entry = cache._index[cache_key]
        entry.expires_at = time.time() - 100

        # Trigger cleanup
        cache._cleanup_expired()

        # Both index entry and file should be removed
        assert cache_key not in cache._index
        assert not cache_file.exists()


class TestCacheEntryDataclass:
    """Test CacheEntry dataclass functionality."""

    def test_is_expired_boundary_conditions(self) -> None:
        """Test is_expired at exact boundary times."""
        now = time.time()

        # Exactly at expiration time (should be expired)
        entry_at_boundary = CacheEntry(
            key="test",
            created_at=now - 100,
            expires_at=now,
            file_path=Path("/test.wav"),
            file_hash="abc",
            provider="test",
            language="en",
        )
        assert entry_at_boundary.is_expired()

        # Just before expiration (should not be expired)
        entry_before = CacheEntry(
            key="test",
            created_at=now - 100,
            expires_at=now + 0.1,
            file_path=Path("/test.wav"),
            file_hash="abc",
            provider="test",
            language="en",
        )
        assert not entry_before.is_expired()

    def test_serialization_roundtrip_preserves_all_fields(self) -> None:
        """Test that serialization preserves all CacheEntry fields."""
        original = CacheEntry(
            key="unique_key_123",
            created_at=1234567890.123,
            expires_at=1234571490.456,
            file_path=Path("/path/to/audio.wav"),
            file_hash="sha256hashvalue",
            provider="deepgram",
            language="en-US",
        )

        data = original.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.key == original.key
        assert restored.created_at == original.created_at
        assert restored.expires_at == original.expires_at
        assert restored.file_path == original.file_path
        assert restored.file_hash == original.file_hash
        assert restored.provider == original.provider
        assert restored.language == original.language


class TestCacheRobustness:
    """Test cache robustness against edge cases."""

    def test_handles_missing_audio_file(self, cache: TranscriptionCache) -> None:
        """Test graceful handling of missing audio files."""
        missing_file = Path("/nonexistent/audio.wav")
        result = cache.get(missing_file, "deepgram", "en")
        assert result is None

    def test_handles_corrupted_index(self, mock_config: MagicMock) -> None:
        """Test recovery from corrupted index file."""
        index_path = mock_config.cache_dir / "cache_index.json"
        mock_config.cache_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text("corrupted {not valid json")

        # Should recover gracefully
        cache = TranscriptionCache(config=mock_config)
        stats = cache.stats()
        assert stats["entries"] == 0

    def test_handles_missing_cache_file_in_index(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test handling when index references missing cache file."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Manually delete cache file
        cache_file = cache._get_cache_file_path(cache_key)
        cache_file.unlink()

        # Get should return None and fix index
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None
        assert cache_key not in cache._index

    def test_handles_corrupted_cache_file(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test handling of corrupted cache data file."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Corrupt the cache file
        cache_file = cache._get_cache_file_path(cache_key)
        cache_file.write_text("corrupted json {{{")

        with pytest.raises(CacheCorruptionError):
            cache.get(sample_audio_file, "deepgram", "en")

    def test_clear_handles_missing_files(
        self,
        cache: TranscriptionCache,
        sample_audio_file: Path,
        sample_result: TranscriptionResult,
    ) -> None:
        """Test that clear handles already-deleted files."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Manually delete the file
        cache_file = cache._get_cache_file_path(cache_key)
        cache_file.unlink()

        # Clear should not raise
        count = cache.clear()
        assert count == 1  # Still counted as cleared from index


class TestFileHashGeneration:
    """Test file hash generation for cache keys."""

    def test_hash_is_deterministic(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that file hash is deterministic."""
        hash1 = cache._generate_file_hash(sample_audio_file)
        hash2 = cache._generate_file_hash(sample_audio_file)
        assert hash1 == hash2

    def test_hash_changes_with_content(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test that hash changes when file content changes."""
        hash1 = cache._generate_file_hash(sample_audio_file)

        sample_audio_file.write_bytes(b"different content")

        hash2 = cache._generate_file_hash(sample_audio_file)
        assert hash1 != hash2

    def test_hash_is_sha256(self, cache: TranscriptionCache, sample_audio_file: Path) -> None:
        """Test that the hash is a valid SHA-256 hex digest."""
        file_hash = cache._generate_file_hash(sample_audio_file)

        # SHA-256 produces 64 hex characters
        assert len(file_hash) == 64
        assert all(c in "0123456789abcdef" for c in file_hash)

    def test_hash_handles_large_files(self, cache: TranscriptionCache, tmp_path: Path) -> None:
        """Test hash generation for larger files."""
        large_file = tmp_path / "large.wav"
        # Create ~1MB file
        large_file.write_bytes(b"x" * (1024 * 1024))

        # Should not raise
        file_hash = cache._generate_file_hash(large_file)
        assert len(file_hash) == 64
