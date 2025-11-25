"""Focused unit tests for the HomeScreen view."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.ui.tui.state import AppState
from src.ui.tui.views.home import HomeScreen
from src.ui.tui.widgets.filtered_tree import FilteredDirectoryTree


@dataclass
class DummyApp:
    """Minimal stand-in for the Textual App used in unit tests."""

    state: AppState
    pushed: list[str]
    popped: int = 0

    def push_screen(self, screen: str) -> None:
        self.pushed.append(screen)

    def pop_screen(self) -> None:
        self.popped += 1


@pytest.fixture
def home_screen(tmp_path: Path) -> HomeScreen:
    screen = HomeScreen(start_dir=tmp_path)
    dummy_app = DummyApp(state=AppState(), pushed=[])
    screen.app = dummy_app  # type: ignore[assignment]
    return screen


def _stub_table() -> SimpleNamespace:
    return SimpleNamespace(
        rows=[],
        cursor_row=None,
        columns=None,
        add_columns=lambda *args, **kwargs: None,
        add_row=lambda *args, **kwargs: None,
        clear=lambda: None,
        focus=lambda: None,
        get_row_key=lambda row: None,
    )


def _stub_tree(path: Path | None) -> SimpleNamespace:
    node = SimpleNamespace(data=SimpleNamespace(path=path)) if path else None
    return SimpleNamespace(cursor_node=node, focus=lambda: None, filter="")


def test_start_dir_alias(tmp_path: Path) -> None:
    screen = HomeScreen(start_dir=tmp_path)
    assert screen.start_dir == tmp_path


@patch("src.ui.tui.views.home.load_recent_files", return_value=[])
def test_on_mount_configures_table(mock_load, home_screen: HomeScreen) -> None:  # type: ignore[override]
    table = _stub_table()
    tree = _stub_tree(Path("/tmp"))

    def _query(selector: str, *_args):
        return {"#recent-table": table, "#file-tree": tree}[selector]

    home_screen.query_one = MagicMock(side_effect=_query)
    home_screen.on_mount()

    assert mock_load.called
    assert home_screen.query_one.call_count >= 2


@patch("src.ui.tui.views.home.add_recent_file")
def test_action_select_file_from_tree(
    mock_add_recent, tmp_path: Path, home_screen: HomeScreen
) -> None:
    file_path = tmp_path / "input.mp3"
    file_path.write_text("data")

    tree = _stub_tree(file_path)
    home_screen.query_one = MagicMock(return_value=tree)
    home_screen.app.pushed.clear()

    home_screen.action_select_file()

    assert home_screen.app.state.input_path == file_path
    mock_add_recent.assert_called_once_with(file_path)
    assert home_screen.app.pushed == ["config"]


@patch("src.ui.tui.views.home.add_recent_file")
def test_action_select_file_from_recent(
    mock_add_recent, tmp_path: Path, home_screen: HomeScreen
) -> None:
    file_path = tmp_path / "recent.mp3"
    file_path.write_text("data")

    table = _stub_table()
    table.cursor_row = 0
    table.get_row_key = lambda _row: str(file_path)

    home_screen._active_pane = "recent"
    home_screen.query_one = MagicMock(return_value=table)
    home_screen.app.pushed.clear()

    home_screen.action_select_file()

    assert home_screen.app.state.input_path == file_path
    mock_add_recent.assert_called_once_with(file_path)
    assert home_screen.app.pushed == ["config"]


def test_action_select_file_directory_warns(tmp_path: Path, home_screen: HomeScreen) -> None:
    directory = tmp_path / "nested"
    directory.mkdir()
    tree = _stub_tree(directory)
    home_screen.query_one = MagicMock(return_value=tree)
    home_screen.notify = MagicMock()

    home_screen.action_select_file()

    home_screen.notify.assert_called_with(
        "Please select a file, not a directory", severity="warning"
    )


@patch("src.ui.tui.views.home.load_recent_files", return_value=[])
def test_action_refresh_recent_adds_placeholder(mock_load, home_screen: HomeScreen) -> None:  # type: ignore[override]
    table = _stub_table()
    calls = []

    def add_row(*args, **kwargs):
        calls.append((args, kwargs))

    table.add_row = add_row
    table.clear = lambda: calls.append(("clear", {}))

    home_screen.query_one = MagicMock(return_value=table)
    home_screen.notify = MagicMock()

    home_screen.action_refresh_recent()

    assert calls[0] == ("clear", {})
    assert "[dim]No recent files[/dim]" in calls[-1][0][0]
    home_screen.notify.assert_called_with("Recent files refreshed", severity="information")


def test_action_back_pops_screen(home_screen: HomeScreen) -> None:
    home_screen.app.pop_screen = MagicMock()
    home_screen.action_back()
    home_screen.app.pop_screen.assert_called_once()


def test_on_input_submitted_sets_filter(home_screen: HomeScreen) -> None:
    tree = _stub_tree(None)
    home_screen.query_one = MagicMock(return_value=tree)

    event = SimpleNamespace(input=SimpleNamespace(id="filter-input"), value="*.mp3")
    home_screen.on_input_submitted(event)

    assert tree.filter == "*.mp3"


def test_on_input_changed_sets_filter_dynamically(home_screen: HomeScreen) -> None:
    """Test that filter is applied dynamically as user types."""
    tree = _stub_tree(None)
    home_screen.query_one = MagicMock(return_value=tree)

    # Test typing a partial filter
    event = SimpleNamespace(input=SimpleNamespace(id="filter-input"), value="*.m")
    home_screen.on_input_changed(event)
    assert tree.filter == "*.m"

    # Test typing more characters
    event = SimpleNamespace(input=SimpleNamespace(id="filter-input"), value="*.mp")
    home_screen.on_input_changed(event)
    assert tree.filter == "*.mp"

    # Test clearing the filter
    event = SimpleNamespace(input=SimpleNamespace(id="filter-input"), value="")
    home_screen.on_input_changed(event)
    assert tree.filter == ""
