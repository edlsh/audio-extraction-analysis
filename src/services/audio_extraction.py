"""Audio extraction service using FFmpeg."""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

from ..exceptions import (
    AudioExtractionError,
    AudioExtractionTimeoutError,
    AudioFileCorruptedError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
)
from ..utils.file_validation import FileValidator, safe_validate_media_file
from .ffmpeg_core import build_extract_commands

logger = logging.getLogger(__name__)


class AudioQuality(Enum):
    """Audio quality presets for extraction."""

    HIGH = "high"  # 320k bitrate - Best for archival
    STANDARD = "standard"  # Variable bitrate - Good balance
    SPEECH = "speech"  # Mono, normalized - Best for transcription
    COMPRESSED = "compressed"  # 128k - Smaller file size


class AudioExtractor:
    """FFmpeg-based audio extraction service."""

    # Security: Define allowed file extensions and maximum file size
    ALLOWED_EXTENSIONS = {
        # Video formats
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".flv",
        ".wmv",
        ".m4v",
        ".3gp",
        # Audio formats
        ".mp3",
        ".wav",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".wma",
        ".opus",
    }
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit

    def __init__(self) -> None:
        self._check_ffmpeg()

    def _validate_path(self, file_path: Path) -> None:
        """Validate file path for security.

        Args:
            file_path: Path to validate

        Raises:
            ValueError: If path is invalid or potentially dangerous
        """
        # Delegate to common validation utility
        FileValidator.validate_file_path(
            file_path,
            must_exist=True,
            allowed_extensions=self.ALLOWED_EXTENSIONS,
            max_size=self.MAX_FILE_SIZE,
        )

        # Security: Check for path traversal attempts
        resolved_path = file_path.resolve()
        if ".." in str(resolved_path) or str(resolved_path).startswith("/"):
            # Allow absolute paths but validate they don't contain dangerous shell characters
            # Note: Square brackets [], parentheses (), and spaces are common in media filenames
            # and are safe when properly quoted with shlex.quote()
            path_str = str(resolved_path)
            if re.search(r"[;&|`$<>]", path_str):
                raise ValueError(f"Invalid characters in file path: {file_path}")

    def _sanitize_path(self, file_path: Path) -> str:
        """Sanitize file path for safe subprocess usage.

        Args:
            file_path: Path to sanitize

        Returns:
            Safely quoted path string
        """
        return shlex.quote(str(file_path.resolve()))

    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is available.

        Raises:
            FFmpegNotFoundError: If FFmpeg is not installed or not accessible
        """
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=10)
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
            logger.error("FFmpeg version check timed out")
            raise FFmpegNotFoundError(
                "FFmpeg version check timed out", context={"timeout": 10}
            ) from e

    def get_video_info(self, input_path: Path) -> dict[str, Any]:
        """Get video/audio file information using ffprobe."""
        try:
            # Security: Validate input path
            self._validate_path(input_path)

            # Use ffprobe to extract media information
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

            # Parse duration from ffprobe output
            duration = None
            if result.stdout.strip():
                try:
                    duration = float(result.stdout.strip())
                except ValueError:
                    logger.warning(f"Could not parse duration: {result.stdout}")

            file_size = input_path.stat().st_size

            return {
                "duration": duration,
                "size_bytes": file_size,
                "size_mb": file_size / (1024 * 1024),
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"FFmpeg failed to get video info: {e}")
            return {}
        except (FileNotFoundError, ValueError, PermissionError) as e:
            logger.warning(f"Could not get video info: {e}")
            return {}
        except OSError as e:
            logger.warning(f"System error getting video info: {e}")
            return {}

    def extract_audio(
        self,
        input_path: Path,
        output_path: Path | None = None,
        quality: AudioQuality = AudioQuality.SPEECH,
    ) -> Path:
        """Extract audio from video using specified quality preset.

        Args:
            input_path: Input video file path
            output_path: Output audio file path (optional)
            quality: Audio quality preset

        Returns:
            Path to extracted audio file

        Raises:
            AudioExtractionTimeoutError: If extraction exceeds timeout (600s)
            FFmpegNotFoundError: If FFmpeg is not installed
            FFmpegExecutionError: If FFmpeg execution fails
            AudioFileCorruptedError: If input file is corrupted
            AudioExtractionError: For other extraction failures
        """
        input_path, output_path = self._prepare_extraction_paths(input_path, output_path)
        logger.info(f"Extracting audio from {input_path} with {quality.value} quality")

        temp_path = None
        try:
            self._log_input_info(input_path)
            cmds, temp_path = build_extract_commands(input_path, output_path, quality.value)
            self._run_ffmpeg_commands(cmds)
            return self._verify_output(input_path, output_path)

        except subprocess.TimeoutExpired as e:
            raise self._timeout_error(input_path, quality) from e
        except subprocess.CalledProcessError as e:
            raise self._process_ffmpeg_error(e, input_path, output_path, quality) from e
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"File system error during extraction: {e}")
            raise AudioExtractionError(
                f"File system error during audio extraction: {e}",
                context={"input_path": str(input_path), "error_type": type(e).__name__},
            ) from e
        finally:
            self._cleanup_temp_file(temp_path)

    def _prepare_extraction_paths(
        self, input_path: Path, output_path: Path | None
    ) -> tuple[Path, Path]:
        """Validate input and prepare output path."""
        validated_path = safe_validate_media_file(input_path, max_file_size=self.MAX_FILE_SIZE)
        if validated_path is None:
            raise ValueError(f"Invalid media file: {input_path}")

        if output_path is None:
            output_path = validated_path.with_suffix(".mp3")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        return validated_path, output_path

    def _log_input_info(self, input_path: Path) -> None:
        """Log input video information."""
        info = self.get_video_info(input_path)
        if info:
            logger.info(
                f"Input video: {info.get('duration', 'unknown')} duration, "
                f"{info.get('size_mb', 0):.2f} MB"
            )

    def _run_ffmpeg_commands(self, cmds: list[list[str]]) -> None:
        """Run FFmpeg commands sequentially."""
        for cmd in cmds:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)

    def _verify_output(self, input_path: Path, output_path: Path) -> Path:
        """Verify output file was created and log success."""
        if not output_path.exists():
            logger.error("Audio extraction completed but output file not found")
            raise AudioExtractionError(
                f"FFmpeg completed but output file not found: {output_path.name}",
                context={"input_path": str(input_path), "expected_output": str(output_path)},
            )

        final_size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Successfully extracted audio: {final_size:.2f} MB")
        return output_path

    def _timeout_error(self, input_path: Path, quality: AudioQuality) -> AudioExtractionTimeoutError:
        """Create timeout error."""
        logger.error("Audio extraction timed out after 600s")
        return AudioExtractionTimeoutError(
            f"Audio extraction timed out after 600s for {input_path.name}",
            context={"input_path": str(input_path), "timeout": 600, "quality": quality.value},
        )

    def _process_ffmpeg_error(
        self, e: subprocess.CalledProcessError, input_path: Path, output_path: Path, quality: AudioQuality
    ) -> Exception:
        """Process FFmpeg error and return appropriate exception."""
        stderr = e.stderr if hasattr(e, "stderr") else str(e)
        logger.error(f"FFmpeg execution failed: {stderr}")

        if stderr and ("Invalid data" in stderr or "corrupt" in stderr.lower()):
            return AudioFileCorruptedError(
                f"Input file appears corrupted: {input_path.name}",
                context={
                    "input_path": str(input_path),
                    "ffmpeg_stderr": stderr[:500] if stderr else None,
                    "return_code": e.returncode,
                },
            )

        return FFmpegExecutionError(
            f"FFmpeg failed to extract audio from {input_path.name}",
            context={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "return_code": e.returncode,
                "stderr": stderr[:500] if stderr else None,
                "quality": quality.value,
            },
        )

    def _cleanup_temp_file(self, temp_path: Path | None) -> None:
        """Clean up temporary file if it exists."""
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                logger.debug(f"Cleaned up temp file: {temp_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")

