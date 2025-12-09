"""Focused unit tests for persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

pytest.importorskip("textual")

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


# ============== API Key Tests ==============


def test_load_api_keys_returns_defaults_when_empty(monkeypatch):
    """Test load_api_keys returns empty strings when no keys are configured."""
    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: None)
    keys = persistence.load_api_keys()

    assert "deepgram" in keys
    assert "elevenlabs" in keys
    assert "gemini" in keys
    assert keys["deepgram"] == ""


def test_load_api_keys_returns_stored_keys(monkeypatch):
    """Test load_api_keys returns previously saved keys."""
    settings_file = Path("/tmp/tui_settings.json")
    stored_settings = {
        "api_keys": {
            "deepgram": "dg-test-key",
            "elevenlabs": "",
            "gemini": "gem-key",
        }
    }

    monkeypatch.setattr("src.ui.tui.persistence.get_config_dir", lambda: settings_file.parent)
    patcher = mock_open(read_data=json.dumps(stored_settings))

    with patch("builtins.open", patcher), patch.object(Path, "exists", return_value=True):
        keys = persistence.load_api_keys()

    assert keys["deepgram"] == "dg-test-key"
    assert keys["elevenlabs"] == ""
    assert keys["gemini"] == "gem-key"


@patch("src.ui.tui.persistence.save_settings", return_value=True)
@patch("src.ui.tui.persistence.load_settings")
def test_save_api_key_updates_settings(mock_load, mock_save):
    """Test save_api_key updates the correct provider key."""
    mock_load.return_value = persistence.default_settings()

    result = persistence.save_api_key("deepgram", "new-key-123")

    assert result is True
    assert mock_save.called
    saved_settings = mock_save.call_args[0][0]
    assert saved_settings["api_keys"]["deepgram"] == "new-key-123"


def test_save_api_key_rejects_invalid_provider(monkeypatch):
    """Test save_api_key returns False for unknown providers."""
    result = persistence.save_api_key("unknown_provider", "some-key")
    assert result is False


def test_inject_api_keys_to_env_sets_variables(monkeypatch):
    """Test inject_api_keys_to_env sets environment variables."""
    # Mock load_api_keys to return test keys
    monkeypatch.setattr(
        "src.ui.tui.persistence.load_api_keys",
        lambda: {"deepgram": "test-dg-key", "elevenlabs": "", "gemini": "test-gem-key"},
    )

    # Clear any existing env vars
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    import os

    count = persistence.inject_api_keys_to_env()

    assert count == 2  # Only deepgram and gemini have values
    assert os.environ.get("DEEPGRAM_API_KEY") == "test-dg-key"
    assert os.environ.get("ELEVENLABS_API_KEY") is None  # Empty string not set
    assert os.environ.get("GEMINI_API_KEY") == "test-gem-key"


def test_inject_api_keys_does_not_override_existing(monkeypatch):
    """Test inject_api_keys_to_env does not override existing env vars."""
    import os

    # Set existing env var
    monkeypatch.setenv("DEEPGRAM_API_KEY", "existing-key")

    # Mock load_api_keys to return different key
    monkeypatch.setattr(
        "src.ui.tui.persistence.load_api_keys",
        lambda: {"deepgram": "stored-key", "elevenlabs": "", "gemini": ""},
    )

    count = persistence.inject_api_keys_to_env()

    assert count == 0  # Nothing injected since DEEPGRAM_API_KEY exists
    assert os.environ.get("DEEPGRAM_API_KEY") == "existing-key"
