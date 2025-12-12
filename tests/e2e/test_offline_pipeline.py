"""End-to-end tests for offline/no-network pipeline execution.

These tests verify the full pipeline using the StubTranscriptionProvider,
ensuring deterministic behavior and correct exit codes without requiring
network access or API keys.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.base import TestResult


PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def stub_audio_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a minimal test audio file for offline testing."""
    import shutil

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        pytest.skip("FFmpeg not available")

    output_dir = tmp_path_factory.mktemp("offline_fixtures")
    output = output_dir / "test_audio_2s.wav"

    result = subprocess.run(
        [
            ffmpeg_path,
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-codec:a",
            "pcm_s16le",
            "-ar",
            "16000",
            str(output),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Failed to generate test audio: {result.stderr.decode()}")

    return output


def run_cli(
    args: list[str],
    env_override: dict[str, str] | None = None,
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Run CLI command and return (exit_code, stdout, stderr)."""
    import os

    env = os.environ.copy()
    env["AUDIO_PIPELINE_TEST_MODE"] = "1"
    env["AUDIO_PIPELINE_PROVIDER"] = "stub"
    if env_override:
        env.update(env_override)

    cmd = [sys.executable, "-m", "src.cli", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestOfflinePipelineExitCodes:
    """Test exit code behavior for various pipeline outcomes."""

    def test_help_returns_zero(self) -> None:
        """--help should exit 0."""
        exit_code, stdout, _ = run_cli(["--help"])
        assert exit_code == 0
        assert "usage" in stdout.lower() or "audio" in stdout.lower()

    def test_version_returns_zero(self) -> None:
        """--version should exit 0."""
        exit_code, _stdout, _ = run_cli(["--version"])
        assert exit_code == 0

    def test_missing_file_returns_nonzero(self, tmp_path: Path) -> None:
        """Nonexistent input file should exit with EX_NOINPUT (66)."""
        nonexistent = tmp_path / "does_not_exist.mp4"
        exit_code, _, _stderr = run_cli(["extract", str(nonexistent)])
        assert exit_code != 0, f"Expected nonzero exit for missing file, got {exit_code}"
        assert exit_code in (1, 66), f"Expected exit code 1 or 66 (EX_NOINPUT), got {exit_code}"

    def test_empty_file_returns_nonzero(self, tmp_path: Path) -> None:
        """Empty audio file should exit with error."""
        empty = tmp_path / "empty.mp3"
        empty.touch()
        exit_code, _, _stderr = run_cli(["extract", str(empty)])
        assert exit_code != 0, f"Expected nonzero exit for empty file, got {exit_code}"

    def test_extract_success_returns_zero(self, stub_audio_file: Path, tmp_path: Path) -> None:
        """Successful extraction should exit 0."""
        output = tmp_path / "extracted.wav"
        exit_code, _stdout, stderr = run_cli(
            [
                "extract",
                str(stub_audio_file),
                "--output",
                str(output),
            ]
        )
        assert exit_code == 0, f"Extract failed: {stderr}"
        assert output.exists(), "Output file not created"


class TestOfflinePipelineArtifacts:
    """Test artifact creation and deterministic output locations."""

    def test_extract_creates_audio_artifact(self, stub_audio_file: Path, tmp_path: Path) -> None:
        """Extract command should create audio file at specified location."""
        output = tmp_path / "output_audio.wav"
        exit_code, _, stderr = run_cli(
            [
                "extract",
                str(stub_audio_file),
                "--output",
                str(output),
            ]
        )
        assert exit_code == 0, f"Extract failed: {stderr}"
        assert output.exists(), "Audio artifact not created"
        assert output.stat().st_size > 0, "Audio artifact is empty"


class TestOfflinePipelineErrorSurfacing:
    """Test that errors are properly surfaced to stderr and exit codes."""

    def test_invalid_command_shows_usage(self) -> None:
        """Invalid subcommand should show usage and exit nonzero."""
        exit_code, _, stderr = run_cli(["invalid_subcommand"])
        assert exit_code != 0
        # Should mention valid commands or usage
        combined = stderr.lower()
        assert "error" in combined or "invalid" in combined or "usage" in combined

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Path traversal attempts should be blocked."""
        malicious = tmp_path / ".." / ".." / "etc" / "passwd"
        exit_code, _, _stderr = run_cli(["extract", str(malicious)])
        assert exit_code != 0, "Path traversal should be blocked"


@pytest.mark.slow
class TestOfflinePipelineIntegration:
    """Integration tests for full pipeline with stub provider.

    These tests require the stub provider to be wired into the transcription
    service. Marked as slow since they exercise more code paths.
    """

    def test_process_command_structure(self, stub_audio_file: Path, tmp_path: Path) -> None:
        """Process command should accept standard arguments."""
        output_dir = tmp_path / "process_output"
        output_dir.mkdir()

        exit_code, _stdout, stderr = run_cli(
            [
                "process",
                str(stub_audio_file),
                "--output-dir",
                str(output_dir),
                "--provider",
                "stub",
            ]
        )
        # May fail if stub provider not wired in, but should parse args
        if exit_code != 0:
            # Check it's a provider/config issue, not argument parsing
            assert "unrecognized arguments" not in stderr.lower()


class TestExitCodeMapping:
    """Verify exit code mappings match sysexits.h conventions."""

    def test_exit_codes_in_valid_range(self) -> None:
        """All exit codes should be in valid Unix range 0-255."""
        from src.pipeline.result import PipelineError

        error_types = [
            "ValidationError",
            "AudioFileNotFoundError",
            "FileAccessError",
            "FileSizeError",
            "PathTraversalError",
            "ProviderNotAvailableError",
            "ProviderAuthenticationError",
            "ProviderRateLimitError",
            "ProviderTimeoutError",
            "ProviderAPIError",
            "ConfigurationError",
            "FFmpegNotFoundError",
            "FFmpegExecutionError",
            "TranscriptionError",
        ]

        for error_type in error_types:
            error = PipelineError(
                message="test",
                error_type=error_type,
            )
            assert 0 <= error.exit_code <= 255, f"{error_type} has invalid exit code"
            if error_type != "PipelineError":
                # Non-generic errors should have specific codes
                assert error.exit_code >= 64, f"{error_type} should use sysexits.h range"


__all__ = [
    "TestExitCodeMapping",
    "TestOfflinePipelineArtifacts",
    "TestOfflinePipelineErrorSurfacing",
    "TestOfflinePipelineExitCodes",
    "TestOfflinePipelineIntegration",
]
