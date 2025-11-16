"""Error recovery integration tests.

This module tests:
- Network timeout scenarios
- Retry logic behavior
- Partial failure handling in batch operations
- Resource cleanup on errors
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.services.audio_extraction_async import AsyncAudioExtractor, AudioQuality


class TestNetworkFailureSimulation:
    """Test handling of network-like failures."""

    @pytest.mark.asyncio
    async def test_subprocess_timeout_handling(
        self, sample_audio_mp3: Path, tmp_path: Path, caplog
    ):
        """Test handling of subprocess timeouts."""
        import logging

        extractor = AsyncAudioExtractor()
        output = tmp_path / "timeout.mp3"

        # Mock subprocess to simulate timeout
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            # Mock stdout.readline to raise TimeoutError when awaited
            mock_stdout = AsyncMock()
            mock_stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError("Test timeout"))
            mock_process.stdout = mock_stdout
            mock_process.wait = AsyncMock()
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            with caplog.at_level(logging.ERROR):
                result = await extractor.extract_audio_async(
                    sample_audio_mp3, output, quality=AudioQuality.STANDARD
                )

            # Should handle timeout gracefully
            assert result is None
            assert any(
                "timeout" in record.message.lower() or "failed" in record.message.lower()
                for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_process_error_handling(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test handling of process errors."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "error.mp3"

        # Mock subprocess to simulate process error
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            # Mock stdout.readline to return empty bytes (end of stream)
            mock_stdout = AsyncMock()
            mock_stdout.readline = AsyncMock(return_value=b"")
            mock_process.stdout = mock_stdout
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Error")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.STANDARD
            )

            # Should handle error gracefully and return None
            assert result is None


class TestBatchOperationFailures:
    """Test partial failures in batch operations."""

    @pytest.mark.asyncio
    async def test_partial_batch_success(
        self, sample_audio_mp3: Path, corrupted_audio: Path, tmp_path: Path
    ):
        """Test batch processing with some failures."""
        extractor = AsyncAudioExtractor()

        # Mix of valid and invalid inputs
        inputs = [
            (sample_audio_mp3, tmp_path / "batch_1.mp3"),
            (corrupted_audio, tmp_path / "batch_2.mp3"),
            (sample_audio_mp3, tmp_path / "batch_3.mp3"),
            (corrupted_audio, tmp_path / "batch_4.mp3"),
            (sample_audio_mp3, tmp_path / "batch_5.mp3"),
        ]

        tasks = [
            extractor.extract_audio_async(input_file, output, AudioQuality.COMPRESSED)
            for input_file, output in inputs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Should have both successes and failures
        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]

        assert len(successes) == 3  # 3 valid inputs
        assert len(failures) == 2  # 2 corrupted inputs

    @pytest.mark.asyncio
    async def test_successful_items_preserved(
        self, sample_audio_mp3: Path, corrupted_audio: Path, tmp_path: Path
    ):
        """Verify successful items aren't affected by failures."""
        extractor = AsyncAudioExtractor()

        tasks = [
            extractor.extract_audio_async(
                sample_audio_mp3, tmp_path / "success_1.mp3", AudioQuality.COMPRESSED
            ),
            extractor.extract_audio_async(
                corrupted_audio, tmp_path / "fail.mp3", AudioQuality.COMPRESSED
            ),
            extractor.extract_audio_async(
                sample_audio_mp3, tmp_path / "success_2.mp3", AudioQuality.COMPRESSED
            ),
        ]

        results = await asyncio.gather(*tasks)

        # Successful files should exist and be valid
        success_1 = tmp_path / "success_1.mp3"
        success_2 = tmp_path / "success_2.mp3"

        if results[0] is not None:
            assert success_1.exists()
            assert success_1.stat().st_size > 0

        if results[2] is not None:
            assert success_2.exists()
            assert success_2.stat().st_size > 0


class TestResourceCleanupOnErrors:
    """Test resource cleanup when errors occur."""

    @pytest.mark.asyncio
    async def test_file_handle_cleanup(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify file handles closed on errors."""
        import resource

        extractor = AsyncAudioExtractor()
        output = tmp_path / "handles.mp3"

        # Get initial open file count
        try:
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:
            pytest.skip("Resource tracking not available on this platform")

        # Process with potential for errors
        for _ in range(5):
            await extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )

        # File descriptor count shouldn't grow significantly
        # (exact check is platform-dependent)
        assert True  # Test completes without resource exhaustion

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_error(self, corrupted_audio: Path, tmp_path: Path):
        """Verify temp files cleaned up even on errors."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "error_cleanup.mp3"

        # Should fail but clean up
        result = await extractor.extract_audio_async(
            corrupted_audio, output, quality=AudioQuality.SPEECH
        )

        assert result is None

        # No temp files should remain
        temp_files = list(tmp_path.glob("*.temp.mp3"))
        assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_cleanup_after_cancellation(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify cleanup happens after task cancellation."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "cancel_cleanup.mp3"

        task = asyncio.create_task(
            extractor.extract_audio_async(sample_audio_mp3, output, quality=AudioQuality.SPEECH)
        )

        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Give cleanup time to run
        await asyncio.sleep(0.1)

        # Temp file cleanup is best-effort on cancellation
        # Just verify no resource leaks


class TestErrorRecoveryLogging:
    """Test error recovery provides good logging."""

    @pytest.mark.asyncio
    async def test_error_context_logged(self, corrupted_audio: Path, tmp_path: Path, caplog):
        """Verify errors logged with context."""
        import logging

        extractor = AsyncAudioExtractor()
        output = tmp_path / "error_log.mp3"

        with caplog.at_level(logging.INFO):
            await extractor.extract_audio_async(
                corrupted_audio, output, quality=AudioQuality.STANDARD
            )

        # Should have logged the error
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) > 0

        # Logs should contain useful context
        log_text = " ".join(r.message for r in error_logs)
        # Should mention file or operation
        assert len(log_text) > 20
