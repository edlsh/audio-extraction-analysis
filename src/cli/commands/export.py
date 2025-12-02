"""Export command handler."""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...error_handlers import handle_cli_error
from ...formatters.markdown_formatter import MarkdownFormatter
from ...models.transcription import TranscriptionResult
from ...services.transcription import TranscriptionService
from ...ui.console import ConsoleManager
from ...utils.file_validation import validate_audio_file
from ...utils.paths import ensure_subpath, safe_write_json, sanitize_dirname
from ..utils import DEFAULT_OUTPUT_DIR

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = logging.getLogger(__name__)


def create_export_markdown_subparser(
    subparsers: "_SubParsersAction[argparse.ArgumentParser]",
) -> None:
    """Create the export-markdown subcommand parser."""
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


def _validate_and_setup_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Validate input audio file and setup output directory."""
    audio_path = validate_audio_file(args.audio_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return audio_path, output_dir


def _resolve_provider_name(provider: str) -> str | None:
    """Resolve provider name mapping."""
    # Simple pass through for now, logic was inline or implicit in CLI
    if provider == "auto":
        return None
    return provider


def _perform_transcription(audio_path: Path, args: argparse.Namespace) -> TranscriptionResult:
    """Perform transcription of the audio file."""
    service = TranscriptionService()
    provider_name = _resolve_provider_name(args.provider)

    logger.info(f"Transcribing {audio_path} using {args.provider} provider...")
    result = service.transcribe(audio_path, provider_name=provider_name, language=args.language)

    if not result:
        raise Exception("Transcription failed")

    return result


def _prepare_source_info(audio_path: Path, result: TranscriptionResult) -> dict[str, object]:
    """Prepare source information dictionary."""
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
    """Generate and save markdown transcript."""
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
    """Save metadata to JSON file."""
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
    """Save segments to JSON file."""
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
    """Handle the export-markdown subcommand."""
    try:
        # Validate input and setup paths
        try:
            audio_path, output_dir = _validate_and_setup_paths(args)
        except Exception:  # ValidationError might need import
            return 1

        # Perform transcription
        result = _perform_transcription(audio_path, args)

        # Create output directory structure
        safe_name = sanitize_dirname(audio_path.stem)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_dir = ensure_subpath(output_dir, Path(f"{safe_name}_{timestamp}"))
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
        return handle_cli_error(e, "export-markdown")
