"""Configuration screen for pipeline settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

from ..persistence import default_settings as _default_settings
from ..persistence import load_settings, save_settings

# Re-export for test patching convenience
default_settings = _default_settings

if TYPE_CHECKING:
    from ..app import AudioExtractionApp

logger = logging.getLogger(__name__)


class ConfigScreen(Screen):
    """Configuration screen for pipeline settings.

    Features:
    - Quality preset selection
    - Provider selection (auto, deepgram, whisper, etc.)
    - Language selection
    - Analysis style selection
    - Output directory input
    - Export options (markdown, HTML dashboard)
    - Auto-save on change (debounced)

    Bindings:
    - s: Start run
    - r: Reset to defaults
    - Esc: Back to home screen
    """

    BINDINGS = [
        ("s", "start_run", "Start Run"),
        ("r", "reset_defaults", "Reset"),
        ("escape", "back", "Back"),
    ]

    CSS = """
    ConfigScreen {
        layout: vertical;
    }

    #config-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $accent;
    }

    #config-form {
        height: 1fr;
        padding: 1 2;
    }

    .config-group {
        margin: 1 0;
        padding: 1;
        border: solid $primary;
    }

    .config-label {
        text-style: bold;
        margin-bottom: 1;
    }

    Select {
        margin-bottom: 1;
    }

    Input {
        margin-bottom: 1;
    }

    Checkbox {
        margin: 1 0;
    }

    #button-row {
        dock: bottom;
        height: auto;
        padding: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self):
        """Initialize config screen."""
        super().__init__()
        self.settings = load_settings()
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
        """Compose the config screen layout."""
        yield Header()
        yield Label("Configure Pipeline", id="config-title")

        quality_group = Container(
            Label("Audio Quality", classes="config-label"),
            Label("[dim]Choose extraction quality preset[/dim]", classes="config-help"),
            Select(
                options=[
                    ("Speech (optimized for transcription)", "speech"),
                    ("Standard (balanced quality)", "standard"),
                    ("High (best quality)", "high"),
                    ("Compressed (smaller files)", "compressed"),
                ],
                value=self.settings["defaults"]["quality"],
                id="quality-select",
            ),
            classes="config-group",
        )

        provider_group = Container(
            Label("Transcription Provider", classes="config-label"),
            Label(
                "[dim]Select transcription service (auto = best available)[/dim]",
                classes="config-help",
            ),
            Select(
                options=[
                    ("Auto (automatic selection)", "auto"),
                    ("Deepgram Nova 3 (cloud, best quality)", "deepgram"),
                    ("ElevenLabs (cloud)", "elevenlabs"),
                    ("Whisper (local, no API key)", "whisper"),
                    ("Parakeet (local, no API key)", "parakeet"),
                ],
                value=self.settings["defaults"]["provider"],
                id="provider-select",
            ),
            classes="config-group",
        )

        language_group = Container(
            Label("Language", classes="config-label"),
            Label("[dim]Primary language of the audio content[/dim]", classes="config-help"),
            Select(
                options=[
                    ("English", "en"),
                    ("Spanish", "es"),
                    ("French", "fr"),
                    ("German", "de"),
                    ("Italian", "it"),
                    ("Portuguese", "pt"),
                ],
                value=self.settings["defaults"]["language"],
                id="language-select",
            ),
            classes="config-group",
        )

        style_group = Container(
            Label("Analysis Style", classes="config-label"),
            Label(
                "[dim]Output format: concise = 1 file, full = 5 detailed files[/dim]",
                classes="config-help",
            ),
            Select(
                options=[
                    ("Concise (single comprehensive file)", "concise"),
                    ("Full (5 detailed analysis files)", "full"),
                ],
                value=self.settings["defaults"]["analysis_style"],
                id="style-select",
            ),
            classes="config-group",
        )

        output_group = Container(
            Label("Output Directory", classes="config-label"),
            Label(
                "[dim]Where to save output files (default: ./output)[/dim]", classes="config-help"
            ),
            Input(
                placeholder="./output (or specify custom path)",
                value=self.settings["last_output_dir"],
                id="output-dir-input",
            ),
            classes="config-group",
        )

        export_group = Container(
            Label("Export Options", classes="config-label"),
            Label("[dim]Additional output formats[/dim]", classes="config-help"),
            Checkbox(
                "Export Markdown transcript (recommended)", value=True, id="export-md-checkbox"
            ),
            Checkbox(
                "Generate HTML dashboard (interactive)",
                value=False,
                id="html-dashboard-checkbox",
            ),
            Checkbox(
                "Keep downloaded videos after processing (URL runs)",
                value=self.settings["defaults"].get("keep_downloaded_videos", False),
                id="keep-videos-checkbox",
            ),
            classes="config-group",
        )

        yield VerticalScroll(
            quality_group,
            provider_group,
            language_group,
            style_group,
            output_group,
            export_group,
            id="config-form",
        )

        yield Horizontal(
            Button("Start Run", variant="primary", id="start-btn"),
            Button("Reset to Defaults", variant="default", id="reset-btn"),
            Button("Back", variant="default", id="back-btn"),
            id="button-row",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen on mount."""
        # Update app state with loaded settings
        self.app.state.quality = self.settings["defaults"]["quality"]
        self.app.state.provider = self.settings["defaults"]["provider"]
        self.app.state.language = self.settings["defaults"]["language"]
        self.app.state.analysis_style = self.settings["defaults"]["analysis_style"]

        if self.app.state.output_dir is None:
            self.app.state.output_dir = Path(self.settings["last_output_dir"])

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes and auto-save.

        Args:
            event: Selection changed event
        """
        # Update app state
        select_id = event.select.id

        if select_id == "quality-select":
            self.app.state.quality = str(event.value)
            self.settings["defaults"]["quality"] = str(event.value)

        elif select_id == "provider-select":
            self.app.state.provider = str(event.value)
            self.settings["defaults"]["provider"] = str(event.value)

        elif select_id == "language-select":
            self.app.state.language = str(event.value)
            self.settings["defaults"]["language"] = str(event.value)

        elif select_id == "style-select":
            self.app.state.analysis_style = str(event.value)
            self.settings["defaults"]["analysis_style"] = str(event.value)

        # Auto-save settings
        save_settings(self.settings)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "output-dir-input":
            output_path = Path(event.value)
            self.app.state.output_dir = output_path
            self.settings["last_output_dir"] = str(output_path)
            # Auto-save settings
            save_settings(self.settings)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        event.stop()

        if event.button.id == "start-btn":
            self.action_start_run()

        elif event.button.id == "reset-btn":
            self.action_reset_defaults()

        elif event.button.id == "back-btn":
            self.action_back()

        elif event.button.id == "keep-videos-checkbox":
            # Mirror checkbox value into settings
            self.settings["defaults"]["keep_downloaded_videos"] = bool(event.button.value)
            save_settings(self.settings)

    def action_start_run(self) -> None:
        """Start the pipeline run."""
        # Validate configuration
        if self.app.state.input_path is None:
            self.notify("No input file selected!", severity="error", timeout=3)
            return

        if self.app.state.output_dir is None:
            self.notify("Output directory not set!", severity="error", timeout=3)
            return

        # Save current settings
        save_settings(self.settings)

        keep_videos = bool(self.settings["defaults"].get("keep_downloaded_videos", False))

        # Build config dict from settings
        config = {
            "output_dir": str(self.app.state.output_dir),
            "quality": self.settings["defaults"]["quality"],
            "provider": self.settings["defaults"]["provider"],
            "language": self.settings["defaults"]["language"],
            "analysis_style": self.settings["defaults"]["analysis_style"],
            "export_markdown": self.settings["exports"]["markdown"],
            "export_html": self.settings["exports"]["html"],
            "keep_downloaded_videos": keep_videos,
        }

        # Store config and navigate to run screen
        logger.info("Starting pipeline run")
        self.app.state.pending_run_config = config
        self.app.push_screen("run")

    def action_reset_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.settings = default_settings()
        save_settings(self.settings)

        # Reset UI selects
        self.query_one("#quality-select", Select).value = self.settings["defaults"]["quality"]
        self.query_one("#provider-select", Select).value = self.settings["defaults"]["provider"]
        self.query_one("#language-select", Select).value = self.settings["defaults"]["language"]
        self.query_one("#style-select", Select).value = self.settings["defaults"]["analysis_style"]
        self.query_one("#output-dir-input", Input).value = self.settings["last_output_dir"]
        keep_default = bool(self.settings["defaults"].get("keep_downloaded_videos", False))
        self.query_one("#keep-videos-checkbox", Checkbox).value = keep_default

        self.notify("Configuration reset to defaults", severity="information", timeout=2)

    def action_back(self) -> None:
        """Go back to home screen."""
        self.app.pop_screen()
