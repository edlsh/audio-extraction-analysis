"""Common utilities for CLI commands."""

import argparse
import logging

from ..services.audio_extraction import AudioQuality

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "output"


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
