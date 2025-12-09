"""Settings screen for API key configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

from src.utils.logger import get_logger

from ..persistence import load_api_keys, save_api_key

if TYPE_CHECKING:
    from ..app import AudioExtractionApp

logger = get_logger(__name__)


class SettingsScreen(Screen):
    """Settings screen for configuring API keys.

    Features:
    - Password-masked input fields for each provider's API key
    - Visual feedback showing which keys are configured
    - Save individual keys with success notification
    - Keys are persisted to user config directory

    Bindings:
    - Esc: Back to previous screen
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    CSS = """
    SettingsScreen {
        layout: vertical;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $panel;
        color: $accent;
        height: auto;
    }

    #settings-form {
        height: 1fr;
        padding: 1 2;
    }

    .settings-section {
        margin: 1 0;
        padding: 1;
        border: solid $primary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .api-key-group {
        margin: 1 0;
        min-height: 5;
    }

    .api-key-label {
        margin-bottom: 0;
    }

    .api-key-help {
        color: $text-muted;
        margin-bottom: 1;
    }

    .key-status {
        margin-left: 1;
    }

    Input {
        margin-bottom: 1;
        width: 100%;
    }

    #button-row {
        dock: bottom;
        height: 3;
        padding: 0 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        """Initialize settings screen."""
        super().__init__()
        self._app_override: AudioExtractionApp | None = None
        self.api_keys = load_api_keys()

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
        """Compose the settings screen layout."""
        yield Header()
        yield Label("⚙️ Settings", id="settings-title")

        # API Keys section
        api_keys_section = Vertical(
            Label("API Keys", classes="section-title"),
            Label(
                "[dim]Configure API keys for transcription providers. "
                "Keys are stored locally in your config directory.[/dim]"
            ),
            # Deepgram
            Vertical(
                Horizontal(
                    Label("Deepgram API Key", classes="api-key-label"),
                    Static(
                        (
                            "[green]✓ Configured[/green]"
                            if self.api_keys.get("deepgram")
                            else "[dim]Not set[/dim]"
                        ),
                        id="deepgram-status",
                        classes="key-status",
                    ),
                ),
                Label("[dim]Get from console.deepgram.com[/dim]", classes="api-key-help"),
                Input(
                    placeholder="dg-xxxxxxxx...",
                    password=True,
                    value=self.api_keys.get("deepgram", ""),
                    id="deepgram-key-input",
                ),
                classes="api-key-group",
            ),
            # ElevenLabs
            Vertical(
                Horizontal(
                    Label("ElevenLabs API Key", classes="api-key-label"),
                    Static(
                        (
                            "[green]✓ Configured[/green]"
                            if self.api_keys.get("elevenlabs")
                            else "[dim]Not set[/dim]"
                        ),
                        id="elevenlabs-status",
                        classes="key-status",
                    ),
                ),
                Label("[dim]Get from elevenlabs.io/app/settings[/dim]", classes="api-key-help"),
                Input(
                    placeholder="sk-xxxxxxxx...",
                    password=True,
                    value=self.api_keys.get("elevenlabs", ""),
                    id="elevenlabs-key-input",
                ),
                classes="api-key-group",
            ),
            # Gemini
            Vertical(
                Horizontal(
                    Label("Gemini API Key", classes="api-key-label"),
                    Static(
                        (
                            "[green]✓ Configured[/green]"
                            if self.api_keys.get("gemini")
                            else "[dim]Not set[/dim]"
                        ),
                        id="gemini-status",
                        classes="key-status",
                    ),
                ),
                Label("[dim]Get from aistudio.google.com[/dim]", classes="api-key-help"),
                Input(
                    placeholder="AIza...",
                    password=True,
                    value=self.api_keys.get("gemini", ""),
                    id="gemini-key-input",
                ),
                classes="api-key-group",
            ),
            classes="settings-section",
        )

        yield VerticalScroll(
            api_keys_section,
            id="settings-form",
        )

        yield Horizontal(
            Button("Save All", variant="primary", id="save-btn"),
            Button("Back", variant="default", id="back-btn"),
            id="button-row",
        )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        event.stop()

        if event.button.id == "save-btn":
            self._save_all_keys()

        elif event.button.id == "back-btn":
            self.action_back()

    def _save_all_keys(self) -> None:
        """Save all API keys."""
        providers = [
            ("deepgram", "deepgram-key-input", "deepgram-status"),
            ("elevenlabs", "elevenlabs-key-input", "elevenlabs-status"),
            ("gemini", "gemini-key-input", "gemini-status"),
        ]

        saved_count = 0
        for provider, input_id, status_id in providers:
            try:
                input_widget = self.query_one(f"#{input_id}", Input)
                status_widget = self.query_one(f"#{status_id}", Static)
                key_value = input_widget.value.strip()

                if save_api_key(provider, key_value):
                    saved_count += 1
                    # Update status indicator
                    if key_value:
                        status_widget.update("[green]✓ Configured[/green]")
                    else:
                        status_widget.update("[dim]Not set[/dim]")
            except Exception as e:
                logger.error(f"Failed to save {provider} key: {e}")

        if saved_count > 0:
            self.notify(
                f"Saved {saved_count} API key(s). Restart TUI to apply.",
                severity="information",
                timeout=3,
            )
        else:
            self.notify("No keys were saved", severity="warning", timeout=2)

    def action_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()
