"""Unit tests for TUI HomeScreen."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, DirectoryTree, Input

from src.ui.tui.app import AudioExtractionApp
from src.ui.tui.state import AppState
from src.ui.tui.views.home import HomeScreen


@pytest.fixture
def app_with_state():
    """Create app with initialized state."""
    app = AudioExtractionApp()
    app.state = AppState()
    return app


@pytest.fixture
def home_screen(app_with_state):
    """Create HomeScreen with app context."""
    screen = HomeScreen()
    screen.app = app_with_state
    return screen


@pytest.fixture
def mock_recent_files():
    """Create mock recent files data."""
    return [
        {
            "path": "/test/file1.mp3",
            "last_used": "2024-01-01T12:00:00",
            "size_mb": 10.5,
        },
        {
            "path": "/test/file2.wav",
            "last_used": "2024-01-02T14:30:00",
            "size_mb": 25.2,
        },
        {
            "path": "/test/file3.mp4",
            "last_used": "2024-01-03T09:15:00",
            "size_mb": 150.8,
        },
    ]


class TestHomeScreenInit:
    """Test HomeScreen initialization."""

    def test_init_default(self):
        """Test default initialization."""
        screen = HomeScreen(start_dir=None)
        assert screen.start_dir == Path.home()

    def test_init_with_start_dir(self):
        """Test initialization with custom start directory."""
        start_dir = Path("/custom/path")
        screen = HomeScreen(start_dir=start_dir)
        assert screen.start_dir == start_dir


class TestHomeScreenCompose:
    """Test HomeScreen UI composition."""

    def test_compose_creates_widgets(self, home_screen):
        """Test that compose creates all required widgets."""
        widgets = list(home_screen.compose())

        # Check that we have the expected widget types
        widget_types = [type(w).__name__ for w in widgets]
        assert "Header" in widget_types
        assert "Footer" in widget_types
        assert "Container" in widget_types


class TestHomeScreenMount:
    """Test HomeScreen mount behavior."""

    @patch("src.ui.tui.views.home.load_recent_files")
    def test_on_mount_loads_recent_files(self, mock_load, home_screen):
        """Test that on_mount loads recent files."""
        mock_recent = [
            {"path": "/test/file.mp3", "last_used": "2024-01-01", "size_mb": 10}
        ]
        mock_load.return_value = mock_recent

        # Create mock table
        mock_table = Mock(spec=DataTable)
        home_screen.query_one = Mock(return_value=mock_table)

        home_screen.on_mount()

        mock_load.assert_called_once()
        # Verify table was populated
        assert mock_table.add_row.called

    def test_on_mount_sets_focus(self, home_screen):
        """Test that on_mount sets focus to file tree."""
        mock_tree = Mock(spec=DirectoryTree)
        home_screen.query_one = Mock(return_value=mock_tree)

        home_screen.on_mount()

        mock_tree.focus.assert_called_once()


class TestHomeScreenActions:
    """Test HomeScreen actions."""

    @patch("src.ui.tui.views.home.add_recent_file")
    def test_action_select_file_from_tree(self, mock_add_recent, home_screen):
        """Test selecting a file from the directory tree."""
        home_screen.app.push_screen = AsyncMock()
        home_screen.notify = Mock()

        # Mock tree with selected file
        mock_tree = Mock(spec=DirectoryTree)
        mock_tree.cursor_node = Mock(data=Mock(path=Path("/test/audio.mp3")))
        home_screen.query_one = Mock(return_value=mock_tree)

        home_screen.action_select_file()

        # Verify file was selected
        assert home_screen.app.state.input_path == Path("/test/audio.mp3")

        # Verify recent file was added
        mock_add_recent.assert_called_once_with(Path("/test/audio.mp3"))

        # Verify navigation to config screen
        home_screen.app.push_screen.assert_called_once()

    @patch("src.ui.tui.views.home.add_recent_file")
    def test_action_select_file_from_table(self, mock_add_recent, home_screen):
        """Test selecting a file from the recent files table."""
        home_screen.app.push_screen = AsyncMock()
        home_screen.notify = Mock()
        home_screen._current_pane = "recent"

        # Mock table with selected file
        mock_table = Mock(spec=DataTable)
        mock_table.cursor_row = 1
        mock_table.get_row_key = Mock(return_value="/test/recent.mp3")
        home_screen.query_one = Mock(return_value=mock_table)

        home_screen.action_select_file()

        # Verify file was selected
        assert home_screen.app.state.input_path == Path("/test/recent.mp3")

        # Verify recent file was added
        mock_add_recent.assert_called_once_with(Path("/test/recent.mp3"))

        # Verify navigation to config screen
        home_screen.app.push_screen.assert_called_once()

    def test_action_select_file_no_selection(self, home_screen):
        """Test selecting a file with no selection."""
        home_screen.notify = Mock()

        # Mock tree with no selection
        mock_tree = Mock(spec=DirectoryTree)
        mock_tree.cursor_node = None
        home_screen.query_one = Mock(return_value=mock_tree)

        home_screen.action_select_file()

        home_screen.notify.assert_called_with(
            "No file selected",
            severity="warning"
        )

    def test_action_select_file_directory(self, home_screen):
        """Test selecting a directory instead of a file."""
        home_screen.notify = Mock()

        # Mock tree with directory selected
        mock_tree = Mock(spec=DirectoryTree)
        mock_tree.cursor_node = Mock(data=Mock(path=Path("/test/directory/")))
        home_screen.query_one = Mock(return_value=mock_tree)

        # Mock path to be a directory
        with patch("pathlib.Path.is_file", return_value=False):
            home_screen.action_select_file()

        home_screen.notify.assert_called_with(
            "Please select a file, not a directory",
            severity="warning"
        )

    def test_action_select_file_not_found(self, home_screen):
        """Test selecting a file that doesn't exist."""
        home_screen.notify = Mock()
        home_screen._current_pane = "recent"

        # Mock table with non-existent file
        mock_table = Mock(spec=DataTable)
        mock_table.cursor_row = 1
        mock_table.get_row_key = Mock(return_value="/test/missing.mp3")
        home_screen.query_one = Mock(return_value=mock_table)

        # Mock path to not exist
        with patch("pathlib.Path.exists", return_value=False):
            home_screen.action_select_file()

        home_screen.notify.assert_called_with(
            "File not found: /test/missing.mp3",
            severity="error"
        )

    def test_action_switch_pane(self, home_screen):
        """Test switching between panes."""
        # Start with tree pane
        home_screen._current_pane = "tree"

        # Mock widgets
        mock_tree = Mock(spec=DirectoryTree)
        mock_table = Mock(spec=DataTable)
        home_screen.query_one = Mock(side_effect=lambda selector, _: {
            "#file-tree": mock_tree,
            "#recent-table": mock_table,
        }.get(selector.split(",")[0]))

        # Switch to recent pane
        home_screen.action_switch_pane()

        assert home_screen._current_pane == "recent"
        mock_table.focus.assert_called_once()

        # Switch back to tree pane
        home_screen.action_switch_pane()

        assert home_screen._current_pane == "tree"
        mock_tree.focus.assert_called_once()

    def test_action_filter(self, home_screen):
        """Test focusing the filter input."""
        mock_input = Mock(spec=Input)
        home_screen.query_one = Mock(return_value=mock_input)

        home_screen.action_filter()

        mock_input.focus.assert_called_once()

    @patch("src.ui.tui.views.home.load_recent_files")
    def test_action_refresh_recent(self, mock_load, home_screen):
        """Test refreshing recent files."""
        home_screen.notify = Mock()
        mock_recent = [
            {"path": "/test/new.mp3", "last_used": "2024-01-05", "size_mb": 5}
        ]
        mock_load.return_value = mock_recent

        # Mock table
        mock_table = Mock(spec=DataTable)
        home_screen.query_one = Mock(return_value=mock_table)

        home_screen.action_refresh_recent()

        # Verify table was cleared and repopulated
        mock_table.clear.assert_called_once()
        mock_table.add_row.assert_called()

        home_screen.notify.assert_called_with(
            "Recent files refreshed",
            severity="information"
        )

    def test_action_back(self, home_screen):
        """Test back action."""
        home_screen.app.pop_screen = Mock()

        home_screen.action_back()

        home_screen.app.pop_screen.assert_called_once()


class TestHomeScreenEventHandlers:
    """Test HomeScreen event handlers."""

    @patch("src.ui.tui.views.home.add_recent_file")
    def test_on_directory_tree_file_selected(self, mock_add_recent, home_screen):
        """Test handling file selection from tree."""
        home_screen.app.push_screen = AsyncMock()

        # Create mock event
        event = Mock()
        event.path = Path("/test/selected.mp3")

        home_screen.on_directory_tree_file_selected(event)

        # Verify state was updated
        assert home_screen.app.state.input_path == Path("/test/selected.mp3")

        # Verify recent file was added
        mock_add_recent.assert_called_once_with(Path("/test/selected.mp3"))

        # Verify navigation
        home_screen.app.push_screen.assert_called_once()

    @patch("src.ui.tui.views.home.add_recent_file")
    def test_on_data_table_row_selected(self, mock_add_recent, home_screen):
        """Test handling row selection from recent files table."""
        home_screen.app.push_screen = AsyncMock()

        # Create mock event
        event = Mock()
        event.row_key = Mock(value="/test/recent.mp3")

        # Mock path existence
        with patch("pathlib.Path.exists", return_value=True):
            home_screen.on_data_table_row_selected(event)

        # Verify state was updated
        assert home_screen.app.state.input_path == Path("/test/recent.mp3")

        # Verify recent file was added
        mock_add_recent.assert_called_once_with(Path("/test/recent.mp3"))

        # Verify navigation
        home_screen.app.push_screen.assert_called_once()

    def test_on_data_table_row_selected_not_found(self, home_screen):
        """Test handling row selection for missing file."""
        home_screen.notify = Mock()

        # Create mock event
        event = Mock()
        event.row_key = Mock(value="/test/missing.mp3")

        # Mock path not existing
        with patch("pathlib.Path.exists", return_value=False):
            home_screen.on_data_table_row_selected(event)

        home_screen.notify.assert_called_with(
            "File not found: /test/missing.mp3",
            severity="error"
        )

    def test_on_input_submitted_filters_tree(self, home_screen):
        """Test that filter input filters the directory tree."""
        mock_tree = Mock(spec=DirectoryTree)
        home_screen.query_one = Mock(return_value=mock_tree)

        # Create mock event
        event = Mock()
        event.input = Mock(id="filter-input")
        event.value = "*.mp3"

        home_screen.on_input_submitted(event)

        # Verify filter was applied
        assert mock_tree.filter == "*.mp3"


class TestHomeScreenHelpers:
    """Test HomeScreen helper methods."""

    @patch("src.ui.tui.views.home.load_recent_files")
    def test_load_recent_files(self, mock_load, home_screen, mock_recent_files):
        """Test loading recent files into table."""
        mock_load.return_value = mock_recent_files

        # Mock table
        mock_table = Mock(spec=DataTable)
        home_screen.query_one = Mock(return_value=mock_table)

        home_screen._load_recent_files()

        # Verify table was populated correctly
        assert mock_table.add_row.call_count == 3

        # Verify first row data
        first_call = mock_table.add_row.call_args_list[0]
        assert "file1.mp3" in first_call[0][0]  # File name
        assert "10.5 MB" in first_call[0][1]     # Size

    def test_load_recent_files_empty(self, home_screen):
        """Test loading when no recent files exist."""
        with patch("src.ui.tui.views.home.load_recent_files", return_value=[]):
            mock_table = Mock(spec=DataTable)
            home_screen.query_one = Mock(return_value=mock_table)

            home_screen._load_recent_files()

            # Verify table shows empty message
            mock_table.add_row.assert_called_once_with(
                "[dim]No recent files[/dim]", "", "", key="none"
            )


class TestHomeScreenIntegration:
    """Integration tests for HomeScreen."""

    @pytest.mark.asyncio
    async def test_file_selection_flow(self):
        """Test complete file selection flow."""
        async with AudioExtractionApp().run_test() as pilot:
            app = pilot.app

            # Push home screen
            await app.push_screen(HomeScreen())
            await pilot.pause()

            # Should start with file tree focused
            tree = app.query_one("#file-tree", DirectoryTree)
            assert tree.has_focus

            # Switch to recent files
            await pilot.press("tab")
            await pilot.pause()

            table = app.query_one("#recent-table", DataTable)
            # Table might have focus now depending on implementation

    @pytest.mark.asyncio
    async def test_pane_switching(self):
        """Test switching between file tree and recent files."""
        async with AudioExtractionApp().run_test() as pilot:
            app = pilot.app
            screen = HomeScreen()
            await app.push_screen(screen)
            await pilot.pause()

            # Start with tree pane
            assert screen._current_pane == "tree"

            # Switch panes with Tab
            await pilot.press("tab")
            await pilot.pause()

            # Should be on recent pane
            assert screen._current_pane == "recent"

            # Switch back
            await pilot.press("tab")
            await pilot.pause()

            assert screen._current_pane == "tree"

    @pytest.mark.asyncio
    async def test_filter_input_focus(self):
        """Test that filter action focuses the input field."""
        async with AudioExtractionApp().run_test() as pilot:
            app = pilot.app
            await app.push_screen(HomeScreen())
            await pilot.pause()

            # Press 'f' to focus filter
            await pilot.press("f")
            await pilot.pause()

            # Filter input should have focus
            filter_input = app.query_one("#filter-input", Input)
            assert filter_input.has_focus