"""Async audio extraction service using FFmpeg."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from ..utils.file_validation import safe_validate_media_file
from .audio_extraction import AudioExtractor, AudioQuality
from .ffmpeg_core import build_extract_commands

logger = logging.getLogger(__name__)


class AsyncAudioExtractor(AudioExtractor):
    """Async FFmpeg-based audio extraction service."""

    async def extract_audio_async(
        self,
        input_path: Path,
        output_path: Path | None = None,
        quality: AudioQuality = AudioQuality.SPEECH,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """Extract audio from video using specified quality preset with async progress tracking.

        Args:
            input_path: Input video file path
            output_path: Output audio file path (optional)
            quality: Audio quality preset
            progress_callback: Optional callback for progress updates (completed, total)

        Returns:
            Path to extracted audio file, or None if extraction failed
        """
        # Validate input video file (for audio extraction)
        validated_path = safe_validate_media_file(input_path, max_file_size=self.MAX_FILE_SIZE)
        if validated_path is None:
            return None
        input_path = validated_path

        # Set default output path
        if output_path is None:
            output_path = input_path.with_suffix(".mp3")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Extracting audio from {input_path} with {quality.value} quality")

        try:
            # Get video duration first for progress calculation
            duration = await self._get_video_duration(str(input_path))
            if duration is None:
                duration = 100  # Fallback estimate

            # Get video info for logging
            info = self.get_video_info(input_path)
            if info:
                logger.info(
                    f"Input video: {info.get('duration', 'unknown')} duration, "
                    f"{info.get('size_mb', 0):.2f} MB"
                )

            cmds, temp_path = build_extract_commands(input_path, output_path, quality.value)

            # Run FFmpeg command(s) with progress tracking
            stage_names = ["Extracting audio"] * len(cmds)
            if len(cmds) == 2:
                stage_names = ["Extracting audio", "Normalizing audio"]

            for cmd, stage in zip(cmds, stage_names, strict=False):
                await self._run_ffmpeg_with_progress(cmd, duration, progress_callback, stage=stage)

            # Log success
            if output_path.exists():
                final_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Successfully extracted audio: {final_size:.2f} MB")
                return output_path
            else:
                logger.error("Audio extraction completed but output file not found")
                return None

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            TimeoutError,  # Async timeout from readline() or other async operations
            FileNotFoundError,
            PermissionError,
            OSError,
            ValueError,
            RuntimeError,  # Raised by _run_ffmpeg_with_progress on non-zero return codes
        ) as e:
            # Error already logged by individual operations
            logger.error(f"Async audio extraction failed: {e}")
            return None

        finally:
            # Cleanup possible temp file from SPEECH pipeline
            try:
                if "temp_path" in locals() and temp_path and temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    async def _get_video_duration(self, video_path: str) -> float | None:
        """Get video duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration",
                video_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await proc.communicate()

            if proc.returncode == 0:
                data = json.loads(stdout.decode())
                duration = float(data.get("format", {}).get("duration", 0))
                return duration if duration > 0 else None

        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}")

        return None

    async def _run_ffmpeg_with_progress(
        self,
        ffmpeg_args: list,
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

        # Parse progress from stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            line = line.decode("utf-8").strip()

            # Parse FFmpeg progress format: "out_time_ms=12345678"
            if line.startswith("out_time_ms="):
                try:
                    time_ms = int(line.split("=")[1])
                    current_seconds = time_ms / 1_000_000  # Convert microseconds to seconds

                    if progress_callback and total_duration > 0:
                        # Calculate percentage with bounds checking
                        percentage = min(100, max(0, (current_seconds / total_duration) * 100))
                        progress_callback(int(percentage), 100)

                except (ValueError, IndexError):
                    continue

        # Wait for process completion
        await proc.wait()

        if proc.returncode != 0:
            stderr = await proc.stderr.read()
            raise RuntimeError(f"FFmpeg failed with code {proc.returncode}: {stderr.decode()}")
