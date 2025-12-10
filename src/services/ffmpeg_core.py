"""Shared FFmpeg helpers for sync and async extractors.

This module centralizes command construction and common behaviors to
reduce duplication between `audio_extraction.py` and `audio_extraction_async.py`.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    pass

from ..exceptions import (
    AudioExtractionError,
    FFmpegNotFoundError,
)
from ..utils.constants import MediaLimits, Timeouts
from ..utils.file_validation import safe_validate_media_file, validate_media_file_or_raise

logger = get_logger(__name__)


# =============================================================================
# Media Probing
# =============================================================================


@dataclass
class MediaProbeResult:
    """Result of probing a media file with ffprobe.

    Consolidates all metadata needed by extraction and transcription
    to avoid multiple ffprobe subprocess calls.
    """

    duration: float | None
    """Duration in seconds, or None if unavailable."""

    size_bytes: int
    """File size in bytes."""

    size_mb: float
    """File size in megabytes."""


def probe_media_sync(path: Path, timeout: float = 30.0) -> MediaProbeResult:
    """Probe media file synchronously using ffprobe.

    Single ffprobe call to get all needed metadata. Use this instead of
    calling ffprobe multiple times for duration and info separately.

    Args:
        path: Path to the media file
        timeout: Timeout in seconds for ffprobe subprocess

    Returns:
        MediaProbeResult with duration and file size info

    Raises:
        FileNotFoundError: If file doesn't exist
        subprocess.TimeoutExpired: If ffprobe times out
    """
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {path}")

    file_size = path.stat().st_size
    duration = None

    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration",
            str(path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            raw_duration = data.get("format", {}).get("duration")
            if raw_duration:
                duration = float(raw_duration)
                if duration <= 0:
                    duration = None

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.debug(f"Failed to parse ffprobe output: {e}")
    except FileNotFoundError:
        logger.warning("ffprobe not found in PATH - duration extraction will be unavailable")
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out after {timeout}s - duration may be unavailable")

    return MediaProbeResult(
        duration=duration,
        size_bytes=file_size,
        size_mb=file_size / (1024 * 1024),
    )


async def probe_media_async(path: Path, timeout: float = 30.0) -> MediaProbeResult:
    """Probe media file asynchronously using ffprobe.

    Single ffprobe call to get all needed metadata. Use this instead of
    calling ffprobe multiple times for duration and info separately.

    Args:
        path: Path to the media file
        timeout: Timeout in seconds for ffprobe subprocess

    Returns:
        MediaProbeResult with duration and file size info

    Raises:
        FileNotFoundError: If file doesn't exist
        asyncio.TimeoutError: If ffprobe times out
    """
    if not path.exists():
        raise FileNotFoundError(f"Media file not found: {path}")

    file_size = path.stat().st_size
    duration = None

    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning(f"ffprobe timed out after {timeout}s - duration may be unavailable")
            stdout = b""

        if proc.returncode == 0 and stdout:
            data = json.loads(stdout.decode())
            raw_duration = data.get("format", {}).get("duration")
            if raw_duration:
                duration = float(raw_duration)
                if duration <= 0:
                    duration = None

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.debug(f"Failed to parse ffprobe output: {e}")
    except FileNotFoundError:
        logger.warning("ffprobe not found in PATH - duration extraction will be unavailable")

    return MediaProbeResult(
        duration=duration,
        size_bytes=file_size,
        size_mb=file_size / (1024 * 1024),
    )


# =============================================================================
# FFmpeg Availability Check
# =============================================================================


def check_ffmpeg_available(timeout: float | None = None) -> None:
    """Check if FFmpeg is available in PATH.

    Args:
        timeout: Timeout in seconds for the version check (default: from constants)

    Raises:
        FFmpegNotFoundError: If FFmpeg is not installed or not accessible
    """
    check_timeout = timeout if timeout is not None else Timeouts.FFMPEG_VERSION_CHECK
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=check_timeout,
        )
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg check failed")
        raise FFmpegNotFoundError(
            "FFmpeg is required but not installed or not accessible",
            context={"check_type": "version"},
        ) from e
    except FileNotFoundError as e:
        logger.error("FFmpeg is not installed or not in PATH")
        raise FFmpegNotFoundError(
            "FFmpeg not found in PATH", context={"error": "not_in_path"}
        ) from e
    except subprocess.TimeoutExpired as e:
        logger.error(f"FFmpeg version check timed out after {check_timeout}s")
        raise FFmpegNotFoundError(
            "FFmpeg version check timed out",
            context={"timeout": check_timeout},
        ) from e


# =============================================================================
# Path Preparation & Output Verification
# =============================================================================


def prepare_extraction_paths(
    input_path: Path,
    output_path: Path | None,
    max_file_size: int = MediaLimits.MAX_FILE_SIZE_BYTES,
    default_suffix: str = ".mp3",
) -> tuple[Path, Path]:
    """Validate input file and prepare output path for extraction.

    Args:
        input_path: Path to the input media file
        output_path: Optional path for output file (auto-generated if None)
        max_file_size: Maximum allowed file size in bytes
        default_suffix: Default suffix for auto-generated output path

    Returns:
        Tuple of (validated_input_path, output_path)

    Raises:
        ValidationError: If input file validation fails
    """
    validated_path = validate_media_file_or_raise(input_path, max_file_size=max_file_size)

    if output_path is None:
        output_path = validated_path.with_suffix(default_suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    return validated_path, output_path


def verify_extraction_output(
    input_path: Path,
    output_path: Path,
    log_success: bool = True,
) -> Path:
    """Verify extraction output file exists and log success.

    Args:
        input_path: Original input path (for error context)
        output_path: Expected output file path
        log_success: Whether to log successful extraction with file size

    Returns:
        The output_path if file exists

    Raises:
        AudioExtractionError: If output file was not created
    """
    if not output_path.exists():
        logger.error("Audio extraction completed but output file not found")
        raise AudioExtractionError(
            f"FFmpeg completed but output file not found: {output_path.name}",
            context={"input_path": str(input_path), "expected_output": str(output_path)},
        )

    if log_success:
        final_size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Successfully extracted audio: {final_size:.2f} MB")

    return output_path


# =============================================================================
# Path Validation & Sanitization
# =============================================================================


def validate_path_security(file_path: Path) -> None:
    """Validate file path for security concerns.

    Checks for dangerous shell characters that could enable command injection.
    Note: Square brackets [], parentheses (), and spaces are common in media
    filenames and are safe when properly quoted with shlex.quote().

    Args:
        file_path: Path to validate

    Raises:
        ValueError: If path contains dangerous shell characters
    """
    resolved_path = file_path.resolve()
    path_str = str(resolved_path)

    # Check for dangerous shell metacharacters
    if re.search(r"[;&|`$<>]", path_str):
        raise ValueError(f"Invalid characters in file path: {file_path}")


def sanitize_path(file_path: Path) -> str:
    """Sanitize file path for safe subprocess usage.

    Args:
        file_path: Path to sanitize

    Returns:
        Safely quoted path string for shell usage
    """
    return shlex.quote(str(file_path.resolve()))


# =============================================================================
# Temp File Cleanup
# =============================================================================


def cleanup_temp_file(temp_path: Path | None) -> None:
    """Clean up temporary file if it exists.

    Args:
        temp_path: Path to temporary file, or None
    """
    if temp_path and temp_path.exists():
        try:
            temp_path.unlink()
            logger.debug(f"Cleaned up temp file: {temp_path}")
        except OSError as e:
            logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


# =============================================================================
# FFmpeg Command Building
# =============================================================================


def build_base_cmd(input_path: Path, allow_overwrite: bool = True) -> list[str]:
    """Build the base ffmpeg command with input file.

    Args:
        input_path: Path to the input media file to process.
        allow_overwrite: If True, add "-y" flag to enable automatic overwrite
                        of existing output files. Default is True to prevent
                        interactive prompts that could cause hangs.

    Returns:
        List of command arguments: ["ffmpeg", "-y", "-i", <input_path>]
        with "-y" flag by default to enable automatic overwrite.
    """
    cmd = ["ffmpeg"]
    if allow_overwrite:
        cmd.append("-y")
    cmd.extend(["-i", str(input_path)])
    return cmd


def build_extract_commands(
    input_path: Path, output_path: Path, quality: str, allow_overwrite: bool = True
) -> tuple[list[list[str]], Path | None]:
    """Build ffmpeg command(s) for audio extraction based on quality preset.

    Args:
        input_path: Path to the input media file.
        output_path: Path where the extracted audio should be saved.
        quality: Quality preset string. Valid values:
            - "high": 320kbps bitrate, high quality stereo
            - "standard": Variable bitrate (VBR) quality 0, balanced quality
            - "compressed": 128kbps bitrate, smaller file size
            - "speech" (default): Two-step process with normalization and mono conversion
        allow_overwrite: If True, add "-y" flag to enable automatic file overwrite.
                        Default is True for backward compatibility.

    Returns:
        A tuple of (commands, temp_path) where:
            - commands: List of ffmpeg command lists to execute sequentially
            - temp_path: Path to temporary file for SPEECH quality (requires cleanup),
                        None for other quality presets

    Notes:
        - SPEECH quality uses a two-step pipeline:
          1. Extract audio with VBR quality 0
          2. Normalize loudness (I=-16 LUFS, TP=-1.5 dB, LRA=11 LU) and convert to mono
        - Commands optionally include "-y" flag based on allow_overwrite parameter
        - The "-map a" flag selects all audio streams from the input
    """
    base = build_base_cmd(input_path, allow_overwrite=allow_overwrite)

    if quality == "high":
        extract = [*base, "-b:a", "320k", "-map", "a", str(output_path)]
        return [extract], None

    if quality == "standard":
        extract = [*base, "-q:a", "0", "-map", "a", str(output_path)]
        return [extract], None

    if quality == "compressed":
        extract = [*base, "-b:a", "128k", "-map", "a", str(output_path)]
        return [extract], None

    # Default to SPEECH behavior: two-step process for optimal voice clarity
    temp_path = output_path.with_suffix(".temp.mp3")
    # Step 1: Extract audio at high quality to temporary file
    extract = [*base, "-q:a", "0", "-map", "a", str(temp_path)]
    # Step 2: Apply loudness normalization and convert to mono for speech optimization
    normalize_cmd = ["ffmpeg", "-i", str(temp_path)]
    if allow_overwrite:
        normalize_cmd.append("-y")
    normalize_cmd.extend(
        [
            "-ac",
            "1",  # Convert to mono (single audio channel)
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",  # EBU R128 loudness normalization
            str(output_path),
        ]
    )
    return [extract, normalize_cmd], temp_path
