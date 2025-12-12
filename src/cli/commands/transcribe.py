"""Transcribe command handler."""

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ...error_handlers import handle_cli_error
from ...formatters.markdown_formatter import MarkdownFormatter
from ...models.transcription import TranscriptionResult
from ...services.transcription import TranscriptionService
from ...ui.console import ConsoleManager
from ...utils.file_validation import validate_audio_file
from ..json_output import CommandTiming, JsonCommandResult, log_json_message
from ..utils import add_markdown_export_options, add_transcription_options

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = get_logger(__name__)


def create_transcribe_subparser(subparsers: "_SubParsersAction[argparse.ArgumentParser]") -> None:
    """Create the transcribe subcommand parser."""
    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio files using multiple providers",
        description="Transcribe audio with provider selection (Deepgram Nova 3, ElevenLabs)",
    )
    transcribe_parser.add_argument("audio_file", help="Input audio file path")
    transcribe_parser.add_argument(
        "--output", "-o", help="Output transcript file path (default: <audio>_transcript.txt)"
    )
    add_transcription_options(transcribe_parser)
    add_markdown_export_options(transcribe_parser)


def _validate_transcribe_input(input_path: Path) -> None:
    """Validate input file for transcription."""
    validate_audio_file(input_path)


def _determine_transcribe_output_path(input_path: Path, output_arg: str | None) -> Path:
    """Determine output path for transcript."""
    if output_arg:
        return Path(output_arg)
    return input_path.parent / f"{input_path.stem}_transcript.txt"


def _execute_transcription(
    service: TranscriptionService,
    input_path: Path,
    provider: str,
    language: str,
) -> TranscriptionResult | None:
    """Execute transcription."""
    return service.transcribe(
        input_path,
        provider_name=None if provider == "auto" else provider,
        language=language,
    )


def _export_markdown_if_requested(
    result: TranscriptionResult,
    args: argparse.Namespace,
    input_path: Path,
    console_manager: ConsoleManager | None,
) -> None:
    """Export markdown transcript if requested."""
    if not getattr(args, "export_markdown", False):
        return

    formatter = MarkdownFormatter()
    md_path = input_path.parent / f"{input_path.stem}_transcript.md"

    source_info = {
        "source": str(input_path),
        "processed_at": result.generated_at.isoformat(),
        "provider": result.provider_name,
        "total_duration": result.duration,
    }

    md_content = formatter.format_transcript(
        result,
        source_info,
        md_path,
        include_timestamps=args.md_include_timestamps,
        include_speakers=args.md_include_speakers,
        include_confidence=args.md_include_confidence,
        template=args.md_template,
    )

    formatter.save_transcript(md_content, md_path)
    logger.info(f"Markdown transcript saved to: {md_path}")
    if console_manager:
        console_manager.print_success(f"Markdown transcript saved to: {md_path}")


def _handle_transcribe_success(
    result: TranscriptionResult,
    service: TranscriptionService,
    output_path: Path,
    console_manager: ConsoleManager | None,
    args: argparse.Namespace,
    input_path: Path,
) -> None:
    """Handle successful transcription result."""
    # Save basic text result
    service.save_transcription_result(result, output_path, args.provider)
    logger.info(f"Transcription saved to: {output_path}")

    # Only print Rich output if not in JSON mode
    if console_manager and not console_manager.json_output:
        console_manager.print_success(f"Transcription saved to: {output_path}")
        console_manager.print_result_summary(result)

    # Export Markdown if requested
    _export_markdown_if_requested(result, args, input_path, console_manager)


def transcribe_command(
    args: argparse.Namespace, console_manager: ConsoleManager | None = None
) -> int:
    """Handle the transcribe subcommand."""
    timing = CommandTiming()
    json_mode = console_manager is not None and console_manager.json_output
    input_str = getattr(args, "audio_file", "")

    try:
        input_path = Path(args.audio_file)

        timing.start_stage("validate")
        _validate_transcribe_input(input_path)
        timing.end_stage("validate")

        output_path = _determine_transcribe_output_path(input_path, args.output)

        # Setup logging and display
        if console_manager and not json_mode:
            console_manager.setup_logging(logger)
            console_manager.print_stage("Transcription", "starting")

        if json_mode:
            log_json_message("info", f"Transcribing {input_path} using {args.provider}")
        else:
            logger.info(f"Transcribing {input_path} in {args.language} using {args.provider}")

        # Create transcription service and execute transcription
        timing.start_stage("transcribe")
        transcription_service = TranscriptionService()
        result = _execute_transcription(
            transcription_service, input_path, args.provider, args.language
        )
        timing.end_stage("transcribe")

        # Handle result
        if result:
            _handle_transcribe_success(
                result, transcription_service, output_path, console_manager, args, input_path
            )

            if json_mode:
                outputs: dict[str, object] = {"transcript": str(output_path)}

                # Check for markdown export
                if getattr(args, "export_markdown", False):
                    md_path = input_path.parent / f"{input_path.stem}_transcript.md"
                    outputs["markdown"] = str(md_path)

                json_result = JsonCommandResult(
                    success=True,
                    command="transcribe",
                    input=str(input_path),
                    exit_code=0,
                    outputs=outputs,
                    timing={
                        "total_seconds": timing.total_seconds,
                        "stages": timing.stages,
                    },
                    metadata={
                        "provider": result.provider_name,
                        "language": args.language,
                        "duration": result.duration,
                        "transcript_length": len(result.transcript),
                    },
                )
                json_result.print_json()

            return 0
        else:
            if json_mode:
                json_result = JsonCommandResult(
                    success=False,
                    command="transcribe",
                    input=str(input_path),
                    exit_code=1,
                    errors=["Transcription failed"],
                    timing={
                        "total_seconds": timing.total_seconds,
                        "stages": timing.stages,
                    },
                )
                json_result.print_json()
            else:
                logger.error("Transcription failed")
            return 1

    except Exception as e:
        if json_mode:
            json_result = JsonCommandResult(
                success=False,
                command="transcribe",
                input=input_str,
                exit_code=1,
                errors=[str(e)],
                timing={
                    "total_seconds": timing.total_seconds,
                    "stages": timing.stages,
                },
            )
            json_result.print_json()
            return 1
        return handle_cli_error(e, "transcribe")
