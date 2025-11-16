"""Help screen displaying keyboard shortcuts and usage guide."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class HelpScreen(Screen):
    """Help screen with keyboard shortcuts and usage guide.

    Displays comprehensive information about:
    - Global keyboard shortcuts
    - Screen-specific shortcuts
    - Navigation flow
    - Feature descriptions
    - Tips and tricks

    Bindings:
        Esc: Return to previous screen
        q: Quit application
    """

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    CSS = """
    HelpScreen {
        background: $surface;
    }

    #help-container {
        width: 100%;
        height: 100%;
        padding: 2;
    }

    .help-section {
        margin-bottom: 2;
    }

    .help-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .help-content {
        margin-left: 2;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the help screen layout."""
        yield Header()

        with VerticalScroll(id="help-container"):
            for renderable in self._build_help_sections():
                yield Static(renderable, classes="help-content")

        yield Footer()

    def _build_help_sections(self) -> list[Text | Table]:
        """Build ordered help renderables."""
        sections: list[Text | Table] = []
        sections.append(
            Text.from_markup(
                "[bold cyan]📖 Audio Extraction & Transcription Analysis - TUI Guide[/bold cyan]"
            )
        )
        sections.append(self._section_overview())
        sections.extend(self._section_global_shortcuts())
        sections.extend(self._section_screen_shortcuts())
        sections.append(self._section_navigation())
        sections.append(self._section_features())
        sections.append(self._section_tips())
        return sections

    def _section_overview(self) -> Text:
        """Build overview section."""
        return Text.from_markup(
            """[bold yellow]Overview[/bold yellow]
This TUI provides an interactive interface for audio extraction, transcription, and analysis.
It features live progress monitoring, real-time log streaming, and provider health checks.

[dim]Navigate between screens using keyboard shortcuts or buttons.[/dim]\n"""
        )

    def _section_global_shortcuts(self) -> list[Text | Table]:
        table = self._build_shortcut_table(
            [
                ("q", "Quit application"),
                ("t", "Switch theme (select from list)"),
                ("d", "Switch theme (same as 't')"),
                ("h", "Show this help screen"),
                ("?", "Show this help screen"),
                ("Esc", "Go back / Close screen"),
            ]
        )
        return [
            Text.from_markup("[bold yellow]Global Keyboard Shortcuts[/bold yellow]"),
            table,
        ]

    def _section_screen_shortcuts(self) -> list[Text | Table]:
        renderables: list[Text | Table] = [
            Text.from_markup("[bold yellow]Screen-Specific Shortcuts[/bold yellow]"),
            Text.from_markup("[bold cyan]Home Screen[/bold cyan]"),
            self._build_shortcut_table(
                [
                    ("Enter", "Select file / directory"),
                    ("Tab", "Switch between file tree and recent files"),
                    ("/", "Filter / search files"),
                    ("r", "Refresh recent files list"),
                    ("c", "Continue to configuration"),
                ]
            ),
            Text.from_markup("[bold cyan]Configuration Screen[/bold cyan]"),
            self._build_shortcut_table(
                [
                    ("s", "Start pipeline run"),
                    ("r", "Reset to defaults"),
                    ("Tab", "Navigate between fields"),
                ]
            ),
            Text.from_markup("[bold cyan]Run Screen[/bold cyan]"),
            self._build_shortcut_table(
                [
                    ("c", "Cancel running pipeline"),
                    ("o", "Open output directory"),
                    ("a", "Show all logs"),
                    ("d", "Show debug+ logs"),
                    ("i", "Show info+ logs"),
                    ("w", "Show warning+ logs"),
                    ("e", "Show error logs only"),
                ]
            ),
        ]
        return renderables

    def _section_navigation(self) -> Text:
        return Text.from_markup(
            """[bold yellow]Navigation Flow[/bold yellow]

[cyan]Welcome Screen[/cyan] → [dim](Start button)[/dim]
    ↓
[cyan]Home Screen[/cyan] → [dim](Select file)[/dim]
    ↓
[cyan]Configuration Screen[/cyan] → [dim](Configure settings, Start run)[/dim]
    ↓
[cyan]Run Screen[/cyan] → [dim](Monitor progress, view logs)[/dim]
    ↓
[green]Complete![/green] → [dim](Open output directory)[/dim]

[dim]Press 'Esc' to go back at any time (except during pipeline execution).[/dim]\n"""
        )

    def _section_features(self) -> Text:
        return Text.from_markup(
            """[bold yellow]Key Features[/bold yellow]

[cyan]• Live Progress Monitoring[/cyan]
  Three-stage progress cards with ETAs for extraction, transcription, and analysis

[cyan]• Real-Time Log Streaming[/cyan]
  Filterable logs with color-coded levels (DEBUG, INFO, WARNING, ERROR)

[cyan]• Provider Health Checks[/cyan]
  Monitor health status of transcription providers (Deepgram, ElevenLabs, Whisper, Parakeet)

[cyan]• Configuration Persistence[/cyan]
  Settings and recent files are automatically saved across sessions

[cyan]• Recent Files[/cyan]
  Quick access to your 20 most recently processed files

[cyan]• Pipeline Cancellation[/cyan]
  Cancel long-running operations at any time with the 'c' key

[cyan]• Auto-Save Settings[/cyan]
  Configuration changes are saved automatically\n"""
        )

    def _section_tips(self) -> Text:
        return Text.from_markup(
            """[bold yellow]Tips & Tricks[/bold yellow]

[green]💡 Tip:[/green] Use Tab to quickly navigate between input fields and lists

[green]💡 Tip:[/green] Filter logs during pipeline execution to focus on errors (press 'e')

[green]💡 Tip:[/green] Recent files are stored with metadata - select one to auto-populate settings

[green]💡 Tip:[/green] The output directory defaults to './output' but can be customized

[green]💡 Tip:[/green] Dark mode can be toggled anytime with 'd' key

[green]💡 Tip:[/green] Progress ETAs use exponential moving average for accuracy

[green]💡 Tip:[/green] Press '?' or 'h' anytime to return to this help screen

[dim]For more information, see the full documentation in docs/TUI_GUIDE.md[/dim]\n"""
        )

    @staticmethod
    def _build_shortcut_table(rows: list[tuple[str, str]]) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")
        for key, action in rows:
            table.add_row(key, action)
        return table

    def action_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()
