"""Theme selection screen for the TUI application."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual._context import active_app
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.app import ComposeResult

from ..persistence import save_settings
from ..themes import CUSTOM_THEMES

if TYPE_CHECKING:
    from ..app import AudioExtractionApp


class ThemeSelectorScreen(Screen):
    """Screen for selecting application theme."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "select", "Select", show=False),
    ]

    CSS = """
    ThemeSelectorScreen {
        align: center middle;
    }

    #theme-container {
        width: 60;
        height: 80%;
        min-height: 20;
        max-height: 40;
        border: solid $accent;
        padding: 1;
    }

    #theme-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    OptionList {
        height: 1fr;
        border: none;
        padding: 0 1;
    }

    OptionList:focus {
        border: none;
    }

    #current-theme {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }
    """

    def __init__(self):
        """Initialize the theme selector screen."""
        super().__init__()
        self._app_override: AudioExtractionApp | None = None

    @property
    def app(self) -> AudioExtractionApp:
        """Get the app instance."""
        if self._app_override is not None:
            return self._app_override
        return cast("AudioExtractionApp", super().app)

    @app.setter
    def app(self, value: AudioExtractionApp) -> None:
        """Set the app instance for testing."""
        self._app_override = value
        active_app.set(value)

    def compose(self) -> ComposeResult:
        """Compose the theme selector layout."""
        yield Header()

        with Container(id="theme-container"):
            yield Label("Select Theme", id="theme-title")
            yield OptionList(id="theme-list")
            yield Static("", id="current-theme")

        yield Footer()

    def _add_theme_section(
        self, option_list: OptionList, section_title: str, theme_names: list[str]
    ) -> None:
        """Add a themed section with options to the list."""
        if not theme_names:
            return
        option_list.add_option(Option(f"──── {section_title} ────", disabled=True))
        current_theme = self.app.theme
        for theme_name in theme_names:
            display_name = self._format_theme_name(theme_name)
            if theme_name == current_theme:
                display_name = f"▶ {display_name}"
            option_list.add_option(Option(display_name, id=theme_name))

    def _get_available_themes(self, theme_list: list[str]) -> list[str]:
        """Filter theme list to only available themes."""
        return [t for t in theme_list if t in self.app.available_themes]

    def on_mount(self) -> None:
        """Initialize the theme list when screen is mounted."""
        option_list = self.query_one("#theme-list", OptionList)

        # Add custom themes section
        custom_theme_names = [theme.name for theme in CUSTOM_THEMES]
        self._add_theme_section(option_list, "Custom Themes", custom_theme_names)

        # Add built-in dark themes
        dark_themes = [
            "nord",
            "gruvbox",
            "dracula",
            "monokai",
            "catppuccin-mocha",
            "tokyo-night",
            "textual-dark",
        ]
        self._add_theme_section(
            option_list, "Built-in Dark Themes", self._get_available_themes(dark_themes)
        )

        # Add built-in light themes
        light_themes = ["textual-light", "catppuccin-latte", "solarized-light"]
        self._add_theme_section(
            option_list, "Built-in Light Themes", self._get_available_themes(light_themes)
        )

        # Finalize setup
        self._update_current_theme_display()
        option_list.focus()
        self._highlight_current_theme()

    def _format_theme_name(self, theme_name: str) -> str:
        """Format theme name for display.

        Args:
            theme_name: Internal theme name

        Returns:
            Formatted display name
        """
        # Remove prefixes
        name = theme_name.replace("audio-extraction-", "")
        name = name.replace("textual-", "")
        name = name.replace("-", " ")

        # Capitalize words
        words = name.split()
        formatted = " ".join(word.capitalize() for word in words)

        # Add emoji indicators for our custom themes
        if theme_name.startswith("audio-extraction"):
            if "blue" in theme_name:
                formatted = f"🔵 {formatted}"
            elif "purple" in theme_name:
                formatted = f"🟣 {formatted}"
            elif "green" in theme_name:
                formatted = f"🟢 {formatted}"
            elif "light" in theme_name:
                formatted = f"☀️ {formatted}"

        return formatted

    def _update_current_theme_display(self) -> None:
        """Update the current theme display text."""
        current_theme_label = self.query_one("#current-theme", Static)
        current_theme = self.app.theme
        formatted_name = self._format_theme_name(current_theme)
        current_theme_label.update(f"Current: {formatted_name}")

    def _highlight_current_theme(self) -> None:
        """Highlight the current theme in the list."""
        option_list = self.query_one("#theme-list", OptionList)
        current_theme = self.app.theme

        # Find and highlight the current theme option
        for index in range(option_list.option_count):
            option = option_list.get_option_at_index(index)
            if option and hasattr(option, "id") and option.id == current_theme:
                option_list.highlighted = index
                break

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle theme selection.

        Args:
            event: Option selected event
        """
        if event.option_id:
            self._apply_theme(event.option_id)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the selected theme.

        Args:
            theme_name: Name of the theme to apply
        """
        # Apply the theme
        self.app.theme = theme_name

        # Save to settings
        self.app.settings["ui"]["theme"] = theme_name
        save_settings(self.app.settings)

        # Show notification
        formatted_name = self._format_theme_name(theme_name)
        self.app.notify(f"Theme changed to: {formatted_name}", severity="information")

        # Return to previous screen
        self.app.pop_screen()

    def action_cancel(self) -> None:
        """Cancel theme selection and return to previous screen."""
        self.app.pop_screen()

    def action_select(self) -> None:
        """Select the highlighted theme."""
        option_list = self.query_one("#theme-list", OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option and hasattr(option, "id") and option.id:
                self._apply_theme(option.id)
