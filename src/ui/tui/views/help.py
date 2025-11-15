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
            yield Static(self._build_help_content(), classes="help-content")

        yield Footer()

    def _build_help_content(self) -> str:
        """Build the help content with formatting.

        Returns:
            Formatted help text with Rich markup
        """
        sections = []

        # Title
        sections.append(
            "[bold cyan]📖 Audio Extraction & Transcription Analysis - TUI Guide[/bold cyan]\n"
        )

        # Overview
        sections.append(self._section_overview())

        # Global Shortcuts
        sections.append(self._section_global_shortcuts())

        # Screen-specific Shortcuts
        sections.append(self._section_screen_shortcuts())

        # Navigation Flow
        sections.append(self._section_navigation())

        # Features
        sections.append(self._section_features())

        # Tips
        sections.append(self._section_tips())

        return "\n".join(sections)

    def _section_overview(self) -> str:
        """Build overview section."""
        return """[bold yellow]Overview[/bold yellow]
This TUI provides an interactive interface for audio extraction, transcription, and analysis.
It features live progress monitoring, real-time log streaming, and provider health checks.

[dim]Navigate between screens using keyboard shortcuts or buttons.[/dim]
"""

    def _section_global_shortcuts(self) -> str:
        """Build global shortcuts section."""
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")

        shortcuts = [
            ("q", "Quit application"),
            ("d", "Toggle dark mode"),
            ("h, ?", "Show this help screen"),
            ("Esc", "Go back / Close screen"),
        ]

        for key, action in shortcuts:
            table.add_row(key, action)

        return f"[bold yellow]Global Keyboard Shortcuts[/bold yellow]\n{table}"

    def _section_screen_shortcuts(self) -> str:
        """Build screen-specific shortcuts section."""
        content = ["[bold yellow]Screen-Specific Shortcuts[/bold yellow]\n"]

        # Home Screen
        content.append("[bold cyan]Home Screen[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")
        table.add_row("Enter", "Select file / directory")
        table.add_row("Tab", "Switch between file tree and recent files")
        table.add_row("/", "Filter / search files")
        table.add_row("r", "Refresh recent files list")
        table.add_row("c", "Continue to configuration")
        content.append(str(table))

        # Config Screen
        content.append("\n[bold cyan]Configuration Screen[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")
        table.add_row("s", "Start pipeline run")
        table.add_row("r", "Reset to defaults")
        table.add_row("Tab", "Navigate between fields")
        content.append(str(table))

        # Run Screen
        content.append("\n[bold cyan]Run Screen[/bold cyan]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Action", style="white")
        table.add_row("c", "Cancel running pipeline")
        table.add_row("o", "Open output directory")
        table.add_row("a", "Show all logs")
        table.add_row("d", "Show debug+ logs")
        table.add_row("i", "Show info+ logs")
        table.add_row("w", "Show warning+ logs")
        table.add_row("e", "Show error logs only")
        content.append(str(table))

        return "\n".join(content)

    def _section_navigation(self) -> str:
        """Build navigation flow section."""
        return """[bold yellow]Navigation Flow[/bold yellow]

[cyan]Welcome Screen[/cyan] → [dim](Start button)[/dim]
    ↓
[cyan]Home Screen[/cyan] → [dim](Select file)[/dim]
    ↓
[cyan]Configuration Screen[/cyan] → [dim](Configure settings, Start run)[/dim]
    ↓
[cyan]Run Screen[/cyan] → [dim](Monitor progress, view logs)[/dim]
    ↓
[green]Complete![/green] → [dim](Open output directory)[/dim]

[dim]Press 'Esc' to go back at any time (except during pipeline execution).[/dim]
"""

    def _section_features(self) -> str:
        """Build features section."""
        return """[bold yellow]Key Features[/bold yellow]

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
  Configuration changes are saved automatically
"""

    def _section_tips(self) -> str:
        """Build tips and tricks section."""
        return """[bold yellow]Tips & Tricks[/bold yellow]

[green]💡 Tip:[/green] Use Tab to quickly navigate between input fields and lists

[green]💡 Tip:[/green] Filter logs during pipeline execution to focus on errors (press 'e')

[green]💡 Tip:[/green] Recent files are stored with metadata - select one to auto-populate settings

[green]💡 Tip:[/green] The output directory defaults to './output' but can be customized

[green]💡 Tip:[/green] Dark mode can be toggled anytime with 'd' key

[green]💡 Tip:[/green] Progress ETAs use exponential moving average for accuracy

[green]💡 Tip:[/green] Press '?' or 'h' anytime to return to this help screen

[dim]For more information, see the full documentation in docs/TUI_GUIDE.md[/dim]
"""

    def action_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()
