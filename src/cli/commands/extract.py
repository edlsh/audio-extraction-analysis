"""Extract command handler."""

import argparse
from src.utils.logger import get_logger
from pathlib import Path
from typing import TYPE_CHECKING

from ...error_handlers import handle_cli_error
from ...services.audio_extraction import AudioExtractor, AudioQuality
from ...ui.console import ConsoleManager
from ...utils.sanitization import PathSanitizer
from ..utils import parse_quality_preset

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = get_logger(__name__)


def create_extract_subparser(subparsers: "_SubParsersAction[argparse.ArgumentParser]") -> None:
    """Create the extract subcommand parser."""
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract audio from video files",
        description="Extract audio from video files using FFmpeg with quality presets",
    )
    extract_parser.add_argument("input_file", help="Input video file path")
    extract_parser.add_argument(
        "--output", "-o", help="Output audio file path (default: <input>.mp3)"
    )
    extract_parser.add_argument(
        "--quality",
        "-q",
        choices=["high", "standard", "speech", "compressed"],
        default="speech",
        help="Audio quality preset (default: speech)",
    )
    extract_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force overwrite of existing output file",
    )


def _validate_extract_input(input_path: Path) -> None:
    """Validate input file for extraction."""
    try:
        PathSanitizer.validate_path_security(input_path)
    except ValueError as exc:
        logger.error("Input file not found or invalid path")
        logger.debug("Path validation failure for %s: %s", input_path, exc)
        raise ValueError("Path validation failed") from exc

    allowed_suffixes = {".mp3", ".mp4", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".mkv", ".mov"}
    if input_path.suffix.lower() not in allowed_suffixes:
        logger.error("Invalid or unsupported input file type")
        logger.debug("Rejected file with suffix '%s'", input_path.suffix)
        raise ValueError(f"Unsupported file type: {input_path.suffix}")

    if not input_path.exists():
        logger.error("Input file not found or invalid path")
        logger.debug("Missing input path attempted: %s", input_path)
        raise ValueError(f"File not found: {input_path}")


def _determine_extract_output_path(input_path: Path, output_arg: str | None) -> Path:
    """Determine output path for extracted audio."""
    if output_arg:
        return Path(output_arg)
    return input_path.with_suffix(".mp3")


def _execute_audio_extraction(
    extractor: AudioExtractor,
    input_path: Path,
    output_path: Path,
    quality: AudioQuality,
    console_manager: ConsoleManager | None,
) -> Path | None:
    """Execute audio extraction with optional progress tracking."""
    if console_manager:
        with console_manager.progress_context("Extracting audio...") as progress:
            progress.update(10)
            result_path = extractor.extract_audio(input_path, output_path, quality)
            progress.update(100)
    else:
        result_path = extractor.extract_audio(input_path, output_path, quality)

    return result_path


def extract_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the extract subcommand."""
    try:
        input_path = Path(args.input_file)
        _validate_extract_input(input_path)

        output_path = _determine_extract_output_path(input_path, args.output)
        PathSanitizer.validate_path_security(output_path)

        if output_path.exists() and not args.force:
            logger.error(f"Output file already exists: {output_path}")
            return 1

        quality = parse_quality_preset(args.quality)

        extractor = AudioExtractor()

        if console_manager:
            console_manager.print_stage("Audio Extraction", "starting")

        logger.info(f"Extracting audio from {input_path} (quality: {quality.value})")

        result = _execute_audio_extraction(
            extractor, input_path, output_path, quality, console_manager
        )

        if result:
            logger.info(f"Audio extracted to: {result}")
            if console_manager:
                console_manager.print_success(f"Audio extracted to: {result}")
            return 0
        else:
            logger.error("Audio extraction failed")
            return 1

    except Exception as e:
        return handle_cli_error(e, "extract")
