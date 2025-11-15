"""Home screen with file picker and recent files."""

from __future__ import annotations

import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, DirectoryTree, Footer, Header, Input, Label

from ..persistence import add_recent_file, load_recent_files

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
        ("r", "refresh_recent", "Refresh Recent"),
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

    def __init__(self, initial_path: Path | None = None):
        """Initialize home screen.

        Args:
            initial_path: Initial directory to show in tree
        """
        super().__init__()
        self.initial_path = initial_path or Path.home()
        self._active_pane = "tree"  # "tree" or "recent"

    def compose(self) -> ComposeResult:
        """Compose the home screen layout."""
        yield Header()
        yield Label("Select Input File", id="home-title")

        with Container(id="home-container"):
            with Vertical(id="tree-pane"):
                yield Label("Browse Files")
                yield DirectoryTree(str(self.initial_path), id="file-tree")

            with Vertical(id="recent-pane"):
                yield Label("Recent Files")
                yield DataTable(id="recent-files")

        yield Input(placeholder="Type / to filter files...", id="filter-input")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen on mount."""
        # Configure recent files table
        table = self.query_one("#recent-files", DataTable)
        table.add_columns("File", "Size", "Last Used")
        table.cursor_type = "row"

        self._load_recent_files()

        # Focus the file tree initially
        self.query_one("#file-tree").focus()

    def _load_recent_files(self) -> None:
        """Load and display recent files in table."""
        table = self.query_one("#recent-files", DataTable)
        table.clear()

        recent = load_recent_files(max_entries=20)

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
            tree = self.query_one("#file-tree", DirectoryTree)
            if tree.cursor_node and tree.cursor_node.data:
                selected_path = tree.cursor_node.data.path
                if selected_path.is_file():
                    self._select_file(selected_path)

        elif self._active_pane == "recent":
            table = self.query_one("#recent-files", DataTable)
            if table.cursor_row is not None:
                row_key = table.get_row_at(table.cursor_row)
                if row_key:
                    # The key is the file path (string)
                    selected_path = Path(str(table.get_row_key(table.cursor_row)))
                    self._select_file(selected_path)

    def _select_file(self, path: Path) -> None:
        """Select a file and proceed to config screen.

        Args:
            path: Path to selected file
        """
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
            self.query_one("#recent-files").focus()
        else:
            self._active_pane = "tree"
            self.query_one("#file-tree").focus()

    def action_filter(self) -> None:
        """Focus the filter input (/ key)."""
        self.query_one("#filter-input").focus()

    def action_refresh_recent(self) -> None:
        """Refresh recent files list (r key)."""
        self._load_recent_files()
        self.notify("Recent files refreshed")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
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
            selected_path = Path(str(row_key.value))
            self._select_file(selected_path)
