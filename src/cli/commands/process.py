"""Process command handler."""

import argparse
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ...config import get_config
from ...error_handlers import handle_cli_error
from ...models.transcription import TranscriptionResult
from ...pipeline.simple_pipeline import process_pipeline
from ...services.url_ingestion import UrlIngestionError, UrlIngestionService
from ...ui.console import ConsoleManager
from ..utils import (
    DEFAULT_OUTPUT_DIR,
    add_markdown_export_options,
    add_transcription_options,
    parse_quality_preset,
)
from .export import _prepare_source_info, _save_markdown_transcript

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = get_logger(__name__)


def create_process_subparser(subparsers: "_SubParsersAction[argparse.ArgumentParser]") -> None:
    """Create the process subcommand parser."""
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
    add_transcription_options(process_parser)
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
    add_markdown_export_options(process_parser)


def _setup_process_output_dir(args: argparse.Namespace) -> Path:
    """Setup and create output directory for processing."""
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(DEFAULT_OUTPUT_DIR)

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def _execute_processing_pipeline(
    input_path: Path,
    output_dir: Path,
    quality: str,  # AudioQuality passed as enum, but type hint might be specific
    args: argparse.Namespace,
    console_manager: ConsoleManager | None,
) -> tuple[dict[str, object], TranscriptionResult | None]:
    """Execute the audio processing pipeline."""
    # Note: quality arg passed to process_pipeline expects AudioQuality enum
    pipeline_result = await process_pipeline(
        input_path=str(input_path),
        output_dir=str(output_dir),
        quality=quality,
        language=args.language,
        provider=args.provider,
        analysis_style=args.analysis_style,
        console_manager=console_manager,
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
    """Handle successful processing result."""
    logger.info("Processing completed successfully!")
    logger.info(f"Results saved to: {output_dir}")

    if getattr(args, "export_markdown", False):
        source_info = _prepare_source_info(input_path, result)
        _save_markdown_transcript(result, source_info, output_dir, args)


async def process_command(
    args: argparse.Namespace, console_manager: ConsoleManager | None = None
) -> int:
    """Handle the process subcommand (extract + transcribe)."""
    try:
        input_path = _resolve_input_source(args)
        if input_path is None:
            return 1

        output_dir = _setup_process_output_dir(args)
        quality = parse_quality_preset(args.quality)

        logger.info(
            f"Processing video {input_path} (quality: {quality.value}, provider: {args.provider})"
        )

        try:
            _pipeline_result, result = await _execute_processing_pipeline(
                input_path, output_dir, quality, args, console_manager
            )
        except Exception as e:
            return handle_cli_error(e, "process")

        if result:
            _handle_process_success(result, output_dir, args, input_path)
            return 0

        logger.error("Processing failed")
        return 1

    except Exception as e:
        return handle_cli_error(e, "process")


def _resolve_input_source(args: argparse.Namespace) -> Path | None:
    """Resolve input from URL or local file. Returns None on error."""
    if getattr(args, "url", None) and args.video_file:
        logger.error("Specify either a local video file or --url, not both.")
        return None

    if getattr(args, "url", None):
        return _ingest_from_url(args)

    return _resolve_local_file(args)


def _ingest_from_url(args: argparse.Namespace) -> Path | None:
    """Download media from URL. Returns audio path or None on error."""
    config = get_config()

    if not config.url_ingest_enabled:
        logger.error("URL ingestion is disabled by configuration.")
        return None

    quality = parse_quality_preset(args.quality)
    logger.info("Downloading media from URL: %s", args.url)

    ingestion_service = UrlIngestionService(
        download_dir=config.url_ingest_download_dir,
        prefer_audio_only=config.url_ingest_prefer_audio_only,
        keep_video=config.url_ingest_keep_video_default,
    )

    try:
        ingest_result = ingestion_service.ingest(args.url, quality=quality)
        return ingest_result.audio_path
    except UrlIngestionError as exc:
        logger.error("URL ingestion failed: %s", exc)
        return None


def _resolve_local_file(args: argparse.Namespace) -> Path | None:
    """Resolve local video file. Returns path or None on error."""
    if not args.video_file:
        logger.error("You must provide a local video file or --url.")
        return None

    input_path = Path(args.video_file)
    if not input_path.exists():
        logger.error(f"Video file not found: {input_path}")
        return None

    return input_path
