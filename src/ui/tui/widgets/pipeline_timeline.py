"""Horizontal pipeline timeline widget showing all stages.

Displays a connected timeline of all pipeline stages with visual state
indicators (pending, running, complete, error) and compact status info.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

if TYPE_CHECKING:
    from ..state import AppState


class TimelineNode(Static):
    """A single node in the pipeline timeline.

    Displays a stage icon/indicator with name and compact status below.
    Supports states: pending, running, complete, error, skipped.
    """

    DEFAULT_CSS = """
    TimelineNode {
        width: 1fr;
        height: auto;
        min-height: 5;
        content-align: center middle;
        padding: 0;
    }

    TimelineNode .node-indicator {
        width: 100%;
        height: 1;
        text-align: center;
        text-style: bold;
    }

    TimelineNode .node-name {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text;
    }

    TimelineNode .node-status {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-disabled;
    }

    TimelineNode.pending .node-indicator {
        color: $text-disabled;
    }

    TimelineNode.running .node-indicator {
        color: $accent;
    }

    TimelineNode.complete .node-indicator {
        color: $success;
    }

    TimelineNode.error .node-indicator {
        color: $error;
    }

    TimelineNode.skipped .node-indicator {
        color: $text-disabled;
    }

    TimelineNode.skipped .node-name {
        color: $text-disabled;
        text-style: italic;
    }
    """

    # Reactive state
    status: reactive[str] = reactive("pending")
    duration: reactive[float] = reactive(0.0)

    # Status indicators
    INDICATORS = {
        "pending": "○",
        "running": "◉",
        "complete": "●",
        "error": "✗",
        "skipped": "⊘",
    }

    def __init__(
        self,
        stage_id: str,
        stage_name: str,
        stage_icon: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize timeline node.

        Args:
            stage_id: Stage identifier (e.g., "extract")
            stage_name: Display name (e.g., "Extract")
            stage_icon: Optional icon for the stage
        """
        super().__init__(*args, **kwargs)
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.stage_icon = stage_icon

    def compose(self) -> ComposeResult:
        """Compose the node layout."""
        yield Label(self.INDICATORS["pending"], classes="node-indicator")
        yield Label(self.stage_name, classes="node-name")
        yield Label("", classes="node-status")

    def on_mount(self) -> None:
        """Set initial state on mount."""
        self.add_class("pending")
        self._update_display()

    def watch_status(self, old_status: str, new_status: str) -> None:
        """React to status changes with visual updates."""
        # Remove old status class
        self.remove_class("pending", "running", "complete", "error", "skipped")
        # Add new status class
        self.add_class(new_status)

        # Update indicator
        self._update_display()

        # Flash effect for fast completions
        if old_status == "running" and new_status == "complete":
            if self.duration > 0 and self.duration < 1.0:
                self.add_class("flash-complete")
                self.set_timer(0.5, lambda: self.remove_class("flash-complete"))

    def watch_duration(self, duration: float) -> None:
        """React to duration changes."""
        self._update_display()

    def _update_display(self) -> None:
        """Update the visual display based on current state."""
        try:
            indicator = self.query_one(".node-indicator", Label)
            status_label = self.query_one(".node-status", Label)

            # Update indicator symbol
            indicator.update(self.INDICATORS.get(self.status, "○"))

            # Update status text
            if self.status == "pending":
                status_label.update("[dim]Pending[/dim]")
            elif self.status == "running":
                status_label.update("[cyan]Running[/cyan]")
            elif self.status == "complete":
                if self.duration > 0:
                    status_label.update(f"[green]✓ {self.duration:.1f}s[/green]")
                else:
                    status_label.update("[green]✓ Done[/green]")
            elif self.status == "error":
                status_label.update("[red]✗ Error[/red]")
            elif self.status == "skipped":
                status_label.update("[dim]Skipped[/dim]")
        except Exception:
            pass  # Widget not yet mounted


class TimelineConnector(Static):
    """Connector line between timeline nodes."""

    DEFAULT_CSS = """
    TimelineConnector {
        width: 3;
        height: 5;
        content-align: center middle;
    }

    TimelineConnector .connector-line {
        width: 100%;
        height: 1;
        background: $panel-darken-2;
        margin-top: 0;
    }

    TimelineConnector.complete .connector-line {
        background: $success;
    }

    TimelineConnector.active .connector-line {
        background: $accent;
    }
    """

    status: reactive[str] = reactive("pending")

    def compose(self) -> ComposeResult:
        """Compose the connector."""
        yield Static("───", classes="connector-line")

    def watch_status(self, status: str) -> None:
        """Update connector appearance based on status."""
        self.remove_class("pending", "complete", "active")
        if status == "complete":
            self.add_class("complete")
        elif status == "active":
            self.add_class("active")


class PipelineTimeline(Widget):
    """Horizontal timeline showing all pipeline stages.

    Displays a connected series of nodes representing each pipeline stage,
    with visual indicators for pending, running, complete, and error states.

    Example:
        >>> timeline = PipelineTimeline()
        >>> timeline.update_from_state(app_state)
    """

    DEFAULT_CSS = """
    PipelineTimeline {
        width: 100%;
        height: 5;
        layout: horizontal;
        align: center middle;
        padding: 0 1;
        background: $panel;
        border: solid $primary-darken-2;
    }
    """

    # Stage definitions: (id, name, icon)
    STAGES = [
        ("url_download", "Download", "⬇"),
        ("url_prepare", "Prepare", "🔧"),
        ("extract", "Extract", "🎵"),
        ("transcribe", "Transcribe", "📝"),
        ("analyze", "Analyze", "📊"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize pipeline timeline."""
        super().__init__(*args, **kwargs)
        self._stage_nodes: dict[str, TimelineNode] = {}
        self._stage_connectors: list[TimelineConnector] = []

    def compose(self) -> ComposeResult:
        """Compose the timeline layout."""
        with Horizontal():
            for i, (stage_id, stage_name, stage_icon) in enumerate(self.STAGES):
                # Add node
                node = TimelineNode(
                    stage_id=stage_id,
                    stage_name=stage_name,
                    stage_icon=stage_icon,
                    id=f"node-{stage_id}",
                )
                self._stage_nodes[stage_id] = node
                yield node

                # Add connector between nodes (except after last)
                if i < len(self.STAGES) - 1:
                    connector = TimelineConnector(id=f"connector-{i}")
                    self._stage_connectors.append(connector)
                    yield connector

    def update_from_state(self, state: AppState) -> None:
        """Update timeline from application state.

        Args:
            state: Current application state
        """
        prev_complete = True  # Track if previous stages are complete

        for i, (stage_id, _, _) in enumerate(self.STAGES):
            node = self._stage_nodes.get(stage_id)
            if not node:
                continue

            # Determine status
            status = state.stage_status.get(stage_id, "pending")

            # Handle skipped stages (URL stages when using local file)
            if stage_id in ("url_download", "url_prepare"):
                if state.input_path and not state.stage_status.get(stage_id):
                    # Local file - URL stages are skipped
                    status = "skipped"

            # Fallback status determination
            if not status or status not in ("pending", "running", "complete", "error", "skipped"):
                if state.current_stage == stage_id:
                    status = "running"
                elif stage_id in state.stage_durations:
                    status = "complete"
                else:
                    status = "pending"

            # Update node
            node.status = status
            node.duration = state.stage_durations.get(stage_id, 0.0)

            # Update connector to this node
            if i > 0 and i - 1 < len(self._stage_connectors):
                connector = self._stage_connectors[i - 1]
                if status in ("complete", "error"):
                    connector.status = "complete"
                elif status == "running":
                    connector.status = "active"
                elif prev_complete:
                    connector.status = "complete"
                else:
                    connector.status = "pending"

            # Track completion for connector logic
            prev_complete = status == "complete"

    def reset(self) -> None:
        """Reset all nodes to pending state."""
        for node in self._stage_nodes.values():
            node.status = "pending"
            node.duration = 0.0
        for connector in self._stage_connectors:
            connector.status = "pending"
