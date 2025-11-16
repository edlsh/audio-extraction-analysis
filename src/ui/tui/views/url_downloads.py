"""URL Downloads screen for TUI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from ..app import AudioExtractionApp


class UrlDownloadsScreen(Screen):
    """Simple screen that lets the user paste a media URL.

    On submit, stores the URL in app state and routes to the config screen,
    reusing the existing configuration and run flow.
    """

    BINDINGS = [
        ("enter", "start_from_url", "Start from URL"),
        ("escape", "back", "Back"),
    ]

    CSS = """
    UrlDownloadsScreen {
        layout: vertical;
    }

    #url-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $accent;
    }

    #url-container {
        height: 1fr;
        padding: 2;
    }

    #url-input {
        width: 1fr;
        margin-top: 1;
    }

    #url-buttons {
        margin-top: 2;
        width: auto;
        height: auto;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
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

    def compose(self) -> ComposeResult:  # pragma: no cover - Textual composition
        yield Header()
        yield Label("Process Media from URL", id="url-title")

        yield Container(
            Vertical(
                Label(
                    "Paste a single video URL (YouTube or similar).",
                    id="url-help",
                ),
                Input(
                    placeholder="https://example.com/video",
                    id="url-input",
                ),
                Container(
                    Button("Start", variant="primary", id="start-url-btn"),
                    Button("Back", variant="default", id="back-btn"),
                    id="url-buttons",
                ),
                id="url-vertical",
            ),
            id="url-container",
        )

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "start-url-btn":
            self.action_start_from_url()
        elif event.button.id == "back-btn":
            self.action_back()

    def action_start_from_url(self) -> None:
        url_input = self.query_one("#url-input", Input)
        url = url_input.value.strip()

        if not url:
            self.notify("Please enter a URL.", severity="warning")
            return

        # Lightweight validation: must at least look like a URL
        if not (url.startswith("http://") or url.startswith("https://")):
            self.notify("URL must start with http:// or https://", severity="error")
            return

        # Store URL on app state; the run service will interpret it
        # and use URL ingestion rather than a local file.
        self.app.state.input_path = None
        if self.app.state.pending_run_config is None:
            self.app.state.pending_run_config = {}
        self.app.state.pending_run_config["url"] = url

        # Proceed to config screen to reuse all settings and then run
        self.app.push_screen("config")

    def action_back(self) -> None:
        self.app.pop_screen()
