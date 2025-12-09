"""Common utilities for CLI commands."""

import argparse

from src.utils.logger import get_logger

from ..services.audio_extraction import AudioQuality

logger = get_logger(__name__)

DEFAULT_OUTPUT_DIR = "output"

# Available transcription providers
TRANSCRIPTION_PROVIDERS = ["deepgram", "elevenlabs", "whisper", "parakeet", "auto"]


def add_transcription_options(parser: argparse.ArgumentParser) -> None:
    """Add common transcription options to a parser.

    Adds --language and --provider options that are shared across
    transcribe and process commands.

    Args:
        parser: ArgumentParser to add options to
    """
    parser.add_argument(
        "--language",
        "-l",
        default="en",
        help="Language code for transcription (default: en)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=TRANSCRIPTION_PROVIDERS,
        default="auto",
        help="Transcription provider to use (default: auto)",
    )


def add_markdown_export_options(parser: argparse.ArgumentParser) -> None:
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


def parse_quality_preset(quality_str: str) -> AudioQuality:
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
