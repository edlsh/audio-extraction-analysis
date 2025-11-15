"""TUI widgets - reusable UI components."""

from __future__ import annotations

__all__ = []

# Conditionally import widgets if textual is available
try:
    from .log_panel import LogPanel
    from .progress_board import ProgressBoard

    __all__.extend(["LogPanel", "ProgressBoard"])
except ImportError:
    # Textual not installed
    pass
