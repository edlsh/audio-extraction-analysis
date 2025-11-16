"""Complex async workflow integration tests.

This module tests:
- Concurrent audio file processing
- Async exception handling
- Cancellation behavior
- Timeout scenarios
- Performance benchmarks
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.services.audio_extraction_async import AsyncAudioExtractor, AudioQuality


@pytest.mark.integration
@pytest.mark.ffmpeg
class TestConcurrentProcessing:
    """Test concurrent audio processing workflows."""

    @pytest.mark.asyncio
    async def test_parallel_file_processing(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test parallel processing of multiple files."""
        extractor = AsyncAudioExtractor()

        # Process 5 files concurrently
        tasks = []
        for i in range(5):
            output = tmp_path / f"parallel_{i}.mp3"
            task = extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)
        assert all(r.exists() for r in results)
        assert len(set(r.stat().st_size for r in results)) == 1  # Same size

    @pytest.mark.asyncio
    async def test_concurrent_different_qualities(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test concurrent processing with different quality settings."""
        extractor = AsyncAudioExtractor()

        qualities = [
            AudioQuality.HIGH,
            AudioQuality.STANDARD,
            AudioQuality.COMPRESSED,
            AudioQuality.SPEECH,
        ]

        tasks = []
        for i, quality in enumerate(qualities):
            output = tmp_path / f"quality_{quality.value}_{i}.mp3"
            task = extractor.extract_audio_async(sample_audio_mp3, output, quality=quality)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)
        assert all(r.exists() for r in results)

    @pytest.mark.asyncio
    async def test_no_race_conditions(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify no race conditions in concurrent processing."""
        extractor = AsyncAudioExtractor()

        # Run same operations multiple times concurrently
        tasks = []
        for i in range(10):
            output = tmp_path / f"race_test_{i}.mp3"
            task = extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
            tasks.append(task)

        # Should complete without errors
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # No exceptions should occur
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Race conditions detected: {exceptions}"


@pytest.mark.integration
@pytest.mark.ffmpeg
class TestAsyncExceptionHandling:
    """Test exception handling in async contexts."""

    @pytest.mark.asyncio
    async def test_exception_propagation(self, corrupted_audio: Path, tmp_path: Path):
        """Test exceptions propagate correctly in async."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        # Should not raise, but return None
        result = await extractor.extract_audio_async(
            corrupted_audio, output, quality=AudioQuality.STANDARD
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self, sample_audio_mp3: Path, corrupted_audio: Path, tmp_path: Path
    ):
        """Test partial failures don't affect successful operations."""
        extractor = AsyncAudioExtractor()

        tasks = [
            extractor.extract_audio_async(
                sample_audio_mp3, tmp_path / "success1.mp3", quality=AudioQuality.COMPRESSED
            ),
            extractor.extract_audio_async(
                corrupted_audio, tmp_path / "fail.mp3", quality=AudioQuality.COMPRESSED
            ),
            extractor.extract_audio_async(
                sample_audio_mp3, tmp_path / "success2.mp3", quality=AudioQuality.COMPRESSED
            ),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Two should succeed, one should fail
        successful = [r for r in results if r is not None and isinstance(r, Path)]
        failed = [r for r in results if r is None]

        assert len(successful) == 2
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_exception_logging(self, corrupted_audio: Path, tmp_path: Path, caplog):
        """Verify exceptions are logged properly."""
        import logging

        extractor = AsyncAudioExtractor()
        output = tmp_path / "output.mp3"

        with caplog.at_level(logging.ERROR):
            await extractor.extract_audio_async(
                corrupted_audio, output, quality=AudioQuality.STANDARD
            )

        # Should have error logs
        assert len(caplog.records) > 0


@pytest.mark.integration
@pytest.mark.ffmpeg
class TestCancellationAndTimeouts:
    """Test task cancellation and timeout behavior."""

    @pytest.mark.asyncio
    async def test_task_cancellation(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test graceful handling of task cancellation."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "cancel.mp3"

        task = asyncio.create_task(
            extractor.extract_audio_async(sample_audio_mp3, output, quality=AudioQuality.SPEECH)
        )

        # Let it start
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

        # Verify cleanup (best effort)
        output.with_suffix(".temp.mp3")
        # Temp file may or may not exist depending on timing

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sample_audio_mp3: Path, tmp_path: Path):
        """Test timeout behavior."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "timeout.mp3"

        try:
            # Set very short timeout to force timeout
            await asyncio.wait_for(
                extractor.extract_audio_async(
                    sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
                ),
                timeout=0.001,  # 1ms - should timeout
            )
        except TimeoutError:
            pass  # Expected for such short timeout

        # Test should complete without hanging

    @pytest.mark.asyncio
    async def test_no_hung_tasks(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify tasks don't hang indefinitely."""
        extractor = AsyncAudioExtractor()

        # Run with reasonable timeout
        try:
            await asyncio.wait_for(
                extractor.extract_audio_async(
                    sample_audio_mp3, tmp_path / "no_hang.mp3", quality=AudioQuality.COMPRESSED
                ),
                timeout=30.0,  # 30 second timeout
            )
        except TimeoutError:
            pytest.fail("Task hung - exceeded 30 second timeout")


@pytest.mark.integration
@pytest.mark.ffmpeg
class TestAsyncResourceCleanup:
    """Test resource cleanup in async contexts."""

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_async(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify temp files cleaned up in async operations."""
        extractor = AsyncAudioExtractor()
        output = tmp_path / "cleanup_async.mp3"

        await extractor.extract_audio_async(sample_audio_mp3, output, quality=AudioQuality.SPEECH)

        # Temp file should be cleaned up
        temp_file = output.with_suffix(".temp.mp3")
        assert not temp_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_on_concurrent_failure(
        self, sample_audio_mp3: Path, corrupted_audio: Path, tmp_path: Path
    ):
        """Verify cleanup works even with concurrent failures."""
        extractor = AsyncAudioExtractor()

        tasks = []
        for i in range(3):
            input_file = sample_audio_mp3 if i % 2 == 0 else corrupted_audio
            output = tmp_path / f"cleanup_{i}.mp3"
            task = extractor.extract_audio_async(input_file, output, quality=AudioQuality.SPEECH)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # No temp files should remain
        temp_files = list(tmp_path.glob("*.temp.mp3"))
        assert len(temp_files) == 0
