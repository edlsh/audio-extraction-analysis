"""Completed stages summary widget.

Displays a compact horizontal summary of all completed pipeline stages
with their durations, providing a quick overview of finished work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

if TYPE_CHECKING:
    from ..state import AppState


class CompletedSummary(Widget):
    """Compact summary row showing completed pipeline stages.

    Displays completed stages in a horizontal format with durations:
    "✓ Download (0.3s) • ✓ Prepare (0.1s) • ✓ Extract (2.5s)"

    Features:
    - Flash animation when new stages complete
    - Compact display for space efficiency
    - Shows only completed/error stages

    Example:
        >>> summary = CompletedSummary()
        >>> summary.update_from_state(app_state)
    """

    DEFAULT_CSS = """
    CompletedSummary {
        width: 100%;
        height: auto;
        min-height: 1;
        max-height: 3;
        padding: 0 1;
        background: $panel;
        border: solid $panel-darken-2;
    }

    CompletedSummary .summary-content {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
    }

    CompletedSummary .summary-label {
        width: auto;
        padding-right: 1;
    }

    CompletedSummary .stage-item {
        width: auto;
        padding: 0 1;
    }

    CompletedSummary .stage-item.complete {
        color: $success;
    }

    CompletedSummary .stage-item.error {
        color: $error;
    }

    CompletedSummary .stage-item.skipped {
        color: $text-disabled;
    }

    CompletedSummary .separator {
        width: auto;
        color: $text-disabled;
    }

    CompletedSummary .empty-message {
        width: 100%;
        text-align: center;
        color: $text-disabled;
    }

    CompletedSummary.flash-complete {
        background: $success-darken-2;
    }
    """

    # Stage short names for compact display
    STAGE_NAMES = {
        "url_download": "Download",
        "url_prepare": "Prepare",
        "extract": "Extract",
        "transcribe": "Transcribe",
        "analyze": "Analyze",
    }

    # Stage order for display
    STAGE_ORDER = ["url_download", "url_prepare", "extract", "transcribe", "analyze"]

    # Reactive state
    completed_count: reactive[int] = reactive(0)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize completed summary."""
        super().__init__(*args, **kwargs)
        self._completed_stages: list[tuple[str, str, float]] = []  # (stage_id, status, duration)
        self._last_count: int = 0

    def compose(self) -> ComposeResult:
        """Compose the summary layout."""
        with Horizontal(classes="summary-content"):
            yield Label("[dim]Completed:[/dim]", classes="summary-label")
            yield Label("[dim]None yet[/dim]", id="summary-text", classes="empty-message")

    def watch_completed_count(self, count: int) -> None:
        """React to completed count changes."""
        # Flash effect when new stage completes
        if count > self._last_count and self._last_count > 0:
            self.add_class("flash-complete")
            self.set_timer(0.5, lambda: self.remove_class("flash-complete"))
        self._last_count = count

    def update_from_state(self, state: AppState) -> None:
        """Update summary from application state.

        Args:
            state: Current application state
        """
        # Collect completed stages in order
        completed_stages: list[tuple[str, str, float]] = []

        for stage_id in self.STAGE_ORDER:
            status = state.stage_status.get(stage_id, "pending")
            duration = state.stage_durations.get(stage_id, 0.0)

            # Handle skipped URL stages
            if stage_id in ("url_download", "url_prepare"):
                if state.input_path and stage_id not in state.stage_status:
                    status = "skipped"

            if status in ("complete", "error", "skipped"):
                completed_stages.append((stage_id, status, duration))

        self._completed_stages = completed_stages
        self.completed_count = len([s for s in completed_stages if s[1] == "complete"])
        self._update_display()

    def _update_display(self) -> None:
        """Update the visual display."""
        try:
            summary_text = self.query_one("#summary-text", Label)

            if not self._completed_stages:
                summary_text.update("[dim]None yet[/dim]")
                return

            # Build summary string
            parts = []
            for stage_id, status, duration in self._completed_stages:
                name = self.STAGE_NAMES.get(stage_id, stage_id)

                if status == "complete":
                    if duration > 0:
                        parts.append(f"[green]✓ {name} ({duration:.1f}s)[/green]")
                    else:
                        parts.append(f"[green]✓ {name}[/green]")
                elif status == "error":
                    parts.append(f"[red]✗ {name}[/red]")
                elif status == "skipped":
                    parts.append(f"[dim]⊘ {name}[/dim]")

            summary_text.update(" • ".join(parts))
        except Exception:
            pass  # Widget not yet mounted

    def reset(self) -> None:
        """Reset summary to initial state."""
        self._completed_stages.clear()
        self._last_count = 0
        self.completed_count = 0
        self._update_display()
