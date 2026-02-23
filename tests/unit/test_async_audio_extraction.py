"""Test for async audio extraction functionality."""

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import AudioExtractionTimeoutError
from src.services.audio_extraction import AsyncAudioExtractor, AudioQuality
from src.services.ffmpeg_core import MediaProbeResult

# Apply markers to all tests in this module
pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.mock,
]


class TestAsyncAudioExtractor:
    """Test async audio extraction functionality."""

    class _MockStream:
        def __init__(self, data: bytes = b"") -> None:
            self._data = data

        async def read(self) -> bytes:
            return self._data

    class _HangingProcess:
        def __init__(self) -> None:
            self.stdout = self
            self.stderr = TestAsyncAudioExtractor._MockStream()
            self.returncode: int | None = None

        async def readline(self) -> bytes:
            await asyncio.sleep(10)
            return b""

        async def wait(self) -> int | None:
            await asyncio.sleep(0)
            return self.returncode

        def terminate(self) -> None:
            self.returncode = -15

        def kill(self) -> None:
            self.returncode = -9

    class _FailingProcess:
        def __init__(self) -> None:
            self.stdout = self
            self.stderr = TestAsyncAudioExtractor._MockStream(b"boom")
            self.returncode = 1
            self._lines = [b"", b""]

        async def readline(self) -> bytes:
            return self._lines.pop(0) if self._lines else b""

        async def wait(self) -> int:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = -15

        def kill(self) -> None:
            self.returncode = -9

    def test_import_works(self):
        """Test that we can import the async audio extractor."""
        # Mock the FFmpeg check to prevent failures in CI environments
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor()
            assert extractor is not None

    @pytest.mark.asyncio
    async def test_extract_audio_async_method_exists(self):
        """Test that the async extraction method exists."""
        # Mock the FFmpeg check to prevent failures in CI environments
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor()
            assert hasattr(extractor, "extract_audio_async")

    @pytest.mark.asyncio
    async def test_extract_audio_async_handles_timeout_error(self, tmp_path):
        """Test that TimeoutError is properly caught and handled."""
        # Mock the FFmpeg check to prevent failures in CI environments
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor()
        input_file = tmp_path / "test_video.mp4"
        input_file.write_bytes(b"fake video data")

        # Create a fake probe result
        fake_probe = MediaProbeResult(duration=100.0, size_bytes=1000, size_mb=0.001)

        # Mock probe_media_async to return our fake result
        with patch(
            "src.services.audio_extraction.probe_media_async",
            AsyncMock(return_value=fake_probe),
        ):
            # Mock _run_ffmpeg_with_progress to raise TimeoutError
            with patch.object(
                extractor, "_run_ffmpeg_with_progress", side_effect=TimeoutError("Timeout")
            ):
                with pytest.raises(AudioExtractionTimeoutError):
                    await extractor.extract_audio_async(
                        input_path=input_file, quality=AudioQuality.SPEECH
                    )

    @pytest.mark.asyncio
    async def test_run_ffmpeg_times_out_and_terminates(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor(ffmpeg_timeout=0.01, termination_grace=0.01)

        hanging_proc = self._HangingProcess()

        with patch(
            "src.services.audio_extraction.asyncio.create_subprocess_exec",
            AsyncMock(return_value=hanging_proc),
        ):
            with pytest.raises(TimeoutError):
                await extractor._run_ffmpeg_with_progress(["ffmpeg"], 100, None, stage="Test")

        assert hanging_proc.returncode in {-15, -9}

    @pytest.mark.asyncio
    async def test_run_ffmpeg_raises_on_non_zero_exit(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor()

        failing_proc = self._FailingProcess()

        with patch(
            "src.services.audio_extraction.asyncio.create_subprocess_exec",
            AsyncMock(return_value=failing_proc),
        ):
            with pytest.raises(RuntimeError):
                await extractor._run_ffmpeg_with_progress(["ffmpeg"], 100, None, stage="Test")

    @pytest.mark.asyncio
    async def test_extract_audio_async_handles_subprocess_timeout(self, tmp_path):
        """Test that subprocess.TimeoutExpired is properly caught and handled."""
        # Mock the FFmpeg check to prevent failures in CI environments
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            extractor = AsyncAudioExtractor()
        input_file = tmp_path / "test_video.mp4"
        input_file.write_bytes(b"fake video data")

        # Create a fake probe result
        fake_probe = MediaProbeResult(duration=100.0, size_bytes=1000, size_mb=0.001)

        # Mock probe_media_async to return our fake result
        with patch(
            "src.services.audio_extraction.probe_media_async",
            AsyncMock(return_value=fake_probe),
        ):
            # Mock _run_ffmpeg_with_progress to raise subprocess.TimeoutExpired
            with patch.object(
                extractor,
                "_run_ffmpeg_with_progress",
                side_effect=subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=30),
            ):
                with pytest.raises(AudioExtractionTimeoutError):
                    await extractor.extract_audio_async(
                        input_path=input_file, quality=AudioQuality.SPEECH
                    )
