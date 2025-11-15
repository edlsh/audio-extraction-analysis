"""Run screen - displays live pipeline progress and logs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from ..events import EventConsumer, EventConsumerConfig
from ..services import run_pipeline
from ..widgets import LogPanel, ProgressBoard

if TYPE_CHECKING:
    from ..state import AppState


class RunScreen(Screen):
    """Screen for running the pipeline with live progress.

    Features:
    - Progress board showing extraction, transcription, analysis
    - Scrollable log panel with filtering
    - Cancel button to stop pipeline
    - Auto-opens output on completion

    Layout:
        ┌─────────────────────────────────┐
        │ Header                          │
        ├─────────────────────────────────┤
        │ Progress Board (30%)            │
        │  ┌───────┐ ┌───────┐ ┌───────┐ │
        │  │Extract│ │Trans- │ │Analyze│ │
        │  │       │ │cribe  │ │       │ │
        │  └───────┘ └───────┘ └───────┘ │
        ├─────────────────────────────────┤
        │ Logs (60%)                      │
        │  [filterable scrolling logs]    │
        ├─────────────────────────────────┤
        │ Controls (10%)                  │
        │  [Cancel] [Open Output]         │
        ├─────────────────────────────────┤
        │ Footer                          │
        └─────────────────────────────────┘

    Args:
        input_file: Path to input audio/video file
        config: Pipeline configuration dictionary

    Example:
        >>> app.push_screen(RunScreen("/path/to/audio.mp3", config_dict))
    """

    BINDINGS = [
        Binding("c", "cancel", "Cancel", show=True),
        Binding("o", "open_output", "Open Output", show=True),
        Binding("escape", "back", "Back", show=False),
    ]

    CSS = """
    RunScreen {
        layout: vertical;
    }

    #progress-container {
        height: 30%;
        border: solid $accent;
        padding: 1;
    }

    #log-container {
        height: 60%;
        border: solid $panel;
        padding: 1;
    }

    #controls-container {
        height: 10%;
        align: center middle;
        padding: 1;
    }

    #status-panel {
        width: 100%;
        height: 100%;
    }

    .button-row {
        width: auto;
        height: auto;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, input_file: str | Path | None = None, config: dict | None = None, **kwargs):
        """Initialize run screen.

        Args:
            input_file: Path to input file
            config: Pipeline configuration
            **kwargs: Additional screen arguments
        """
        super().__init__(**kwargs)
        self.input_file = Path(input_file) if input_file else None
        self.config = dict(config) if config else None
        self._event_consumer: EventConsumer | None = None
        self._pipeline_task: asyncio.Task | None = None
        self._monitor_task: asyncio.Task | None = None
        self._consume_task: asyncio.Task | None = None
        self._running = False
        self._output_dir: Path | None = None

    def compose(self) -> ComposeResult:
        """Compose the run screen layout."""
        yield Header()

        # Progress board container
        with Container(id="progress-container"):
            yield ProgressBoard(id="progress-board")

        # Log panel container
        with Container(id="log-container"):
            yield LogPanel(id="log-panel")

        # Controls container
        with Container(id="controls-container"):
            with Horizontal(classes="button-row"):
                yield Button("Cancel", variant="error", id="cancel-btn")
                yield Button("Open Output", variant="success", id="output-btn", disabled=True)

        yield Footer()

    def on_mount(self) -> None:
        """Start pipeline when screen mounts."""
        # Start pipeline after mount
        self.app.call_later(self._start_pipeline_async)

    def _start_pipeline_async(self) -> None:
        """Create async task to start pipeline."""
        asyncio.create_task(self._start_pipeline())

    async def _start_pipeline(self) -> None:
        """Start the pipeline in background."""
        import uuid
        from ..state import apply_event

        self._ensure_runtime_context()
        self._running = True

        consumer_config = EventConsumerConfig()
        event_queue = EventConsumer.create_queue(consumer_config)

        # Define batch handler to update app state
        def handle_batch(events: list) -> None:
            """Process batch of events and update app state."""
            for event in events:
                self.app.state = apply_event(self.app.state, event)
            # Update UI after processing batch
            self.app.call_from_thread(self._update_display)

        # Initialize event consumer with queue and handler
        self._event_consumer = EventConsumer(
            queue=event_queue,
            on_batch=handle_batch,
            config=consumer_config,
        )

        # Generate run ID
        run_id = str(uuid.uuid4())
        self.app.state.run_id = run_id

        # Create pipeline task with correct parameters
        self._pipeline_task = asyncio.create_task(
            self._run_pipeline_with_events(event_queue, run_id)
        )

        # Start event consumer
        self._consume_task = asyncio.create_task(self._event_consumer.run())

        # Monitor pipeline completion
        self._monitor_task = asyncio.create_task(self._monitor_pipeline())

    async def _run_pipeline_with_events(self, event_queue: asyncio.Queue, run_id: str) -> None:
        """Run pipeline and feed events to consumer.

        Args:
            event_queue: Queue to send events to
            run_id: Unique run identifier
        """
        from src.models.events import QueueEventSink

        try:
            # Create event sink for the queue
            event_sink = QueueEventSink(event_queue)

            # Run pipeline with correct parameters
            result = await run_pipeline(
                input_path=self.input_file,
                output_dir=Path(self.config["output_dir"]),
                quality=self.config.get("quality", "speech"),
                language=self.config.get("language", "en"),
                provider=self.config.get("provider", "auto"),
                analysis_style=self.config.get("analysis_style", "concise"),
                event_sink=event_sink,
                run_id=run_id,
            )

            # Store output directory from result
            self._output_dir = Path(self.config["output_dir"])

        except asyncio.CancelledError:
            # Pipeline was cancelled
            self.notify("Pipeline cancelled", severity="warning")
            raise
        except Exception as e:
            # Pipeline error
            self.notify(f"Pipeline failed: {e}", severity="error")
            self._running = False
        else:
            # Pipeline completed successfully
            self._running = False
            self.notify("Pipeline completed!", severity="information")

            # Enable output button
            output_btn = self.query_one("#output-btn", Button)
            output_btn.disabled = False

    async def _monitor_pipeline(self) -> None:
        """Monitor pipeline and update UI."""
        # Wait for pipeline to finish
        if self._pipeline_task:
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass

        # Stop event consumer
        if self._event_consumer:
            await self._event_consumer.stop()
        if self._consume_task:
            await self._consume_task

        # Update UI one final time
        self._update_display()

    def _update_display(self) -> None:
        """Update progress board and logs from app state."""
        # Update progress board
        progress_board = self.query_one("#progress-board", ProgressBoard)
        progress_board.update_display(self.app.state)

        # Update log panel
        log_panel = self.query_one("#log-panel", LogPanel)
        log_panel.update_logs(self.app.state)

    # Button handlers

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "cancel-btn":
            await self.action_cancel()
        elif event.button.id == "output-btn":
            await self.action_open_output()

    # Actions

    async def action_cancel(self) -> None:
        """Cancel the running pipeline."""
        if not self._running:
            self.notify("Pipeline is not running", severity="warning")
            return

        # Cancel pipeline task
        if self._pipeline_task:
            self._pipeline_task.cancel()
            self._running = False
            self.notify("Cancelling pipeline...", severity="warning")

        # Disable cancel button
        cancel_btn = self.query_one("#cancel-btn", Button)
        cancel_btn.disabled = True

    async def action_open_output(self) -> None:
        """Open output directory."""
        if not self._output_dir or not self._output_dir.exists():
            self.notify("Output directory not found", severity="error")
            return

        # Import open_path service
        from ..services import open_path

        try:
            # open_path is sync, no await needed
            open_path(str(self._output_dir))
            self.notify(f"Opened {self._output_dir}", severity="information")
        except Exception as e:
            self.notify(f"Failed to open output: {e}", severity="error")

    def action_back(self) -> None:
        """Go back to previous screen."""
        if self._running:
            self.notify("Please cancel pipeline first", severity="warning")
            return

        self.app.pop_screen()

    def _ensure_runtime_context(self) -> None:
        """Ensure the run screen has input and config before starting."""
        if self.input_file is None:
            if self.app.state.input_path is None:
                raise RuntimeError("No input file available for RunScreen")
            self.input_file = Path(self.app.state.input_path)

        if self.config is None:
            config = getattr(self.app.state, "pending_run_config", None)
            if config is None:
                raise RuntimeError("No pipeline configuration available for RunScreen")
            self.config = dict(config)
            self.app.state.pending_run_config = None
