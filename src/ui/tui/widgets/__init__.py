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


# Placeholders for optional Textual dependencies - assigned dynamically below
Card: Any
HeroCard: Any
InfoCard: Any
CompletedSummary: Any
FilteredDirectoryTree: Any
FocusCard: Any
HealthPanel: Any
LogPanel: Any
PipelineTimeline: Any
ProgressBoard: Any
ProgressCard: Any

try:  # pragma: no cover
    from .card import Card, HeroCard, InfoCard
except ImportError:
    Card = _placeholder("Card")
    HeroCard = _placeholder("HeroCard")
    InfoCard = _placeholder("InfoCard")

try:  # pragma: no cover
    from .completed_summary import CompletedSummary
except ImportError:
    CompletedSummary = _placeholder("CompletedSummary")

try:  # pragma: no cover - covered via higher-level tests
    from .filtered_tree import FilteredDirectoryTree
except ImportError:
    FilteredDirectoryTree = _placeholder("FilteredDirectoryTree")

try:  # pragma: no cover
    from .focus_card import FocusCard
except ImportError:
    FocusCard = _placeholder("FocusCard")

try:  # pragma: no cover
    from .health_panel import HealthPanel
except ImportError:
    HealthPanel = _placeholder("HealthPanel")

try:  # pragma: no cover
    from .log_panel import LogPanel
except ImportError:
    LogPanel = _placeholder("LogPanel")

try:  # pragma: no cover
    from .pipeline_timeline import PipelineTimeline
except ImportError:
    PipelineTimeline = _placeholder("PipelineTimeline")

try:  # pragma: no cover
    from .progress_board import ProgressBoard
except ImportError:
    ProgressBoard = _placeholder("ProgressBoard")

try:  # pragma: no cover
    from .progress_card import ProgressCard
except ImportError:
    ProgressCard = _placeholder("ProgressCard")
