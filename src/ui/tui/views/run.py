"""Run screen - displays live pipeline progress and logs."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from rich.panel import Panel
from textual._context import active_app
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

from src.exceptions import AudioAnalysisError

from ..events import EventConsumer, EventConsumerConfig
from ..services import open_path, run_pipeline
from ..widgets import LogPanel, ProgressBoard

if TYPE_CHECKING:
    from ..app import AudioExtractionApp
    from ..state import AppState


class RunScreen(Screen):
    """Screen for running the pipeline with live progress.

    Features:
    - Pipeline timeline showing all 5 stages at a glance
    - Focus card for the currently active stage
    - Completed stages summary row
    - Scrollable log panel with filtering
    - Cancel button to stop pipeline
    - Auto-opens output on completion

    Layout:
        ┌─────────────────────────────────────────┐
        │ Header                                   │
        ├─────────────────────────────────────────┤
        │ Pipeline Timeline (horizontal)           │
        │ ●───●───●───○───○                        │
        │ DL  Prep Ext  Trans Analyze              │
        ├─────────────────────────────────────────┤
        │ Focus Card (active stage)                │
        │  ⚡ Extracting Audio            72%     │
        │  ████████████████░░░░░  ETA: 00:45      │
        ├─────────────────────────────────────────┤
        │ Completed: ✓ Download • ✓ Prepare        │
        ├─────────────────────────────────────────┤
        │ Logs (scrollable)                        │
        │  [filterable scrolling logs]             │
        ├─────────────────────────────────────────┤
        │ [Cancel] [Open Output]                   │
        ├─────────────────────────────────────────┤
        │ Footer                                   │
        └─────────────────────────────────────────┘

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
        height: auto;
        min-height: 18;
        max-height: 50%;
        border: solid $accent;
        padding: 1;
        overflow: hidden;
    }

    #log-container {
        height: 1fr;
        min-height: 8;
        border: solid $panel;
        padding: 0;
        overflow: hidden;
    }

    #log-container LogPanel {
        height: 100%;
        width: 100%;
    }

    #status-container {
        height: 3;
        padding: 0 1;
    }

    #controls-container {
        height: 5;
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
        self._app_override: AudioExtractionApp | None = None

    @property
    def app(self) -> AudioExtractionApp:
        if self._app_override is not None:
            return self._app_override
        return cast("AudioExtractionApp", super().app)

    @app.setter
    def app(self, value: AudioExtractionApp) -> None:
        self._app_override = value
        active_app.set(value)

    def compose(self) -> ComposeResult:
        """Compose the run screen layout."""
        yield Header()

        yield Container(ProgressBoard(id="progress-board"), id="progress-container")

        yield Container(LogPanel(id="log-panel"), id="log-container")

        yield Container(Static("", id="status-panel"), id="status-container")

        controls = Horizontal(
            Button("Cancel", variant="error", id="cancel-btn"),
            Button("Open Output", variant="success", id="output-btn", disabled=True),
            classes="button-row",
        )
        yield Container(controls, id="controls-container")

        yield Footer()

    def on_mount(self) -> None:
        """Start pipeline when screen mounts."""
        # Start pipeline after mount
        self.app.call_later(self._start_pipeline_async)

    def _start_pipeline_async(self) -> None:
        """Create async task to start pipeline."""
        self._pipeline_task = asyncio.create_task(self._start_pipeline())

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
            # Update UI after processing batch - use call_later since we're in same event loop
            self.app.call_later(self._update_display)

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

    async def _run_pipeline_with_events(
        self,
        event_queue: asyncio.Queue | None = None,
        run_id: str | None = None,
    ) -> None:
        """Run pipeline and feed events to consumer.

        Args:
            event_queue: Queue to send events to
            run_id: Unique run identifier
        """
        import uuid

        from src.exceptions import AudioAnalysisError
        from src.models.events import QueueEventSink

        try:
            self._ensure_runtime_context()
            queue = event_queue or asyncio.Queue()
            run_identifier = run_id or getattr(self.app.state, "run_id", None) or str(uuid.uuid4())

            # Create event sink for the queue
            event_sink = QueueEventSink(queue)

            # Run pipeline with correct parameters
            await run_pipeline(
                input_path=self.input_file,
                output_dir=Path(self.config["output_dir"]),
                quality=self.config.get("quality", "speech"),
                language=self.config.get("language", "en"),
                provider=self.config.get("provider", "auto"),
                analysis_style=self.config.get("analysis_style", "concise"),
                event_sink=event_sink,
                run_id=run_identifier,
                url=self.config.get("url"),
                keep_downloaded_videos=self.config.get("keep_downloaded_videos"),
            )

            # Store output directory from result
            self._output_dir = Path(self.config["output_dir"])

        except asyncio.CancelledError:
            # Pipeline was cancelled
            self.notify("Pipeline cancelled", severity="warning")
            raise
        except (AudioAnalysisError, ValueError) as e:
            # Pipeline error
            self.notify(f"Pipeline failed: {e}", severity="error")
            self._running = False
            raise
        except Exception:
            self.notify("Pipeline failed: unexpected error", severity="error")
            self._running = False
            raise
        else:
            # Pipeline completed successfully
            self._running = False
            self.notify("Pipeline completed!", severity="information")

            # Enable output button
            output_btn = self._get_button("#output-btn")
            if output_btn:
                output_btn.disabled = False

    async def _monitor_pipeline(self) -> None:
        """Monitor pipeline and update UI."""
        # Wait for pipeline to finish
        if self._pipeline_task:
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass
            except (AudioAnalysisError, ValueError):
                pass

        # Stop event consumer
        if self._event_consumer:
            await self._event_consumer.stop()
        if self._consume_task:
            await self._consume_task
        self._consume_task = None
        self._event_consumer = None

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

        # Update status line
        status_panel = self.query_one("#status-panel", Static)
        status_panel.update(self._render_status_line())

    def _render_status_line(self) -> str:
        """Render a compact status line with current stage and ETA."""

        state: AppState = self.app.state  # type: ignore[assignment]
        if state.current_stage:
            eta = self._compute_eta(state)
            msg = state.current_message or state.stage_messages.get(state.current_stage, "")
            message_part = f" - {msg}" if msg else ""
            eta_part = f" (ETA {eta})" if eta != "--:--" else ""
            return f"[bold]{state.current_stage.title()}[/bold]{message_part}{eta_part}"

        if state.summary:
            return "[green]Completed[/green]"

        if state.errors:
            return f"[red]{state.errors[-1]}[/red]"

        return "[dim]Idle[/dim]"

    def _compute_eta(self, state: AppState) -> str:
        """Compute ETA for the currently running stage."""

        stage = state.current_stage
        if not stage:
            return "--:--"

        completed = state.stage_completed.get(stage, 0)
        total = state.stage_totals.get(stage, 0)
        if completed <= 0 or total <= 0:
            return "--:--"

        started_at = state.stage_started_at.get(stage)
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

    def _get_button(self, selector: str) -> Button | None:
        """Return a button if present in the DOM."""

        try:
            return self.query_one(selector, Button)
        except NoMatches:
            return None

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
        cancel_btn = self._get_button("#cancel-btn")
        if cancel_btn:
            cancel_btn.disabled = True

    async def action_open_output(self) -> None:
        """Open output directory."""
        output_dir = self._output_dir
        if not output_dir or not output_dir.exists():
            self.notify("Output directory not found", severity="error")
            return

        try:
            # open_path is sync, no await needed
            opened = open_path(output_dir)
            if opened:
                self.notify(f"Opened {output_dir}", severity="information")
            else:
                self.notify("Failed to open output folder", severity="error")
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
        if self.config is None:
            config = getattr(self.app.state, "pending_run_config", None)
            if config is None:
                raise RuntimeError("No pipeline configuration available for RunScreen")
            self.config = dict(config)
            self.app.state.pending_run_config = None

        url_value = self.config.get("url") if self.config else None

        if self.input_file is None:
            if self.app.state.input_path is None and not url_value:
                raise RuntimeError("No input file or URL available for RunScreen")
            if self.app.state.input_path is not None:
                self.input_file = Path(self.app.state.input_path)
