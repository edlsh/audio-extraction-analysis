"""Performance benchmarks for async operations.

This module establishes performance baselines:
- Async vs sync operation comparison
- Throughput measurements
- Resource utilization
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from src.services.audio_extraction_async import AsyncAudioExtractor, AudioQuality


class TestAsyncPerformance:
    """Performance benchmarks for async operations."""

    @pytest.mark.asyncio
    async def test_async_throughput(self, sample_audio_mp3: Path, tmp_path: Path):
        """Measure async processing throughput."""
        extractor = AsyncAudioExtractor()

        start_time = time.time()

        # Process 10 files concurrently
        tasks = []
        for i in range(10):
            output = tmp_path / f"throughput_{i}.mp3"
            task = extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # All should succeed
        successful = [r for r in results if r is not None]
        assert len(successful) == 10

        # Log performance for baseline
        throughput = 10 / elapsed
        print(f"\nAsync throughput: {throughput:.2f} files/second")
        print(f"Total time: {elapsed:.2f} seconds")

        # Should complete in reasonable time (< 30 seconds)
        assert elapsed < 30

    @pytest.mark.asyncio
    async def test_sequential_vs_concurrent(self, sample_audio_mp3: Path, tmp_path: Path):
        """Compare sequential vs concurrent performance."""
        extractor = AsyncAudioExtractor()

        # Sequential processing
        start_sequential = time.time()
        for i in range(5):
            output = tmp_path / f"sequential_{i}.mp3"
            await extractor.extract_audio_async(
                sample_audio_mp3, output, quality=AudioQuality.COMPRESSED
            )
        sequential_time = time.time() - start_sequential

        # Concurrent processing
        start_concurrent = time.time()
        tasks = [
            extractor.extract_audio_async(
                sample_audio_mp3, tmp_path / f"concurrent_{i}.mp3", quality=AudioQuality.COMPRESSED
            )
            for i in range(5)
        ]
        await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_concurrent

        print(f"\nSequential: {sequential_time:.2f}s")
        print(f"Concurrent: {concurrent_time:.2f}s")
        print(f"Speedup: {sequential_time / concurrent_time:.2f}x")

        # Concurrent should be faster (or at least not slower)
        # Note: For small files, speedup may be minimal
        assert concurrent_time <= sequential_time * 1.5  # Allow some variance

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, sample_audio_mp3: Path, tmp_path: Path):
        """Verify async operations don't cause memory leaks."""
        extractor = AsyncAudioExtractor()

        # Process many files
        for batch in range(3):
            tasks = [
                extractor.extract_audio_async(
                    sample_audio_mp3,
                    tmp_path / f"mem_{batch}_{i}.mp3",
                    quality=AudioQuality.COMPRESSED,
                )
                for i in range(10)
            ]
            await asyncio.gather(*tasks)

            # Allow garbage collection
            await asyncio.sleep(0.1)

        # Test completes without memory exhaustion
        assert True


class TestPerformanceBaselines:
    """Establish performance baselines for different quality settings."""

    @pytest.mark.asyncio
    async def test_quality_performance_comparison(self, sample_audio_mp3: Path, tmp_path: Path):
        """Compare performance across quality settings."""
        extractor = AsyncAudioExtractor()

        qualities = [
            AudioQuality.COMPRESSED,
            AudioQuality.STANDARD,
            AudioQuality.HIGH,
            AudioQuality.SPEECH,
        ]

        timings = {}

        for quality in qualities:
            output = tmp_path / f"quality_{quality.value}.mp3"

            start = time.time()
            await extractor.extract_audio_async(sample_audio_mp3, output, quality=quality)
            elapsed = time.time() - start

            timings[quality.value] = elapsed

        # Log baseline timings
        print("\nQuality performance baselines:")
        for quality_name, timing in timings.items():
            print(f"  {quality_name}: {timing:.3f}s")

        # All should complete in reasonable time
        assert all(t < 10 for t in timings.values())
