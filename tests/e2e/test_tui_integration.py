"""Lightweight integration checks for the TUI application."""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

from textual.pilot import Pilot

from src.ui.tui.app import AudioExtractionApp
from src.ui.tui.views.help import HelpScreen


@pytest.mark.asyncio
async def test_start_button_navigates_to_home() -> None:
    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        await pilot.click("#start-btn")
        await pilot.pause()

        # The stack should have the default Screen, WelcomeScreen, and HomeScreen
        assert len(app.screen_stack) == 3
        assert app.screen_stack[-1].__class__.__name__ == "HomeScreen"


@pytest.mark.asyncio
async def test_help_button_adds_help_screen() -> None:
    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        await pilot.click("#help-btn")
        await pilot.pause()

        # The stack should have the default Screen, WelcomeScreen, and HelpScreen
        assert len(app.screen_stack) == 3
        assert isinstance(app.screen_stack[-1], HelpScreen)
