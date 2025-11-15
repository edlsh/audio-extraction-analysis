"""Main TUI application using Textual."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Static

from ...models.events import Event, QueueEventSink
from .state import AppState
from .views.config import ConfigScreen
from .views.home import HomeScreen

logger = logging.getLogger(__name__)


class WelcomeScreen(Static):
    """Welcome screen with basic information."""

    def compose(self) -> ComposeResult:
        """Compose the welcome screen."""
        yield Container(
            Label("🎵 Audio Extraction & Transcription Analysis", id="title"),
            Label(""),
            Label("Welcome to the interactive TUI!", classes="welcome-text"),
            Label(""),
            Label(
                "This interface provides live progress updates, "
                "provider health checks, and artifact management.",
                classes="welcome-text",
            ),
            Label(""),
            Horizontal(
                Button("Start Processing", variant="primary", id="start-btn"),
                Button("Exit", variant="error", id="exit-btn"),
                classes="button-row",
            ),
            id="welcome-container",
        )


class AudioExtractionApp(App):
    """Main TUI application for audio extraction and transcription.

    Provides an interactive interface with live progress updates via event streaming.
    """

    SCREENS = {
        "home": HomeScreen,
        "config": ConfigScreen,
    }

    CSS = """
    Screen {
        background: $surface;
    }

    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1;
    }

    .welcome-text {
        text-align: center;
        padding: 0 2;
    }

    #welcome-container {
        align: center middle;
        width: 100%;
        height: 100%;
    }

    .button-row {
        align: center middle;
        width: auto;
        height: auto;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]

    def __init__(
        self,
        input_path: str | None = None,
        output_dir: str | None = None,
    ):
        """Initialize the TUI application.

        Args:
            input_path: Optional pre-populated input file path
            output_dir: Optional pre-populated output directory
        """
        super().__init__()
        self.state = AppState(
            input_path=Path(input_path) if input_path else None,
            output_dir=Path(output_dir) if output_dir else None,
        )
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.event_sink = QueueEventSink(self.event_queue)
        self.pipeline_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        """Compose the main UI layout."""
        yield Header()
        yield WelcomeScreen()
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "exit-btn":
            self.exit()
        elif event.button.id == "start-btn":
            # Navigate to home screen for file selection
            self.push_screen("home")

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark

    async def _run_pipeline(self) -> None:
        """Run the pipeline with event streaming.

        This method will be fully implemented once the TUI views are complete.
        It will:
        1. Set up event sink
        2. Launch pipeline in background
        3. Consume events from queue
        4. Update UI in real-time
        """
        from ...models.events import set_event_sink
        from ...pipeline.simple_pipeline import process_pipeline

        # Set event sink for this thread
        set_event_sink(self.event_sink)

        try:
            # Run pipeline
            result = await process_pipeline(
                input_path=self.state.input_path,
                output_dir=self.state.output_dir,
                quality=self.state.quality,  # type: ignore
                language=self.state.language,
                provider=self.state.provider,
                analysis_style=self.state.analysis_style,
                console_manager=None,  # Disable console output in TUI mode
            )

            # Update state with results
            self.state.summary = result

        except Exception as e:
            logger.exception("Pipeline error: %s", e)
            self.state.errors.append(str(e))

    async def _consume_events(self) -> None:
        """Consume events from the queue and update UI.

        This background task processes events emitted by the pipeline.
        """
        while True:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=0.1)

                # Update state based on event type
                if event.type == "stage_start":
                    self.state.current_stage = event.stage
                    self.state.current_message = event.data.get("description", "")
                    self.state.current_progress = 0.0

                elif event.type == "stage_progress":
                    completed = event.data.get("completed", 0)
                    total = event.data.get("total", 100)
                    self.state.current_progress = (completed / total) * 100

                elif event.type == "stage_end":
                    self.state.current_stage = None
                    self.state.current_progress = 0.0

                elif event.type == "artifact":
                    self.state.artifacts.append(event.data)

                elif event.type == "error":
                    self.state.errors.append(event.data.get("message", "Unknown error"))

                elif event.type == "summary":
                    self.state.summary = event.data

                elif event.type == "cancelled":
                    self.state.is_running = False
                    break

            except asyncio.TimeoutError:
                # No event available, continue
                continue
            except Exception as e:
                logger.exception("Error consuming event: %s", e)
                continue


def main() -> None:
    """Main entry point for standalone TUI execution."""
    app = AudioExtractionApp()
    app.run()


if __name__ == "__main__":
    main()
