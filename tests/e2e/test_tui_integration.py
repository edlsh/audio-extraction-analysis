"""Lightweight integration checks for the TUI application."""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

from textual.pilot import Pilot

from src.ui.tui.app import AudioExtractionApp
from src.ui.tui.views.help import HelpScreen
from src.ui.tui.views.home import HomeScreen


@pytest.mark.asyncio
async def test_app_launches_to_home_screen() -> None:
    """Verify app launches directly to HomeScreen (no welcome screen)."""
    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # The stack should have the default Screen and HomeScreen
        assert len(app.screen_stack) == 2
        assert isinstance(app.screen_stack[-1], HomeScreen)


@pytest.mark.asyncio
async def test_help_key_opens_help_screen() -> None:
    """Verify pressing 'h' opens help screen from home."""
    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Press 'h' to open help
        await pilot.press("h")
        await pilot.pause()

        # The stack should have default Screen, HomeScreen, and HelpScreen
        assert len(app.screen_stack) == 3
        assert isinstance(app.screen_stack[-1], HelpScreen)


@pytest.mark.asyncio
async def test_ctrl_s_opens_settings_screen() -> None:
    """Verify pressing Ctrl+S opens settings screen from home."""
    from src.ui.tui.views.settings import SettingsScreen

    app = AudioExtractionApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Press Ctrl+S to open settings
        await pilot.press("ctrl+s")
        await pilot.pause()

        # The stack should have default Screen, HomeScreen, and SettingsScreen
        assert len(app.screen_stack) == 3
        assert isinstance(app.screen_stack[-1], SettingsScreen)
