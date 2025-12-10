"""TUI widgets - reusable UI components.

This module exposes widget classes for convenient imports, while providing
lightweight fallbacks when Textual (or other UI deps) are unavailable. The
fallbacks satisfy type checking and tests that don't exercise real rendering.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "Card",
    "CompletedSummary",
    "FilteredDirectoryTree",
    "FocusCard",
    "HealthPanel",
    "HeroCard",
    "InfoCard",
    "LogPanel",
    "PipelineTimeline",
    "ProgressBoard",
    "ProgressCard",
]


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


try:  # pragma: no cover
    from .card import Card, HeroCard, InfoCard
except ImportError:
    # type: ignore[misc] - Placeholder for optional dependency
    Card = _placeholder("Card")  # type: ignore[misc]
    HeroCard = _placeholder("HeroCard")  # type: ignore[misc]
    InfoCard = _placeholder("InfoCard")  # type: ignore[misc]

try:  # pragma: no cover
    from .completed_summary import CompletedSummary
except ImportError:
    # type: ignore[misc] - Placeholder for optional dependency
    CompletedSummary = _placeholder("CompletedSummary")  # type: ignore[misc]

try:  # pragma: no cover - covered via higher-level tests
    from .filtered_tree import FilteredDirectoryTree
except ImportError:  # Textual or related deps not installed
    # type: ignore[misc] - Placeholder doesn't match full widget interface, but that's intentional
    # for graceful degradation when Textual is not available
    FilteredDirectoryTree = _placeholder("FilteredDirectoryTree")  # type: ignore[misc]

try:  # pragma: no cover
    from .focus_card import FocusCard
except ImportError:
    # type: ignore[misc] - Placeholder for optional dependency
    FocusCard = _placeholder("FocusCard")  # type: ignore[misc]

try:  # pragma: no cover
    from .health_panel import HealthPanel
except ImportError:
    # type: ignore[misc] - Same pattern as above: placeholder for optional dependency
    HealthPanel = _placeholder("HealthPanel")  # type: ignore[misc]

try:  # pragma: no cover
    from .log_panel import LogPanel
except ImportError:
    # type: ignore[misc] - Same pattern as above: placeholder for optional dependency
    LogPanel = _placeholder("LogPanel")  # type: ignore[misc]

try:  # pragma: no cover
    from .pipeline_timeline import PipelineTimeline
except ImportError:
    # type: ignore[misc] - Placeholder for optional dependency
    PipelineTimeline = _placeholder("PipelineTimeline")  # type: ignore[misc]

try:  # pragma: no cover
    from .progress_board import ProgressBoard
except ImportError:
    # type: ignore[misc] - Same pattern as above: placeholder for optional dependency
    ProgressBoard = _placeholder("ProgressBoard")  # type: ignore[misc]

try:  # pragma: no cover
    from .progress_card import ProgressCard
except ImportError:
    # type: ignore[misc] - Same pattern as above: placeholder for optional dependency
    ProgressCard = _placeholder("ProgressCard")  # type: ignore[misc]
