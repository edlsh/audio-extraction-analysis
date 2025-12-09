"""TUI command handler."""

import argparse
import sys
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ...error_handlers import handle_cli_error
from ...ui.console import ConsoleManager

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = get_logger(__name__)


def create_tui_subparser(subparsers: "_SubParsersAction[argparse.ArgumentParser]") -> None:
    """Create the TUI subcommand parser."""
    subparsers.add_parser(
        "tui",
        help="Launch interactive Terminal User Interface",
        description=(
            "Launch the interactive TUI for audio extraction and transcription "
            "with live progress updates, provider health checks, and artifact management."
        ),
    )


def tui_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the TUI subcommand."""
    try:
        # Import the TUI app here to avoid circular imports and only load when needed
        from ...ui.tui.app import AudioExtractionApp

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
