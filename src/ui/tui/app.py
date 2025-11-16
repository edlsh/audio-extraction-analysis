"""Main TUI application using Textual."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen as TextualScreen
from textual.widgets import Button, Footer, Header, Label

from ...models.events import Event, QueueEventSink
from .persistence import load_settings, save_settings
from .state import AppState
from .themes import CUSTOM_THEMES, DEFAULT_CUSTOM_THEME
from .views.config import ConfigScreen
from .views.help import HelpScreen
from .views.home import HomeScreen
from .views.run import RunScreen
from .views.theme_selector import ThemeSelectorScreen
from .views.url_downloads import UrlDownloadsScreen

logger = logging.getLogger(__name__)


class WelcomeScreen(TextualScreen):
    """Welcome screen with basic information."""

    def compose(self) -> ComposeResult:
        """Compose the welcome screen."""
        yield Header()
        yield Container(
            Label("🎵 Audio Extraction & Transcription Analysis", id="title"),
            Label(""),
            Label("Welcome to the interactive TUI!", classes="welcome-text"),
            Label(""),
            Label(
                "Transform audio/video files into analyzed transcripts with ease.",
                classes="welcome-text",
            ),
            Label(""),
            Label("[dim]Features:[/dim]", classes="welcome-text"),
            Label(
                "  • Live progress monitoring with ETAs",
                classes="welcome-text feature-item",
            ),
            Label(
                "  • Real-time log streaming and filtering",
                classes="welcome-text feature-item",
            ),
            Label(
                "  • Multiple transcription providers (Deepgram, ElevenLabs, Whisper, Parakeet)",
                classes="welcome-text feature-item",
            ),
            Label(
                "  • Provider health monitoring",
                classes="welcome-text feature-item",
            ),
            Label(
                "  • Auto-save configuration and recent files",
                classes="welcome-text feature-item",
            ),
            Label(""),
            Label("[dim]Press 'h' or '?' anytime for help[/dim]", classes="welcome-text"),
            Label(""),
            Horizontal(
                Button(
                    "Start Processing",
                    variant="primary",
                    id="start-btn",
                ),
                Button(
                    "Help",
                    variant="default",
                    id="help-btn",
                ),
                Button(
                    "Exit",
                    variant="error",
                    id="exit-btn",
                ),
                classes="button-row",
            ),
            id="welcome-container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events on the welcome screen."""
        if event.button.id == "exit-btn":
            self.app.exit()
        elif event.button.id == "start-btn":
            self.app.push_screen("home")
        elif event.button.id == "help-btn":
            self.app.push_screen("help")


class AudioExtractionApp(App):
    """Main TUI application for audio extraction and transcription.

    Provides an interactive interface with live progress updates via event streaming.
    """

    SCREENS = {
        "welcome": WelcomeScreen,
        "home": HomeScreen,
        "config": ConfigScreen,
        "help": HelpScreen,
        "run": RunScreen,
        "theme_selector": ThemeSelectorScreen,
        "url_downloads": UrlDownloadsScreen,
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
        ("t", "show_theme_selector", "Switch Theme"),
        ("d", "show_theme_selector", "Switch Theme"),  # Keep 'd' for backwards compatibility
        ("h", "help", "Help"),
        ("?", "help", "Help"),
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
        # Load settings to determine initial theme
        self.settings = load_settings()
        saved_theme = self.settings.get("ui", {}).get("theme", DEFAULT_CUSTOM_THEME)
        
        # Initialize parent
        super().__init__()
        
        # Register custom themes
        for theme in CUSTOM_THEMES:
            self.register_theme(theme)
        
        # Set theme based on settings
        # For backwards compatibility, map old theme names
        if saved_theme == "dark":
            self.theme = DEFAULT_CUSTOM_THEME
        elif saved_theme == "light":
            self.theme = "audio-extraction-light"
        elif saved_theme in [t.name for t in CUSTOM_THEMES]:
            self.theme = saved_theme
        elif saved_theme in self.available_themes:
            self.theme = saved_theme
        else:
            self.theme = DEFAULT_CUSTOM_THEME
        
        self.state = AppState(
            input_path=Path(input_path) if input_path else None,
            output_dir=Path(output_dir) if output_dir else None,
        )
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.event_sink = QueueEventSink(self.event_queue)
        self.pipeline_task: asyncio.Task | None = None

    def on_mount(self) -> None:
        """Push the welcome screen when the app starts."""
        self.push_screen("welcome")

    def action_show_theme_selector(self) -> None:
        """Show theme selection screen."""
        # Check if theme selector is already in the stack
        for screen in self.screen_stack:
            if isinstance(screen, ThemeSelectorScreen):
                # Already showing theme selector, don't push another
                return
        
        # Push theme selector screen
        self.push_screen("theme_selector")

    def action_help(self) -> None:
        """Show help screen."""
        stack_help = next(
            (screen for screen in self.screen_stack if isinstance(screen, HelpScreen)), None
        )
        if stack_help is self.screen:
            return
        if stack_help is not None:
            self.switch_screen("help")
            return
        self.push_screen("help")

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
