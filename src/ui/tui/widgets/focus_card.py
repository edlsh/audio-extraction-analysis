"""Focus card widget for displaying the currently active pipeline stage.

Shows detailed progress information for the running stage including
progress bar, ETA, message, and processing rate visualization.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Sparkline, Static

if TYPE_CHECKING:
    from ..state import AppState


class FocusCard(Widget):
    """Expanded progress display for the currently active pipeline stage.

    Shows detailed information including:
    - Stage name with icon
    - Full-width progress bar with percentage
    - ETA countdown
    - Current operation message
    - Processing rate sparkline

    Only one FocusCard is shown at a time (for the running stage).
    When no stage is running, displays a "waiting" or "complete" state.

    Example:
        >>> card = FocusCard()
        >>> card.update_from_state(app_state)
    """

    DEFAULT_CSS = """
    FocusCard {
        width: 100%;
        height: auto;
        min-height: 8;
        border: solid $accent;
        padding: 1;
        background: $surface;
        transition: opacity 300ms;
    }

    FocusCard.idle {
        border: solid $panel-darken-2;
    }

    FocusCard.complete {
        border: solid $success;
    }

    FocusCard.error {
        border: solid $error;
    }

    FocusCard .card-header {
        width: 100%;
        height: 1;
        layout: horizontal;
    }

    FocusCard .stage-icon {
        width: 3;
        text-align: center;
    }

    FocusCard .stage-title {
        width: 1fr;
        text-style: bold;
        padding-left: 1;
    }

    FocusCard .stage-percentage {
        width: auto;
        min-width: 6;
        text-align: right;
        text-style: bold;
        color: $accent;
    }

    FocusCard.complete .stage-percentage {
        color: $success;
    }

    FocusCard .progress-row {
        width: 100%;
        height: 1;
        margin: 1 0;
    }

    FocusCard ProgressBar {
        width: 1fr;
    }

    FocusCard .eta-label {
        width: auto;
        min-width: 12;
        text-align: right;
        padding-left: 2;
        color: $text-disabled;
    }

    FocusCard .message-row {
        width: 100%;
        height: 1;
    }

    FocusCard .stage-message {
        width: 100%;
        color: $text-muted;
    }

    FocusCard .rate-row {
        width: 100%;
        height: 2;
        margin-top: 1;
    }

    FocusCard .rate-sparkline {
        width: 1fr;
        height: 1;
    }

    FocusCard .rate-label {
        width: auto;
        min-width: 16;
        text-align: right;
        padding-left: 2;
        color: $text-disabled;
    }

    FocusCard .idle-message {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: $text-disabled;
    }
    """

    # Stage icons
    STAGE_ICONS = {
        "url_download": "⬇",
        "url_prepare": "🔧",
        "extract": "🎵",
        "transcribe": "📝",
        "analyze": "📊",
    }

    # Stage display names
    STAGE_NAMES = {
        "url_download": "Downloading Media",
        "url_prepare": "Preparing Media",
        "extract": "Extracting Audio",
        "transcribe": "Transcribing",
        "analyze": "Analyzing Content",
    }

    # Reactive state
    active_stage: reactive[str | None] = reactive(None)
    percentage: reactive[float] = reactive(0.0)
    message: reactive[str] = reactive("")
    eta: reactive[str] = reactive("--:--")
    is_complete: reactive[bool] = reactive(False)
    has_error: reactive[bool] = reactive(False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize focus card."""
        super().__init__(*args, **kwargs)
        self.rate_history: list[float] = []
        self._last_update_time: float = 0.0
        self._last_completed: int = 0

    def compose(self) -> ComposeResult:
        """Compose the card layout."""
        with Vertical():
            # Header row: icon + title + percentage
            with Horizontal(classes="card-header"):
                yield Label("", id="stage-icon", classes="stage-icon")
                yield Label("", id="stage-title", classes="stage-title")
                yield Label("", id="stage-percentage", classes="stage-percentage")

            # Progress row: bar + ETA
            with Horizontal(classes="progress-row"):
                yield ProgressBar(id="main-progress", show_eta=False, show_percentage=False)
                yield Label("", id="eta-label", classes="eta-label")

            # Message row
            with Horizontal(classes="message-row"):
                yield Label("", id="stage-message", classes="stage-message")

            # Rate visualization row
            with Horizontal(classes="rate-row"):
                yield Sparkline([], id="rate-sparkline", classes="rate-sparkline")
                yield Label("", id="rate-label", classes="rate-label")

            # Idle message (shown when no stage active)
            yield Static("", id="idle-message", classes="idle-message")

    def on_mount(self) -> None:
        """Configure initial state on mount."""
        self._update_display_mode()

    def watch_active_stage(self, stage: str | None) -> None:
        """React to active stage changes."""
        self._update_display_mode()
        self._update_content()

    def watch_percentage(self, percentage: float) -> None:
        """React to percentage changes."""
        self._update_progress()

    def watch_message(self, message: str) -> None:
        """React to message changes."""
        self._update_message()

    def watch_eta(self, eta: str) -> None:
        """React to ETA changes."""
        self._update_eta()

    def watch_is_complete(self, is_complete: bool) -> None:
        """React to completion state changes."""
        self.remove_class("idle", "complete", "error")
        if is_complete:
            self.add_class("complete")
        elif not self.active_stage:
            self.add_class("idle")

    def watch_has_error(self, has_error: bool) -> None:
        """React to error state changes."""
        if has_error:
            self.remove_class("idle", "complete")
            self.add_class("error")

    def _update_display_mode(self) -> None:
        """Update visibility of components based on active stage."""
        try:
            # Get elements
            header = self.query_one(".card-header", Horizontal)
            progress_row = self.query_one(".progress-row", Horizontal)
            message_row = self.query_one(".message-row", Horizontal)
            rate_row = self.query_one(".rate-row", Horizontal)
            idle_msg = self.query_one("#idle-message", Static)

            if self.active_stage:
                # Show active stage UI
                header.display = True
                progress_row.display = True
                message_row.display = True
                rate_row.display = len(self.rate_history) > 1
                idle_msg.display = False
                self.remove_class("idle")
            else:
                # Show idle state
                header.display = False
                progress_row.display = False
                message_row.display = False
                rate_row.display = False
                idle_msg.display = True

                if self.is_complete:
                    idle_msg.update("[green]✓ Pipeline completed successfully![/green]")
                    self.add_class("complete")
                elif self.has_error:
                    idle_msg.update("[red]✗ Pipeline encountered an error[/red]")
                    self.add_class("error")
                else:
                    idle_msg.update("[dim]Waiting for pipeline to start...[/dim]")
                    self.add_class("idle")
        except Exception:
            pass  # Widget not yet mounted

    def _update_content(self) -> None:
        """Update stage-specific content."""
        if not self.active_stage:
            return

        try:
            icon_label = self.query_one("#stage-icon", Label)
            title_label = self.query_one("#stage-title", Label)

            icon = self.STAGE_ICONS.get(self.active_stage, "⚡")
            name = self.STAGE_NAMES.get(self.active_stage, self.active_stage.title())

            icon_label.update(icon)
            title_label.update(name)
        except Exception:
            pass

    def _update_progress(self) -> None:
        """Update progress bar and percentage display."""
        try:
            progress_bar = self.query_one("#main-progress", ProgressBar)
            pct_label = self.query_one("#stage-percentage", Label)

            # Update progress bar
            if progress_bar.total is None:
                progress_bar.update(total=100)
            progress_bar.update(progress=self.percentage)

            # Update percentage label
            pct_label.update(f"{self.percentage:.0f}%")
        except Exception:
            pass

    def _update_message(self) -> None:
        """Update the message display."""
        try:
            msg_label = self.query_one("#stage-message", Label)
            # Truncate long messages
            display_msg = self.message[:60] + "..." if len(self.message) > 60 else self.message
            msg_label.update(display_msg or "Processing...")
        except Exception:
            pass

    def _update_eta(self) -> None:
        """Update ETA display."""
        try:
            eta_label = self.query_one("#eta-label", Label)
            if self.eta != "--:--":
                eta_label.update(f"ETA: {self.eta}")
            else:
                eta_label.update("")
        except Exception:
            pass

    def _update_rate(self, rate: float) -> None:
        """Update rate sparkline and label."""
        try:
            sparkline = self.query_one("#rate-sparkline", Sparkline)
            rate_label = self.query_one("#rate-label", Label)
            rate_row = self.query_one(".rate-row", Horizontal)

            sparkline.data = self.rate_history
            rate_row.display = len(self.rate_history) > 1

            if rate > 0:
                rate_label.update(f"{rate:.1f} units/s")
            else:
                rate_label.update("")
        except Exception:
            pass

    def update_from_state(self, state: AppState) -> None:
        """Update card from application state.

        Args:
            state: Current application state
        """
        # Determine if pipeline is complete or has error
        self.is_complete = bool(state.summary)
        self.has_error = bool(state.errors)

        # Get active stage
        self.active_stage = state.current_stage

        if not self.active_stage:
            return

        # Get progress
        completed = state.stage_completed.get(self.active_stage, 0)
        total = state.stage_totals.get(self.active_stage, 100)
        self.percentage = (completed / total * 100) if total > 0 else 0

        # Get message
        self.message = state.current_message or state.stage_messages.get(self.active_stage, "")

        # Calculate ETA
        self.eta = self._calculate_eta(state, completed, total)

        # Calculate rate for sparkline
        now = time.time()
        if completed > self._last_completed:
            elapsed = now - self._last_update_time if self._last_update_time > 0 else 1.0
            if elapsed > 0.1:
                rate = (completed - self._last_completed) / elapsed
                self.rate_history.append(rate)
                # Keep last 30 data points
                if len(self.rate_history) > 30:
                    self.rate_history = self.rate_history[-30:]

                self._last_update_time = now
                self._last_completed = completed
                self._update_rate(rate)

    def _calculate_eta(self, state: AppState, completed: int, total: int) -> str:
        """Calculate ETA for current stage."""
        if completed <= 0 or total <= 0:
            return "--:--"

        started_at = state.stage_started_at.get(self.active_stage)
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
        self.active_stage = None
        self.percentage = 0.0
        self.message = ""
        self.eta = "--:--"
        self.is_complete = False
        self.has_error = False
        self.rate_history.clear()
        self._last_update_time = 0.0
        self._last_completed = 0
