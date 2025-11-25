"""Focused unit tests for the RunScreen view."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ui.tui.state import AppState
from src.ui.tui.views.run import RunScreen


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
        self.notify = MagicMock()
        self.pop_screen = MagicMock()


@pytest.fixture
def run_screen(tmp_path: Path) -> RunScreen:
    screen = RunScreen(input_file=tmp_path / "file.mp3", config={"output_dir": str(tmp_path)})
    screen.app = DummyApp()  # type: ignore[assignment]
    return screen


def test_ensure_runtime_context_from_state(tmp_path: Path) -> None:
    screen = RunScreen()
    dummy = DummyApp()
    dummy.state.input_path = tmp_path / "audio.mp3"
    dummy.state.pending_run_config = {"output_dir": str(tmp_path), "quality": "speech"}
    screen.app = dummy  # type: ignore[assignment]

    screen._ensure_runtime_context()

    assert screen.input_file == tmp_path / "audio.mp3"
    assert screen.config["output_dir"] == str(tmp_path)
    assert dummy.state.pending_run_config is None


@pytest.mark.asyncio
async def test_action_cancel_disables_button(run_screen: RunScreen) -> None:
    run_screen._running = True
    run_screen._pipeline_task = asyncio.create_task(asyncio.sleep(0.1))
    button = MagicMock()
    button.disabled = False
    run_screen._get_button = MagicMock(return_value=button)

    await run_screen.action_cancel()

    assert run_screen._running is False
    assert button.disabled is True


@pytest.mark.asyncio
async def test_action_open_output_success(tmp_path: Path, run_screen: RunScreen) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    run_screen._output_dir = output_dir

    with patch("src.ui.tui.views.run.open_path", return_value=True) as mock_open:
        await run_screen.action_open_output()

    mock_open.assert_called_once_with(output_dir)


@pytest.mark.asyncio
async def test_run_pipeline_with_events_invokes_service(tmp_path: Path) -> None:
    config = {
        "output_dir": str(tmp_path),
        "quality": "standard",
        "language": "en",
        "provider": "auto",
        "analysis_style": "concise",
    }
    screen = RunScreen(input_file=tmp_path / "audio.mp3", config=config)
    screen.app = DummyApp()  # type: ignore[assignment]

    async def fake_pipeline(**kwargs):
        await asyncio.sleep(0)
        return kwargs["output_dir"]

    with patch("src.ui.tui.views.run.run_pipeline", new=fake_pipeline) as mock_run:
        await screen._run_pipeline_with_events()

    assert mock_run  # ensures patch applied
    assert screen._output_dir == Path(config["output_dir"])
