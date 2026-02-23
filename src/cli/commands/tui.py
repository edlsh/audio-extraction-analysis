"""TUI command handler."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

from ...error_handlers import handle_cli_error
from ...ui.console import ConsoleManager

if TYPE_CHECKING:
    from argparse import _SubParsersAction

logger = get_logger(__name__)

_TUI_DISTRIBUTION_POLICY = "source-checkout-only"


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


def _find_frontend_dir() -> Path | None:
    """Locate the frontend directory relative to this package."""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "frontend",
        Path.cwd() / "frontend",
    ]
    for candidate in candidates:
        if (candidate / "package.json").exists():
            return candidate
    return None


def _find_runtime() -> tuple[str, list[str]] | None:
    """Find Bun runtime. Node cannot execute the TSX entrypoint directly."""
    try:
        subprocess.run(
            ["bun", "--version"],
            capture_output=True,
            check=True,
        )
        return ("bun", ["run"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def tui_command(args: argparse.Namespace, console_manager: ConsoleManager | None = None) -> int:
    """Handle the TUI subcommand - launches OpenTUI frontend."""
    try:
        frontend_dir = _find_frontend_dir()
        if not frontend_dir:
            print("✗ TUI Error: frontend directory not found", file=sys.stderr)
            print("  Expected: project checkout with ./frontend/package.json", file=sys.stderr)
            print(f"  Policy: {_TUI_DISTRIBUTION_POLICY}", file=sys.stderr)
            return 1

        runtime = _find_runtime()
        if not runtime:
            print("✗ TUI Error: Bun runtime not found", file=sys.stderr)
            print("  Install bun: curl -fsSL https://bun.sh/install | bash", file=sys.stderr)
            print(f"  Policy: {_TUI_DISTRIBUTION_POLICY}", file=sys.stderr)
            return 1

        cmd, run_args = runtime
        entry_point = frontend_dir / "src" / "app" / "index.tsx"

        if not entry_point.exists():
            print(f"✗ TUI Error: entry point not found: {entry_point}", file=sys.stderr)
            return 1

        logger.info("Launching OpenTUI frontend with %s", cmd)

        env = os.environ.copy()
        env["PROJECT_ROOT"] = str(Path(__file__).parent.parent.parent.parent)
        env["AUDIO_ANALYSIS_PYTHON"] = sys.executable

        result = subprocess.run(
            [cmd, *run_args, str(entry_point)],
            cwd=str(frontend_dir),
            env=env,
        )
        return result.returncode

    except KeyboardInterrupt:
        return 0
    except Exception as e:
        return handle_cli_error(e, "tui")
