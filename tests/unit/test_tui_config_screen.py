"""Focused unit tests for the ConfigScreen view."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.ui.tui.persistence import default_settings
from src.ui.tui.state import AppState
from src.ui.tui.views.config import ConfigScreen


class DummyApp:
    def __init__(self) -> None:
        self.state = AppState(
            input_path=Path("/tmp/input.mp3"),
            output_dir=Path("/tmp/output"),
            quality="speech",
            provider="auto",
            language="en",
            analysis_style="concise",
        )
        self.push_screen = MagicMock()
        self.pop_screen = MagicMock()
        self.notify = MagicMock()


@pytest.fixture
def config_screen(monkeypatch) -> ConfigScreen:
    monkeypatch.setattr(
        "src.ui.tui.views.config.load_settings",
        lambda: default_settings(),
    )
    screen = ConfigScreen()
    screen.app = DummyApp()  # type: ignore[assignment]
    return screen


def test_on_input_changed_updates_state(config_screen: ConfigScreen) -> None:
    event = SimpleNamespace(input=SimpleNamespace(id="output-dir-input"), value="/data/out")
    config_screen.on_input_changed(event)
    assert config_screen.app.state.output_dir == Path("/data/out")


def test_on_select_changed_updates_defaults(config_screen: ConfigScreen) -> None:
    event = SimpleNamespace(select=SimpleNamespace(id="style-select"), value="full")
    config_screen.on_select_changed(event)
    assert config_screen.settings["defaults"]["analysis_style"] == "full"
    assert config_screen.app.state.analysis_style == "full"


def test_action_start_run_missing_input(config_screen: ConfigScreen) -> None:
    config_screen.app.state.input_path = None
    config_screen.notify = MagicMock()
    config_screen.action_start_run()
    config_screen.notify.assert_called_with("No input file selected!", severity="error", timeout=3)


@patch("src.ui.tui.views.config.save_settings", return_value=True)
def test_action_start_run_success(mock_save, config_screen: ConfigScreen) -> None:  # type: ignore[override]
    config_screen.notify = MagicMock()
    config_screen.action_start_run()

    mock_save.assert_called()
    assert config_screen.app.state.pending_run_config is not None
    config_screen.app.push_screen.assert_called_with("run")


@patch("src.ui.tui.views.config.save_settings", return_value=True)
@patch("src.ui.tui.views.config.default_settings")
def test_action_reset_defaults(mock_defaults, _mock_save, config_screen: ConfigScreen) -> None:
    defaults = default_settings()
    defaults["defaults"].update({"quality": "high", "provider": "deepgram", "language": "es", "analysis_style": "full"})
    defaults["last_output_dir"] = "/tmp/out"
    mock_defaults.return_value = defaults

    quality_select = SimpleNamespace(value="")
    provider_select = SimpleNamespace(value="")
    language_select = SimpleNamespace(value="")
    style_select = SimpleNamespace(value="")
    output_input = SimpleNamespace(value="")

    mapping = {
        "#quality-select": quality_select,
        "#provider-select": provider_select,
        "#language-select": language_select,
        "#style-select": style_select,
        "#output-dir-input": output_input,
    }

    config_screen.query_one = MagicMock(side_effect=lambda selector, *_: mapping[selector])
    config_screen.action_reset_defaults()

    assert quality_select.value == "high"
    assert provider_select.value == "deepgram"
    assert language_select.value == "es"
    assert style_select.value == "full"
    assert output_input.value == "/tmp/out"


def test_action_back_invokes_app(config_screen: ConfigScreen) -> None:
    config_screen.action_back()
    config_screen.app.pop_screen.assert_called_once()
