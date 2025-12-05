"""Tests for the TranscriptionCache service."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import CacheCorruptionError, CacheReadError, CacheWriteError
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


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_is_expired_false_when_valid(self) -> None:
        """Test is_expired returns False for valid entries."""
        entry = CacheEntry(
            key="test_key",
            created_at=time.time(),
            expires_at=time.time() + 3600,
            file_path=Path("/test/file.wav"),
            file_hash="abc123",
            provider="test",
            language="en",
        )
        assert not entry.is_expired()

    def test_is_expired_true_when_expired(self) -> None:
        """Test is_expired returns True for expired entries."""
        entry = CacheEntry(
            key="test_key",
            created_at=time.time() - 7200,
            expires_at=time.time() - 3600,
            file_path=Path("/test/file.wav"),
            file_hash="abc123",
            provider="test",
            language="en",
        )
        assert entry.is_expired()

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """Test serialization/deserialization roundtrip."""
        original = CacheEntry(
            key="test_key",
            created_at=1234567890.0,
            expires_at=1234571490.0,
            file_path=Path("/test/file.wav"),
            file_hash="abc123",
            provider="deepgram",
            language="en",
        )
        data = original.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.key == original.key
        assert restored.created_at == original.created_at
        assert restored.expires_at == original.expires_at
        assert restored.file_hash == original.file_hash
        assert restored.provider == original.provider
        assert restored.language == original.language


class TestTranscriptionCache:
    """Tests for TranscriptionCache service."""

    def test_init_creates_directories(self, mock_config: MagicMock) -> None:
        """Test that init creates required directories."""
        _cache = TranscriptionCache(config=mock_config)
        assert mock_config.cache_dir.exists()
        assert (mock_config.cache_dir / TranscriptionCache.CACHE_DATA_DIR).exists()

    def test_put_and_get_roundtrip(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test storing and retrieving a transcription result."""
        provider = "deepgram"
        language = "en"

        # Store
        cache_key = cache.put(sample_audio_file, provider, language, sample_result)
        assert cache_key is not None

        # Retrieve
        cached = cache.get(sample_audio_file, provider, language)
        assert cached is not None
        assert cached.transcript == sample_result.transcript
        assert cached.provider_name == sample_result.provider_name

    def test_get_returns_none_for_missing(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test get returns None for non-existent cache entry."""
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_get_returns_none_for_expired(
        self, mock_config: MagicMock, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test get returns None for expired entries."""
        mock_config.cache_ttl = 1  # 1 second TTL
        cache = TranscriptionCache(config=mock_config)

        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Wait for expiration
        time.sleep(1.5)

        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_has_returns_true_for_valid_entry(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test has returns True for valid cache entries."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        assert cache.has(sample_audio_file, "deepgram", "en")

    def test_has_returns_false_for_missing(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test has returns False for missing entries."""
        assert not cache.has(sample_audio_file, "deepgram", "en")

    def test_invalidate_removes_entry(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test invalidate removes a specific cache entry."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        assert cache.has(sample_audio_file, "deepgram", "en")

        result = cache.invalidate(sample_audio_file, "deepgram", "en")
        assert result is True
        assert not cache.has(sample_audio_file, "deepgram", "en")

    def test_invalidate_returns_false_for_missing(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test invalidate returns False for non-existent entries."""
        result = cache.invalidate(sample_audio_file, "deepgram", "en")
        assert result is False

    def test_clear_removes_all_entries(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test clear removes all cache entries."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        cache.put(sample_audio_file, "elevenlabs", "en", sample_result)

        count = cache.clear()
        assert count == 2
        assert not cache.has(sample_audio_file, "deepgram", "en")
        assert not cache.has(sample_audio_file, "elevenlabs", "en")

    def test_stats_returns_correct_info(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test stats returns correct cache information."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)

        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["max_entries"] == 10
        assert stats["ttl_seconds"] == 3600
        assert stats["total_size_bytes"] > 0

    def test_lru_eviction(
        self, mock_config: MagicMock, tmp_path: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test LRU eviction when cache exceeds max size."""
        mock_config.cache_max_size = 3
        cache = TranscriptionCache(config=mock_config)

        # Create multiple audio files
        files = []
        for i in range(4):
            f = tmp_path / f"audio_{i}.wav"
            f.write_bytes(f"content {i}".encode() * 100)
            files.append(f)

        # Fill cache beyond capacity
        for _i, f in enumerate(files):
            cache.put(f, "deepgram", "en", sample_result)

        # First entry should be evicted (LRU)
        assert not cache.has(files[0], "deepgram", "en")
        # Later entries should still exist
        assert cache.has(files[3], "deepgram", "en")

    def test_different_providers_cached_separately(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test same file with different providers creates separate cache entries."""
        result1 = TranscriptionResult(
            transcript="Deepgram transcription",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.wav",
            provider_name="deepgram",
        )
        result2 = TranscriptionResult(
            transcript="ElevenLabs transcription",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.wav",
            provider_name="elevenlabs",
        )

        cache.put(sample_audio_file, "deepgram", "en", result1)
        cache.put(sample_audio_file, "elevenlabs", "en", result2)

        cached1 = cache.get(sample_audio_file, "deepgram", "en")
        cached2 = cache.get(sample_audio_file, "elevenlabs", "en")

        assert cached1 is not None
        assert cached2 is not None
        assert cached1.transcript == "Deepgram transcription"
        assert cached2.transcript == "ElevenLabs transcription"

    def test_different_languages_cached_separately(
        self, cache: TranscriptionCache, sample_audio_file: Path
    ) -> None:
        """Test same file with different languages creates separate cache entries."""
        result_en = TranscriptionResult(
            transcript="English transcription",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.wav",
            provider_name="deepgram",
        )
        result_es = TranscriptionResult(
            transcript="Spanish transcription",
            duration=10.0,
            generated_at=datetime.now(),
            audio_file="test.wav",
            provider_name="deepgram",
        )

        cache.put(sample_audio_file, "deepgram", "en", result_en)
        cache.put(sample_audio_file, "deepgram", "es", result_es)

        cached_en = cache.get(sample_audio_file, "deepgram", "en")
        cached_es = cache.get(sample_audio_file, "deepgram", "es")

        assert cached_en is not None
        assert cached_es is not None
        assert cached_en.transcript == "English transcription"
        assert cached_es.transcript == "Spanish transcription"

    def test_file_modification_invalidates_cache(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test that modifying the audio file invalidates the cache."""
        cache.put(sample_audio_file, "deepgram", "en", sample_result)
        assert cache.has(sample_audio_file, "deepgram", "en")

        # Modify the file
        sample_audio_file.write_bytes(b"different content" * 100)

        # Cache should miss due to hash mismatch
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None

    def test_corrupted_cache_file_raises_error(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test that corrupted cache files raise CacheCorruptionError."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Corrupt the cache file
        cache_file = cache._get_cache_file_path(cache_key)
        cache_file.write_text("not valid json {{{")

        with pytest.raises(CacheCorruptionError):
            cache.get(sample_audio_file, "deepgram", "en")

    def test_persistence_across_instances(
        self, mock_config: MagicMock, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test cache persists across cache instances."""
        cache1 = TranscriptionCache(config=mock_config)
        cache1.put(sample_audio_file, "deepgram", "en", sample_result)

        # Create new instance pointing to same directory
        cache2 = TranscriptionCache(config=mock_config)
        cached = cache2.get(sample_audio_file, "deepgram", "en")

        assert cached is not None
        assert cached.transcript == sample_result.transcript


class TestTranscriptionCacheEdgeCases:
    """Edge case tests for TranscriptionCache."""

    def test_handles_missing_audio_file_gracefully(self, cache: TranscriptionCache) -> None:
        """Test cache handles missing audio files gracefully."""
        missing_file = Path("/nonexistent/file.wav")
        result = cache.get(missing_file, "deepgram", "en")
        assert result is None

    def test_handles_corrupted_index_gracefully(self, mock_config: MagicMock) -> None:
        """Test cache handles corrupted index file gracefully."""
        index_path = mock_config.cache_dir / TranscriptionCache.CACHE_INDEX_FILE
        index_path.write_text("corrupted {{{ json")

        # Should not raise, just reinitialize
        cache = TranscriptionCache(config=mock_config)
        stats = cache.stats()
        assert stats["entries"] == 0

    def test_handles_missing_cache_file(
        self, cache: TranscriptionCache, sample_audio_file: Path, sample_result: TranscriptionResult
    ) -> None:
        """Test cache handles manually deleted cache files."""
        cache_key = cache.put(sample_audio_file, "deepgram", "en", sample_result)

        # Manually delete the cache file
        cache_file = cache._get_cache_file_path(cache_key)
        cache_file.unlink()

        # Should return None and clean up index
        result = cache.get(sample_audio_file, "deepgram", "en")
        assert result is None
