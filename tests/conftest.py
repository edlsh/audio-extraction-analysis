"""Global pytest fixtures and configuration.

This module provides shared fixtures for all tests including:
- FFmpeg binary detection
- Test audio file generation
- Secure configuration for testing
- API mocking utilities
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def ffmpeg_binary() -> Path:
    """Locate FFmpeg binary, skip tests if not found.

    Returns:
        Path to FFmpeg binary

    Raises:
        pytest.skip: If FFmpeg is not available
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        pytest.skip("FFmpeg not available - install FFmpeg to run integration tests")
    return Path(ffmpeg_path)


@pytest.fixture(scope="session")
def sample_audio_mp3(tmp_path_factory: pytest.TempPathFactory, ffmpeg_binary: Path) -> Path:
    """Generate 5-second MP3 test audio file (session-scoped for performance).

    Args:
        tmp_path_factory: pytest temp path factory
        ffmpeg_binary: FFmpeg binary path

    Returns:
        Path to generated MP3 file
    """
    output_dir = tmp_path_factory.mktemp("fixtures")
    output = output_dir / "test_audio_5s.mp3"

    # Generate 5-second sine wave at 440 Hz (A4 note)
    result = subprocess.run(
        [
            str(ffmpeg_binary),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=5",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(output),
        ],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.skip(f"Failed to generate test audio: {result.stderr.decode()}")

    return output


@pytest.fixture(scope="session")
def sample_audio_wav(tmp_path_factory: pytest.TempPathFactory, ffmpeg_binary: Path) -> Path:
    """Generate 5-second WAV test audio file.

    Args:
        tmp_path_factory: pytest temp path factory
        ffmpeg_binary: FFmpeg binary path

    Returns:
        Path to generated WAV file
    """
    output_dir = tmp_path_factory.mktemp("fixtures")
    output = output_dir / "test_audio_5s.wav"

    result = subprocess.run(
        [
            str(ffmpeg_binary),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=5",
            "-codec:a",
            "pcm_s16le",
            "-ar",
            "44100",
            str(output),
        ],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.skip(f"Failed to generate test WAV: {result.stderr.decode()}")

    return output


@pytest.fixture
def corrupted_audio(tmp_path: Path) -> Path:
    """Create corrupted audio file for error testing.

    Args:
        tmp_path: pytest temp directory

    Returns:
        Path to corrupted file
    """
    corrupted = tmp_path / "corrupted.mp3"
    # Write truncated MP3 header
    corrupted.write_bytes(b"\xff\xfb\x90\x00")  # Incomplete MP3 header
    return corrupted


@pytest.fixture
def empty_audio(tmp_path: Path) -> Path:
    """Create empty audio file for error testing.

    Args:
        tmp_path: pytest temp directory

    Returns:
        Path to empty file
    """
    empty = tmp_path / "empty.mp3"
    empty.touch()
    return empty
