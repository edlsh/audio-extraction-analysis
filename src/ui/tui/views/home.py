"""Home screen with file picker and recent files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

from ..persistence import add_recent_file, load_recent_files
from ..widgets.filtered_tree import FilteredDirectoryTree

if TYPE_CHECKING:
    from ..app import AudioExtractionApp

logger = logging.getLogger(__name__)


class HomeScreen(Screen):
    """Home screen for file selection.

    Features:
    - Directory tree for browsing filesystem
    - Recent files table for quick access
    - Filter input for searching files
    - Keyboard navigation (arrows, Enter, Tab, /)

    Bindings:
    - Enter: Select highlighted file
    - Tab: Switch between tree and recent files
    - /: Focus filter input
    - r: Refresh recent files
    - q: Quit (inherited)
    """

    BINDINGS = [
        ("enter", "select_file", "Select"),
        ("tab", "switch_pane", "Switch Pane"),
        ("/", "filter", "Filter"),
        ("f", "filter", "Filter"),
        ("r", "refresh_recent", "Refresh Recent"),
        ("u", "open_url_downloads", "URL from Web"),
    ]

    CSS = """
    HomeScreen {
        layout: vertical;
    }

    #home-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $accent;
    }

    #home-container {
        layout: horizontal;
        height: 100%;
    }

    #tree-pane {
        width: 60%;
        border-right: solid $primary;
    }

    #recent-pane {
        width: 40%;
    }

    DirectoryTree {
        height: 1fr;
    }

    DataTable {
        height: 1fr;
    }

    #filter-input {
        dock: bottom;
        margin: 1;
    }
    """

    def __init__(
        self,
        initial_path: Path | None = None,
        *,
        start_dir: Path | None = None,
    ) -> None:
        """Initialize home screen.

        Args:
            initial_path: Initial directory to show in tree.
            start_dir: Backwards compatible alias for initial_path.
        """
        super().__init__()
        path = start_dir if start_dir is not None else initial_path
        self.initial_path = path or Path.home()
        self._active_pane = "tree"  # "tree" or "recent"
        self._app_override: AudioExtractionApp | None = None

    @property
    def start_dir(self) -> Path:
        """Return the configured starting directory."""

        return self.initial_path

    @start_dir.setter
    def start_dir(self, value: Path) -> None:
        self.initial_path = value

    @property
    def app(self) -> AudioExtractionApp:
        """Return the strongly typed application instance."""

        if self._app_override is not None:
            return self._app_override
        return cast("AudioExtractionApp", super().app)

    @app.setter
    def app(self, value: AudioExtractionApp) -> None:
        self._app_override = value
        active_app.set(value)

    def compose(self) -> ComposeResult:
        """Compose the home screen layout."""
        yield Header()
        yield Label("Select Input File", id="home-title")

        tree_pane = Vertical(
            Label("Browse Files"),
            FilteredDirectoryTree(str(self.initial_path), id="file-tree"),
            id="tree-pane",
        )

        recent_pane = Vertical(
            Label("Recent Files"),
            DataTable(id="recent-table"),
            Button("Process from URL", id="open-url-btn"),
            id="recent-pane",
        )

        yield Container(tree_pane, recent_pane, id="home-container")
        yield Input(placeholder="Type / to filter files...", id="filter-input")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen on mount."""
        # Configure recent files table
        table = self.query_one("#recent-table", DataTable)
        table.add_columns("File", "Size", "Last Used")
        table.cursor_type = "row"

        self._load_recent_files()

        # Focus the file tree initially
        self.query_one("#file-tree").focus()

    def _load_recent_files(self) -> None:
        """Load and display recent files in table."""
        table = self.query_one("#recent-table", DataTable)
        table.clear()

        recent = load_recent_files(max_entries=20)

        if not recent:
            table.add_row("[dim]No recent files[/dim]", "", "", key="none")
            return

        for file_data in recent:
            path = Path(file_data["path"])
            name = path.name
            size = f"{file_data['size_mb']:.1f} MB"
            # Simplify timestamp to just date
            last_used = file_data["last_used"][:10]  # YYYY-MM-DD

            table.add_row(name, size, last_used, key=str(path))

    def action_select_file(self) -> None:
        """Handle file selection (Enter key)."""
        if self._active_pane == "tree":
            tree = self.query_one("#file-tree", FilteredDirectoryTree)
            node = tree.cursor_node
            if not node or not node.data:
                self.notify("No file selected", severity="warning")
                return
            self._select_file(Path(node.data.path))

        elif self._active_pane == "recent":
            table = self.query_one("#recent-table", DataTable)
            if table.cursor_row is None:
                self.notify("No recent file selected", severity="warning")
                return

            key = table.get_row_key(table.cursor_row)
            if not key:
                self.notify("No recent file selected", severity="warning")
                return

            key_value = getattr(key, "value", key)
            selected_path = Path(str(key_value))
            self._select_file(selected_path)
        else:
            self.notify("Unknown pane", severity="error")

    def _select_file(self, path: Path) -> None:
        """Select a file and proceed to config screen.

        Args:
            path: Path to selected file
        """
        if not path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return

        if not path.is_file():
            self.notify("Please select a file, not a directory", severity="warning")
            return

        logger.info(f"File selected: {path}")

        # Add to recent files
        add_recent_file(path)

        # Post message to app with selected file
        self.app.state.input_path = path

        # Navigate to config screen
        self.app.push_screen("config")

    def action_switch_pane(self) -> None:
        """Switch focus between tree and recent files (Tab key)."""
        if self._active_pane == "tree":
            self._active_pane = "recent"
            self.query_one("#recent-table").focus()
        else:
            self._active_pane = "tree"
            self.query_one("#file-tree").focus()

    def action_filter(self) -> None:
        """Focus the filter input (/ key)."""
        self.query_one("#filter-input").focus()

    def action_refresh_recent(self) -> None:
        """Refresh recent files list (r key)."""
        self._load_recent_files()
        self.notify("Recent files refreshed", severity="information")

    def action_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()

    def action_open_url_downloads(self) -> None:
        """Navigate to the URL downloads screen."""
        self.app.push_screen("url_downloads")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses on the home screen."""
        if event.button.id == "open-url-btn":
            event.stop()
            self.action_open_url_downloads()

    def on_directory_tree_file_selected(self, event: FilteredDirectoryTree.FileSelected) -> None:
        """Handle file selection from directory tree.

        Args:
            event: File selected event
        """
        event.stop()
        self._select_file(event.path)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection from recent files table.

        Args:
            event: Row selected event
        """
        event.stop()
        row_key = event.row_key
        if row_key:
            key_value = getattr(row_key, "value", row_key)
            if key_value == "none":
                self.notify("No recent file selected", severity="warning")
                return
            selected_path = Path(str(key_value))
            self._select_file(selected_path)
        else:
            self.notify("No recent file selected", severity="warning")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Dynamically filter the directory tree as the user types."""
        if event.input.id != "filter-input":
            return

        tree = self.query_one("#file-tree", FilteredDirectoryTree)
        tree.filter = event.value or ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Filter the directory tree when the filter input is submitted."""

        if event.input.id != "filter-input":
            return

        tree = self.query_one("#file-tree", FilteredDirectoryTree)
        tree.filter = event.value or ""
