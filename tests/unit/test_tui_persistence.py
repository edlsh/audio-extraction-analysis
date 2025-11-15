"""Focused unit tests for persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.ui.tui import persistence


def test_load_settings_merges_defaults(monkeypatch):
    defaults = persistence.default_settings()
    settings_file = Path("/tmp/tui_settings.json")

    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: settings_file.parent)
    patcher = mock_open(read_data=json.dumps({"defaults": {"quality": "high"}}))

    with patch("builtins.open", patcher), patch.object(Path, "exists", return_value=True):
        loaded = persistence.load_settings()

    assert loaded["defaults"]["quality"] == "high"
    assert loaded["defaults"]["language"] == defaults["defaults"]["language"]


def test_save_settings_writes_file(monkeypatch):
    target = Path("/tmp/tui_settings.json")
    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: target.parent)
    m = mock_open()
    with patch("builtins.open", m):
        assert persistence.save_settings({"foo": "bar"}) is True


def test_save_recent_files_handles_missing_config(monkeypatch):
    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: None)
    assert persistence.save_recent_files([]) is False


def test_save_recent_files_writes_payload(monkeypatch):
    target = Path("/tmp/recent_files.json")
    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: target.parent)
    m = mock_open()
    with patch("builtins.open", m):
        assert persistence.save_recent_files([{"path": "/tmp/file.mp3"}]) is True


@patch("src.ui.tui.persistence.save_recent_files", return_value=True)
@patch("src.ui.tui.persistence.load_recent_files", return_value=[])
def test_add_recent_file_inserts_entry(mock_load, mock_save, tmp_path: Path):  # type: ignore[override]
    file_path = tmp_path / "sample.mp3"
    file_path.write_text("data")

    with patch("src.ui.tui.persistence.get_config_dir", return_value=tmp_path):
        result = persistence.add_recent_file(file_path)

    assert result is True
    assert mock_save.called


def test_clear_recent_files_writes_empty(monkeypatch):
    target = Path("/tmp/recent_files.json")
    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: target.parent)
    m = mock_open()
    with patch("builtins.open", m):
        assert persistence.clear_recent_files() is True
