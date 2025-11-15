"""Configuration screen for pipeline settings."""

from __future__ import annotations

import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

from ..persistence import load_settings, save_settings

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

    def compose(self) -> ComposeResult:
        """Compose the config screen layout."""
        yield Header()
        yield Label("Configure Pipeline", id="config-title")

        with VerticalScroll(id="config-form"):
            # Quality selection
            with Container(classes="config-group"):
                yield Label("Audio Quality", classes="config-label")
                yield Select(
                    options=[
                        ("Speech (optimized for transcription)", "speech"),
                        ("Standard (balanced quality)", "standard"),
                        ("High (best quality)", "high"),
                        ("Compressed (smaller files)", "compressed"),
                    ],
                    value=self.settings["defaults"]["quality"],
                    id="quality-select",
                )

            # Provider selection
            with Container(classes="config-group"):
                yield Label("Transcription Provider", classes="config-label")
                yield Select(
                    options=[
                        ("Auto (automatic selection)", "auto"),
                        ("Deepgram Nova 3", "deepgram"),
                        ("ElevenLabs", "elevenlabs"),
                        ("Whisper (local)", "whisper"),
                        ("Parakeet (local)", "parakeet"),
                    ],
                    value=self.settings["defaults"]["provider"],
                    id="provider-select",
                )

            # Language selection
            with Container(classes="config-group"):
                yield Label("Language", classes="config-label")
                yield Select(
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
                )

            # Analysis style
            with Container(classes="config-group"):
                yield Label("Analysis Style", classes="config-label")
                yield Select(
                    options=[
                        ("Concise (single file)", "concise"),
                        ("Full (5 detailed files)", "full"),
                    ],
                    value=self.settings["defaults"]["analysis_style"],
                    id="analysis-select",
                )

            # Output directory
            with Container(classes="config-group"):
                yield Label("Output Directory", classes="config-label")
                yield Input(
                    placeholder="Output directory path",
                    value=self.settings["last_output_dir"],
                    id="output-input",
                )

            # Export options
            with Container(classes="config-group"):
                yield Label("Export Options", classes="config-label")
                yield Checkbox("Export Markdown transcript", value=True, id="export-md-checkbox")
                yield Checkbox("Generate HTML dashboard", value=False, id="html-dashboard-checkbox")

        with Horizontal(id="button-row"):
            yield Button("Start Run", variant="primary", id="start-btn")
            yield Button("Reset to Defaults", variant="default", id="reset-btn")
            yield Button("Back", variant="default", id="back-btn")

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

        elif select_id == "analysis-select":
            self.app.state.analysis_style = str(event.value)
            self.settings["defaults"]["analysis_style"] = str(event.value)

        # Auto-save settings
        save_settings(self.settings)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "output-input":
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

        # Build config dict from settings
        config = {
            "output_dir": str(self.app.state.output_dir),
            "quality": self.settings["defaults"]["quality"],
            "provider": self.settings["defaults"]["provider"],
            "language": self.settings["defaults"]["language"],
            "analysis_style": self.settings["defaults"]["analysis_style"],
            "export_markdown": self.settings["exports"]["markdown"],
            "export_html": self.settings["exports"]["html"],
        }

        # Store config and navigate to run screen
        logger.info("Starting pipeline run")
        self.app.state.pending_run_config = config
        self.app.push_screen("run")

    def action_reset_defaults(self) -> None:
        """Reset configuration to defaults."""
        from ..persistence import default_settings

        self.settings = default_settings()
        save_settings(self.settings)

        # Reset UI selects
        self.query_one("#quality-select", Select).value = self.settings["defaults"]["quality"]
        self.query_one("#provider-select", Select).value = self.settings["defaults"]["provider"]
        self.query_one("#language-select", Select).value = self.settings["defaults"]["language"]
        self.query_one("#analysis-select", Select).value = self.settings["defaults"][
            "analysis_style"
        ]
        self.query_one("#output-input", Input).value = self.settings["last_output_dir"]

        self.notify("Configuration reset to defaults", severity="information", timeout=2)

    def action_back(self) -> None:
        """Go back to home screen."""
        self.app.pop_screen()
