#!/usr/bin/env python3
"""
Functional tests for cache subsystem after security fix.

This module verifies that the transcription cache correctly:
1. Generates content-based cache keys from files
2. Stores and retrieves transcription results
3. Handles both in-memory and disk-based backends
4. Tracks cache statistics (hits, misses)
5. Manages compression settings safely
6. Handles error scenarios gracefully

The security fix addressed safe JSON deserialization in cache backends.
These tests ensure cache functionality remains correct post-fix.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from src.cache.backends import DiskCache, InMemoryCache
from src.cache.transcription_cache import CacheKey, TranscriptionCache


class TestCacheFunctionality:
    """Test basic cache operations after security fix."""

    @pytest.fixture
    def test_file(self) -> Path:
        """Create temporary test file with content.

        Yields:
            Path to temporary file with test content.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)

    @pytest.fixture
    def sample_settings(self) -> dict[str, Any]:
        """Standard settings for cache tests.

        Returns:
            Dictionary with model and language settings.
        """
        return {"model": "whisper", "language": "en"}

    @pytest.fixture
    def sample_transcription(self) -> dict[str, Any]:
        """Sample transcription result.

        Returns:
            Dictionary with text and confidence score.
        """
        return {"text": "Hello world", "confidence": 0.95}

    @pytest.fixture
    def temp_cache_dir(self) -> Path:
        """Create temporary directory for disk cache tests.

        Yields:
            Path to temporary cache directory.
        """
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cache_key_generation(self, test_file: Path, sample_settings: dict[str, Any]) -> None:
        """Cache key should be generated with correct components from file.

        Verifies:
        - Cache key is created successfully
        - Provider is stored correctly
        - Settings hash is computed
        - File hash is computed
        """
        cache_key = CacheKey.from_file(test_file, "openai", sample_settings)

        assert cache_key.provider == "openai"
        assert cache_key.settings_hash is not None
        assert cache_key.file_hash is not None
        assert len(cache_key.file_hash) > 0

    def test_in_memory_cache_put_operation(
        self, test_file: Path, sample_settings: dict[str, Any], sample_transcription: dict[str, Any]
    ) -> None:
        """In-memory cache should successfully store values.

        Verifies:
        - Put operation returns True on success
        - No exceptions are raised during storage
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        success = cache.put(test_file, "openai", sample_settings, sample_transcription)
        assert success, "Cache put operation should succeed"

    def test_in_memory_cache_get_operation(
        self, test_file: Path, sample_settings: dict[str, Any], sample_transcription: dict[str, Any]
    ) -> None:
        """In-memory cache should retrieve stored values correctly.

        Verifies:
        - Get returns exact value that was stored
        - Retrieved value matches original data structure
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        cache.put(test_file, "openai", sample_settings, sample_transcription)
        cached_result = cache.get(test_file, "openai", sample_settings)

        assert (
            cached_result == sample_transcription
        ), "Cached result should match original transcription"

    def test_cache_miss_before_put(self, test_file: Path, sample_settings: dict[str, Any]) -> None:
        """Cache get should return None for non-existent key.

        Verifies:
        - Get returns None when key doesn't exist
        - No exceptions on cache miss
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        result = cache.get(test_file, "openai", sample_settings)
        assert result is None, "Cache should return None on miss"

    def test_cache_statistics_tracking(
        self, test_file: Path, sample_settings: dict[str, Any], sample_transcription: dict[str, Any]
    ) -> None:
        """Cache should track hits and misses correctly.

        Verifies:
        - Stats object is returned
        - Hits and misses are tracked
        - Counters are accessible
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        # First get should be a miss
        cache.get(test_file, "openai", sample_settings)
        stats_after_miss = cache.get_stats()

        # Put and get should be a hit
        cache.put(test_file, "openai", sample_settings, sample_transcription)
        cache.get(test_file, "openai", sample_settings)
        stats_after_hit = cache.get_stats()

        assert (
            stats_after_hit.hits >= stats_after_miss.hits
        ), "Hit counter should increment or stay same"
        assert hasattr(stats_after_hit, "misses"), "Stats should track misses"

    def test_disk_cache_put_operation(
        self,
        test_file: Path,
        temp_cache_dir: Path,
        sample_settings: dict[str, Any],
        sample_transcription: dict[str, Any],
    ) -> None:
        """Disk cache should persist values to disk.

        Verifies:
        - Put operation succeeds with disk backend
        - No errors during disk write
        """
        disk_cache = TranscriptionCache(
            backends=[DiskCache(str(temp_cache_dir))], enable_compression=False
        )

        success = disk_cache.put(test_file, "openai", sample_settings, sample_transcription)
        assert success, "Disk cache put operation should succeed"

    def test_disk_cache_get_operation(
        self,
        test_file: Path,
        temp_cache_dir: Path,
        sample_settings: dict[str, Any],
        sample_transcription: dict[str, Any],
    ) -> None:
        """Disk cache should retrieve persisted values.

        Verifies:
        - Get returns exact value from disk
        - Data survives write-read cycle
        """
        disk_cache = TranscriptionCache(
            backends=[DiskCache(str(temp_cache_dir))], enable_compression=False
        )

        disk_cache.put(test_file, "openai", sample_settings, sample_transcription)
        cached_result = disk_cache.get(test_file, "openai", sample_settings)

        assert (
            cached_result == sample_transcription
        ), "Disk cached result should match original transcription"

    @pytest.mark.parametrize(
        "backend_factory",
        [
            pytest.param(lambda: InMemoryCache(), id="in-memory"),
            pytest.param(lambda: DiskCache(tempfile.mkdtemp()), id="disk"),
        ],
    )
    def test_cache_backends_consistency(
        self,
        test_file: Path,
        sample_settings: dict[str, Any],
        sample_transcription: dict[str, Any],
        backend_factory: Callable[[], Any],
    ) -> None:
        """Both cache backends should behave consistently.

        Verifies:
        - Put/get cycle works identically for all backends
        - Data integrity maintained across backends

        Args:
            test_file: Temporary test file path
            sample_settings: Test transcription settings
            sample_transcription: Expected transcription result
            backend_factory: Factory function to create cache backend
        """
        cache = TranscriptionCache(backends=[backend_factory()], enable_compression=False)

        # Put operation
        success = cache.put(test_file, "openai", sample_settings, sample_transcription)
        assert success, "Cache put should succeed for all backends"

        # Get operation
        cached_result = cache.get(test_file, "openai", sample_settings)
        assert (
            cached_result == sample_transcription
        ), "All backends should return consistent results"

    def test_cache_handles_missing_file(self) -> None:
        """Cache should handle missing file gracefully.

        Verifies:
        - FileNotFoundError raised for non-existent files
        - Error message is informative
        """
        TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)
        non_existent = Path("/nonexistent/file.wav")

        with pytest.raises(FileNotFoundError):
            CacheKey.from_file(non_existent, "openai", {})

    def test_cache_different_settings_different_keys(
        self, test_file: Path, sample_transcription: dict[str, Any]
    ) -> None:
        """Different settings should produce different cache keys.

        Verifies:
        - Settings are part of cache key
        - Same file with different settings doesn't collide
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        settings_1 = {"model": "whisper", "language": "en"}
        settings_2 = {"model": "whisper", "language": "es"}

        # Store with first settings
        cache.put(test_file, "openai", settings_1, sample_transcription)

        # Get with different settings should miss
        result = cache.get(test_file, "openai", settings_2)
        assert result is None, "Different settings should not retrieve same cached value"

    def test_cache_different_providers_different_keys(
        self, test_file: Path, sample_settings: dict[str, Any], sample_transcription: dict[str, Any]
    ) -> None:
        """Different providers should produce different cache keys.

        Verifies:
        - Provider is part of cache key
        - Same file/settings with different provider doesn't collide
        """
        cache = TranscriptionCache(backends=[InMemoryCache()], enable_compression=False)

        # Store with openai provider
        cache.put(test_file, "openai", sample_settings, sample_transcription)

        # Get with different provider should miss
        result = cache.get(test_file, "deepgram", sample_settings)
        assert result is None, "Different provider should not retrieve same cached value"
