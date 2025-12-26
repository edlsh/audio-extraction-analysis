"""Shared FFmpeg helpers for sync and async extractors.

This module centralizes command construction and common behaviors to
reduce duplication between `audio_extraction.py` and `audio_extraction_async.py`.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    pass

from ..exceptions import (
    AudioExtractionError,
    FFmpegNotFoundError,
)
from ..utils.constants import Limits, MediaLimits, Timeouts
from ..utils.file_validation import validate_media_file_or_raise

logger = get_logger(__name__)


# =============================================================================
# Probe Cache
# =============================================================================


# Cache TTL - invalidate after this many seconds
_PROBE_CACHE_TTL = 60.0


@dataclass
class _CachedProbe:
    """Cached probe result with metadata for invalidation."""

    result: MediaProbeResult
    mtime: float
    cached_at: float = field(default_factory=time.time)

    def is_valid(self, current_mtime: float) -> bool:
        """Check if cache entry is still valid."""
        # Invalidate if file was modified or cache expired
        if current_mtime != self.mtime:
            return False
        if (time.time() - self.cached_at) > Limits.PROBE_CACHE_TTL:
            return False
        return True


class _ProbeCache:
    """Thread-safe cache for FFprobe results.

    Caches results by file path and modification time to avoid
    redundant subprocess calls within a pipeline run.
    """

    def __init__(self) -> None:
        self._cache: dict[str, _CachedProbe] = {}
        self._lock = threading.Lock()

    def get(self, path: Path) -> MediaProbeResult | None:
        """Get cached probe result if still valid."""
        key = str(path.resolve())
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            try:
                current_mtime = path.stat().st_mtime
            except OSError:
                # File might have been deleted
                del self._cache[key]
                return None

            if entry.is_valid(current_mtime):
                logger.debug(f"Probe cache hit for {path.name}")
                return entry.result

            # Cache invalid - remove it
            del self._cache[key]
            return None

    def put(self, path: Path, result: MediaProbeResult) -> None:
        """Store probe result in cache."""
        key = str(path.resolve())
        try:
            mtime = path.stat().st_mtime
        except OSError:
            # Can't cache without mtime
            return

        with self._lock:
            self._cache[key] = _CachedProbe(result=result, mtime=mtime)
            logger.debug(f"Cached probe result for {path.name}")

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()


# Module-level probe cache instance
_probe_cache = _ProbeCache()


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

    Results are cached by file path and modification time to avoid
    redundant subprocess calls within a pipeline run.

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

    # Check cache first
    cached = _probe_cache.get(path)
    if cached is not None:
        return cached

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

    probe_result = MediaProbeResult(
        duration=duration,
        size_bytes=file_size,
        size_mb=file_size / (1024 * 1024),
    )

    # Cache the result
    _probe_cache.put(path, probe_result)

    return probe_result


async def probe_media_async(path: Path, timeout: float = 30.0) -> MediaProbeResult:
    """Probe media file asynchronously using ffprobe.

    Single ffprobe call to get all needed metadata. Use this instead of
    calling ffprobe multiple times for duration and info separately.

    Results are cached by file path and modification time to avoid
    redundant subprocess calls within a pipeline run.

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

    # Check cache first
    cached = _probe_cache.get(path)
    if cached is not None:
        return cached

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
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
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

    probe_result = MediaProbeResult(
        duration=duration,
        size_bytes=file_size,
        size_mb=file_size / (1024 * 1024),
    )

    # Cache the result
    _probe_cache.put(path, probe_result)

    return probe_result


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

    DEPRECATED: Use PathSanitizer.validate_path_security from src.utils.sanitization
    for consistency across the codebase.

    Checks for dangerous shell characters that could enable command injection.
    Note: Square brackets [], parentheses (), and spaces are common in media
    filenames and are safe when properly quoted with shlex.quote().

    Args:
        file_path: Path to validate

    Raises:
        ValueError: If path contains dangerous shell characters
    """
    # Delegate to canonical implementation for consistency
    from ..utils.sanitization import PathSanitizer

    PathSanitizer.validate_path_security(file_path)


def sanitize_path(file_path: Path) -> str:
    """Sanitize file path for safe subprocess usage.

    DEPRECATED: Use PathSanitizer.sanitize_for_subprocess from src.utils.sanitization
    for consistency across the codebase.

    Args:
        file_path: Path to sanitize

    Returns:
        Safely quoted path string for shell usage
    """
    # Delegate to canonical implementation
    from ..utils.sanitization import PathSanitizer

    return PathSanitizer.sanitize_for_subprocess(file_path)


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
