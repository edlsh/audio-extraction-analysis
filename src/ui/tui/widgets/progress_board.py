"""Progress board widget for displaying pipeline stage progress."""

from __future__ import annotations

import time
from collections import deque

from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from textual.app import ComposeResult
from textual.widgets import Static

from ..state import AppState


class ProgressBoard(Static):
    """Display progress cards for each pipeline stage.

    Features:
    - Three cards: Extract, Transcribe, Analyze
    - Progress bars with percentage
    - ETA calculation using exponential moving average
    - Status indicators (pending, running, complete, error)

    Example:
        >>> board = ProgressBoard()
        >>> board.update(app_state)
    """

    # Stage display names and order
    STAGES = [
        ("url_download", "URL Download"),
        ("url_prepare", "Prepare Media"),
        ("extract", "Extract Audio"),
        ("transcribe", "Transcribe"),
        ("analyze", "Analyze"),
    ]

    # Status colors
    STATUS_COLORS = {
        "pending": "dim",
        "running": "blue",
        "complete": "green",
        "error": "red",
    }

    def __init__(self, **kwargs):
        """Initialize progress board."""
        super().__init__(**kwargs)
        self._eta_history: dict[str, deque[float]] = {}  # {stage: deque of rates}
        self._last_update: dict[str, float] = {}  # {stage: timestamp}

    def on_mount(self) -> None:
        """Set up refresh timer on mount."""
        self.set_interval(0.1, self._refresh_display)

    def _refresh_display(self) -> None:
        """Refresh the display periodically."""
        if hasattr(self.app, "state"):
            self.update_display(self.app.state)

    def update_display(self, state: AppState) -> None:
        """Update display from app state.

        Args:
            state: Current application state
        """
        table = Table.grid(padding=(1, 2))
        table.add_column(justify="center")

        for stage_id, stage_name in self.STAGES:
            card = self._render_stage_card(state, stage_id, stage_name)
            table.add_row(card)

        self.update(table)

    def _render_stage_card(self, state: AppState, stage_id: str, stage_name: str) -> Panel:
        """Render a progress card for a stage.

        Args:
            state: Application state
            stage_id: Stage identifier (e.g., "extract")
            stage_name: Display name (e.g., "Extract Audio")

        Returns:
            Rich Panel with progress information
        """
        # Determine status
        status = self._get_stage_status(state, stage_id)

        # Get progress
        completed = state.stage_completed.get(stage_id, 0)
        total = state.stage_totals.get(stage_id, 100)
        percentage = (completed / total * 100) if total > 0 else 0

        # Build progress bar
        bar_width = 30
        filled = int(percentage / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        # Get ETA
        eta_str = self._calculate_eta(state, stage_id, completed, total)

        # Build content
        content_lines = [
            f"[bold]{bar}[/bold] {percentage:.0f}%",
            "",
        ]

        if status == "running":
            content_lines.append(f"[cyan]ETA: {eta_str}[/cyan]")
        elif status == "complete":
            duration = state.stage_durations.get(stage_id, 0)
            content_lines.append(f"[green]✓ Completed in {duration:.1f}s[/green]")
        elif status == "error":
            content_lines.append("[red]✗ Error[/red]")
        else:
            content_lines.append("[dim]Waiting...[/dim]")

        # Add current message if running
        if status == "running" and state.current_stage == stage_id:
            msg = state.current_message[:40]  # Truncate long messages
            if msg:
                content_lines.append(f"[dim]{msg}[/dim]")

        content = "\n".join(content_lines)

        # Get border style based on status
        border_style = self.STATUS_COLORS.get(status, "white")

        return Panel(
            content,
            title=f"[bold]{stage_name}[/bold]",
            border_style=border_style,
            padding=(0, 1),
        )

    def _get_stage_status(self, state: AppState, stage_id: str) -> str:
        """Get stage status.

        Args:
            state: Application state
            stage_id: Stage identifier

        Returns:
            Status: "pending", "running", "complete", or "error"
        """
        # Check for errors
        if state.errors and state.current_stage == stage_id:
            return "error"

        # Check if complete
        if stage_id in state.stage_durations:
            return "complete"

        # Check if running
        if state.current_stage == stage_id:
            return "running"

        # Check if started
        if stage_id in state.stage_completed:
            return "running"

        return "pending"

    def _calculate_eta(self, state: AppState, stage_id: str, completed: int, total: int) -> str:
        """Calculate ETA for a stage using exponential moving average.

        Args:
            state: Application state
            stage_id: Stage identifier
            completed: Completed units
            total: Total units

        Returns:
            ETA string (e.g., "00:15")
        """
        if completed == 0 or total == 0:
            return "--:--"

        # Initialize history for this stage
        if stage_id not in self._eta_history:
            self._eta_history[stage_id] = deque(maxlen=10)
            self._last_update[stage_id] = time.time()

        # Calculate rate (units per second)
        now = time.time()
        if stage_id in self._last_update:
            time_delta = now - self._last_update[stage_id]
            if time_delta > 0:
                # Store rate in history
                rate = 1.0 / time_delta  # Simple rate for now
                self._eta_history[stage_id].append(rate)

        self._last_update[stage_id] = now

        # Calculate average rate
        if not self._eta_history[stage_id]:
            return "--:--"

        avg_rate = sum(self._eta_history[stage_id]) / len(self._eta_history[stage_id])

        if avg_rate == 0:
            return "--:--"

        # Calculate remaining time
        remaining_units = total - completed
        remaining_seconds = remaining_units / avg_rate

        # Format as MM:SS
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)

        if minutes > 99:
            return "99:59"

        return f"{minutes:02d}:{seconds:02d}"
