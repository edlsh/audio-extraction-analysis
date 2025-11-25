"""Unified CLI for audio extraction and transcription analysis."""

import argparse
import asyncio
import logging
import sys

from ..error_handlers import handle_keyboard_interrupt
from ..ui.console import ConsoleManager
from .commands.export import create_export_markdown_subparser, export_markdown_command
from .commands.extract import create_extract_subparser, extract_command
from .commands.process import create_process_subparser, process_command
from .commands.transcribe import create_transcribe_subparser, transcribe_command
from .commands.tui import create_tui_subparser, tui_command

__version__ = "2.0.0"

logger = logging.getLogger(__name__)

def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)

    # Set specific loggers
    logging.getLogger("src").setLevel(level)

def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
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
    create_extract_subparser(subparsers)
    create_transcribe_subparser(subparsers)
    create_process_subparser(subparsers)
    create_export_markdown_subparser(subparsers)
    create_tui_subparser(subparsers)

    return parser

def main() -> int:
    """Main CLI entry point."""
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
            return asyncio.run(process_command(args, console_manager))
        elif args.command == "export-markdown":
            return export_markdown_command(args, console_manager)
        elif args.command == "tui":
            return tui_command(args, console_manager)
    except KeyboardInterrupt:
        # Handle user cancellation (Ctrl+C)
        handle_keyboard_interrupt()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
