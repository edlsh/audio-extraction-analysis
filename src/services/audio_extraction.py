"""Audio extraction service using FFmpeg (sync and async)."""

from __future__ import annotations

import asyncio
import subprocess
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import get_config
from src.utils.logger import get_logger

from ..exceptions import (
    AudioExtractionError,
    AudioExtractionTimeoutError,
    AudioFileCorruptedError,
    FFmpegExecutionError,
    ValidationError,
)
from ..utils.constants import MediaLimits, Timeouts
from ..utils.file_validation import FileValidator
from ..utils.sanitization import PathSanitizer
from .ffmpeg_core import (
    MediaProbeResult,
    build_extract_commands,
    check_ffmpeg_available,
    cleanup_temp_file,
    prepare_extraction_paths,
    probe_media_async,
    probe_media_sync,
    verify_extraction_output,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class AudioQuality(Enum):
    """Audio quality presets for extraction."""

    HIGH = "high"
    STANDARD = "standard"
    SPEECH = "speech"
    COMPRESSED = "compressed"


class AudioExtractor:
    """FFmpeg-based audio extraction service (sync)."""

    ALLOWED_EXTENSIONS = MediaLimits.get_allowed_extensions()
    MAX_FILE_SIZE = MediaLimits.MAX_FILE_SIZE_BYTES

    def __init__(self) -> None:
        check_ffmpeg_available()
        self._config = get_config()

    def _get_timeout_seconds(self) -> int:
        return self._config.ffmpeg_timeout_seconds

    def _get_terminate_grace_seconds(self) -> int:
        return self._config.ffmpeg_terminate_grace_seconds

    def _validate_path(self, file_path: Path) -> None:
        FileValidator.validate_file_path(
            file_path,
            must_exist=True,
            allowed_extensions=self.ALLOWED_EXTENSIONS,
            max_size=self.MAX_FILE_SIZE,
        )
        PathSanitizer.validate_path_security(file_path)

    def get_video_info(self, input_path: Path) -> dict[str, Any]:
        """Get video/audio file information using ffprobe."""
        try:
            self._validate_path(input_path)
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
        except (FileNotFoundError, ValueError, PermissionError, OSError) as e:
            logger.warning(f"Could not get video info: {e}")
            raise AudioExtractionError(
                f"Failed to access media file {input_path}",
                context={"error": str(e), "input_path": str(input_path)},
            ) from e

    def extract_audio(
        self,
        input_path: Path,
        output_path: Path | None = None,
        quality: AudioQuality = AudioQuality.SPEECH,
    ) -> Path:
        """Extract audio from video using specified quality preset."""
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
        try:
            info = self.get_video_info(input_path)
            logger.info(
                f"Input video: {info.get('duration', 'unknown')} duration, "
                f"{info.get('size_mb', 0):.2f} MB"
            )
        except AudioExtractionError:
            logger.warning(f"Could not log info for {input_path}")

    def _run_ffmpeg_commands(self, cmds: list[list[str]]) -> None:
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
                logger.warning(f"FFmpeg timed out after {timeout}s, sending SIGTERM")
                proc.terminate()
                try:
                    proc.wait(timeout=grace_period)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        f"FFmpeg didn't respond to SIGTERM after {grace_period}s, sending SIGKILL"
                    )
                    proc.kill()
                    proc.wait()
                raise

    def _timeout_error(
        self, input_path: Path, quality: AudioQuality
    ) -> AudioExtractionTimeoutError:
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
        """Extract audio with async progress tracking."""
        input_path, output_path = prepare_extraction_paths(
            input_path, output_path, max_file_size=self.MAX_FILE_SIZE
        )

        logger.info(f"Extracting audio from {input_path} with {quality.value} quality")

        temp_path = None
        try:
            probe = await probe_media_async(input_path)
            self._log_probe_info(probe, input_path)

            cmds, temp_path = build_extract_commands(input_path, output_path, quality.value)
            await self._run_extraction_stages(cmds, probe.duration or 100, progress_callback)

            return verify_extraction_output(input_path, output_path)

        except Exception as exc:
            raise self._map_extraction_error(exc, input_path, output_path) from exc

        finally:
            cleanup_temp_file(temp_path)

    def _log_probe_info(self, probe: MediaProbeResult, input_path: Path) -> None:
        duration_str = f"{probe.duration:.2f}s" if probe.duration else "unknown"
        logger.info(f"Input video: {duration_str} duration, {probe.size_mb:.2f} MB")

    async def _run_extraction_stages(
        self,
        cmds: list[list[str]],
        duration: float,
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:
        stage_names = (
            ["Extracting audio", "Normalizing audio"]
            if len(cmds) == 2
            else ["Extracting audio"] * len(cmds)
        )
        for cmd, stage in zip(cmds, stage_names, strict=False):
            await self._run_ffmpeg_with_progress(cmd, duration, progress_callback, stage=stage)

    def _map_extraction_error(
        self, exc: Exception, input_path: Path, output_path: Path
    ) -> Exception:
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

    async def _run_ffmpeg_with_progress(
        self,
        ffmpeg_args: list[str],
        total_duration: float,
        progress_callback: Callable[[int, int], None] | None,
        stage: str = "Processing",
    ) -> None:
        ffmpeg_args_with_progress = [*ffmpeg_args, "-progress", "pipe:1", "-nostats"]

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_args_with_progress,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        timed_out = False
        try:
            await asyncio.wait_for(
                self._consume_ffmpeg_progress(proc, total_duration, progress_callback, stage),
                timeout=self._ffmpeg_timeout,
            )
        except asyncio.CancelledError:
            await self._terminate_process(proc, stage)
            raise
        except TimeoutError as exc:
            timed_out = True
            await self._terminate_process(proc, stage)
            raise TimeoutError(
                f"FFmpeg stage '{stage}' timed out after {self._ffmpeg_timeout} seconds"
            ) from exc
        finally:
            if not timed_out and proc.returncode is None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=self._ffmpeg_terminate_grace)
                except TimeoutError:
                    await self._terminate_process(proc, stage)

        await self._ensure_process_succeeded(proc, stage)

    async def _consume_ffmpeg_progress(
        self,
        proc: asyncio.subprocess.Process,
        total_duration: float,
        progress_callback: Callable[[int, int], None] | None,
        stage: str,
    ) -> None:
        assert proc.stdout is not None
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
                    logger.debug(f"Failed to parse FFmpeg progress for {stage}: {line_str}")
                    continue

    async def _ensure_process_succeeded(self, proc: asyncio.subprocess.Process, stage: str) -> None:
        returncode = await proc.wait()
        if returncode != 0:
            stderr = await self._read_stream(proc.stderr)
            raise RuntimeError(f"FFmpeg stage '{stage}' failed with code {returncode}: {stderr}")

    async def _terminate_process(self, proc: asyncio.subprocess.Process, stage: str) -> None:
        if proc.returncode is not None:
            return

        logger.error(f"FFmpeg stage '{stage}' exceeded timeout; terminating")
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=self._ffmpeg_terminate_grace)
        except TimeoutError:
            logger.error(f"FFmpeg stage '{stage}' did not terminate gracefully; killing")
            proc.kill()
            await proc.wait()

        stderr = await self._read_stream(proc.stderr)
        if stderr:
            logger.error(f"FFmpeg stderr for stage '{stage}': {stderr.strip()}")

    async def _read_stream(self, stream: asyncio.StreamReader | None) -> str:
        if stream is None:
            return ""
        try:
            data = await stream.read()
        except Exception as e:
            logger.warning(f"Failed to read FFmpeg stderr stream: {e}")
            return f"[stderr read failed: {type(e).__name__}]"
        return data.decode("utf-8", errors="replace")
