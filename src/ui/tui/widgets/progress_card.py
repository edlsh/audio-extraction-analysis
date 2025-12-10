"""Modern progress card widget using composable Textual widgets.

Features:
- Rounded borders with status-based styling
- LoadingIndicator for pending stages
- Digits widget for large percentage display
- Sparkline for processing rate visualization
- Theme-aware colors via CSS variables
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Digits, Label, LoadingIndicator, Sparkline, Static

from ..themes import ANIM_EASING, ANIM_FAST, ANIM_MED

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
        border: round $panel;
        padding: 0 1;
        margin: 0 0 1 0;
        background: $surface;
    }

    /* Status variants with rounded borders */
    ProgressCard.pending {
        border: round $panel;
        background: $surface;
    }

    ProgressCard.running {
        border: round $accent;
        background: $surface;
    }

    ProgressCard.complete {
        border: round $success;
        background: $surface;
    }

    ProgressCard.error {
        border: round $error;
        background: $surface;
    }

    /* Card header */
    ProgressCard .card-header {
        text-style: bold;
        text-align: center;
        padding: 0;
        margin-bottom: 1;
        color: $accent;
    }

    ProgressCard.pending .card-header {
        color: $text-disabled;
    }

    ProgressCard.complete .card-header {
        color: $success;
    }

    ProgressCard.error .card-header {
        color: $error;
    }

    /* Percentage display */
    ProgressCard .percentage-display {
        text-align: center;
        height: 3;
    }

    ProgressCard .percentage-display Digits {
        text-align: center;
        width: 100%;
    }

    /* Status line */
    ProgressCard .status-line {
        text-align: center;
        color: $text-disabled;
        padding-top: 1;
    }

    /* Sparkline */
    ProgressCard .rate-sparkline {
        height: 1;
        margin: 0 2;
        color: $accent;
    }

    /* Loading indicator */
    ProgressCard LoadingIndicator {
        height: 3;
    }
    """

    status: reactive[str] = reactive("pending")
    percentage: reactive[float] = reactive(0.0)
    message: reactive[str] = reactive("")
    eta: reactive[str] = reactive("--:--")

    def __init__(
        self,
        stage_id: str,
        stage_name: str,
        *args: object,
        **kwargs: object,
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

    def watch_status(self, old_status: str, status: str) -> None:
        """React to status changes with optional animation."""
        self.remove_class("pending", "running", "complete", "error")
        self.add_class(status)
        self._update_display_mode()

    def watch_percentage(self, percentage: float) -> None:
        """React to percentage changes."""
        try:
            digits = self.query_one(f"#digits-{self.stage_id}", Digits)
            digits.update(f"{percentage:.0f}%")
        except Exception:
            pass

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
                loading.display = True
                digits.display = False
                sparkline.display = False
            else:
                loading.display = False
                digits.display = True
                sparkline.display = self.status == "running" and len(self.rate_history) > 1
        except Exception:
            pass

    def _update_status_line(self) -> None:
        """Update the status line text with theme-aware colors."""
        try:
            status_label = self.query_one(f"#status-{self.stage_id}", Label)

            if self.status == "pending":
                status_label.update("[dim]Waiting...[/dim]")
            elif self.status == "running":
                eta_text = f" (ETA {self.eta})" if self.eta != "--:--" else ""
                msg = self.message[:40] if self.message else "Processing..."
                status_label.update(f"{msg}{eta_text}")
            elif self.status == "complete":
                status_label.update(f"✓ {self.message or 'Completed'}")
            elif self.status == "error":
                status_label.update(f"✗ {self.message or 'Error'}")
        except Exception:
            pass

    def update_from_state(self, state: AppState) -> None:
        """Update card from application state.

        Args:
            state: Current application state
        """
        status = state.stage_status.get(self.stage_id, "pending")
        if not status or status not in ("pending", "running", "complete", "error"):
            if state.current_stage == self.stage_id:
                status = "running"
            elif self.stage_id in state.stage_durations:
                status = "complete"
            else:
                status = "pending"

        self.status = status

        completed = state.stage_completed.get(self.stage_id, 0)
        total = state.stage_totals.get(self.stage_id, 100)
        self.percentage = (completed / total * 100) if total > 0 else 0

        now = time.time()
        if status == "running" and completed > self._last_completed:
            elapsed = now - self._last_update_time if self._last_update_time > 0 else 1.0
            if elapsed > 0.1:
                rate = (completed - self._last_completed) / elapsed
                self.rate_history.append(rate)
                if len(self.rate_history) > 30:
                    self.rate_history = self.rate_history[-30:]

                self._last_update_time = now
                self._last_completed = completed

                try:
                    sparkline = self.query_one(f"#sparkline-{self.stage_id}", Sparkline)
                    sparkline.data = self.rate_history
                    sparkline.display = len(self.rate_history) > 1
                except Exception:
                    pass

        if state.current_stage == self.stage_id:
            self.message = state.current_message or state.stage_messages.get(self.stage_id, "")
        else:
            msg = state.stage_messages.get(self.stage_id, "")
            if status == "complete":
                duration = state.stage_durations.get(self.stage_id, 0)
                self.message = f"Completed in {duration:.1f}s"
            else:
                self.message = msg

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
