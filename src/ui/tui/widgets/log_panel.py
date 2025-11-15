"""Log panel widget for displaying filtered pipeline logs."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from ..state import AppState, LogEntry


class LogPanel(VerticalScroll):
    """Scrollable, filterable log viewer.

    Features:
    - Auto-scroll to latest log
    - Filter by level (all, debug, info, warning, error)
    - Color-coded log levels
    - Timestamps
    - Keyboard shortcuts for filtering

    Bindings:
        a: Show all logs
        d: Show debug+ logs
        i: Show info+ logs
        w: Show warning+ logs
        e: Show error logs only

    Example:
        >>> panel = LogPanel()
        >>> panel.update_logs(app_state)
    """

    BINDINGS = [
        Binding("a", "filter_all", "All", show=True),
        Binding("d", "filter_debug", "Debug+", show=True),
        Binding("i", "filter_info", "Info+", show=True),
        Binding("w", "filter_warning", "Warn+", show=True),
        Binding("e", "filter_error", "Error", show=True),
    ]

    # Log level colors
    LEVEL_COLORS = {
        "DEBUG": "dim cyan",
        "INFO": "white",
        "WARNING": "yellow",
        "ERROR": "red",
    }

    # Log level filtering order
    LEVEL_ORDER = ["DEBUG", "INFO", "WARNING", "ERROR"]

    def __init__(self, **kwargs):
        """Initialize log panel."""
        super().__init__(**kwargs)
        self._filter_level = "DEBUG"  # Show all by default
        self._log_display = Static()
        self._auto_scroll = True

    def compose(self) -> ComposeResult:
        """Compose log display."""
        yield self._log_display

    def on_mount(self) -> None:
        """Set up refresh timer on mount."""
        self.set_interval(0.2, self._refresh_display)

    def _refresh_display(self) -> None:
        """Refresh the display periodically."""
        if hasattr(self.app, "state"):
            self.update_logs(self.app.state)

    def update_logs(self, state: AppState) -> None:
        """Update logs from app state.

        Args:
            state: Current application state
        """
        # Filter logs
        filtered_logs = self._filter_logs(state.logs)

        # Build display
        if not filtered_logs:
            self._log_display.update("[dim]No logs to display[/dim]")
            return

        # Render as table
        table = Table.grid(padding=(0, 1))
        table.add_column("time", width=12, style="dim")
        table.add_column("level", width=8)
        table.add_column("message", no_wrap=False)

        for entry in filtered_logs[-100:]:  # Show last 100 logs
            # Handle truncation marker
            if isinstance(entry, dict) and entry.get("truncated"):
                count = entry.get("count", 0)
                table.add_row(
                    "[dim]--:--:--[/dim]",
                    "[yellow]SKIP[/yellow]",
                    f"[dim italic]... {count} entries truncated ...[/dim italic]",
                )
            # Handle normal log entries
            elif hasattr(entry, "timestamp"):
                table.add_row(
                    self._format_timestamp(entry.timestamp),
                    self._format_level(entry.level),
                    self._format_message(entry.message),
                )

        self._log_display.update(table)

        # Auto-scroll to bottom
        if self._auto_scroll:
            self.scroll_end(animate=False)

    def _filter_logs(self, logs: list[LogEntry | dict]) -> list[LogEntry | dict]:
        """Filter logs based on current filter level.

        Args:
            logs: All log entries (LogEntry objects or truncation marker dicts)

        Returns:
            Filtered log entries
        """
        if self._filter_level == "DEBUG":
            return logs  # Show all

        # Get minimum level index
        try:
            min_index = self.LEVEL_ORDER.index(self._filter_level)
        except ValueError:
            return logs

        # Filter logs
        filtered = []
        for entry in logs:
            # Handle truncation markers
            if isinstance(entry, dict) and entry.get("truncated"):
                filtered.append(entry)
                continue

            # Handle LogEntry objects
            if hasattr(entry, "level"):
                try:
                    level_index = self.LEVEL_ORDER.index(entry.level)
                    if level_index >= min_index:
                        filtered.append(entry)
                except ValueError:
                    # Unknown level, include it
                    filtered.append(entry)

        return filtered

    def _format_timestamp(self, timestamp: float) -> str:
        """Format timestamp for display.

        Args:
            timestamp: Unix timestamp

        Returns:
            Formatted time string (HH:MM:SS)
        """
        import time

        local_time = time.localtime(timestamp)
        return time.strftime("%H:%M:%S", local_time)

    def _format_level(self, level: str) -> Text:
        """Format log level with color.

        Args:
            level: Log level string

        Returns:
            Colored text
        """
        color = self.LEVEL_COLORS.get(level, "white")
        return Text(level.ljust(7), style=color)

    def _format_message(self, message: str) -> str:
        """Format log message.

        Args:
            message: Log message

        Returns:
            Formatted message
        """
        # Truncate very long messages
        max_length = 200
        if len(message) > max_length:
            return message[: max_length - 3] + "..."
        return message

    # Action handlers for filtering

    def action_filter_all(self) -> None:
        """Show all logs."""
        self._filter_level = "DEBUG"
        self.notify("Showing all logs")

    def action_filter_debug(self) -> None:
        """Show debug+ logs."""
        self._filter_level = "DEBUG"
        self.notify("Showing debug+ logs")

    def action_filter_info(self) -> None:
        """Show info+ logs."""
        self._filter_level = "INFO"
        self.notify("Showing info+ logs")

    def action_filter_warning(self) -> None:
        """Show warning+ logs."""
        self._filter_level = "WARNING"
        self.notify("Showing warning+ logs")

    def action_filter_error(self) -> None:
        """Show error logs only."""
        self._filter_level = "ERROR"
        self.notify("Showing error logs only")
