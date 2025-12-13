"""Async tests for TranscriptionCache.

Tests the async variants of cache methods to ensure they are non-blocking
and correctly delegate to the sync implementations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.transcription import TranscriptionResult
from src.services.cache import TranscriptionCache


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
    config.cache_ttl = 3600
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


@pytest.mark.asyncio
async def test_invalidate_async_nonblocking(
    cache: TranscriptionCache,
    sample_audio_file: Path,
    sample_result: TranscriptionResult,
) -> None:
    """Test that invalidate_async delegates to invalidate via asyncio.to_thread."""
    cache.put(sample_audio_file, "test_provider", "en", sample_result)
    assert cache.has(sample_audio_file, "test_provider", "en")

    with patch.object(cache, "invalidate", wraps=cache.invalidate) as mock_invalidate:
        result = await cache.invalidate_async(sample_audio_file, "test_provider", "en")

        assert result is True
        mock_invalidate.assert_called_once_with(
            sample_audio_file, "test_provider", "en"
        )

    assert not cache.has(sample_audio_file, "test_provider", "en")


@pytest.mark.asyncio
async def test_invalidate_async_returns_false_for_missing_entry(
    cache: TranscriptionCache,
    sample_audio_file: Path,
) -> None:
    """Test that invalidate_async returns False when entry doesn't exist."""
    result = await cache.invalidate_async(sample_audio_file, "test_provider", "en")
    assert result is False


@pytest.mark.asyncio
async def test_invalidate_async_concurrent_execution(
    cache: TranscriptionCache,
    tmp_path: Path,
    sample_result: TranscriptionResult,
) -> None:
    """Test that multiple invalidate_async calls can run concurrently."""
    files = []
    for i in range(3):
        f = tmp_path / f"audio_{i}.wav"
        f.write_bytes(f"unique content {i}".encode() * 100)
        files.append(f)
        cache.put(f, "test_provider", "en", sample_result)

    results = await asyncio.gather(
        *[cache.invalidate_async(f, "test_provider", "en") for f in files]
    )

    assert all(results)
    for f in files:
        assert not cache.has(f, "test_provider", "en")
