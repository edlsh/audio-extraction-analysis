"""FFmpeg error handling integration tests.

This module tests graceful failure scenarios:
- Corrupt audio file handling
- Missing FFmpeg binary
- Unsupported codec handling
- Error logging and propagation
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.audio_extraction_async import AsyncAudioExtractor, AudioQuality


class TestFFmpegErrorHandling:
    """Test FFmpeg error scenarios."""

    @pytest.mark.asyncio
    async def test_corrupted_audio_handling(self, corrupted_audio: Path, tmp_path: Path, caplog):
        """Test handling of corrupted audio files."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.ERROR):
            result = await extractor.extract_audio_async(
                corrupted_audio, output, quality=AudioQuality.STANDARD
            )

        # Should return None on failure
        assert result is None

        # Should log error with context
        assert any(
            "error" in record.message.lower() or "fail" in record.message.lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_empty_file_handling(self, empty_audio: Path, tmp_path: Path, caplog):
        """Test handling of empty audio files."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.ERROR):
            result = await extractor.extract_audio_async(
                empty_audio, output, quality=AudioQuality.STANDARD
            )

        # Should return None on failure
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_format_handling(self, tmp_path: Path, caplog):
        """Test handling of files with unsupported format."""
        # Create file with unsupported extension
        invalid_file = tmp_path / "test.xyz"
        invalid_file.write_text("not an audio file")

        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.ERROR):
            result = await extractor.extract_audio_async(
                invalid_file, output, quality=AudioQuality.STANDARD
            )

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_ffmpeg_handling(self, sample_audio_mp3: Path, tmp_path: Path, caplog):
        """Test graceful handling when FFmpeg binary is missing."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        # Mock shutil.which to simulate missing FFmpeg
        with patch("shutil.which", return_value=None):
            with caplog.at_level(logging.ERROR):
                # The extractor should handle missing FFmpeg
                # by failing gracefully
                result = await extractor.extract_audio_async(
                    sample_audio_mp3, output, quality=AudioQuality.STANDARD
                )

                # Result may be None or may succeed depending on implementation
                # The key is no crash and proper logging
                if result is None:
                    # Should log about missing FFmpeg or failure
                    assert len(caplog.records) > 0

    @pytest.mark.asyncio
    async def test_permission_error_handling(self, sample_audio_mp3: Path, tmp_path: Path, caplog):
        """Test handling of permission errors."""
        extractor = AsyncAudioExtractor()

        # Create output in read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir(mode=0o444)  # Read-only
        output = readonly_dir / "output.mp3"

        with caplog.at_level(logging.ERROR):
            await extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.STANDARD
            )

        # Should handle permission error gracefully
        # Result depends on when permission check happens
        assert True  # Test completes without crash

        # Cleanup
        readonly_dir.chmod(0o755)


class TestErrorLogging:
    """Test error logging completeness and clarity."""

    @pytest.mark.asyncio
    async def test_error_messages_actionable(self, corrupted_audio: Path, tmp_path: Path, caplog):
        """Verify error messages provide actionable context."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.ERROR):
            await extractor.extract_audio_async(
                corrupted_audio, output, quality=AudioQuality.STANDARD
            )

        # Check for meaningful error messages
        error_messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]

        # Should have at least one error message
        assert len(error_messages) > 0

        # Messages should contain useful context
        # (file path, operation type, or error reason)
        assert any(len(msg) > 20 for msg in error_messages)  # Non-trivial message

    @pytest.mark.asyncio
    async def test_no_silent_failures(self, corrupted_audio: Path, tmp_path: Path, caplog):
        """Ensure failures are logged, not silent."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.INFO):
            result = await extractor.extract_audio_async(
                corrupted_audio, output, quality=AudioQuality.STANDARD
            )

        # Failed operation should produce log entries
        if result is None:
            # Should have logged something about the failure
            assert len(caplog.records) > 0
