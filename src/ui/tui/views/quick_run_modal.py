"""Quick Run modal for confirming settings before running pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

from ..persistence import load_settings

if TYPE_CHECKING:
    from ..app import AudioExtractionApp


class QuickRunModal(ModalScreen):
    """Modal for quick-run confirmation with saved settings.

    Shows a summary of current settings and offers:
    - Start Now: Run pipeline immediately with saved settings
    - Customize: Go to full config screen to adjust settings

    This modal provides a faster path for repeat users who don't need
    to change settings every time.
    """

    BINDINGS = [
        Binding("enter", "start_now", "Start Now", show=True),
        Binding("c", "customize", "Customize", show=True),
        Binding("escape", "back", "Back", show=True),
    ]

    CSS = """
    QuickRunModal {
        align: center middle;
    }

    #quick-run-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 2;
    }

    #quick-run-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    #quick-run-file {
        text-align: center;
        padding: 1 0;
        text-style: italic;
    }

    #settings-grid {
        padding: 1 2;
    }

    .setting-row {
        height: auto;
        padding: 0;
    }

    .setting-label {
        width: 16;
        text-style: bold;
    }

    .setting-value {
        width: 1fr;
        color: $text;
    }

    #button-row {
        height: auto;
        padding-top: 2;
        align: center middle;
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

    def compose(self) -> ComposeResult:
        """Compose the quick run modal layout."""
        settings = load_settings()
        defaults = settings.get("defaults", {})

        # Get display info
        input_display = self._get_input_display()
        quality_display = self._format_quality(defaults.get("quality", "speech"))
        provider_display = self._format_provider(defaults.get("provider", "auto"))
        language_display = self._format_language(defaults.get("language", "en"))
        output_display = settings.get("last_output_dir", "./output")

        with Container(id="quick-run-container"):
            yield Label("▶ Ready to Process", id="quick-run-title")
            yield Static(f"📄 {input_display}", id="quick-run-file")

            with Vertical(id="settings-grid"):
                yield Horizontal(
                    Label("Quality:", classes="setting-label"),
                    Label(quality_display, classes="setting-value"),
                    classes="setting-row",
                )
                yield Horizontal(
                    Label("Provider:", classes="setting-label"),
                    Label(provider_display, classes="setting-value"),
                    classes="setting-row",
                )
                yield Horizontal(
                    Label("Language:", classes="setting-label"),
                    Label(language_display, classes="setting-value"),
                    classes="setting-row",
                )
                yield Horizontal(
                    Label("Output:", classes="setting-label"),
                    Label(output_display, classes="setting-value"),
                    classes="setting-row",
                )

            yield Horizontal(
                Button("▶ Start Now", variant="success", id="start-now-btn"),
                Button("⚙ Customize...", variant="default", id="customize-btn"),
                id="button-row",
            )

    def _get_input_display(self) -> str:
        """Get display string for input file or URL."""
        if self.app.state.input_path:
            return self.app.state.input_path.name

        pending = self.app.state.pending_run_config or {}
        url = pending.get("url", "")
        if url:
            # Truncate long URLs
            if len(url) > 40:
                return url[:37] + "..."
            return url

        return "No input selected"

    def _format_quality(self, quality: str) -> str:
        """Format quality value for display."""
        mapping = {
            "speech": "Speech (optimized)",
            "standard": "Standard (balanced)",
            "high": "High (best quality)",
            "compressed": "Compressed (smaller)",
        }
        return mapping.get(quality, quality.title())

    def _format_provider(self, provider: str) -> str:
        """Format provider value for display."""
        mapping = {
            "auto": "Auto (best available)",
            "deepgram": "Deepgram Nova 3",
            "elevenlabs": "ElevenLabs",
            "whisper": "Whisper (local)",
            "parakeet": "Parakeet (local)",
        }
        return mapping.get(provider, provider.title())

    def _format_language(self, language: str) -> str:
        """Format language code for display."""
        mapping = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
        }
        return mapping.get(language, language.upper())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        event.stop()
        if event.button.id == "start-now-btn":
            self.action_start_now()
        elif event.button.id == "customize-btn":
            self.action_customize()

    def action_start_now(self) -> None:
        """Start pipeline immediately with saved settings."""
        settings = load_settings()
        defaults = settings.get("defaults", {})

        # Build config from saved settings
        config = {
            "output_dir": settings.get("last_output_dir", "./output"),
            "quality": defaults.get("quality", "speech"),
            "provider": defaults.get("provider", "auto"),
            "language": defaults.get("language", "en"),
            "analysis_style": defaults.get("analysis_style", "concise"),
            "export_markdown": settings.get("exports", {}).get("markdown", True),
            "export_html": settings.get("exports", {}).get("html", False),
            "keep_downloaded_videos": defaults.get("keep_downloaded_videos", False),
        }

        # Merge with any pending config (e.g., URL)
        pending = self.app.state.pending_run_config or {}
        if pending.get("url"):
            config["url"] = pending["url"]

        # Store config and go to run screen
        self.app.state.pending_run_config = config
        self.dismiss()
        self.app.push_screen("run")

    def action_customize(self) -> None:
        """Go to full config screen for customization."""
        self.dismiss()
        self.app.push_screen("config")

    def action_back(self) -> None:
        """Return to home screen."""
        self.dismiss()
