"""Audio extraction service using FFmpeg."""

from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

from src.config import get_config
from src.utils.logger import get_logger

from ..exceptions import (
    AudioExtractionError,
    AudioExtractionTimeoutError,
    AudioFileCorruptedError,
    FFmpegExecutionError,
)
from ..utils.constants import MediaLimits, Timeouts
from ..utils.file_validation import FileValidator
from .ffmpeg_core import (
    build_extract_commands,
    check_ffmpeg_available,
    cleanup_temp_file,
    prepare_extraction_paths,
    probe_media_sync,
    validate_path_security,
    verify_extraction_output,
)

logger = get_logger(__name__)


class AudioQuality(Enum):
    """Audio quality presets for extraction."""

    HIGH = "high"  # 320k bitrate - Best for archival
    STANDARD = "standard"  # Variable bitrate - Good balance
    SPEECH = "speech"  # Mono, normalized - Best for transcription
    COMPRESSED = "compressed"  # 128k - Smaller file size


class AudioExtractor:
    """FFmpeg-based audio extraction service."""

    # Security: Define allowed file extensions and maximum file size
    ALLOWED_EXTENSIONS = MediaLimits.get_allowed_extensions()
    MAX_FILE_SIZE = MediaLimits.MAX_FILE_SIZE_BYTES

    def __init__(self) -> None:
        check_ffmpeg_available()
        self._config = get_config()

    def _get_timeout_seconds(self) -> int:
        """Get FFmpeg extraction timeout from config.

        Returns:
            Timeout in seconds, from config or fallback to constants.
        """
        return self._config.ffmpeg_timeout_seconds

    def _get_terminate_grace_seconds(self) -> int:
        """Get FFmpeg terminate grace period from config.

        Returns:
            Grace period in seconds before SIGKILL.
        """
        return self._config.ffmpeg_terminate_grace_seconds

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

        # Security: Check for dangerous shell characters
        validate_path_security(file_path)

    def get_video_info(self, input_path: Path) -> dict[str, Any]:
        """Get video/audio file information using ffprobe.

        Args:
            input_path: Path to media file.

        Returns:
            Dictionary with 'duration' (float), 'size_bytes' (int), 'size_mb' (float).

        Raises:
            AudioExtractionError: If file info cannot be retrieved or parsed.
        """
        try:
            # Security: Validate input path
            self._validate_path(input_path)

            # Use shared probe function
            probe = probe_media_sync(input_path, timeout=Timeouts.FFMPEG_PROBE)
            return {
                "duration": probe.duration,
                "size_bytes": probe.size_bytes,
                "size_mb": probe.size_mb,
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"FFmpeg failed to get video info: {e}")
            raise AudioExtractionError(
                f"Failed to retrieve media info for {input_path}",
                context={"error": str(e), "input_path": str(input_path)},
            ) from e
        except (FileNotFoundError, ValueError, PermissionError) as e:
            logger.warning(f"Could not get video info: {e}")
            raise AudioExtractionError(
                f"Failed to access media file {input_path}",
                context={"error": str(e), "input_path": str(input_path)},
            ) from e
        except OSError as e:
            logger.warning(f"System error getting video info: {e}")
            raise AudioExtractionError(
                f"System error accessing media file {input_path}",
                context={"error": str(e), "input_path": str(input_path)},
            ) from e

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
            ValidationError: If input file validation fails (missing, invalid, too large)
            AudioExtractionTimeoutError: If extraction exceeds configured timeout
            FFmpegExecutionError: If FFmpeg execution fails
            AudioFileCorruptedError: If input file is corrupted
            AudioExtractionError: For other extraction failures
        """
        input_path, output_path = prepare_extraction_paths(
            input_path, output_path, max_file_size=self.MAX_FILE_SIZE
        )
        logger.info(f"Extracting audio from {input_path} with {quality.value} quality")

        temp_path = None
        try:
            self._log_input_info(input_path)
            cmds, temp_path = build_extract_commands(input_path, output_path, quality.value)
            self._run_ffmpeg_commands(cmds)
            return verify_extraction_output(input_path, output_path)

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
            cleanup_temp_file(temp_path)

    def _log_input_info(self, input_path: Path) -> None:
        """Log input video information."""
        try:
            info = self.get_video_info(input_path)
            logger.info(
                f"Input video: {info.get('duration', 'unknown')} duration, "
                f"{info.get('size_mb', 0):.2f} MB"
            )
        except AudioExtractionError:
            # Non-critical logging failure
            logger.warning(f"Could not log info for {input_path}")

    def _run_ffmpeg_commands(self, cmds: list[list[str]]) -> None:
        """Run FFmpeg commands sequentially with configurable timeout and termination handling.

        Uses config-based timeout and implements graceful termination:
        1. Send SIGTERM and wait for grace period
        2. Send SIGKILL if process doesn't terminate
        """
        timeout = self._get_timeout_seconds()
        grace_period = self._get_terminate_grace_seconds()

        for cmd in cmds:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, cmd, stdout, stderr)
            except subprocess.TimeoutExpired:
                # Graceful termination: SIGTERM first
                logger.warning(f"FFmpeg timed out after {timeout}s, sending SIGTERM")
                proc.terminate()
                try:
                    proc.wait(timeout=grace_period)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    logger.warning(
                        f"FFmpeg didn't respond to SIGTERM after {grace_period}s, sending SIGKILL"
                    )
                    proc.kill()
                    proc.wait()
                raise

    def _timeout_error(
        self, input_path: Path, quality: AudioQuality
    ) -> AudioExtractionTimeoutError:
        """Create timeout error."""
        timeout = self._get_timeout_seconds()
        logger.error(f"Audio extraction timed out after {timeout}s")
        return AudioExtractionTimeoutError(
            f"Audio extraction timed out after {timeout}s for {input_path.name}",
            context={"input_path": str(input_path), "timeout": timeout, "quality": quality.value},
        )

    def _process_ffmpeg_error(
        self,
        e: subprocess.CalledProcessError,
        input_path: Path,
        output_path: Path,
        quality: AudioQuality,
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
