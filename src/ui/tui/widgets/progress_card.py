"""Modern progress card widget using composable Textual widgets.

Features:
- LoadingIndicator for pending stages
- Digits widget for large percentage display
- Sparkline for processing rate visualization
- Smooth CSS animations for status transitions
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label, LoadingIndicator, Sparkline, Static

if TYPE_CHECKING:
    from ..state import AppState


class ProgressCard(Static):
    """A single progress card for a pipeline stage.

    Displays:
    - Stage name as title
    - Large percentage display using Digits
    - Processing rate sparkline
    - Status message and ETA

    Attributes:
        stage_id: Identifier for the pipeline stage
        stage_name: Human-readable stage name
        status: Current status (pending, running, complete, error)
        percentage: Completion percentage (0-100)
        rate_history: List of processing rates for sparkline
    """

    DEFAULT_CSS = """
    ProgressCard {
        width: 100%;
        height: auto;
        min-height: 7;
        border: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
        background: $surface;
    }

    ProgressCard.pending {
        border: solid $panel-darken-2;
    }

    ProgressCard.running {
        border: solid $accent;
    }

    ProgressCard.complete {
        border: solid $success;
    }

    ProgressCard.error {
        border: solid $error;
    }

    ProgressCard .card-header {
        text-style: bold;
        text-align: center;
        padding: 0;
        margin-bottom: 1;
    }

    ProgressCard .percentage-display {
        text-align: center;
        height: 3;
    }

    ProgressCard .percentage-display Digits {
        text-align: center;
        width: 100%;
    }

    ProgressCard .status-line {
        text-align: center;
        color: $text-disabled;
    }

    ProgressCard .rate-sparkline {
        height: 1;
        margin: 0 2;
    }

    ProgressCard LoadingIndicator {
        height: 3;
    }
    """

    # Reactive attributes
    status: reactive[str] = reactive("pending")
    percentage: reactive[float] = reactive(0.0)
    message: reactive[str] = reactive("")
    eta: reactive[str] = reactive("--:--")

    def __init__(
        self,
        stage_id: str,
        stage_name: str,
        *args,
        **kwargs,
    ) -> None:
        """Initialize progress card.

        Args:
            stage_id: Stage identifier (e.g., "extract")
            stage_name: Display name (e.g., "Extract Audio")
        """
        super().__init__(*args, **kwargs)
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.rate_history: list[float] = []
        self._last_update_time: float = 0.0
        self._last_completed: int = 0

    def compose(self) -> ComposeResult:
        """Compose the card layout."""
        yield Label(self.stage_name, classes="card-header")

        with Vertical(classes="percentage-display"):
            yield Digits("0%", id=f"digits-{self.stage_id}")
            yield LoadingIndicator(id=f"loading-{self.stage_id}")

        yield Sparkline([], id=f"sparkline-{self.stage_id}", classes="rate-sparkline")
        yield Label("", id=f"status-{self.stage_id}", classes="status-line")

    def on_mount(self) -> None:
        """Configure initial visibility on mount."""
        self._update_display_mode()

    def watch_status(self, status: str) -> None:
        """React to status changes."""
        # Remove old status classes
        self.remove_class("pending", "running", "complete", "error")
        # Add new status class
        self.add_class(status)
        self._update_display_mode()

    def watch_percentage(self, percentage: float) -> None:
        """React to percentage changes."""
        try:
            digits = self.query_one(f"#digits-{self.stage_id}", Digits)
            digits.update(f"{percentage:.0f}%")
        except Exception:
            pass  # Widget not yet mounted

    def watch_message(self, message: str) -> None:
        """React to message changes."""
        self._update_status_line()

    def watch_eta(self, eta: str) -> None:
        """React to ETA changes."""
        self._update_status_line()

    def _update_display_mode(self) -> None:
        """Update visibility of components based on status."""
        try:
            loading = self.query_one(f"#loading-{self.stage_id}", LoadingIndicator)
            digits = self.query_one(f"#digits-{self.stage_id}", Digits)
            sparkline = self.query_one(f"#sparkline-{self.stage_id}", Sparkline)

            if self.status == "pending":
                # Show loading indicator, hide digits
                loading.display = True
                digits.display = False
                sparkline.display = False
            else:
                # Show digits and sparkline, hide loading
                loading.display = False
                digits.display = True
                sparkline.display = self.status == "running" and len(self.rate_history) > 1
        except Exception:
            pass  # Widgets not yet mounted

    def _update_status_line(self) -> None:
        """Update the status line text."""
        try:
            status_label = self.query_one(f"#status-{self.stage_id}", Label)

            if self.status == "pending":
                status_label.update("[dim]Waiting...[/dim]")
            elif self.status == "running":
                eta_text = f" (ETA {self.eta})" if self.eta != "--:--" else ""
                msg = self.message[:40] if self.message else "Processing..."
                status_label.update(f"[cyan]{msg}{eta_text}[/cyan]")
            elif self.status == "complete":
                status_label.update(f"[green]✓ {self.message or 'Completed'}[/green]")
            elif self.status == "error":
                status_label.update(f"[red]✗ {self.message or 'Error'}[/red]")
        except Exception:
            pass

    def update_from_state(self, state: AppState) -> None:
        """Update card from application state.

        Args:
            state: Current application state
        """
        # Determine status
        status = state.stage_status.get(self.stage_id, "pending")
        if not status or status not in ("pending", "running", "complete", "error"):
            if state.current_stage == self.stage_id:
                status = "running"
            elif self.stage_id in state.stage_durations:
                status = "complete"
            else:
                status = "pending"

        self.status = status

        # Get progress
        completed = state.stage_completed.get(self.stage_id, 0)
        total = state.stage_totals.get(self.stage_id, 100)
        self.percentage = (completed / total * 100) if total > 0 else 0

        # Calculate rate for sparkline
        now = time.time()
        if status == "running" and completed > self._last_completed:
            elapsed = now - self._last_update_time if self._last_update_time > 0 else 1.0
            if elapsed > 0.1:  # Avoid division by tiny intervals
                rate = (completed - self._last_completed) / elapsed
                self.rate_history.append(rate)
                # Keep last 30 data points
                if len(self.rate_history) > 30:
                    self.rate_history = self.rate_history[-30:]

                self._last_update_time = now
                self._last_completed = completed

                # Update sparkline
                try:
                    sparkline = self.query_one(f"#sparkline-{self.stage_id}", Sparkline)
                    sparkline.data = self.rate_history
                    sparkline.display = len(self.rate_history) > 1
                except Exception:
                    pass

        # Get message
        if state.current_stage == self.stage_id:
            self.message = state.current_message or state.stage_messages.get(self.stage_id, "")
        else:
            msg = state.stage_messages.get(self.stage_id, "")
            if status == "complete":
                duration = state.stage_durations.get(self.stage_id, 0)
                self.message = f"Completed in {duration:.1f}s"
            else:
                self.message = msg

        # Calculate ETA
        self.eta = self._calculate_eta(state, completed, total)

    def _calculate_eta(self, state: AppState, completed: int, total: int) -> str:
        """Calculate ETA for current stage."""
        if completed <= 0 or total <= 0:
            return "--:--"

        started_at = state.stage_started_at.get(self.stage_id)
        if not started_at:
            return "--:--"

        elapsed = max(time.time() - started_at, 0.001)
        rate = completed / elapsed
        if rate <= 0:
            return "--:--"

        remaining = max(total - completed, 0)
        remaining_seconds = remaining / rate

        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)

        if minutes > 99:
            return "99:59"

        return f"{minutes:02d}:{seconds:02d}"

    def reset(self) -> None:
        """Reset card to initial state."""
        self.status = "pending"
        self.percentage = 0.0
        self.message = ""
        self.eta = "--:--"
        self.rate_history.clear()
        self._last_update_time = 0.0
        self._last_completed = 0
