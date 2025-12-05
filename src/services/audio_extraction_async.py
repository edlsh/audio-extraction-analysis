"""Async audio extraction service using FFmpeg."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from ..config import get_config
from ..exceptions import (
    AudioExtractionError,
    AudioExtractionTimeoutError,
    FFmpegExecutionError,
    ValidationError,
)
from ..utils.file_validation import safe_validate_media_file
from .audio_extraction import AudioExtractor, AudioQuality
from .ffmpeg_core import MediaProbeResult, build_extract_commands, probe_media_async

logger = logging.getLogger(__name__)


class AsyncAudioExtractor(AudioExtractor):
    """Async FFmpeg-based audio extraction service."""

    DEFAULT_TIMEOUT_SECONDS = 600.0
    DEFAULT_TERMINATION_GRACE_SECONDS = 5.0

    def __init__(
        self,
        *,
        ffmpeg_timeout: float | None = None,
        termination_grace: float | None = None,
    ) -> None:
        config = get_config()
        super().__init__()
        self._ffmpeg_timeout = float(
            ffmpeg_timeout if ffmpeg_timeout is not None else config.ffmpeg_timeout_seconds
        )
        self._ffmpeg_terminate_grace = float(
            termination_grace
            if termination_grace is not None
            else config.ffmpeg_terminate_grace_seconds
        )

    async def extract_audio_async(
        self,
        input_path: Path,
        output_path: Path | None = None,
        quality: AudioQuality = AudioQuality.SPEECH,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Extract audio from video using specified quality preset with async progress tracking.

        Args:
            input_path: Input video file path
            output_path: Output audio file path (optional)
            quality: Audio quality preset
            progress_callback: Optional callback for progress updates (completed, total)

        Returns:
            Path to extracted audio file

        Raises:
            ValidationError: If input file validation fails
            AudioExtractionTimeoutError: If extraction exceeds configured timeout
            FFmpegExecutionError: If FFmpeg returns a non-zero code
            AudioExtractionError: For other extraction failures
        """
        input_path, output_path = self._validate_and_prepare_paths(input_path, output_path)
        logger.info(f"Extracting audio from {input_path} with {quality.value} quality")

        temp_path = None
        try:
            # Single probe call for all metadata (avoids duplicate ffprobe invocations)
            probe = await probe_media_async(input_path)
            self._log_probe_info(probe, input_path)

            cmds, temp_path = build_extract_commands(input_path, output_path, quality.value)
            await self._run_extraction_stages(cmds, probe.duration or 100, progress_callback)

            return self._finalize_extraction(input_path, output_path)

        except Exception as exc:
            raise self._map_extraction_error(exc, input_path, output_path) from exc

        finally:
            self._cleanup_temp_file(temp_path)

    def _validate_and_prepare_paths(
        self, input_path: Path, output_path: Path | None
    ) -> tuple[Path, Path]:
        """Validate input and prepare output path."""
        validated_path = safe_validate_media_file(input_path, max_file_size=self.MAX_FILE_SIZE)
        if validated_path is None:
            raise ValidationError(
                f"Invalid media file: {input_path}", context={"input_path": str(input_path)}
            )

        if output_path is None:
            output_path = validated_path.with_suffix(".mp3")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        return validated_path, output_path

    def _log_probe_info(self, probe: MediaProbeResult, input_path: Path) -> None:
        """Log input video information from probe result (no subprocess call)."""
        duration_str = f"{probe.duration:.2f}s" if probe.duration else "unknown"
        logger.info(f"Input video: {duration_str} duration, {probe.size_mb:.2f} MB")

    async def _run_extraction_stages(
        self,
        cmds: list[list[str]],
        duration: float,
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:
        """Run FFmpeg extraction stages."""
        stage_names = (
            ["Extracting audio", "Normalizing audio"]
            if len(cmds) == 2
            else ["Extracting audio"] * len(cmds)
        )
        for cmd, stage in zip(cmds, stage_names, strict=False):
            await self._run_ffmpeg_with_progress(cmd, duration, progress_callback, stage=stage)

    def _finalize_extraction(self, input_path: Path, output_path: Path) -> Path:
        """Verify and log successful extraction."""
        if output_path.exists():
            final_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Successfully extracted audio: {final_size:.2f} MB")
            return output_path

        logger.error("Audio extraction completed but output file not found")
        raise AudioExtractionError(
            "FFmpeg completed but output file was not created",
            context={"input_path": str(input_path), "expected_output": str(output_path)},
        )

    def _map_extraction_error(
        self, exc: Exception, input_path: Path, output_path: Path
    ) -> Exception:
        """Map exception to appropriate AudioExtractionError subclass."""
        ctx = {"input_path": str(input_path), "output_path": str(output_path)}

        if isinstance(exc, (subprocess.TimeoutExpired, asyncio.TimeoutError, TimeoutError)):
            return AudioExtractionTimeoutError(
                f"Audio extraction timed out after {self._ffmpeg_timeout}s",
                context={**ctx, "timeout": self._ffmpeg_timeout},
                original_error=exc,
            )
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = exc.stderr if hasattr(exc, "stderr") else None
            return FFmpegExecutionError(
                f"FFmpeg failed with exit code {exc.returncode}",
                context={
                    **ctx,
                    "return_code": exc.returncode,
                    "stderr": stderr[:500] if stderr else None,
                },
                original_error=exc,
            )
        if isinstance(exc, RuntimeError):
            return FFmpegExecutionError(
                "FFmpeg reported failure during processing", context=ctx, original_error=exc
            )
        if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
            return AudioExtractionError(
                f"File system error during audio extraction: {exc}",
                context={**ctx, "error_type": type(exc).__name__},
                original_error=exc,
            )
        if isinstance(exc, ValueError):
            return ValidationError(str(exc), context={"input_path": str(input_path)})
        if isinstance(exc, (ValidationError, AudioExtractionError)):
            return exc
        return AudioExtractionError(
            "Unexpected error during async audio extraction", context=ctx, original_error=exc
        )

    def _cleanup_temp_file(self, temp_path: Path | None) -> None:
        """Clean up temporary file if it exists."""
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as exc:
                logger.warning("Failed to clean up temp file %s: %s", temp_path, exc)

    async def _run_ffmpeg_with_progress(
        self,
        ffmpeg_args: list[str],
        total_duration: float,
        progress_callback: Callable[[int, int], None] | None,
        stage: str = "Processing",
    ) -> None:
        """Run FFmpeg and parse progress output."""
        # Add progress reporting to FFmpeg
        ffmpeg_args_with_progress = [*ffmpeg_args, "-progress", "pipe:1", "-nostats"]

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_args_with_progress,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            await asyncio.wait_for(
                self._consume_ffmpeg_progress(proc, total_duration, progress_callback, stage),
                timeout=self._ffmpeg_timeout,
            )
        except TimeoutError as exc:
            await self._terminate_process(proc, stage)
            raise TimeoutError(
                f"FFmpeg stage '{stage}' timed out after {self._ffmpeg_timeout} seconds"
            ) from exc

        await self._ensure_process_succeeded(proc, stage)

    async def _consume_ffmpeg_progress(
        self,
        proc: asyncio.subprocess.Process,
        total_duration: float,
        progress_callback: Callable[[int, int], None] | None,
        stage: str,
    ) -> None:
        assert proc.stdout is not None, "stdout should be PIPE"
        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()

            if line_str.startswith("out_time_ms="):
                try:
                    parts = line_str.split("=")
                    if len(parts) >= 2:
                        time_ms = int(parts[1])
                        current_seconds = time_ms / 1_000_000
                        if progress_callback and total_duration > 0:
                            percentage = min(100, max(0, (current_seconds / total_duration) * 100))
                            progress_callback(int(percentage), 100)
                except (ValueError, IndexError):
                    logger.debug(
                        "Failed to parse FFmpeg progress line for stage %s: %s", stage, line_str
                    )
                    continue

    async def _ensure_process_succeeded(self, proc: asyncio.subprocess.Process, stage: str) -> None:
        returncode = await proc.wait()
        if returncode != 0:
            stderr = await self._read_stream(proc.stderr)
            raise RuntimeError(f"FFmpeg stage '{stage}' failed with code {returncode}: {stderr}")

    async def _terminate_process(self, proc: asyncio.subprocess.Process, stage: str) -> None:
        if proc.returncode is not None:
            return

        logger.error(
            "FFmpeg stage '%s' exceeded timeout of %.2fs; terminating process",
            stage,
            self._ffmpeg_timeout,
        )
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=self._ffmpeg_terminate_grace)
        except TimeoutError:
            logger.error(
                "FFmpeg stage '%s' did not terminate gracefully; killing process",
                stage,
            )
            proc.kill()
            await proc.wait()

        stderr = await self._read_stream(proc.stderr)
        if stderr:
            logger.error("FFmpeg stderr for stage '%s': %s", stage, stderr.strip())

    async def _read_stream(self, stream: asyncio.StreamReader | None) -> str:
        if stream is None:
            return ""
        try:
            data = await stream.read()
        except Exception:
            return ""
        return data.decode("utf-8", errors="replace")
