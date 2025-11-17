"""Unified CLI for audio extraction and transcription analysis.

This module serves as the main entry point for the CLI with all commands
consolidated in a single file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import _SubParsersAction

    from .models.transcription import TranscriptionResult

# Backwards compatibility imports for tests
try:
    from .config import Config
    from .error_handlers import handle_cli_error, handle_keyboard_interrupt
    from .exceptions import (
        AudioAnalysisError,
        AudioExtractionError,
        FFmpegNotFoundError,
    )
    from .exceptions import ValidationError as CustomValidationError
    from .formatters.markdown_formatter import MarkdownFormatter
    from .pipeline.audio_pipeline import AudioProcessingPipeline
    from .pipeline.simple_pipeline import process_pipeline
    from .services.audio_extraction import AudioExtractor, AudioQuality
    from .services.transcription import TranscriptionService
    from .services.url_ingestion import UrlIngestionError, UrlIngestionService
    from .ui.console import ConsoleManager
    from .utils.file_validation import ValidationError, validate_audio_file
    from .utils.paths import ensure_subpath, safe_write_json, sanitize_dirname
    from .utils.sanitization import PathSanitizer
except ImportError:  # pragma: no cover - fallback for installed package layout
    from src.config import Config
    from src.error_handlers import handle_cli_error, handle_keyboard_interrupt
    from src.exceptions import (
        AudioAnalysisError,
        AudioExtractionError,
        FFmpegNotFoundError,
    )
    from src.exceptions import ValidationError as CustomValidationError
    from src.formatters.markdown_formatter import MarkdownFormatter
    from src.pipeline.audio_pipeline import AudioProcessingPipeline
    from src.pipeline.simple_pipeline import process_pipeline
    from src.services.audio_extraction import AudioExtractor, AudioQuality
    from src.services.transcription import TranscriptionService
    from src.services.url_ingestion import UrlIngestionError, UrlIngestionService
    from src.ui.console import ConsoleManager
    from src.utils.file_validation import ValidationError, validate_audio_file
    from src.utils.paths import ensure_subpath, safe_write_json, sanitize_dirname
    from src.utils.sanitization import PathSanitizer

__version__ = "2.0.0"

# Module-level constants
DEFAULT_OUTPUT_DIR = "output"

logger = logging.getLogger(__name__)


def _redact_sensitive_data(text: str) -> str:
    """Redact API keys and sensitive data from text.

    Args:
        text: Text that may contain sensitive information

    Returns:
        Text with sensitive data redacted

    Patterns redacted:
        - API key patterns (e.g., test_deepgram_key_12345)
        - Token patterns (e.g., auth_token_xyz)
        - Long alphanumeric sequences that might be keys (20+ chars)
        - Patterns containing "key" or "token" with surrounding alphanumeric chars
    """
    import re

    # Redact patterns containing "key" with surrounding characters (e.g., "test_deepgram_key_12345")
    # This catches API keys that have "key" in them
    text = re.sub(r"\b\w+[_-]?\w*key\w*[_-]?\w+\b", "[REDACTED_KEY]", text, flags=re.IGNORECASE)

    # Redact patterns containing "token" with surrounding characters
    text = re.sub(r"\b\w+[_-]?\w*token\w*[_-]?\w+\b", "[REDACTED_TOKEN]", text, flags=re.IGNORECASE)

    # Redact long alphanumeric strings (potential keys/tokens) - 15+ chars to catch more patterns
    text = re.sub(r"\b[a-zA-Z0-9_-]{15,}\b", "[REDACTED]", text)

    return text


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration based on verbosity level.

    Args:
        verbose: If True, set to DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)

    # Set specific loggers
    logging.getLogger("src").setLevel(level)


def _add_markdown_export_options(parser: argparse.ArgumentParser) -> None:
    """Add common markdown export options to a parser.

    Args:
        parser: ArgumentParser to add options to
    """
    parser.add_argument(
        "--export-markdown",
        action="store_true",
        help="Also export a formatted Markdown transcript",
    )
    parser.add_argument(
        "--md-template",
        dest="md_template",
        choices=["default", "minimal", "detailed"],
        default="default",
        help="Markdown template to use",
    )
    parser.add_argument(
        "--md-no-timestamps",
        dest="md_include_timestamps",
        action="store_false",
        help="Exclude timestamps in Markdown output",
    )
    parser.add_argument(
        "--md-no-speakers",
        dest="md_include_speakers",
        action="store_false",
        help="Exclude speaker labels in Markdown output",
    )
    parser.add_argument(
        "--md-confidence",
        dest="md_include_confidence",
        action="store_true",
        help="Include confidence field in Markdown output",
    )


def _create_extract_subparser(subparsers: _SubParsersAction[argparse.ArgumentParser]) -> None:
    """Create the extract subcommand parser.

    Args:
        subparsers: Subparsers object to add the extract parser to
    """
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


def _create_transcribe_subparser(subparsers: _SubParsersAction[argparse.ArgumentParser]) -> None:
    """Create the transcribe subcommand parser.

    Args:
        subparsers: Subparsers object to add the transcribe parser to
    """
    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio files using multiple providers",
        description="Transcribe audio with provider selection (Deepgram Nova 3, ElevenLabs)",
    )
    transcribe_parser.add_argument("audio_file", help="Input audio file path")
    transcribe_parser.add_argument(
        "--output", "-o", help="Output transcript file path (default: <audio>_transcript.txt)"
    )
    transcribe_parser.add_argument(
        "--language", "-l", default="en", help="Language code for transcription (default: en)"
    )
    transcribe_parser.add_argument(
        "--provider",
        "-p",
        choices=["deepgram", "elevenlabs", "whisper", "auto"],
        default="auto",
        help="Transcription provider to use (default: auto)",
    )
    _add_markdown_export_options(transcribe_parser)


def _create_process_subparser(subparsers: _SubParsersAction[argparse.ArgumentParser]) -> None:
    """Create the process subcommand parser.

    Args:
        subparsers: Subparsers object to add the process parser to
    """
    process_parser = subparsers.add_parser(
        "process",
        help="Full pipeline: extract audio and transcribe",
        description="Complete video-to-transcript pipeline with audio extraction and transcription",
    )
    process_parser.add_argument("video_file", nargs="?", help="Input video file path")
    process_parser.add_argument(
        "--url",
        help="Process media from a remote URL (e.g. YouTube). Mutually exclusive with local file.",
    )
    process_parser.add_argument(
        "--output-dir", "-o", help="Output directory for results (default: ./output)"
    )
    process_parser.add_argument(
        "--quality",
        "-q",
        choices=["high", "standard", "speech", "compressed"],
        default="speech",
        help="Audio quality preset (default: speech)",
    )
    process_parser.add_argument(
        "--language", "-l", default="en", help="Language code for transcription (default: en)"
    )
    process_parser.add_argument(
        "--provider",
        "-p",
        choices=["deepgram", "elevenlabs", "whisper", "auto"],
        default="auto",
        help="Transcription provider to use (default: auto)",
    )
    process_parser.add_argument(
        "--analysis-style",
        "-a",
        choices=["concise", "full"],
        default="concise",
        help=(
            "Analysis output style: 'concise' for single comprehensive file, "
            "'full' for 5 detailed files (default: concise)"
        ),
    )
    _add_markdown_export_options(process_parser)


def _create_export_markdown_subparser(
    subparsers: _SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Create the export-markdown subcommand parser.

    Args:
        subparsers: Subparsers object to add the export-markdown parser to
    """
    export_md_parser = subparsers.add_parser(
        "export-markdown",
        help="Transcribe audio and export formatted Markdown transcript",
        description=(
            "Generate professionally formatted Markdown transcripts "
            "with timestamps, speaker labels, and metadata."
        ),
    )
    export_md_parser.add_argument("audio_path", help="Path to audio file")
    export_md_parser.add_argument(
        "--output-dir",
        "-o",
        default=f"./{DEFAULT_OUTPUT_DIR}",
        help=f"Output directory (default: ./{DEFAULT_OUTPUT_DIR})",
    )
    export_md_parser.add_argument(
        "--provider",
        "-p",
        choices=["deepgram", "elevenlabs", "whisper", "auto"],
        default="auto",
        help="Transcription provider to use (default: auto)",
    )
    export_md_parser.add_argument(
        "--language",
        "-l",
        default="en",
        help="Language code (default from config)",
    )
    # Paired flags for booleans in argparse
    export_md_parser.add_argument(
        "--timestamps",
        dest="include_timestamps",
        action="store_true",
        help="Include timestamps in transcript",
    )
    export_md_parser.add_argument(
        "--no-timestamps",
        dest="include_timestamps",
        action="store_false",
        help="Exclude timestamps in transcript",
    )
    export_md_parser.set_defaults(include_timestamps=True)
    export_md_parser.add_argument(
        "--speakers",
        dest="include_speakers",
        action="store_true",
        help="Include speaker labels",
    )
    export_md_parser.add_argument(
        "--no-speakers",
        dest="include_speakers",
        action="store_false",
        help="Exclude speaker labels",
    )
    export_md_parser.set_defaults(include_speakers=True)
    export_md_parser.add_argument(
        "--confidence",
        action="store_true",
        dest="include_confidence",
        help="Include confidence indicators when available",
    )
    export_md_parser.add_argument(
        "--template",
        default="default",
        choices=["default", "minimal", "detailed"],
        help="Markdown template to use",
    )


def _create_tui_subparser(subparsers: _SubParsersAction[argparse.ArgumentParser]) -> None:
    """Create the TUI subcommand parser.

    Args:
        subparsers: Subparsers object to add the TUI parser to
    """
    subparsers.add_parser(
        "tui",
        help="Launch interactive Terminal User Interface",
        description=(
            "Launch the interactive TUI for audio extraction and transcription "
            "with live progress updates, provider health checks, and artifact management."
        ),
    )
    # TUI doesn't need any arguments - it's interactive


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="audio-extraction-analysis",
        description="Audio extraction and transcription analysis tool with multiple providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Extract audio from video
  audio-extraction-analysis extract video.mp4 --quality speech

  # Transcribe audio file with auto provider selection
  audio-extraction-analysis transcribe audio.mp3 --language en

  # Transcribe with specific provider
  audio-extraction-analysis transcribe audio.mp3 --provider deepgram
  audio-extraction-analysis transcribe audio.mp3 --provider elevenlabs

  # Full pipeline: video to transcript
  audio-extraction-analysis process video.mp4 --output-dir ./results

  # With specific provider and verbose logging
  audio-extraction-analysis process video.mp4 --provider deepgram --verbose

Quality presets:
  high       - 320k bitrate, best for archival
  standard   - Variable bitrate, good balance
  speech     - Mono, normalized, best for transcription (default)
  compressed - 128k bitrate, smaller files

Transcription providers:
  deepgram   - Full-featured with speaker diarization, topics, intents, sentiment
  elevenlabs - Basic transcription with timestamps
  whisper    - Local OpenAI Whisper processing (no API key needed)
  auto       - Automatically select best available provider (default)

For more information, see: https://github.com/lucchesi-sec/audio-extraction-analysis
        """,
    )

    # Add global arguments
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit machine-readable JSON events to stderr/stdout",
    )

    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Add all subcommands using helper functions
    _create_extract_subparser(subparsers)
    _create_transcribe_subparser(subparsers)
    _create_process_subparser(subparsers)
    _create_export_markdown_subparser(subparsers)
    _create_tui_subparser(subparsers)

    return parser


def _validate_extract_input(input_path: Path) -> None:
    """Validate input file for extraction.

    Args:
        input_path: Path to input file

    Raises:
        ValueError: If input validation fails
    """
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
    """Determine output path for extracted audio.

    Args:
        input_path: Input file path
        output_arg: Optional output path from command arguments

    Returns:
        Path for output audio file
    """
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
    """Execute audio extraction with optional progress tracking.

    Args:
        extractor: AudioExtractor instance
        input_path: Input file path
        output_path: Output file path
        quality: Audio quality preset
        console_manager: Optional console manager for progress display

    Returns:
        Path to extracted audio file, or None if extraction failed
    """
    if console_manager:
        with console_manager.progress_context("Extracting audio...") as progress:
            progress.update(10)
            result_path = extractor.extract_audio(input_path, output_path, quality)
            progress.update(100)
    else:
        result_path = extractor.extract_audio(input_path, output_path, quality)

    return result_path


def extract_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the extract subcommand.

    Args:
        args: Command line arguments
        console_manager: Optional console manager for rich output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input file
        input_path = Path(args.input_file)
        try:
            _validate_extract_input(input_path)
        except ValueError:
            return 1

        # Determine output path
        output_path = _determine_extract_output_path(input_path, args.output)

        # Security check: ALWAYS refuse to overwrite system files (regardless of --force flag)
        # Use case-insensitive comparison to handle Windows path variations (C:\Windows vs c:\windows)
        system_paths = [
            "/etc/",
            "/bin/",
            "/usr/bin/",
            "/sbin/",
            "/usr/sbin/",
            "/System/",
            "C:\\Windows\\",
        ]
        output_path_lower = str(output_path).lower()
        if any(output_path_lower.startswith(sys_path.lower()) for sys_path in system_paths):
            logger.error("Access denied: Cannot overwrite system files")
            print("Error: Access denied. Cannot overwrite system files.", file=sys.stderr)
            return 1

        # Check if output exists and --force not provided
        if output_path.exists() and not getattr(args, "force", False):
            logger.error("Output file already exists. Use --force to overwrite.")
            print(f"Error: Output file already exists: {output_path}", file=sys.stderr)
            print("Use --force flag to overwrite existing files.", file=sys.stderr)
            return 1

        # Parse quality preset (reuse existing helper)
        quality = _parse_quality_preset(args.quality)

        # Setup logging and display
        display_name = input_path.name
        if console_manager:
            console_manager.setup_logging(logger)
            console_manager.print_stage("Audio Extraction", "starting")
        logger.info(
            "Extracting audio from %s with %s quality",
            display_name,
            getattr(quality, "value", quality),
        )
        logger.debug("Full input path: %s", input_path)

        # Execute extraction
        extractor = AudioExtractor()
        result_path = _execute_audio_extraction(
            extractor, input_path, output_path, quality, console_manager
        )

        # Handle result
        if result_path:
            if console_manager:
                console_manager.print_stage("Audio Extraction", "complete")
            logger.info(f"Audio extracted successfully: {result_path}")
            return 0
        else:
            logger.error("Audio extraction failed")
            return 1

    except Exception as e:
        # Use centralized error handler for all exceptions
        return handle_cli_error(e, "extract")


def export_markdown_transcript(
    args: argparse.Namespace, input_path: Path, result: TranscriptionResult
) -> None:
    """Export transcription result as Markdown.

    Args:
        args: Command line arguments
        input_path: Input audio file path
        result: Transcription result
    """
    try:
        out_root = Path(getattr(args, "markdown_output_dir", DEFAULT_OUTPUT_DIR))
        safe_name = sanitize_dirname(input_path.stem)
        base_dir = ensure_subpath(out_root, Path(safe_name))
        base_dir.mkdir(parents=True, exist_ok=True)

        md = MarkdownFormatter()
        source_info = {
            "source": str(input_path),
            "processed_at": datetime.now().isoformat(),
            "provider": result.provider_name,
            "total_duration": result.duration,
        }

        md_path = base_dir / "transcript.md"
        md_content = md.format_transcript(
            result,
            source_info,
            md_path,
            include_timestamps=getattr(args, "md_include_timestamps", True),
            include_speakers=getattr(args, "md_include_speakers", True),
            include_confidence=getattr(args, "md_include_confidence", False),
            template=getattr(args, "md_template", "default"),
        )
        md.save_transcript(md_content, md_path)

        # Save metadata.json
        metadata = {
            "source": source_info["source"],
            "processed_at": source_info["processed_at"],
            "provider": source_info["provider"],
            "duration_seconds": source_info["total_duration"],
            "segment_count": len(result.utterances or []),
        }
        try:
            safe_write_json(base_dir / "metadata.json", metadata)
        except OSError as e:
            logger.error(f"Failed writing metadata.json: {e}")

        # Save segments.json
        segments = [
            {
                "text": getattr(u, "text", None) or getattr(u, "transcript", ""),
                "start_time": u.start,
                "end_time": u.end,
                "speaker": u.speaker,
            }
            for u in (result.utterances or [])
        ]
        try:
            safe_write_json(base_dir / "segments.json", segments)
        except OSError as e:
            logger.error(f"Failed writing segments.json: {e}")

        logger.info(f"Markdown transcript saved to: {md_path}")

    except Exception as e:
        logger.error(f"Markdown export failed: {e}")


def _resolve_provider_name(provider: str) -> str | None:
    """Convert 'auto' provider to None for auto-selection.

    Args:
        provider: Provider name or 'auto'

    Returns:
        Provider name or None for auto-selection
    """
    return None if provider == "auto" else provider


def _determine_transcribe_output_path(input_path: Path, output_arg: str | None) -> Path:
    """Determine output path for transcription.

    Args:
        input_path: Input audio file path
        output_arg: Optional output path from command arguments

    Returns:
        Path for output transcript file
    """
    if output_arg:
        return Path(output_arg)
    # Safely build default transcript path: <stem>_transcript.txt
    return input_path.parent / f"{input_path.stem}_transcript.txt"


def _execute_transcription(
    transcription_service: TranscriptionService,
    input_path: Path,
    provider: str,
    language: str,
) -> TranscriptionResult | None:
    """Execute transcription with the service.

    Args:
        transcription_service: TranscriptionService instance
        input_path: Input audio file path
        provider: Provider name or "auto"
        language: Language code

    Returns:
        Transcription result object or None if failed

    Note:
        This function may hang indefinitely if the transcription service
        encounters network issues. Timeout handling should be implemented
        at the TranscriptionService level.
    """
    provider_name = _resolve_provider_name(provider)
    result = transcription_service.transcribe(
        input_path,
        provider_name=provider_name,
        language=language,
    )
    return result


def _handle_transcribe_success(
    result: TranscriptionResult,
    transcription_service: TranscriptionService,
    output_path: Path,
    console_manager: ConsoleManager | None,
    args: argparse.Namespace,
    input_path: Path,
) -> None:
    """Handle successful transcription result.

    Args:
        result: Transcription result object
        transcription_service: TranscriptionService instance
        output_path: Output file path for transcript
        console_manager: Optional console manager for rich output
        args: Command line arguments
        input_path: Input audio file path
    """
    # Save result to file using service
    transcription_service.save_transcription_result(
        result, output_path, provider_name=result.provider_name
    )

    if console_manager:
        console_manager.print_stage("Transcription", "complete")

    logger.info("Transcription completed successfully")
    logger.info(f"Provider: {result.provider_name}")
    logger.info(f"Transcript length: {len(result.transcript):,} characters")
    logger.info(f"Duration: {result.duration:.1f} seconds")
    logger.info(f"Speakers detected: {len(result.speakers or [])}")
    logger.info(f"Output saved to: {output_path}")

    # Optional Markdown export if requested
    if getattr(args, "export_markdown", False):
        export_markdown_transcript(args, input_path, result)


def transcribe_command(
    args: argparse.Namespace, console_manager: ConsoleManager | None = None
) -> int:
    """Handle the transcribe subcommand.

    Args:
        args: Command line arguments
        console_manager: Optional console manager for rich output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input audio file
        try:
            input_path = validate_audio_file(args.audio_file)
        except ValidationError:
            return 1

        # Determine output path
        output_path = _determine_transcribe_output_path(input_path, args.output)

        # Setup logging and display
        if console_manager:
            console_manager.setup_logging(logger)
            console_manager.print_stage("Transcription", "starting")
        logger.info(f"Transcribing {input_path} in {args.language} using {args.provider}")

        # Create transcription service and execute transcription
        transcription_service = TranscriptionService()
        result = _execute_transcription(
            transcription_service, input_path, args.provider, args.language
        )

        # Handle result
        if result:
            _handle_transcribe_success(
                result, transcription_service, output_path, console_manager, args, input_path
            )
            return 0
        else:
            logger.error("Transcription failed")
            return 1

    except Exception as e:
        # Use centralized error handler for all exceptions
        return handle_cli_error(e, "transcribe")


def _parse_quality_preset(quality_str: str) -> AudioQuality:
    """Parse quality preset string to AudioQuality enum.

    Args:
        quality_str: Quality preset string (high, standard, speech, compressed)

    Returns:
        AudioQuality enum value
    """
    quality_map = {
        "high": AudioQuality.HIGH,
        "standard": AudioQuality.STANDARD,
        "speech": AudioQuality.SPEECH,
        "compressed": AudioQuality.COMPRESSED,
    }
    quality = quality_map.get(quality_str)
    if quality is None:
        logger.warning(
            "Invalid quality preset '%s'. Falling back to default 'speech'.", quality_str
        )
        return AudioQuality.SPEECH
    return quality


def _setup_process_output_dir(args: argparse.Namespace) -> Path:
    """Setup and create output directory for processing.

    Args:
        args: Command line arguments

    Returns:
        Path to output directory
    """
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(DEFAULT_OUTPUT_DIR)

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _execute_processing_pipeline(
    input_path: Path,
    output_dir: Path,
    quality: AudioQuality,
    args: argparse.Namespace,
    console_manager: ConsoleManager | None,
) -> tuple[dict[str, object], TranscriptionResult]:
    """Execute the audio processing pipeline.

    Args:
        input_path: Input video file path
        output_dir: Output directory for results
        quality: Audio quality preset
        args: Command line arguments
        console_manager: Optional console manager for rich output

    Returns:
        Tuple of (pipeline_result dict, transcription result or None)

    Raises:
        Exception: If pipeline execution fails
    """
    pipeline_result = asyncio.run(
        process_pipeline(
            input_path=str(input_path),
            output_dir=str(output_dir),
            quality=quality,
            language=args.language,
            provider=args.provider,
            analysis_style=args.analysis_style,
            console_manager=console_manager,
        )
    )

    # Extract the transcription result from pipeline results
    if pipeline_result.get("success", False):
        result = pipeline_result.get("transcript")
    else:
        result = None
        errors = pipeline_result.get("errors", ["Unknown error"])
        logger.error(f"Pipeline processing failed: {', '.join(errors)}")
        # Targeted diagnostics: dump stage results and context
        if os.getenv("AUDIO_PIPELINE_DEBUG", "").lower() in {"1", "true", "yes"}:
            diag = {
                "stage_results": pipeline_result.get("stage_results"),
                "stages_completed": pipeline_result.get("stages_completed"),
                "files_created": pipeline_result.get("files_created"),
                "audio_path": pipeline_result.get("audio_path"),
            }
            try:
                logger.error("Pipeline diagnostics: %s", json.dumps(diag, default=str))
            except Exception:
                logger.error(f"Pipeline diagnostics (raw): {diag}")

    return pipeline_result, result


def _handle_process_success(
    result: TranscriptionResult,
    output_dir: Path,
    args: argparse.Namespace,
    input_path: Path,
) -> None:
    """Handle successful processing result.

    Args:
        result: Transcription result
        output_dir: Output directory path
        args: Command line arguments
        input_path: Input file path
    """
    logger.info("Processing completed successfully!")
    logger.info(f"Results saved to: {output_dir}")

    # Optional Markdown export
    if getattr(args, "export_markdown", False):
        # Update args to use output_dir for markdown output
        args.markdown_output_dir = str(output_dir)
        export_markdown_transcript(args, input_path, result)


def process_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the process subcommand (extract + transcribe).

    Args:
        args: Command line arguments
        console_manager: Optional console manager for rich output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Determine input source (local file vs URL)
        if getattr(args, "url", None) and args.video_file:
            logger.error("Specify either a local video file or --url, not both.")
            return 1

        config = Config()

        if getattr(args, "url", None):
            if not config.url_ingest_enabled:
                logger.error("URL ingestion is disabled by configuration.")
                return 1

            quality = _parse_quality_preset(args.quality)

            logger.info("Downloading media from URL: %s", args.url)
            ingestion_service = UrlIngestionService(
                download_dir=config.url_ingest_download_dir,
                prefer_audio_only=config.url_ingest_prefer_audio_only,
                keep_video=config.url_ingest_keep_video_default,
            )
            try:
                ingest_result = ingestion_service.ingest(args.url, quality=quality)
            except UrlIngestionError as exc:
                logger.error("URL ingestion failed: %s", exc)
                return 1

            input_path = ingest_result.audio_path
        else:
            if not args.video_file:
                logger.error("You must provide a local video file or --url.")
                return 1

            input_path = Path(args.video_file)
            if not input_path.exists():
                logger.error(f"Video file not found: {input_path}")
                return 1

        # Setup output directory
        output_dir = _setup_process_output_dir(args)

        # Parse quality preset
        quality = _parse_quality_preset(args.quality)

        logger.info(
            f"Processing video {input_path} (quality: {quality.value}, provider: {args.provider})"
        )

        # Execute pipeline
        try:
            _pipeline_result, result = _execute_processing_pipeline(
                input_path, output_dir, quality, args, console_manager
            )
        except Exception as e:
            # Use centralized error handler for pipeline errors
            return handle_cli_error(e, "process")

        # Handle results
        if result:
            _handle_process_success(result, output_dir, args, input_path)
            return 0
        else:
            logger.error("Processing failed")
            return 1

    except Exception as e:
        # Use centralized error handler for all exceptions
        return handle_cli_error(e, "process")


def _validate_and_setup_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Validate input audio file and setup output directory.

    Args:
        args: Command line arguments

    Returns:
        Tuple of (audio_path, output_dir)

    Raises:
        ValidationError: If audio file validation fails
    """
    audio_path = validate_audio_file(args.audio_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return audio_path, output_dir


def _perform_transcription(audio_path: Path, args: argparse.Namespace) -> TranscriptionResult:
    """Perform transcription of the audio file.

    Args:
        audio_path: Path to the audio file
        args: Command line arguments

    Returns:
        Transcription result object

    Raises:
        Exception: If transcription fails

    Note:
        This function may hang indefinitely if the transcription service
        encounters network issues. Timeout handling should be implemented
        at the TranscriptionService level.
    """
    service = TranscriptionService()
    provider_name = _resolve_provider_name(args.provider)

    logger.info(f"Transcribing {audio_path} using {args.provider} provider...")
    result = service.transcribe(audio_path, provider_name=provider_name, language=args.language)

    if not result:
        raise Exception("Transcription failed")

    return result


def _prepare_source_info(audio_path: Path, result: TranscriptionResult) -> dict[str, object]:
    """Prepare source information dictionary.

    Args:
        audio_path: Path to the audio file
        result: Transcription result object

    Returns:
        Dictionary containing source information
    """
    return {
        "source": str(audio_path),
        "processed_at": datetime.now().isoformat(),
        "provider": result.provider_name,
        "total_duration": result.duration,
    }


def _save_markdown_transcript(
    result: TranscriptionResult,
    source_info: dict[str, object],
    base_dir: Path,
    args: argparse.Namespace,
) -> Path:
    """Generate and save markdown transcript.

    Args:
        result: Transcription result object
        source_info: Source information dictionary
        base_dir: Base directory for output files
        args: Command line arguments

    Returns:
        Path to the saved markdown file
    """
    formatter = MarkdownFormatter()
    md_path = base_dir / "transcript.md"

    md_content = formatter.format_transcript(
        result,
        source_info,
        md_path,
        include_timestamps=args.include_timestamps,
        include_speakers=args.include_speakers,
        include_confidence=args.include_confidence,
        template=args.template,
    )

    formatter.save_transcript(md_content, md_path)
    logger.info(f"Markdown transcript saved to: {md_path}")

    return md_path


def _save_metadata(
    source_info: dict[str, object], result: TranscriptionResult, base_dir: Path
) -> None:
    """Save metadata to JSON file.

    Args:
        source_info: Source information dictionary
        result: Transcription result object
        base_dir: Base directory for output files
    """
    metadata = {
        "source": source_info["source"],
        "processed_at": source_info["processed_at"],
        "provider": source_info["provider"],
        "duration_seconds": source_info["total_duration"],
        "segment_count": len(result.utterances or []),
    }

    try:
        safe_write_json(base_dir / "metadata.json", metadata)
    except OSError as e:
        logger.error(f"Failed writing metadata.json: {e}")


def _save_segments(result: TranscriptionResult, base_dir: Path) -> None:
    """Save segments to JSON file.

    Args:
        result: Transcription result object
        base_dir: Base directory for output files
    """
    segments = [
        {
            "text": getattr(u, "text", None) or getattr(u, "transcript", ""),
            "start_time": u.start,
            "end_time": u.end,
            "speaker": u.speaker,
        }
        for u in (result.utterances or [])
    ]

    try:
        safe_write_json(base_dir / "segments.json", segments)
    except OSError as e:
        logger.error(f"Failed writing segments.json: {e}")


def export_markdown_command(
    args: argparse.Namespace, console_manager: ConsoleManager | None = None
) -> int:
    """Handle the export-markdown subcommand.

    This command transcribes an audio file and emits a formatted Markdown transcript,
    alongside JSON metadata and segment files.

    Args:
        args: Parsed CLI arguments
        console_manager: Optional console manager for rich output

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Validate input and setup paths
        try:
            audio_path, output_dir = _validate_and_setup_paths(args)
        except ValidationError:
            return 1

        # Perform transcription
        result = _perform_transcription(audio_path, args)

        # Create output directory structure
        safe_name = sanitize_dirname(audio_path.stem)
        base_dir = ensure_subpath(output_dir, Path(safe_name))
        base_dir.mkdir(parents=True, exist_ok=True)

        # Prepare source information
        source_info = _prepare_source_info(audio_path, result)

        # Save all output files
        _save_markdown_transcript(result, source_info, base_dir, args)
        _save_metadata(source_info, result, base_dir)
        _save_segments(result, base_dir)

        logger.info("Export completed successfully!")
        return 0

    except Exception as e:
        # Use centralized error handler for all exceptions
        return handle_cli_error(e, "export-markdown")


def tui_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the TUI subcommand.

    This command launches the interactive Terminal User Interface.

    Args:
        args: Parsed CLI arguments (unused for TUI)
        console_manager: Optional console manager (unused for TUI)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Import the TUI app here to avoid circular imports and only load when needed
        from .ui.tui.app import AudioExtractionApp

        # Create and run the TUI application
        app = AudioExtractionApp()
        app.run()
        return 0

    except ImportError as e:
        # Special handling for missing TUI dependencies
        logger.error(
            "TUI dependencies not installed. Install with: pip install -e '.[tui]'. Error: %s", e
        )
        print("✗ TUI Error: Missing dependencies", file=sys.stderr)
        print("  Install with: pip install -e '.[tui]'", file=sys.stderr)
        return 1
    except Exception as e:
        # Use centralized error handler for all other exceptions
        return handle_cli_error(e, "tui")


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse arguments
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Setup console manager if not in JSON output mode
    console_manager = None
    if not args.json_output:
        console_manager = ConsoleManager(verbose=args.verbose)

    try:
        # Route to appropriate command handler
        if args.command == "extract":
            return extract_command(args, console_manager)
        elif args.command == "transcribe":
            return transcribe_command(args, console_manager)
        elif args.command == "process":
            return process_command(args, console_manager)
        elif args.command == "export-markdown":
            # Handle export-markdown command
            return export_markdown_command(args, console_manager)
        elif args.command == "tui":
            # Handle TUI command
            return tui_command(args, console_manager)
    except KeyboardInterrupt:
        # Handle user cancellation (Ctrl+C)
        handle_keyboard_interrupt()


if __name__ == "__main__":
    sys.exit(main())
