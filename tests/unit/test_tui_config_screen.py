"""Unit tests for TUI ConfigScreen."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select

from src.ui.tui.app import AudioExtractionApp
from src.ui.tui.persistence import default_settings
from src.ui.tui.state import AppState
from src.ui.tui.views.config import ConfigScreen


@pytest.fixture
def app_with_state():
    """Create app with initialized state."""
    app = AudioExtractionApp()
    app.state = AppState(
        input_path=Path("/test/audio.mp3"),
        output_dir=Path("/test/output"),
        quality="speech",
        language="en",
        provider="auto",
        analysis_style="concise",
    )
    return app


@pytest.fixture
def config_screen(app_with_state):
    """Create ConfigScreen with app context."""
    screen = ConfigScreen()
    screen.app = app_with_state
    screen.settings = default_settings()
    return screen


class TestConfigScreenInit:
    """Test ConfigScreen initialization."""

    def test_init_default(self):
        """Test default initialization."""
        screen = ConfigScreen()
        assert screen.settings == {}

    def test_init_with_settings(self):
        """Test initialization with custom settings."""
        settings = {"defaults": {"quality": "high"}}
        screen = ConfigScreen()
        screen.settings = settings
        assert screen.settings["defaults"]["quality"] == "high"


class TestConfigScreenCompose:
    """Test ConfigScreen UI composition."""

    def test_compose_creates_widgets(self, config_screen):
        """Test that compose creates all required widgets."""
        widgets = list(config_screen.compose())

        # Check that we have the expected widget types
        widget_types = [type(w).__name__ for w in widgets]
        assert "Header" in widget_types
        assert "Footer" in widget_types
        assert "Container" in widget_types


class TestConfigScreenMount:
    """Test ConfigScreen mount behavior."""

    @patch("src.ui.tui.views.config.load_settings")
    async def test_on_mount_loads_settings(self, mock_load, config_screen):
        """Test that on_mount loads settings."""
        mock_settings = default_settings()
        mock_load.return_value = mock_settings

        config_screen.on_mount()

        mock_load.assert_called_once()
        assert config_screen.settings == mock_settings

    @patch("src.ui.tui.views.config.load_settings")
    async def test_on_mount_applies_settings(self, mock_load, config_screen):
        """Test that on_mount applies loaded settings to UI."""
        mock_settings = default_settings()
        mock_settings["defaults"]["quality"] = "high"
        mock_settings["defaults"]["language"] = "es"
        mock_load.return_value = mock_settings

        # Create mock selects
        quality_select = Mock(spec=Select)
        language_select = Mock(spec=Select)
        config_screen.query_one = Mock(side_effect=lambda selector, _: {
            "#quality-select": quality_select,
            "#language-select": language_select,
        }.get(selector.split(",")[0]))

        config_screen.on_mount()

        # Verify settings were applied to selects
        assert quality_select.value == "high"
        assert language_select.value == "es"


class TestConfigScreenActions:
    """Test ConfigScreen actions."""

    def test_action_start_run_missing_input_path(self, config_screen):
        """Test start run action with missing input path."""
        config_screen.app.state.input_path = None
        config_screen.notify = Mock()

        config_screen.action_start_run()

        config_screen.notify.assert_called_with(
            "Please select an input file first",
            severity="error"
        )

    def test_action_start_run_missing_output_dir(self, config_screen):
        """Test start run action with missing output directory."""
        config_screen.app.state.output_dir = None
        config_screen.notify = Mock()

        config_screen.action_start_run()

        config_screen.notify.assert_called_with(
            "Please select an output directory first",
            severity="error"
        )

    @patch("src.ui.tui.views.config.save_settings")
    def test_action_start_run_success(self, mock_save, config_screen):
        """Test successful start run action."""
        config_screen.app.push_screen = AsyncMock()
        config_screen.notify = Mock()

        # Set up mock UI elements
        quality_select = Mock(spec=Select, value="high")
        provider_select = Mock(spec=Select, value="deepgram")
        language_select = Mock(spec=Select, value="es")
        style_select = Mock(spec=Select, value="full")

        config_screen.query_one = Mock(side_effect=lambda selector, _: {
            "#quality-select": quality_select,
            "#provider-select": provider_select,
            "#language-select": language_select,
            "#style-select": style_select,
        }.get(selector.split(",")[0]))

        config_screen.action_start_run()

        # Verify config was built correctly
        expected_config = {
            "output_dir": str(config_screen.app.state.output_dir),
            "quality": "high",
            "provider": "deepgram",
            "language": "es",
            "analysis_style": "full",
            "export_markdown": True,
            "export_html": False,
        }

        # Verify screen was pushed with correct args
        config_screen.app.push_screen.assert_called_once()
        call_args = config_screen.app.push_screen.call_args[0]
        assert str(call_args[0].input_file) == str(config_screen.app.state.input_path)
        assert call_args[0].config == expected_config

    def test_action_reset_defaults(self, config_screen):
        """Test reset to defaults action."""
        # Set up mock UI elements
        quality_select = Mock(spec=Select)
        provider_select = Mock(spec=Select)
        language_select = Mock(spec=Select)
        style_select = Mock(spec=Select)

        config_screen.query_one = Mock(side_effect=lambda selector, _: {
            "#quality-select": quality_select,
            "#provider-select": provider_select,
            "#language-select": language_select,
            "#style-select": style_select,
        }.get(selector.split(",")[0]))

        config_screen.action_reset_defaults()

        # Verify all selects were reset to defaults
        assert quality_select.value == "speech"
        assert provider_select.value == "auto"
        assert language_select.value == "en"
        assert style_select.value == "concise"

    def test_action_back(self, config_screen):
        """Test back action."""
        config_screen.app.pop_screen = Mock()

        config_screen.action_back()

        config_screen.app.pop_screen.assert_called_once()


class TestConfigScreenEventHandlers:
    """Test ConfigScreen event handlers."""

    @patch("src.ui.tui.views.config.save_settings")
    def test_on_select_changed_saves_settings(self, mock_save, config_screen):
        """Test that select change triggers settings save."""
        # Create mock event
        event = Mock()
        event.select = Mock(id="quality-select")
        event.value = "high"

        config_screen.on_select_changed(event)

        # Verify settings were updated
        assert config_screen.settings["defaults"]["quality"] == "high"

        # Verify settings were saved
        mock_save.assert_called_once_with(config_screen.settings)

    @patch("src.ui.tui.views.config.save_settings")
    def test_on_input_changed_updates_output_dir(self, mock_save, config_screen):
        """Test that input change updates output directory."""
        # Create mock event
        event = Mock()
        event.input = Mock(id="output-dir-input")
        event.value = "/new/output/path"

        config_screen.on_input_changed(event)

        # Verify output dir was updated
        assert str(config_screen.app.state.output_dir) == "/new/output/path"

    def test_on_button_pressed_start(self, config_screen):
        """Test button press for start."""
        config_screen.action_start_run = Mock()

        event = Mock()
        event.button = Mock(id="start-btn")

        config_screen.on_button_pressed(event)

        config_screen.action_start_run.assert_called_once()

    def test_on_button_pressed_reset(self, config_screen):
        """Test button press for reset."""
        config_screen.action_reset_defaults = Mock()

        event = Mock()
        event.button = Mock(id="reset-btn")

        config_screen.on_button_pressed(event)

        config_screen.action_reset_defaults.assert_called_once()

    def test_on_button_pressed_back(self, config_screen):
        """Test button press for back."""
        config_screen.action_back = Mock()

        event = Mock()
        event.button = Mock(id="back-btn")

        config_screen.on_button_pressed(event)

        config_screen.action_back.assert_called_once()


class TestConfigScreenIntegration:
    """Integration tests for ConfigScreen."""

    @pytest.mark.asyncio
    async def test_full_configuration_flow(self):
        """Test complete configuration flow."""
        async with AudioExtractionApp().run_test() as pilot:
            # Navigate to config screen
            app = pilot.app
            app.state = AppState(
                input_path=Path("/test/audio.mp3"),
                output_dir=Path("/test/output"),
            )

            # Push config screen
            await app.push_screen(ConfigScreen())
            await pilot.pause()

            # Change quality setting
            quality_select = app.query_one("#quality-select", Select)
            quality_select.value = "high"

            # Change provider setting
            provider_select = app.query_one("#provider-select", Select)
            provider_select.value = "whisper"

            # Verify state was updated
            assert app.state.quality == "speech"  # Not automatically synced

            # Click start button (would navigate to run screen)
            # We can't fully test this without mocking run_pipeline
            start_btn = app.query_one("#start-btn", Button)
            assert not start_btn.disabled

    @pytest.mark.asyncio
    async def test_validation_prevents_start(self):
        """Test that validation prevents starting without required fields."""
        async with AudioExtractionApp().run_test() as pilot:
            app = pilot.app
            app.state = AppState()  # No input_path or output_dir

            await app.push_screen(ConfigScreen())
            await pilot.pause()

            # Try to start - should show error
            start_btn = app.query_one("#start-btn", Button)
            await pilot.click(start_btn)
            await pilot.pause()

            # Should still be on config screen
            assert isinstance(app.screen, ConfigScreen)

    @pytest.mark.asyncio
    async def test_reset_defaults_updates_ui(self):
        """Test that reset defaults updates all UI elements."""
        async with AudioExtractionApp().run_test() as pilot:
            app = pilot.app
            app.state = AppState(
                input_path=Path("/test/audio.mp3"),
                output_dir=Path("/test/output"),
            )

            await app.push_screen(ConfigScreen())
            await pilot.pause()

            # Change settings
            quality_select = app.query_one("#quality-select", Select)
            quality_select.value = "high"

            language_select = app.query_one("#language-select", Select)
            language_select.value = "es"

            # Reset defaults
            reset_btn = app.query_one("#reset-btn", Button)
            await pilot.click(reset_btn)
            await pilot.pause()

            # Verify defaults were restored
            assert quality_select.value == "speech"
            assert language_select.value == "en"