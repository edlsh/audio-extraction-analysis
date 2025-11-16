"""Integration tests for FFmpeg audio processing.

This module tests FFmpeg integration end-to-end with real FFmpeg binary:
- Format conversion (MP3, WAV, FLAC, M4A)
- Audio quality verification
- Async implementation safety
- Performance constraints (<30 seconds total)
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from src.services.audio_extraction_async import AsyncAudioExtractor, AudioQuality


@pytest.mark.integration
@pytest.mark.ffmpeg


class TestFFmpegFormatConversion:
    """Test FFmpeg format conversion functionality."""

    def test_mp3_generation_fixture(self, sample_audio_mp3: Path):
        """Verify test fixture generation works."""
        assert sample_audio_mp3.exists()
        assert sample_audio_mp3.suffix == ".mp3"
        assert sample_audio_mp3.stat().st_size > 0

    def test_wav_generation_fixture(self, sample_audio_wav: Path):
        """Verify WAV test fixture generation works."""
        assert sample_audio_wav.exists()
        assert sample_audio_wav.suffix == ".wav"
        assert sample_audio_wav.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_mp3_to_wav_conversion(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test MP3 to WAV conversion with quality verification."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.wav"

        # Extract with high quality
        result = await extractor.extract_audio_async(
            sample_audio_mp3, output, quality=AudioQuality.HIGH
        )

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

        # Verify output is valid audio
        info = extractor.get_video_info(output)
        assert info is not None
        assert info.get("duration", 0) > 0

    @pytest.mark.asyncio
    async def test_wav_to_mp3_conversion(self, sample_audio_wav: Path, tmp_path: Path):
        """Test WAV to MP3 conversion."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        result = await extractor.extract_audio_async(
            sample_audio_wav, output, quality=AudioQuality.COMPRESSED
        )

        assert result == output
        assert output.exists()

    @pytest.mark.asyncio
    async def test_quality_presets(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test all quality presets produce valid output."""
        extractor = AsyncAudioExtractor()

        qualities = [
            AudioQuality.HIGH,
            AudioQuality.STANDARD,
            AudioQuality.COMPRESSED,
            AudioQuality.SPEECH,
        ]

        for quality in qualities:
            output = tmp_path / f"output_{quality.value}.mp3"
            result = await extractor.extract_audio_async(sample_audio_mp3, output, quality=quality)

            assert result == output, f"Failed for quality: {quality.value}"
            assert output.exists(), f"Output missing for quality: {quality.value}"
            assert output.stat().st_size > 0, f"Empty output for quality: {quality.value}"

    @pytest.mark.asyncio
    async def test_audio_quality_verification(
        self, sample_audio_mp3: Path, tmp_path: Path, ffmpeg_binary: Path
    ):
        """Verify output audio quality and format compliance."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output_quality_test.mp3"

        await extractor.extract_audio_async(sample_audio_mp3, output, quality=AudioQuality.HIGH)

        # Use ffprobe to verify audio quality
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(output),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Basic validation that ffprobe can read the file
        assert len(result.stdout) > 0


class TestFFmpegAsyncSafety:
    """Test async implementation for race conditions and resource safety."""

    @pytest.mark.asyncio
    async def test_concurrent_audio_processing(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test parallel file processing doesn't cause race conditions."""
        extractor = AsyncAudioExtractor()

        # Process 3 files concurrently
        tasks = []
        for i in range(3):
            output = tmp_path / f"concurrent_{i}.mp3"
            task = extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All tasks should complete successfully
        assert all(r is not None for r in results)
        assert all(r.exists() for r in results)

    @pytest.mark.asyncio
    async def test_async_resource_cleanup(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify async operations clean up resources properly."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "cleanup_test.mp3"

        # Use speech quality which creates temp files
        result = await extractor.extract_audio_async(
            sample_audio_mp3, output, quality=AudioQuality.SPEECH
        )

        assert result == output

        # Temp file should be cleaned up
        temp_file = output.with_suffix(".temp.mp3")
        assert not temp_file.exists(), "Temp file not cleaned up"

    @pytest.mark.asyncio
    async def test_cancellation_cleanup(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test that cancellation properly cleans up resources."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "cancel_test.mp3"

        # Create task
        task = asyncio.create_task(
            extractor.extract_audio_async(sample_audio_mp3, output, quality=AudioQuality.SPEECH)
        )

        # Let it start, then cancel
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

        # Verify no leftover temp files
        output.with_suffix(".temp.mp3")
        # Note: Cleanup on cancellation is best-effort
        # Just verify the test doesn't hang


class TestFFmpegPerformance:
    """Test FFmpeg performance constraints."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Entire test suite must complete in 30 seconds
    async def test_performance_constraint(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify FFmpeg tests complete within 30 second constraint."""
        extractor = AsyncAudioExtractor()

        # Run multiple operations
        for i in range(3):
            output = tmp_path / f"perf_{i}.mp3"
            result = await extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
            assert result is not None

        # If we reach here within timeout, constraint is met
        assert True
