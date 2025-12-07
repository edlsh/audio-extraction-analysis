"""Progress board widget for displaying pipeline stage progress.

This is a modern, composable version using the Timeline + Focus Card
pattern for an improved progress UX that keeps all stages visible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .completed_summary import CompletedSummary
from .focus_card import FocusCard
from .pipeline_timeline import PipelineTimeline

if TYPE_CHECKING:
    from ..state import AppState


class ProgressBoard(Static):
    """Display pipeline progress with timeline and focus card pattern.

    Layout:
    - PipelineTimeline: Horizontal timeline showing all 5 stages
    - FocusCard: Expanded view of the currently running stage
    - CompletedSummary: Compact row of finished stages

    This pattern ensures:
    - All stages are always visible in the timeline
    - Fast stages don't disappear (they're shown in the timeline)
    - Current stage gets prominent display
    - Completed stages are acknowledged with durations

    Example:
        >>> board = ProgressBoard()
        >>> board.update_display(app_state)
    """

    DEFAULT_CSS = """
    ProgressBoard {
        width: 100%;
        height: auto;
        padding: 0;
    }

    ProgressBoard > Vertical {
        width: 100%;
        height: auto;
    }

    ProgressBoard PipelineTimeline {
        margin-bottom: 1;
    }

    ProgressBoard FocusCard {
        margin-bottom: 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize progress board."""
        super().__init__(*args, **kwargs)
        self._timeline: PipelineTimeline | None = None
        self._focus_card: FocusCard | None = None
        self._completed_summary: CompletedSummary | None = None

    def compose(self) -> ComposeResult:
        """Compose the progress board layout."""
        with Vertical():
            # Timeline at top - always visible
            self._timeline = PipelineTimeline(id="pipeline-timeline")
            yield self._timeline

            # Focus card for active stage
            self._focus_card = FocusCard(id="focus-card")
            yield self._focus_card

            # Completed summary at bottom
            self._completed_summary = CompletedSummary(id="completed-summary")
            yield self._completed_summary

    def on_mount(self) -> None:
        """Set up refresh timer on mount."""
        self.set_interval(0.1, self._refresh_display)

    def _refresh_display(self) -> None:
        """Refresh the display periodically."""
        if hasattr(self.app, "state"):
            self.update_display(self.app.state)

    def update_display(self, state: AppState) -> None:
        """Update all components from app state.

        Args:
            state: Current application state
        """
        if self._timeline:
            self._timeline.update_from_state(state)

        if self._focus_card:
            self._focus_card.update_from_state(state)

        if self._completed_summary:
            self._completed_summary.update_from_state(state)

    def reset(self) -> None:
        """Reset all components to initial state."""
        if self._timeline:
            self._timeline.reset()

        if self._focus_card:
            self._focus_card.reset()

        if self._completed_summary:
            self._completed_summary.reset()
