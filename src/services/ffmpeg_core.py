"""Shared FFmpeg helpers for sync and async extractors.

This module centralizes command construction and common behaviors to
reduce duplication between `audio_extraction.py` and `audio_extraction_async.py`.
"""

from __future__ import annotations

from pathlib import Path


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
