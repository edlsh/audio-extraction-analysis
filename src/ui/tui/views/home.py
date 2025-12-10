"""Home screen with file picker and recent files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual._context import active_app
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from textual.app import ComposeResult

from ..persistence import add_recent_file, load_recent_files
from ..widgets.filtered_tree import FilteredDirectoryTree

if TYPE_CHECKING:
    from ..app import AudioExtractionApp

logger = get_logger(__name__)


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
        ("u", "focus_url_input", "URL Input"),
    ]

    CSS = """
    HomeScreen {
        layout: vertical;
    }

    #home-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $panel;
        color: $accent;
    }

    #home-container {
        layout: horizontal;
        height: 1fr;
    }

    #tree-pane {
        width: 60%;
        border-right: solid $panel;
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

    #url-row {
        height: auto;
        padding: 1 2;
        background: $panel;
        border-top: solid $panel;
    }

    #url-label {
        width: auto;
        padding-right: 1;
    }

    #url-input {
        width: 1fr;
    }

    #url-go-btn {
        width: auto;
        margin-left: 1;
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
        logger.debug("HomeScreen.compose() starting...")
        yield Header()
        logger.debug("HomeScreen: Header yielded")
        yield Label("Select Input File or Paste URL", id="home-title")
        logger.debug("HomeScreen: Title yielded")

        logger.debug(f"HomeScreen: Creating tree pane with path: {self.initial_path}")
        tree_pane = Vertical(
            Label("Browse Files"),
            FilteredDirectoryTree(str(self.initial_path), id="file-tree"),
            id="tree-pane",
        )
        logger.debug("HomeScreen: Tree pane created")

        recent_pane = Vertical(
            Label("Recent Files"),
            DataTable(id="recent-table"),
            id="recent-pane",
        )
        logger.debug("HomeScreen: Recent pane created")

        yield Container(tree_pane, recent_pane, id="home-container")
        logger.debug("HomeScreen: Container yielded")
        yield Input(placeholder="Type / to filter files...", id="filter-input")
        logger.debug("HomeScreen: Filter input yielded")

        # Inline URL input row
        yield Horizontal(
            Label("🔗 Or paste a URL:", id="url-label"),
            Input(placeholder="https://youtube.com/watch?v=...", id="url-input"),
            Button("Go", variant="primary", id="url-go-btn"),
            Button("⚙️ Settings", variant="default", id="settings-btn"),
            id="url-row",
        )
        logger.debug("HomeScreen: URL row yielded")

        yield Footer()
        logger.debug("HomeScreen.compose() completed")

    def on_mount(self) -> None:
        """Set up the screen on mount."""
        logger.debug("HomeScreen.on_mount() starting...")
        # Configure recent files table
        table = self.query_one("#recent-table", DataTable)
        logger.debug("HomeScreen: Got recent table")
        table.add_columns("File", "Size", "Last Used")
        table.cursor_type = "row"

        logger.debug("HomeScreen: Loading recent files...")
        self._load_recent_files()
        logger.debug("HomeScreen: Recent files loaded")

        # Focus the file tree initially
        logger.debug("HomeScreen: Focusing file tree...")
        self.query_one("#file-tree").focus()
        logger.debug("HomeScreen.on_mount() completed")

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

        # Navigate to quick run modal for confirmation
        self.app.push_screen("quick_run")

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

    def action_focus_url_input(self) -> None:
        """Focus the URL input field (u key)."""
        self.query_one("#url-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses on the home screen."""
        if event.button.id == "url-go-btn":
            event.stop()
            self._process_url_input()
        elif event.button.id == "settings-btn":
            event.stop()
            self.app.push_screen("settings")

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
        """Handle input submission for filter or URL."""
        if event.input.id == "filter-input":
            tree = self.query_one("#file-tree", FilteredDirectoryTree)
            tree.filter = event.value or ""
        elif event.input.id == "url-input":
            self._process_url_input()

    def _process_url_input(self) -> None:
        """Process the URL from the inline input field."""
        url_input = self.query_one("#url-input", Input)
        url = url_input.value.strip()

        if not url:
            self.notify("Please enter a URL.", severity="warning")
            return

        # Lightweight validation: must at least look like a URL
        if not (url.startswith("http://") or url.startswith("https://")):
            self.notify("URL must start with http:// or https://", severity="error")
            return

        logger.info(f"URL entered: {url}")

        # Store URL on app state; the run service will interpret it
        self.app.state.input_path = None
        if self.app.state.pending_run_config is None:
            self.app.state.pending_run_config = {}
        self.app.state.pending_run_config["url"] = url

        # Navigate to quick run modal for confirmation
        self.app.push_screen("quick_run")
