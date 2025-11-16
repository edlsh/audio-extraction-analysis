"""Test for async audio extraction functionality."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.audio_extraction import AudioQuality
from src.services.audio_extraction_async import AsyncAudioExtractor

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.mock,
]


class TestAsyncAudioExtractor:
    """Test async audio extraction functionality."""

    def test_import_works(self):
        """Test that we can import the async audio extractor."""
        extractor = AsyncAudioExtractor()
        assert extractor is not None

    @pytest.mark.asyncio
    async def test_extract_audio_async_method_exists(self):
        """Test that the async extraction method exists."""
        extractor = AsyncAudioExtractor()
        assert hasattr(extractor, "extract_audio_async")

    @pytest.mark.asyncio
    async def test_extract_audio_async_handles_timeout_error(self, tmp_path):
        """Test that TimeoutError is properly caught and handled."""
        extractor = AsyncAudioExtractor()
        input_file = tmp_path / "test_video.mp4"
        input_file.write_bytes(b"fake video data")

        # Mock _run_ffmpeg_with_progress to raise TimeoutError
        with patch.object(
            extractor, "_run_ffmpeg_with_progress", side_effect=TimeoutError("Timeout")
        ):
            # Mock _get_video_duration to return a value
            with patch.object(extractor, "_get_video_duration", return_value=100.0):
                # Mock get_video_info to return None
                with patch.object(extractor, "get_video_info", return_value=None):
                    result = await extractor.extract_audio_async(
                        input_path=input_file, quality=AudioQuality.SPEECH
                    )

        # Should return None instead of raising the exception
        assert result is None

    @pytest.mark.asyncio
    async def test_extract_audio_async_handles_subprocess_timeout(self, tmp_path):
        """Test that subprocess.TimeoutExpired is properly caught and handled."""
        import subprocess

        extractor = AsyncAudioExtractor()
        input_file = tmp_path / "test_video.mp4"
        input_file.write_bytes(b"fake video data")

        # Mock _run_ffmpeg_with_progress to raise subprocess.TimeoutExpired
        with patch.object(
            extractor,
            "_run_ffmpeg_with_progress",
            side_effect=subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=30),
        ):
            # Mock _get_video_duration to return a value
            with patch.object(extractor, "_get_video_duration", return_value=100.0):
                # Mock get_video_info to return None
                with patch.object(extractor, "get_video_info", return_value=None):
                    result = await extractor.extract_audio_async(
                        input_path=input_file, quality=AudioQuality.SPEECH
                    )

        # Should return None instead of raising the exception
        assert result is None
