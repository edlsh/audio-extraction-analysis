"""TUI widgets - reusable UI components.

This module exposes widget classes for convenient imports, while providing
lightweight fallbacks when Textual (or other UI deps) are unavailable. The
fallbacks satisfy type checking and tests that don't exercise real rendering.
"""

from __future__ import annotations

from typing import Any

__all__ = ["FilteredDirectoryTree", "HealthPanel", "LogPanel", "ProgressBoard"]


def _placeholder(name: str) -> type:
    """Return a minimal placeholder widget class.

    Used when Textual widgets cannot be imported so that importing
    ``src.ui.tui.widgets`` still succeeds in non-UI test environments.
    """

    class _Widget:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial
            self.args = args
            self.kwargs = kwargs

    _Widget.__name__ = name
    return _Widget


try:  # pragma: no cover - covered via higher-level tests
    from .filtered_tree import FilteredDirectoryTree
except ImportError:  # Textual or related deps not installed
    FilteredDirectoryTree = _placeholder("FilteredDirectoryTree")  # type: ignore[misc]

try:  # pragma: no cover
    from .health_panel import HealthPanel
except ImportError:
    HealthPanel = _placeholder("HealthPanel")  # type: ignore[misc]

try:  # pragma: no cover
    from .log_panel import LogPanel
except ImportError:
    LogPanel = _placeholder("LogPanel")  # type: ignore[misc]

try:  # pragma: no cover
    from .progress_board import ProgressBoard
except ImportError:
    ProgressBoard = _placeholder("ProgressBoard")  # type: ignore[misc]
